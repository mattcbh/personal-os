#!/usr/bin/env python3
"""
Toast Analytics ETL - Pull anonymous card-fingerprint payment data into Supabase.

Usage:
    python3 toast_analytics_etl.py                          # Rolling 3-day replay ending yesterday
    python3 toast_analytics_etl.py --date 2026-03-01       # Single day
    python3 toast_analytics_etl.py --backfill 2024-08-01 2024-10-31
    python3 toast_analytics_etl.py --full-backfill
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback
from datetime import date, datetime, timedelta
from pathlib import Path

import requests
from dotenv import load_dotenv

from toast_api_common import (
    DEFAULT_LOCATION_ID,
    auth_headers,
    format_compact_date,
    get_machine_client_token,
    iter_date_windows,
    load_restaurant_map_from_env,
    parse_iso_date,
    request_with_retry,
    resolve_location_id,
)

# Force unbuffered output so progress shows in real-time
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)


SCRIPT_DIR = Path(__file__).resolve().parent
load_dotenv(SCRIPT_DIR.parent / ".env.toast")

TOAST_ANALYTICS_CLIENT_ID = os.environ.get("TOAST_ANALYTICS_CLIENT_ID", "").strip()
TOAST_ANALYTICS_CLIENT_SECRET = os.environ.get("TOAST_ANALYTICS_CLIENT_SECRET", "").strip()
TOAST_ANALYTICS_API_HOST = os.environ.get("TOAST_ANALYTICS_API_HOST", "").strip()
TOAST_RESTAURANT_MAP = load_restaurant_map_from_env()

SUPABASE_URL = os.environ.get(
    "SUPABASE_URL", "https://zxqtclvljxvdxsnmsqka.supabase.co"
)
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY", "")

DEFAULT_BACKFILL_START = parse_iso_date("2024-08-01")
DEFAULT_BATCH_SIZE = 500
DEFAULT_REPORT_POLL_ATTEMPTS = 8
DEFAULT_REPORT_POLL_SECONDS = 2.0
DEFAULT_CREATE_SLEEP_SECONDS = 12.5
DEFAULT_ROLLING_DAYS = 3
DEFAULT_MAX_CREATE_REQUESTS = 60


def require_analytics_env() -> None:
    missing = []
    if not TOAST_ANALYTICS_CLIENT_ID:
        missing.append("TOAST_ANALYTICS_CLIENT_ID")
    if not TOAST_ANALYTICS_CLIENT_SECRET:
        missing.append("TOAST_ANALYTICS_CLIENT_SECRET")
    if not TOAST_ANALYTICS_API_HOST:
        missing.append("TOAST_ANALYTICS_API_HOST")
    if not TOAST_RESTAURANT_MAP:
        missing.append("TOAST_RESTAURANT_MAP_JSON or TOAST_RESTAURANT_GUID")
    if not SUPABASE_KEY:
        missing.append("SUPABASE_SERVICE_ROLE_KEY or SUPABASE_KEY")

    if missing:
        print(
            "ERROR: missing required Toast Analytics config: " + ", ".join(missing),
            file=sys.stderr,
        )
        sys.exit(1)


def fetch_restaurants_information(session: requests.Session, token: str) -> list[dict]:
    """Fetch all restaurants in the Toast management group."""
    resp = request_with_retry(
        session,
        "get",
        f"{TOAST_ANALYTICS_API_HOST}/era/v1/restaurants-information",
        headers=auth_headers(token),
        output_stream=sys.stderr,
    )
    resp.raise_for_status()
    data = resp.json()
    return data if isinstance(data, list) else []


def validate_restaurant_mapping(
    restaurant_map: dict[str, str],
    restaurants: list[dict],
) -> dict[str, dict]:
    """Validate configured restaurant mappings against Toast metadata."""
    by_guid = {
        restaurant.get("restaurantGuid"): restaurant
        for restaurant in restaurants
        if restaurant.get("restaurantGuid")
    }

    missing = [guid for guid in restaurant_map if guid not in by_guid]
    if missing:
        raise RuntimeError(
            "Configured Toast restaurant GUIDs not returned by Analytics API: "
            + ", ".join(missing)
        )

    for guid, metadata in by_guid.items():
        if guid in restaurant_map and metadata.get("archived"):
            print(
                f"  Warning: {guid} ({metadata.get('restaurantName')}) is archived in Toast.",
                file=sys.stderr,
            )

    return by_guid


def create_guest_payments_report(
    session: requests.Session,
    token: str,
    *,
    time_range: str,
    start_date: date,
    end_date: date,
    restaurant_ids: list[str],
) -> str:
    """Create a Toast Analytics guest payments report request."""
    payload = {
        "startDate": format_compact_date(start_date),
        "endDate": format_compact_date(end_date),
        "restaurantIds": restaurant_ids,
        "excludedRestaurantIds": [],
    }
    resp = request_with_retry(
        session,
        "post",
        f"{TOAST_ANALYTICS_API_HOST}/era/v1/guest/payments/{time_range}",
        headers={
            **auth_headers(token),
            "Content-Type": "application/json",
        },
        json=payload,
        output_stream=sys.stderr,
    )
    resp.raise_for_status()
    response_payload = resp.json()
    if isinstance(response_payload, str):
        report_guid = response_payload.strip()
    elif isinstance(response_payload, dict):
        report_guid = response_payload.get("reportRequestGuid")
    else:
        report_guid = None
    if not report_guid:
        raise RuntimeError(
            f"Toast Analytics did not return reportRequestGuid for {payload}: "
            f"{response_payload!r}"
        )
    return report_guid


def retrieve_guest_payments_report(
    session: requests.Session,
    token: str,
    report_request_guid: str,
    *,
    poll_attempts: int,
    poll_seconds: float,
) -> list[dict]:
    """Poll a Toast Analytics report until the payment rows are available."""
    url = f"{TOAST_ANALYTICS_API_HOST}/era/v1/guest/payments/{report_request_guid}"

    for attempt in range(poll_attempts):
        resp = request_with_retry(
            session,
            "get",
            url,
            headers=auth_headers(token),
            output_stream=sys.stderr,
        )

        payload = None
        if resp.status_code == 200:
            payload = resp.json()
            if isinstance(payload, list):
                return payload

        if resp.status_code in {202, 404} or (resp.status_code == 200 and not isinstance(payload, list)):
            if attempt < poll_attempts - 1:
                time.sleep(poll_seconds)
                continue

        resp.raise_for_status()

    raise RuntimeError(
        f"Toast Analytics report {report_request_guid} was not ready after "
        f"{poll_attempts} attempts"
    )


def transform_guest_payment(
    row: dict,
    *,
    restaurant_map: dict[str, str],
    request_time_range: str,
    request_start_date: date,
    request_end_date: date,
    report_request_guid: str,
) -> dict:
    """Transform a Toast Analytics payment row into warehouse shape."""
    restaurant_guid = row.get("restaurantGuid")
    location_id = resolve_location_id(
        restaurant_guid,
        restaurant_map,
        default_location_id=DEFAULT_LOCATION_ID if len(restaurant_map) == 1 else None,
    )
    compact_date = str(row.get("paymentDate", "")).strip()
    if len(compact_date) != 8 or not compact_date.isdigit():
        raise ValueError(f"Unexpected paymentDate in guest payment row: {row}")

    payment_date = (
        f"{compact_date[:4]}-{compact_date[4:6]}-{compact_date[6:8]}"
    )
    fingerprint = row.get("cardFingerprint")
    if isinstance(fingerprint, str):
        fingerprint = fingerprint.strip() or None
    payment_guid = row.get("paymentGuid")
    order_guid = row.get("orderGuid")
    if not payment_guid or not order_guid or not restaurant_guid:
        raise ValueError(f"Guest payment row missing key identifiers: {row}")

    return {
        "payment_guid": payment_guid,
        "order_guid": order_guid,
        "restaurant_guid": restaurant_guid,
        "location_id": location_id,
        "restaurant_name": row.get("restaurantName"),
        "payment_date": payment_date,
        "card_fingerprint": fingerprint,
        "request_time_range": request_time_range,
        "request_start_date": request_start_date.isoformat(),
        "request_end_date": request_end_date.isoformat(),
        "report_request_guid": report_request_guid,
    }


def supabase_headers() -> dict[str, str]:
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal,resolution=merge-duplicates",
    }


def upsert_guest_payments(session: requests.Session, rows: list[dict]) -> int:
    """Upsert guest payment rows into Supabase."""
    if not rows:
        return 0

    url = f"{SUPABASE_URL}/rest/v1/toast_guest_payments?on_conflict=payment_guid"
    headers = supabase_headers()
    loaded = 0

    for i in range(0, len(rows), DEFAULT_BATCH_SIZE):
        batch = rows[i : i + DEFAULT_BATCH_SIZE]
        resp = session.post(url, json=batch, headers=headers, timeout=60)
        if resp.status_code in (200, 201):
            loaded += len(batch)
        else:
            print(
                f"  Guest payments upsert error (batch {i // DEFAULT_BATCH_SIZE}): "
                f"{resp.status_code} - {resp.text[:300]}",
                file=sys.stderr,
            )
    return loaded


def log_pipeline_run(
    session: requests.Session,
    run_date: str,
    status: str,
    rows_loaded: int,
    *,
    error_message: str | None = None,
    metadata: dict | None = None,
) -> None:
    url = f"{SUPABASE_URL}/rest/v1/pipeline_runs"
    headers = supabase_headers()
    headers["Prefer"] = "return=minimal"
    row = {
        "script_name": "toast_analytics_etl",
        "run_date": run_date,
        "status": status,
        "rows_loaded": rows_loaded,
        "error_message": error_message,
        "metadata": json.dumps(metadata or {}),
    }
    session.post(url, json=[row], headers=headers, timeout=30)


def build_daily_windows(end_date: date, rolling_days: int) -> list[tuple[str, date, date]]:
    start_date = end_date - timedelta(days=rolling_days - 1)
    return [("day", day_start, day_end) for day_start, day_end in iter_date_windows(start_date, end_date, 1)]


def build_backfill_windows(start_date: date, end_date: date) -> list[tuple[str, date, date]]:
    return [("week", chunk_start, chunk_end) for chunk_start, chunk_end in iter_date_windows(start_date, end_date, 7)]


def run_windows(
    session: requests.Session,
    token: str,
    windows: list[tuple[str, date, date]],
    *,
    poll_attempts: int,
    poll_seconds: float,
    create_sleep_seconds: float,
    max_create_requests: int,
) -> int:
    """Execute a list of Analytics report windows and upsert results."""
    total_loaded = 0
    restaurant_ids = list(TOAST_RESTAURANT_MAP.keys())
    processed_windows = windows[:max_create_requests]

    if len(windows) > len(processed_windows):
        print(
            f"Limiting this run to {len(processed_windows)} report requests to stay within "
            f"Toast's daily create-report cap. {len(windows) - len(processed_windows)} windows remain.",
            file=sys.stderr,
        )

    for idx, (time_range, start_date, end_date) in enumerate(processed_windows):
        print(
            f"\n--- {time_range} {start_date.isoformat()} -> {end_date.isoformat()} ---",
            file=sys.stderr,
        )
        report_guid = create_guest_payments_report(
            session,
            token,
            time_range=time_range,
            start_date=start_date,
            end_date=end_date,
            restaurant_ids=restaurant_ids,
        )
        rows = retrieve_guest_payments_report(
            session,
            token,
            report_guid,
            poll_attempts=poll_attempts,
            poll_seconds=poll_seconds,
        )
        transformed = [
            transform_guest_payment(
                row,
                restaurant_map=TOAST_RESTAURANT_MAP,
                request_time_range=time_range,
                request_start_date=start_date,
                request_end_date=end_date,
                report_request_guid=report_guid,
            )
            for row in rows
        ]
        loaded = upsert_guest_payments(session, transformed)
        total_loaded += loaded
        print(f"  Retrieved {len(rows)} rows, loaded {loaded}.", file=sys.stderr)
        log_pipeline_run(
            session,
            start_date.isoformat(),
            "success",
            loaded,
            metadata={
                "time_range": time_range,
                "window_start": start_date.isoformat(),
                "window_end": end_date.isoformat(),
                "report_request_guid": report_guid,
                "restaurant_count": len(restaurant_ids),
                "api_count": len(rows),
            },
        )

        if idx < len(processed_windows) - 1:
            time.sleep(create_sleep_seconds)

    return total_loaded


def main() -> None:
    parser = argparse.ArgumentParser(description="Toast Analytics guest payments ETL")
    parser.add_argument("--date", help="Single date to pull (YYYY-MM-DD).")
    parser.add_argument(
        "--backfill",
        nargs=2,
        metavar=("START", "END"),
        help="Weekly backfill range (YYYY-MM-DD YYYY-MM-DD).",
    )
    parser.add_argument(
        "--full-backfill",
        action="store_true",
        help="Backfill from 2024-08-01 through yesterday.",
    )
    parser.add_argument(
        "--rolling-days",
        type=int,
        default=DEFAULT_ROLLING_DAYS,
        help=f"Replay this many daily windows ending yesterday (default: {DEFAULT_ROLLING_DAYS}).",
    )
    parser.add_argument(
        "--max-create-requests",
        type=int,
        default=DEFAULT_MAX_CREATE_REQUESTS,
        help=f"Maximum report create requests per run (default: {DEFAULT_MAX_CREATE_REQUESTS}).",
    )
    parser.add_argument(
        "--create-sleep-seconds",
        type=float,
        default=DEFAULT_CREATE_SLEEP_SECONDS,
        help=f"Seconds to sleep between report create requests (default: {DEFAULT_CREATE_SLEEP_SECONDS}).",
    )
    parser.add_argument(
        "--report-poll-attempts",
        type=int,
        default=DEFAULT_REPORT_POLL_ATTEMPTS,
        help=f"Poll attempts per report (default: {DEFAULT_REPORT_POLL_ATTEMPTS}).",
    )
    parser.add_argument(
        "--report-poll-seconds",
        type=float,
        default=DEFAULT_REPORT_POLL_SECONDS,
        help=f"Seconds between report polls (default: {DEFAULT_REPORT_POLL_SECONDS}).",
    )
    args = parser.parse_args()
    require_analytics_env()

    yesterday = date.today() - timedelta(days=1)
    if args.full_backfill:
        windows = build_backfill_windows(DEFAULT_BACKFILL_START, yesterday)
    elif args.backfill:
        windows = build_backfill_windows(
            parse_iso_date(args.backfill[0]),
            parse_iso_date(args.backfill[1]),
        )
    elif args.date:
        exact_date = parse_iso_date(args.date)
        windows = [("day", exact_date, exact_date)]
    else:
        windows = build_daily_windows(yesterday, args.rolling_days)

    print(
        f"Configured {len(TOAST_RESTAURANT_MAP)} restaurant mapping(s): "
        + ", ".join(f"{guid}->{location}" for guid, location in TOAST_RESTAURANT_MAP.items()),
        file=sys.stderr,
    )

    session = requests.Session()
    print("Authenticating with Toast Analytics API...", file=sys.stderr)
    token = get_machine_client_token(
        session,
        TOAST_ANALYTICS_API_HOST,
        TOAST_ANALYTICS_CLIENT_ID,
        TOAST_ANALYTICS_CLIENT_SECRET,
    )
    print("Authenticated.", file=sys.stderr)

    print("Fetching Analytics restaurant metadata...", file=sys.stderr)
    restaurants = fetch_restaurants_information(session, token)
    validate_restaurant_mapping(TOAST_RESTAURANT_MAP, restaurants)
    print(f"  Found {len(restaurants)} restaurants in the management group.", file=sys.stderr)

    try:
        total_loaded = run_windows(
            session,
            token,
            windows,
            poll_attempts=args.report_poll_attempts,
            poll_seconds=args.report_poll_seconds,
            create_sleep_seconds=args.create_sleep_seconds,
            max_create_requests=args.max_create_requests,
        )
        print(f"\nDone. Total guest payments loaded: {total_loaded}.", file=sys.stderr)
    except Exception as exc:
        failing_date = windows[0][1].isoformat() if windows else yesterday.isoformat()
        print(f"ERROR: {exc}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        log_pipeline_run(
            session,
            failing_date,
            "error",
            0,
            error_message=str(exc),
            metadata={"window_count": len(windows)},
        )
        raise


if __name__ == "__main__":
    main()
