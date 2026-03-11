#!/usr/bin/env python3
"""
Reviews ETL - Pull reviews from Google Business Profile into Supabase.

Usage:
    python3 reviews_etl.py                   # Fetch latest reviews
    python3 reviews_etl.py --csv FILE.csv    # One-time import from BirdEye CSV export

PREREQUISITE: Google Business Profile API access must be approved.
Apply at: https://developers.google.com/my-business/content/prereqs
Typical approval time: 2-4 weeks.

Once approved, add to .env.toast:
    GOOGLE_ACCOUNT_ID=your-account-id
    GOOGLE_LOCATION_ID=your-location-id
    GOOGLE_API_KEY=your-api-key
"""

import argparse
import csv
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
load_dotenv(SCRIPT_DIR.parent / ".env.toast")

SUPABASE_URL = os.environ.get(
    "SUPABASE_URL", "https://zxqtclvljxvdxsnmsqka.supabase.co"
)
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

GOOGLE_ACCOUNT_ID = os.environ.get("GOOGLE_ACCOUNT_ID", "")
GOOGLE_LOCATION_ID = os.environ.get("GOOGLE_LOCATION_ID", "")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")

BATCH_SIZE = 100


# ---------------------------------------------------------------------------
# BirdEye CSV import (one-time)
# ---------------------------------------------------------------------------

def load_birdeye_csv(filepath: str, location_id: str = "kent_ave") -> list[dict]:
    """Parse a BirdEye review export CSV into review rows."""
    rows = []
    with open(filepath, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # BirdEye CSV columns vary, try common ones
            review_date = row.get("Review Date") or row.get("Date") or row.get("Created")
            rating = row.get("Rating") or row.get("Star Rating")
            text = row.get("Review") or row.get("Review Text") or row.get("Comment")
            reviewer = row.get("Reviewer") or row.get("Reviewer Name") or row.get("Name")
            platform = (row.get("Source") or row.get("Platform") or "google").lower()
            review_id = row.get("Review ID") or row.get("ID")

            if not review_date:
                continue

            # Generate a review_id if not provided
            if not review_id:
                review_id = f"{platform}_{review_date}_{hash(text or '')}"

            # Parse the date
            parsed_date = None
            for fmt in ["%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%Y-%m-%dT%H:%M:%S"]:
                try:
                    parsed_date = datetime.strptime(review_date.strip(), fmt)
                    break
                except ValueError:
                    continue

            if not parsed_date:
                continue

            rows.append({
                "location_id": location_id,
                "platform": platform,
                "review_id": review_id,
                "review_date": parsed_date.isoformat(),
                "rating": int(float(rating)) if rating else None,
                "review_text": text.strip() if text else None,
                "reviewer_name": reviewer.strip() if reviewer else None,
                "reply_text": None,
                "reply_date": None,
                "raw_data": json.dumps(dict(row)),
            })

    return rows


# ---------------------------------------------------------------------------
# Google Business Profile API (stub - activate after API approval)
# ---------------------------------------------------------------------------

def fetch_google_reviews(session: requests.Session) -> list[dict]:
    """
    Fetch reviews from Google Business Profile API.
    Requires GOOGLE_ACCOUNT_ID, GOOGLE_LOCATION_ID, GOOGLE_API_KEY.
    """
    if not all([GOOGLE_ACCOUNT_ID, GOOGLE_LOCATION_ID, GOOGLE_API_KEY]):
        print(
            "ERROR: Google Business Profile API credentials not configured.\n"
            "Add GOOGLE_ACCOUNT_ID, GOOGLE_LOCATION_ID, GOOGLE_API_KEY to .env.toast\n"
            "Apply for access at: https://developers.google.com/my-business/content/prereqs",
            file=sys.stderr,
        )
        sys.exit(1)

    url = (
        f"https://mybusiness.googleapis.com/v4/accounts/{GOOGLE_ACCOUNT_ID}"
        f"/locations/{GOOGLE_LOCATION_ID}/reviews"
    )
    headers = {"Authorization": f"Bearer {GOOGLE_API_KEY}"}

    all_reviews = []
    next_page = None

    while True:
        params = {"pageSize": 50}
        if next_page:
            params["pageToken"] = next_page

        resp = session.get(url, headers=headers, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        for review in data.get("reviews", []):
            reviewer = review.get("reviewer", {})
            star_rating = review.get("starRating", "")
            rating_map = {
                "ONE": 1, "TWO": 2, "THREE": 3, "FOUR": 4, "FIVE": 5
            }

            reply = review.get("reviewReply", {})

            all_reviews.append({
                "location_id": "kent_ave",
                "platform": "google",
                "review_id": review.get("reviewId", ""),
                "review_date": review.get("createTime"),
                "rating": rating_map.get(star_rating),
                "review_text": review.get("comment"),
                "reviewer_name": reviewer.get("displayName"),
                "reply_text": reply.get("comment") if reply else None,
                "reply_date": reply.get("updateTime") if reply else None,
                "raw_data": json.dumps(review),
            })

        next_page = data.get("nextPageToken")
        if not next_page:
            break

    return all_reviews


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


def upsert_reviews(session: requests.Session, rows: list[dict]) -> int:
    if not rows:
        return 0
    url = f"{SUPABASE_URL}/rest/v1/reviews"
    headers = supabase_headers()
    loaded = 0
    for i in range(0, len(rows), BATCH_SIZE):
        batch = rows[i : i + BATCH_SIZE]
        resp = session.post(url, json=batch, headers=headers, timeout=60)
        if resp.status_code in (200, 201):
            loaded += len(batch)
        else:
            print(f"  Upsert error: {resp.status_code} - {resp.text[:300]}", file=sys.stderr)
    return loaded


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
        "script_name": "reviews_etl",
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
    parser = argparse.ArgumentParser(description="Reviews ETL")
    parser.add_argument("--csv", help="Path to BirdEye CSV export for one-time import")
    parser.add_argument("--location", default="kent_ave", help="Location ID")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    args = parser.parse_args()

    session = requests.Session()

    if args.csv:
        print(f"Loading reviews from CSV: {args.csv}", file=sys.stderr)
        reviews = load_birdeye_csv(args.csv, args.location)
    else:
        print("Fetching reviews from Google Business Profile API...", file=sys.stderr)
        reviews = fetch_google_reviews(session)

    print(f"  Found {len(reviews)} reviews", file=sys.stderr)

    if args.dry_run:
        for r in reviews[:10]:
            stars = "*" * (r["rating"] or 0)
            print(f"  {r['review_date'][:10]} {stars:5s} {r['reviewer_name'] or 'Anon':20s} {(r['review_text'] or '')[:60]}", file=sys.stderr)
        return

    loaded = upsert_reviews(session, reviews)
    print(f"  Upserted {loaded} reviews", file=sys.stderr)

    log_pipeline_run(
        session,
        "success",
        loaded,
        metadata={"source": "csv" if args.csv else "google_api"},
    )

    print(f"\nDone. {loaded} reviews loaded.", file=sys.stderr)


if __name__ == "__main__":
    main()
