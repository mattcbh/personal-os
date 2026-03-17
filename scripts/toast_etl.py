#!/usr/bin/env python3
"""
Toast API ETL - Pull orders and order items from Toast into Supabase.

Usage:
    python3 toast_etl.py                          # Yesterday's orders
    python3 toast_etl.py --date 2026-02-07        # Specific date
    python3 toast_etl.py --backfill 2026-01-01 2026-01-31  # Date range

Flow:
    1. Authenticate with Toast API
    2. Fetch config lookups (dining options, revenue centers, sales categories)
    3. For each date: list order GUIDs, fetch each full order, transform, upsert
"""

import argparse
import json
import os
import sys
import time
import traceback
from datetime import datetime, timedelta
from pathlib import Path

# Force unbuffered output so progress shows in real-time
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

import requests
from dotenv import load_dotenv

from toast_api_common import (
    DEFAULT_LOCATION_ID,
    get_machine_client_token,
    load_restaurant_map_from_env,
    orders_headers,
    request_with_retry,
    resolve_location_id,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
load_dotenv(SCRIPT_DIR.parent / ".env.toast")

TOAST_CLIENT_ID = os.environ["TOAST_CLIENT_ID"]
TOAST_CLIENT_SECRET = os.environ["TOAST_CLIENT_SECRET"]
TOAST_API_HOST = os.environ["TOAST_API_HOST"]
TOAST_RESTAURANT_GUID = os.environ["TOAST_RESTAURANT_GUID"]
TOAST_RESTAURANT_MAP_JSON = os.environ.get("TOAST_RESTAURANT_MAP_JSON", "").strip()
TOAST_RESTAURANT_MAP = load_restaurant_map_from_env()
if TOAST_RESTAURANT_MAP_JSON and TOAST_RESTAURANT_GUID not in TOAST_RESTAURANT_MAP:
    raise RuntimeError(
        "TOAST_RESTAURANT_MAP_JSON is set but does not include TOAST_RESTAURANT_GUID "
        f"{TOAST_RESTAURANT_GUID}"
    )
LOCATION_ID = resolve_location_id(
    TOAST_RESTAURANT_GUID,
    TOAST_RESTAURANT_MAP,
    default_location_id=DEFAULT_LOCATION_ID if not TOAST_RESTAURANT_MAP_JSON else None,
)

SUPABASE_URL = os.environ.get(
    "SUPABASE_URL", "https://zxqtclvljxvdxsnmsqka.supabase.co"
)
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

BATCH_SIZE = 200  # rows per Supabase POST
ORDER_FETCH_BATCH = 10  # orders to fetch before a brief pause

# Channel classification from dining option names
CHANNEL_MAP = {
    "Dining Inside": ("dine_in", "dine_in"),
    "Dining Outside": ("dine_in", "dine_in"),
    "Counter": ("counter", "dine_in"),
    "DoorDash - Delivery": ("doordash", "3pd"),
    "DoorDash - Takeout": ("doordash", "3pd"),
    "Grubhub - Delivery": ("grubhub", "3pd"),
    "Grubhub - Takeout": ("grubhub", "3pd"),
    "Uber Eats - Delivery": ("ubereats", "3pd"),
    "Uber Eats - Takeout": ("ubereats", "3pd"),
    "Online Ordering - Delivery": ("online", "takeout"),
    "Online Ordering - Takeout": ("online", "takeout"),
    "Pies Website Delivery": ("website", "takeout"),
    "Catering": ("catering", "catering"),
    "Catering - Delivery": ("catering", "catering"),
    "Phone Pick up": ("phone", "takeout"),
    "Commissary": ("commissary", "other"),
    "Ritual Online - Pick Up": ("ritual", "takeout"),
    "E-Gift Cards": ("gift_card", "other"),
}

# Daypart boundaries (hour of day, UTC - Toast returns UTC)
# PnT is in ET, so UTC hour 11 = ET 6am, UTC 16 = ET 11am, etc.
# But openedDate is UTC, so we convert
DAYPART_BREAKS = [
    (0, "late_night"),
    (6, "breakfast"),
    (11, "lunch"),
    (15, "afternoon"),
    (17, "dinner"),
    (22, "late_night"),
]


# ---------------------------------------------------------------------------
# Toast API helpers
# ---------------------------------------------------------------------------

def toast_headers(token: str) -> dict:
    return orders_headers(token, TOAST_RESTAURANT_GUID)


def get_toast_token(session: requests.Session) -> str:
    """Authenticate with Toast and return a bearer token."""
    return get_machine_client_token(
        session,
        TOAST_API_HOST,
        TOAST_CLIENT_ID,
        TOAST_CLIENT_SECRET,
    )


def fetch_config_lookups(session: requests.Session, token: str) -> dict:
    """Fetch dining options, revenue centers, and sales categories.
    Returns a dict of lookup maps: {guid: name}."""
    headers = toast_headers(token)
    lookups = {}

    for config_type in ["diningOptions", "revenueCenters", "salesCategories"]:
        resp = session.get(
            f"{TOAST_API_HOST}/config/v2/{config_type}",
            headers=headers,
            timeout=30,
        )
        if resp.status_code == 200:
            lookups[config_type] = {
                item["guid"]: item.get("name", "")
                for item in resp.json()
            }
        else:
            print(f"  Warning: could not fetch {config_type}: {resp.status_code}", file=sys.stderr)
            lookups[config_type] = {}

    return lookups


def fetch_order_guids(
    session: requests.Session, token: str, biz_date: str
) -> list[str]:
    """Fetch all order GUIDs for a business date (YYYYMMDD format).

    Note: Toast API ignores page/pageSize params and returns all GUIDs
    in a single response. We still handle pagination defensively in case
    this changes, using a seen-set to detect duplicate pages.
    """
    headers = toast_headers(token)
    all_guids = []
    seen = set()
    page = 0
    while True:
        resp = request_with_retry(
            session, "get",
            f"{TOAST_API_HOST}/orders/v2/orders",
            headers=headers,
            params={"businessDate": biz_date, "page": page, "pageSize": 100},
            output_stream=sys.stderr,
        )
        if resp.status_code != 200:
            if resp.status_code == 404:
                break
            resp.raise_for_status()
        guids = resp.json()
        if not guids:
            break
        # Deduplicate: if all returned GUIDs are already seen, stop
        new_guids = [g for g in guids if g not in seen]
        if not new_guids:
            break
        seen.update(new_guids)
        all_guids.extend(new_guids)
        if len(guids) < 100:
            break
        page += 1
        time.sleep(0.2)
    return all_guids


def fetch_order_detail(
    session: requests.Session, token: str, guid: str
) -> dict | None:
    """Fetch a single order's full details."""
    headers = toast_headers(token)
    resp = request_with_retry(
        session, "get",
        f"{TOAST_API_HOST}/orders/v2/orders/{guid}",
        headers=headers,
        output_stream=sys.stderr,
    )
    if resp.status_code == 200:
        return resp.json()
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return None


def fetch_all_orders(
    session: requests.Session, token: str, date_str: str
) -> list[dict]:
    """Fetch all full orders for a single business date (YYYY-MM-DD)."""
    biz_date = date_str.replace("-", "")
    guids = fetch_order_guids(session, token, biz_date)
    if not guids:
        return []

    print(f"  Found {len(guids)} order GUIDs, fetching details...", file=sys.stderr)
    orders = []
    for i, guid in enumerate(guids):
        order = fetch_order_detail(session, token, guid)
        if order:
            orders.append(order)
        # Rate-limit: pause every N orders
        if (i + 1) % ORDER_FETCH_BATCH == 0:
            time.sleep(0.3)
            if (i + 1) % 50 == 0:
                print(f"    Fetched {i + 1}/{len(guids)} orders...", file=sys.stderr)

    return orders


# ---------------------------------------------------------------------------
# Data transformation
# ---------------------------------------------------------------------------

def classify_daypart(hour: int) -> str:
    """Return daypart string for a given hour (0-23, local time)."""
    result = "late_night"
    for boundary_hour, label in DAYPART_BREAKS:
        if hour >= boundary_hour:
            result = label
    return result


def classify_channel(dining_option_name: str) -> tuple[str, str]:
    """Return (channel, channel_group) from dining option name."""
    if dining_option_name in CHANNEL_MAP:
        return CHANNEL_MAP[dining_option_name]
    # Fallback: partial matches
    lower = dining_option_name.lower()
    if "doordash" in lower:
        return ("doordash", "3pd")
    if "grubhub" in lower:
        return ("grubhub", "3pd")
    if "uber" in lower:
        return ("ubereats", "3pd")
    if "delivery" in lower:
        return ("delivery", "3pd")
    if "take" in lower or "pick" in lower:
        return ("takeout", "takeout")
    if "dine" in lower or "inside" in lower or "outside" in lower:
        return ("dine_in", "dine_in")
    if "counter" in lower:
        return ("counter", "dine_in")
    return ("other", "other")


def parse_toast_datetime(iso_str: str | None) -> datetime | None:
    """Parse Toast ISO datetime string (e.g. 2026-02-07T23:37:37.433+0000)."""
    if not iso_str:
        return None
    try:
        return datetime.fromisoformat(iso_str.replace("+0000", "+00:00"))
    except ValueError:
        try:
            return datetime.strptime(iso_str, "%Y-%m-%dT%H:%M:%S.%f%z")
        except ValueError:
            return None


def parse_amount(val) -> float:
    """Safely parse a numeric amount."""
    if val is None:
        return 0.0
    try:
        return round(float(val), 2)
    except (ValueError, TypeError):
        return 0.0


def resolve_guid(ref: dict | None, lookup: dict) -> str:
    """Resolve a Toast entity reference {guid, entityType} to a name."""
    if not ref or not isinstance(ref, dict):
        return ""
    guid = ref.get("guid", "")
    return lookup.get(guid, "")


def transform_order(order: dict, lookups: dict, location_id: str) -> dict | None:
    """Transform a Toast API order into our orders table row."""
    guid = order.get("guid")
    if not guid:
        return None

    # Parse timestamps
    opened = parse_toast_datetime(order.get("openedDate"))
    closed = parse_toast_datetime(order.get("closedDate"))
    if not opened:
        return None

    # Convert UTC to ET for daypart classification (ET = UTC-5)
    et_hour = (opened.hour - 5) % 24
    order_date_raw = str(order.get("businessDate", ""))
    if order_date_raw and len(order_date_raw) == 8:
        order_date = f"{order_date_raw[:4]}-{order_date_raw[4:6]}-{order_date_raw[6:8]}"
    else:
        order_date = opened.strftime("%Y-%m-%d")
    order_time = opened.strftime("%H:%M:%S")

    # Channel classification via config lookup
    dining_name = resolve_guid(order.get("diningOption"), lookups.get("diningOptions", {}))
    channel, channel_group = classify_channel(dining_name)
    daypart = classify_daypart(et_hour)

    # Financial amounts from checks
    checks = order.get("checks", [])
    subtotal = 0.0
    discount_total = 0.0
    tax_total = 0.0
    tip_total = 0.0
    total_amount = 0.0
    item_count = 0
    payment_type = None

    for check in checks:
        check_amount = parse_amount(check.get("amount"))
        check_total = parse_amount(check.get("totalAmount"))
        check_tax = parse_amount(check.get("taxAmount"))

        subtotal += check_amount
        total_amount += check_total
        tax_total += check_tax

        # Tips from payments
        for pmt in check.get("payments", []):
            tip_total += parse_amount(pmt.get("tipAmount"))
            if not payment_type:
                ptype = pmt.get("type", "")
                payment_type = ptype.lower() if ptype else None

        # Discounts
        for disc in check.get("appliedDiscounts", []):
            discount_total += abs(parse_amount(disc.get("discountAmount")))

        # Count items
        for sel in check.get("selections", []):
            qty = parse_amount(sel.get("quantity")) or 1
            item_count += int(qty)

    net_sales = round(subtotal - discount_total, 2)
    guest_count = order.get("numberOfGuests")
    order_source = order.get("source")

    return {
        "toast_order_id": guid,
        "location_id": location_id,
        "order_date": order_date,
        "order_time": order_time,
        "opened_at": opened.isoformat(),
        "closed_at": closed.isoformat() if closed else None,
        "channel": channel,
        "channel_group": channel_group,
        "daypart": daypart,
        "order_source": order_source,
        "subtotal": subtotal,
        "discount_amount": discount_total,
        "tax_amount": tax_total,
        "tip_amount": tip_total,
        "net_sales": net_sales,
        "total_amount": total_amount,
        "guest_count": guest_count,
        "item_count": item_count,
        "payment_type": payment_type,
    }


def parse_business_date(value) -> int | None:
    """Return a YYYYMMDD integer when Toast provides a business date-like field."""
    if value is None:
        return None
    text = str(value).strip()
    return int(text) if len(text) == 8 and text.isdigit() else None


def extract_order_items(order: dict, location_id: str, lookups: dict) -> list[dict]:
    """Extract individual items from an order's checks/selections."""
    items = []
    order_guid = order.get("guid")
    if not order_guid:
        return items

    order_date_raw = str(order.get("businessDate", ""))
    if order_date_raw and len(order_date_raw) == 8:
        order_date = f"{order_date_raw[:4]}-{order_date_raw[4:6]}-{order_date_raw[6:8]}"
    else:
        opened = parse_toast_datetime(order.get("openedDate"))
        order_date = opened.strftime("%Y-%m-%d") if opened else None
    if not order_date:
        return items

    sales_cat_lookup = lookups.get("salesCategories", {})

    for check in order.get("checks", []):
        for sel in check.get("selections", []):
            item_guid = sel.get("guid")
            if not item_guid:
                continue

            item_name = sel.get("displayName") or "Unknown"
            quantity = parse_amount(sel.get("quantity")) or 1
            unit_price = parse_amount(sel.get("price"))
            pre_discount = parse_amount(sel.get("preDiscountPrice"))
            net_amount = round(unit_price * quantity, 2)
            gross_amount = round(pre_discount * quantity, 2) if pre_discount else net_amount

            item_discount = 0.0
            for disc in sel.get("appliedDiscounts", []):
                item_discount += abs(parse_amount(disc.get("discountAmount")))

            # Resolve sales category GUID to name
            category = resolve_guid(sel.get("salesCategory"), sales_cat_lookup)

            # Item group reference
            item_group = sel.get("itemGroup", {})
            menu_group = item_group.get("name") if isinstance(item_group, dict) else None

            # Item reference for menu_item_id
            item_ref = sel.get("item", {})
            menu_item_id = None
            if isinstance(item_ref, dict):
                menu_item_id = item_ref.get("guid") or item_ref.get("externalId")

            is_void = sel.get("voided", False) or sel.get("deferred", False)

            sent_at_str = sel.get("createdDate") or sel.get("modifiedDate")
            sent_at = parse_toast_datetime(sent_at_str)

            items.append({
                "toast_order_id": order_guid,
                "toast_item_guid": item_guid,
                "location_id": location_id,
                "item_name": item_name,
                "menu_item_id": menu_item_id,
                "quantity": int(quantity),
                "unit_price": unit_price,
                "gross_amount": gross_amount,
                "discount_amount": item_discount,
                "net_amount": net_amount,
                "category": category or None,
                "order_date": order_date,
                "sent_at": sent_at.isoformat() if sent_at else None,
                "menu_group": menu_group,
                "is_void": is_void,
                "raw_data": sel,
            })

    return items


def extract_payments(order: dict, location_id: str, restaurant_guid: str) -> list[dict]:
    """Extract check-level Toast payment records for card-fingerprint joins."""
    payments = []
    order_guid = order.get("guid")
    if not order_guid:
        return payments

    for check in order.get("checks", []):
        check_guid = check.get("guid")
        if not check_guid:
            continue

        for payment in check.get("payments", []):
            payment_guid = payment.get("guid")
            if not payment_guid:
                continue
            paid_dt = parse_toast_datetime(payment.get("paidDate"))

            payments.append({
                "payment_guid": payment_guid,
                "check_guid": check_guid,
                "order_guid": order_guid,
                "restaurant_guid": restaurant_guid,
                "location_id": location_id,
                "type": payment.get("type"),
                "amount": parse_amount(payment.get("amount")),
                "tip_amount": parse_amount(payment.get("tipAmount")),
                "card_type": payment.get("cardType"),
                "card_entry_mode": payment.get("cardEntryMode"),
                "payment_status": payment.get("paymentStatus"),
                "paid_date": paid_dt.isoformat() if paid_dt else None,
                "paid_business_date": parse_business_date(
                    payment.get("paidBusinessDate") or payment.get("businessDate")
                ),
            })

    return payments


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


def upsert_orders(session: requests.Session, rows: list[dict]) -> int:
    """Upsert order rows into Supabase. Returns count of rows sent."""
    if not rows:
        return 0
    url = f"{SUPABASE_URL}/rest/v1/orders?on_conflict=toast_order_id,location_id"
    headers = supabase_headers()

    loaded = 0
    for i in range(0, len(rows), BATCH_SIZE):
        batch = rows[i : i + BATCH_SIZE]
        resp = session.post(url, json=batch, headers=headers, timeout=60)
        if resp.status_code in (200, 201):
            loaded += len(batch)
        else:
            print(f"  Orders upsert error (batch {i//BATCH_SIZE}): {resp.status_code} - {resp.text[:300]}", file=sys.stderr)
    return loaded


def upsert_order_items(session: requests.Session, rows: list[dict]) -> int:
    """Upsert order item rows into Supabase. Returns count of rows sent."""
    if not rows:
        return 0
    url = f"{SUPABASE_URL}/rest/v1/order_items?on_conflict=toast_item_guid"
    headers = supabase_headers()

    loaded = 0
    for i in range(0, len(rows), BATCH_SIZE):
        batch = rows[i : i + BATCH_SIZE]
        for row in batch:
            if "raw_data" in row and isinstance(row["raw_data"], dict):
                row["raw_data"] = json.dumps(row["raw_data"])
        resp = session.post(url, json=batch, headers=headers, timeout=60)
        if resp.status_code in (200, 201):
            loaded += len(batch)
        else:
            print(f"  Items upsert error (batch {i//BATCH_SIZE}): {resp.status_code} - {resp.text[:300]}", file=sys.stderr)
    return loaded


def upsert_payments(session: requests.Session, rows: list[dict]) -> int:
    """Upsert Toast payment rows into Supabase. Returns count of rows sent."""
    if not rows:
        return 0
    url = f"{SUPABASE_URL}/rest/v1/toast_payments?on_conflict=payment_guid"
    headers = supabase_headers()

    loaded = 0
    for i in range(0, len(rows), BATCH_SIZE):
        batch = rows[i : i + BATCH_SIZE]
        resp = session.post(url, json=batch, headers=headers, timeout=60)
        if resp.status_code in (200, 201):
            loaded += len(batch)
        else:
            print(
                f"  Payments upsert error (batch {i//BATCH_SIZE}): "
                f"{resp.status_code} - {resp.text[:300]}",
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
        "script_name": "toast_etl",
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
    """Run ETL for a range of dates (inclusive)."""
    session = requests.Session()

    print("Authenticating with Toast API...", file=sys.stderr)
    token = get_toast_token(session)
    print("Authenticated.", file=sys.stderr)
    print(
        f"Using restaurant {TOAST_RESTAURANT_GUID} -> location_id {LOCATION_ID}.",
        file=sys.stderr,
    )

    print("Fetching config lookups...", file=sys.stderr)
    lookups = fetch_config_lookups(session, token)
    print(
        f"  {len(lookups.get('diningOptions', {}))} dining options, "
        f"{len(lookups.get('revenueCenters', {}))} revenue centers, "
        f"{len(lookups.get('salesCategories', {}))} sales categories",
        file=sys.stderr,
    )

    print(f"Pulling orders from {start} to {end}.", file=sys.stderr)

    current = datetime.strptime(start, "%Y-%m-%d")
    end_dt = datetime.strptime(end, "%Y-%m-%d")
    total_orders = 0
    total_items = 0
    total_payments = 0

    while current <= end_dt:
        date_str = current.strftime("%Y-%m-%d")
        print(f"\n--- {date_str} ---", file=sys.stderr)

        try:
            raw_orders = fetch_all_orders(session, token, date_str)
            print(f"  Fetched {len(raw_orders)} full orders", file=sys.stderr)

            if not raw_orders:
                current += timedelta(days=1)
                continue

            # Transform
            order_rows = []
            all_item_rows = []
            all_payment_rows = []
            for raw in raw_orders:
                order_row = transform_order(raw, lookups, LOCATION_ID)
                if order_row:
                    order_rows.append(order_row)
                    item_rows = extract_order_items(raw, order_row["location_id"], lookups)
                    payment_rows = extract_payments(
                        raw,
                        order_row["location_id"],
                        TOAST_RESTAURANT_GUID,
                    )
                    all_item_rows.extend(item_rows)
                    all_payment_rows.extend(payment_rows)

            # Upsert to Supabase
            orders_loaded = upsert_orders(session, order_rows)
            items_loaded = upsert_order_items(session, all_item_rows)
            payments_loaded = upsert_payments(session, all_payment_rows)

            total_orders += orders_loaded
            total_items += items_loaded
            total_payments += payments_loaded
            print(
                f"  Loaded {orders_loaded} orders, {items_loaded} items, "
                f"{payments_loaded} payments",
                file=sys.stderr,
            )

            log_pipeline_run(
                session,
                date_str,
                "success",
                orders_loaded + items_loaded + payments_loaded,
                metadata={
                    "orders": orders_loaded,
                    "items": items_loaded,
                    "payments": payments_loaded,
                    "api_count": len(raw_orders),
                    "restaurant_guid": TOAST_RESTAURANT_GUID,
                    "location_id": LOCATION_ID,
                },
            )

        except Exception as e:
            print(f"  ERROR: {e}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            log_pipeline_run(session, date_str, "error", 0, str(e))

        current += timedelta(days=1)
        time.sleep(0.5)

    print(
        f"\nDone. Total: {total_orders} orders, {total_items} items, "
        f"{total_payments} payments.",
        file=sys.stderr,
    )


def main():
    parser = argparse.ArgumentParser(description="Toast API ETL")
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
