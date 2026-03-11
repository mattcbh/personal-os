#!/usr/bin/env python3
"""
Menu ETL - Pull menu catalog from Toast Menus API into Supabase.

Usage:
    python3 menu_etl.py              # Full menu refresh
    python3 menu_etl.py --dry-run    # Preview without writing

Pulls the full menu catalog from Toast, maps items to our menu_items table,
and upserts. Tracks price changes over time via effective_date / end_date.
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
load_dotenv(SCRIPT_DIR.parent / ".env.toast")

TOAST_CLIENT_ID = os.environ["TOAST_CLIENT_ID"]
TOAST_CLIENT_SECRET = os.environ["TOAST_CLIENT_SECRET"]
TOAST_API_HOST = os.environ["TOAST_API_HOST"]
TOAST_RESTAURANT_GUID = os.environ["TOAST_RESTAURANT_GUID"]

SUPABASE_URL = os.environ.get(
    "SUPABASE_URL", "https://zxqtclvljxvdxsnmsqka.supabase.co"
)
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

BATCH_SIZE = 100


# ---------------------------------------------------------------------------
# Toast API helpers
# ---------------------------------------------------------------------------

def get_toast_token(session: requests.Session) -> str:
    """Authenticate with Toast and return a bearer token."""
    resp = session.post(
        f"{TOAST_API_HOST}/authentication/v1/authentication/login",
        json={
            "clientId": TOAST_CLIENT_ID,
            "clientSecret": TOAST_CLIENT_SECRET,
            "userAccessType": "TOAST_MACHINE_CLIENT",
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["token"]["accessToken"]


def fetch_menus(session: requests.Session, token: str) -> list[dict]:
    """Fetch all menus from Toast Menus API."""
    resp = session.get(
        f"{TOAST_API_HOST}/menus/v2/menus",
        headers={
            "Authorization": f"Bearer {token}",
            "Toast-Restaurant-External-ID": TOAST_RESTAURANT_GUID,
        },
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    # Response is a dict with 'menus' key containing the list
    if isinstance(data, dict) and "menus" in data:
        return data["menus"]
    return data


# ---------------------------------------------------------------------------
# Data transformation
# ---------------------------------------------------------------------------

def extract_menu_items(menus: list[dict], location_id: str = "kent_ave") -> list[dict]:
    """
    Extract individual menu items from the nested menu structure.
    Toast menus have: Menu -> MenuGroup -> MenuItem
    """
    items = []
    today = datetime.now().strftime("%Y-%m-%d")

    for menu in menus:
        menu_name = menu.get("name", "")
        for group in menu.get("menuGroups", []):
            group_name = group.get("name", "")
            for item in group.get("menuItems", []):
                item_guid = item.get("guid")
                if not item_guid:
                    continue

                name = item.get("name", "Unknown")
                price = None
                # Price can be at item level or in the first price level
                if item.get("price") is not None:
                    try:
                        price = round(float(item["price"]), 2)
                    except (ValueError, TypeError):
                        pass

                if price is None:
                    # Check priceLevels
                    for pl in item.get("priceLevels", []):
                        if pl.get("price") is not None:
                            try:
                                price = round(float(pl["price"]), 2)
                                break
                            except (ValueError, TypeError):
                                continue

                # Sales category
                sales_cat = item.get("salesCategory", {})
                category = sales_cat.get("name") if isinstance(sales_cat, dict) else None

                items.append({
                    "toast_item_id": item_guid,
                    "location_id": location_id,
                    "item_name": name,
                    "category": category,
                    "price": price,
                    "effective_date": today,
                    "end_date": None,
                    "is_active": True,
                    "raw_data": json.dumps(item),
                })

    return items


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


def get_existing_items(session: requests.Session, location_id: str) -> dict:
    """Get existing active menu items as {toast_item_id: row}."""
    url = f"{SUPABASE_URL}/rest/v1/menu_items"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
    }
    params = {
        "location_id": f"eq.{location_id}",
        "is_active": "eq.true",
        "select": "id,toast_item_id,item_name,price,effective_date",
    }
    resp = session.get(url, headers=headers, params=params, timeout=30)
    if resp.status_code != 200:
        print(f"  Warning: could not fetch existing items: {resp.status_code}", file=sys.stderr)
        return {}
    rows = resp.json()
    return {r["toast_item_id"]: r for r in rows if r.get("toast_item_id")}


def upsert_menu_items(session: requests.Session, rows: list[dict]) -> int:
    """Upsert menu item rows. Returns count loaded."""
    if not rows:
        return 0
    url = f"{SUPABASE_URL}/rest/v1/menu_items?on_conflict=toast_item_id,location_id,effective_date"
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


def deactivate_items(session: requests.Session, toast_item_ids: list[str]) -> int:
    """Mark items as inactive (no longer on menu). Returns count updated."""
    if not toast_item_ids:
        return 0
    url = f"{SUPABASE_URL}/rest/v1/menu_items"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }
    today = datetime.now().strftime("%Y-%m-%d")
    updated = 0
    for i in range(0, len(toast_item_ids), 50):
        batch_ids = toast_item_ids[i : i + 50]
        id_filter = ",".join(batch_ids)
        params = {
            "toast_item_id": f"in.({id_filter})",
            "is_active": "eq.true",
        }
        resp = session.patch(
            url,
            headers=headers,
            params=params,
            json={"is_active": False, "end_date": today},
            timeout=30,
        )
        if resp.status_code in (200, 204):
            updated += len(batch_ids)
        else:
            print(f"  Deactivate error: {resp.status_code} - {resp.text[:300]}", file=sys.stderr)
    return updated


def log_pipeline_run(
    session: requests.Session,
    status: str,
    rows_loaded: int,
    error_message: str | None = None,
    metadata: dict | None = None,
) -> None:
    url = f"{SUPABASE_URL}/rest/v1/pipeline_runs"
    headers = supabase_headers()
    headers["Prefer"] = "return=minimal"
    today = datetime.now().strftime("%Y-%m-%d")
    row = {
        "script_name": "menu_etl",
        "run_date": today,
        "status": status,
        "rows_loaded": rows_loaded,
        "error_message": error_message,
        "metadata": json.dumps(metadata or {}),
    }
    session.post(url, json=[row], headers=headers, timeout=30)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Toast Menu Catalog ETL")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    parser.add_argument("--location", default="kent_ave", help="Location ID (default: kent_ave)")
    args = parser.parse_args()

    session = requests.Session()

    print("Authenticating with Toast API...", file=sys.stderr)
    token = get_toast_token(session)

    print("Fetching menu catalog...", file=sys.stderr)
    menus = fetch_menus(session, token)
    print(f"  Got {len(menus)} menus", file=sys.stderr)

    items_raw = extract_menu_items(menus, args.location)
    # Deduplicate by toast_item_id (same item can appear in multiple menus)
    seen = {}
    for item in items_raw:
        seen[item["toast_item_id"]] = item
    items = list(seen.values())
    print(f"  Extracted {len(items_raw)} menu items, {len(items)} unique", file=sys.stderr)

    if args.dry_run:
        for item in items[:20]:
            print(f"  {item['item_name']:40s} ${item['price'] or 0:>6.2f}  [{item['category']}]", file=sys.stderr)
        if len(items) > 20:
            print(f"  ... and {len(items) - 20} more", file=sys.stderr)
        return

    # Get existing items to detect removals
    existing = get_existing_items(session, args.location)
    new_ids = {item["toast_item_id"] for item in items}
    removed_ids = [tid for tid in existing if tid not in new_ids]

    # Upsert current items
    loaded = upsert_menu_items(session, items)
    print(f"  Upserted {loaded} items", file=sys.stderr)

    # Deactivate removed items
    deactivated = 0
    if removed_ids:
        deactivated = deactivate_items(session, removed_ids)
        print(f"  Deactivated {deactivated} removed items", file=sys.stderr)

    log_pipeline_run(
        session,
        "success",
        loaded,
        metadata={
            "items_upserted": loaded,
            "items_deactivated": deactivated,
            "menus_fetched": len(menus),
        },
    )

    print(f"\nDone. {loaded} items active, {deactivated} deactivated.", file=sys.stderr)


if __name__ == "__main__":
    main()
