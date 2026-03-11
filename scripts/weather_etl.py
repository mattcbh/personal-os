#!/usr/bin/env python3
"""
Weather ETL - Pull daily weather from Visual Crossing into Supabase.

Usage:
    python3 weather_etl.py                          # Yesterday's weather
    python3 weather_etl.py --date 2026-02-07        # Specific date
    python3 weather_etl.py --backfill 2024-11-01 2025-02-01  # Date range

Uses Visual Crossing Timeline API (free tier: 1,000 records/day).
Upserts into the weather table on (location_id, weather_date).
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
load_dotenv(SCRIPT_DIR.parent / ".env.toast")  # shared env file in repo root

VC_API_KEY = os.environ.get("VISUAL_CROSSING_API_KEY", "")
if not VC_API_KEY:
    print("ERROR: Set VISUAL_CROSSING_API_KEY in .env.toast or environment", file=sys.stderr)
    print("Sign up free at https://www.visualcrossing.com/sign-up", file=sys.stderr)
    sys.exit(1)

SUPABASE_URL = os.environ.get(
    "SUPABASE_URL", "https://zxqtclvljxvdxsnmsqka.supabase.co"
)
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

# Williamsburg, Brooklyn weather station
WEATHER_LOCATION = "40.7138,-73.9604"  # Kent Ave approximate coords
BATCH_SIZE = 200

# Visual Crossing free tier: 1,000 records/day
# Each day of weather = 1 record, so max 1,000 days per API call
VC_MAX_DAYS_PER_REQUEST = 30  # keep requests small to avoid timeouts


# ---------------------------------------------------------------------------
# Visual Crossing API
# ---------------------------------------------------------------------------

def fetch_weather_range(
    session: requests.Session, start: str, end: str
) -> list[dict]:
    """
    Fetch daily weather for a date range from Visual Crossing.
    Returns list of day objects.
    """
    url = (
        f"https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline"
        f"/{WEATHER_LOCATION}/{start}/{end}"
    )
    resp = session.get(
        url,
        params={
            "unitGroup": "us",
            "include": "days",
            "key": VC_API_KEY,
            "contentType": "json",
        },
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    return data.get("days", [])


# ---------------------------------------------------------------------------
# Data transformation
# ---------------------------------------------------------------------------

def transform_weather_day(day: dict, location_id: str = "kent_ave") -> dict:
    """Transform a Visual Crossing day object to our weather table row."""
    return {
        "location_id": location_id,
        "weather_date": day["datetime"],  # YYYY-MM-DD
        "temp_high_f": day.get("tempmax"),
        "temp_low_f": day.get("tempmin"),
        "temp_avg_f": day.get("temp"),
        "feels_like_f": day.get("feelslike"),
        "precip_inches": day.get("precip", 0) or 0,
        "precip_type": ",".join(day.get("preciptype", []) or []) or None,
        "snow_inches": day.get("snow", 0) or 0,
        "wind_speed_mph": day.get("windspeed"),
        "humidity_pct": day.get("humidity"),
        "conditions": day.get("conditions"),
        "icon": day.get("icon"),
        "description": day.get("description"),
        "raw_data": json.dumps(day),
    }


# ---------------------------------------------------------------------------
# Supabase helpers
# ---------------------------------------------------------------------------

def supabase_headers() -> dict:
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal,resolution=merge-duplicates",
    }


def upsert_weather(session: requests.Session, rows: list[dict]) -> int:
    """Upsert weather rows into Supabase. Returns count loaded."""
    if not rows:
        return 0
    url = f"{SUPABASE_URL}/rest/v1/weather"
    headers = supabase_headers()
    loaded = 0
    for i in range(0, len(rows), BATCH_SIZE):
        batch = rows[i : i + BATCH_SIZE]
        resp = session.post(url, json=batch, headers=headers, timeout=60)
        if resp.status_code in (200, 201):
            loaded += len(batch)
        else:
            print(
                f"  Upsert error (batch {i // BATCH_SIZE}): {resp.status_code} - {resp.text[:300]}",
                file=sys.stderr,
            )
    return loaded


def log_pipeline_run(
    session: requests.Session,
    run_date: str,
    status: str,
    rows_loaded: int,
    error_message: str | None = None,
    metadata: dict | None = None,
) -> None:
    """Log a pipeline run to the pipeline_runs table."""
    url = f"{SUPABASE_URL}/rest/v1/pipeline_runs"
    headers = supabase_headers()
    headers["Prefer"] = "return=minimal"
    row = {
        "script_name": "weather_etl",
        "run_date": run_date,
        "status": status,
        "rows_loaded": rows_loaded,
        "error_message": error_message,
        "metadata": json.dumps(metadata or {}),
    }
    session.post(url, json=[row], headers=headers, timeout=30)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_date_range(start: str, end: str) -> None:
    """Run weather ETL for a range of dates."""
    session = requests.Session()
    print(f"Fetching weather from {start} to {end}...", file=sys.stderr)

    current = datetime.strptime(start, "%Y-%m-%d")
    end_dt = datetime.strptime(end, "%Y-%m-%d")
    total_loaded = 0

    while current <= end_dt:
        # Fetch in chunks to stay within API limits
        chunk_end = min(current + timedelta(days=VC_MAX_DAYS_PER_REQUEST - 1), end_dt)
        chunk_start_str = current.strftime("%Y-%m-%d")
        chunk_end_str = chunk_end.strftime("%Y-%m-%d")

        print(f"  Chunk: {chunk_start_str} to {chunk_end_str}", file=sys.stderr)

        try:
            days = fetch_weather_range(session, chunk_start_str, chunk_end_str)
            rows = [transform_weather_day(d) for d in days]
            loaded = upsert_weather(session, rows)
            total_loaded += loaded
            print(f"  Loaded {loaded} days", file=sys.stderr)

            log_pipeline_run(
                session,
                chunk_start_str,
                "success",
                loaded,
                metadata={"start": chunk_start_str, "end": chunk_end_str},
            )
        except Exception as e:
            print(f"  ERROR: {e}", file=sys.stderr)
            log_pipeline_run(session, chunk_start_str, "error", 0, str(e))

        current = chunk_end + timedelta(days=1)
        time.sleep(1)  # rate-limit courtesy

    print(f"\nDone. Total: {total_loaded} days loaded.", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="Weather ETL (Visual Crossing)")
    parser.add_argument(
        "--date",
        help="Single date to pull (YYYY-MM-DD). Default: yesterday.",
    )
    parser.add_argument(
        "--backfill",
        nargs=2,
        metavar=("START", "END"),
        help="Date range to backfill (YYYY-MM-DD YYYY-MM-DD).",
    )
    args = parser.parse_args()

    if args.backfill:
        start, end = args.backfill
    elif args.date:
        start = end = args.date
    else:
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        start = end = yesterday

    run_date_range(start, end)


if __name__ == "__main__":
    main()
