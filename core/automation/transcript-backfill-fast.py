#!/usr/bin/env python3
"""
Accelerated Transcript Backfill via Direct Granola API

Replaces the slow claude -p + MCP approach with direct REST API calls.
At 2 req/sec, processes ~1,037 items in ~15-20 minutes instead of 4-5 months.

Usage:
    python3 transcript-backfill-fast.py              # Process all remaining
    python3 transcript-backfill-fast.py --limit 5    # Process only 5 (for testing)
    python3 transcript-backfill-fast.py --dry-run     # Preview what would be processed
    python3 transcript-backfill-fast.py --status      # Show current progress
"""

import argparse
import base64
import json
import logging
import os
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

# Paths
OBSIDIAN_ROOT = Path.home() / "Obsidian" / "personal-os"
STATE_FILE = OBSIDIAN_ROOT / "core" / "state" / "transcript-backfill.json"
TRANSCRIPTS_DIR = OBSIDIAN_ROOT / "Knowledge" / "TRANSCRIPTS"
LOG_DIR = OBSIDIAN_ROOT / "logs"
LOG_FILE = LOG_DIR / "transcript-backfill-fast.log"
SUPABASE_JSON = Path.home() / "Library" / "Application Support" / "Granola" / "supabase.json"

# Granola API
TRANSCRIPT_URL = "https://api.granola.ai/v1/get-document-transcript"
WORKOS_REFRESH_URL = "https://api.workos.com/user_management/authenticate"
CLIENT_ID = "client_01JZJ0XBDAT8PHJWQY09Y0VD61"

# Rate limiting
REQUESTS_PER_SECOND = 2
REQUEST_INTERVAL = 1.0 / REQUESTS_PER_SECOND

# Retry config
MAX_RETRIES = 4
RETRY_BACKOFF = [2, 4, 8, 16]

# State save interval
STATE_SAVE_INTERVAL = 10


def setup_logging():
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("backfill")
    logger.setLevel(logging.INFO)

    # File handler
    fh = logging.FileHandler(LOG_FILE)
    fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(fh)

    # Console handler
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter("%(asctime)s %(message)s", datefmt="%H:%M:%S"))
    logger.addHandler(ch)

    return logger


def load_tokens():
    """Load WorkOS tokens from Granola's supabase.json."""
    with open(SUPABASE_JSON) as f:
        data = json.load(f)
    return json.loads(data["workos_tokens"])


def save_tokens(tokens):
    """Save refreshed tokens back to supabase.json, preserving other fields."""
    with open(SUPABASE_JSON) as f:
        data = json.load(f)
    data["workos_tokens"] = json.dumps(tokens)
    # Atomic write: write to temp, then rename
    tmp = str(SUPABASE_JSON) + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f)
    os.replace(tmp, SUPABASE_JSON)


def decode_jwt_exp(token):
    """Extract expiration timestamp from JWT without external libraries."""
    payload = token.split(".")[1]
    payload += "=" * (4 - len(payload) % 4)
    decoded = json.loads(base64.urlsafe_b64decode(payload))
    return decoded["exp"]


def ensure_valid_token(tokens, logger):
    """Check token expiry and refresh if needed. Returns valid access_token."""
    exp = decode_jwt_exp(tokens["access_token"])
    now = time.time()
    remaining = exp - now

    if remaining > 300:  # More than 5 min left
        logger.info(f"Token valid for {int(remaining / 60)} more minutes")
        return tokens["access_token"], tokens

    logger.info(f"Token expires in {int(remaining)}s, refreshing...")

    resp = requests.post(WORKOS_REFRESH_URL, json={
        "grant_type": "refresh_token",
        "client_id": CLIENT_ID,
        "refresh_token": tokens["refresh_token"],
    }, timeout=30)

    if resp.status_code != 200:
        logger.error(f"Token refresh failed: {resp.status_code} {resp.text}")
        raise RuntimeError(f"Token refresh failed: {resp.status_code}")

    new_data = resp.json()
    tokens["access_token"] = new_data["access_token"]
    tokens["refresh_token"] = new_data["refresh_token"]
    tokens["expires_in"] = new_data.get("expires_in", 21599)
    tokens["obtained_at"] = int(time.time() * 1000)

    # Save immediately (refresh_token is one-time-use)
    save_tokens(tokens)
    logger.info("Token refreshed and saved")

    return tokens["access_token"], tokens


def load_state():
    with open(STATE_FILE) as f:
        return json.load(f)


def save_state(state):
    tmp = str(STATE_FILE) + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, STATE_FILE)


def format_transcript(utterances):
    """
    Format utterance array into the same text format used by the MCP tool.
    Merges consecutive same-speaker utterances into paragraphs.
    microphone = "Me:", system = "Them:"
    """
    if not utterances:
        return ""

    blocks = []
    current_source = None
    current_texts = []

    for u in utterances:
        source = u.get("source", "system")
        text = u.get("text", "").strip()
        if not text:
            continue

        if source != current_source:
            # Flush previous block
            if current_texts:
                label = " Me:" if current_source == "microphone" else " Them:"
                blocks.append(f"{label} {' '.join(current_texts)}")
            current_source = source
            current_texts = [text]
        else:
            current_texts.append(text)

    # Flush last block
    if current_texts:
        label = " Me:" if current_source == "microphone" else " Them:"
        blocks.append(f"{label} {' '.join(current_texts)}")

    return "  ".join(blocks)


def fetch_transcript(uuid, access_token, logger):
    """Fetch transcript from Granola API with retries."""
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "User-Agent": "Granola/5.354.0",
        "X-Client-Version": "5.354.0",
    }

    for attempt in range(MAX_RETRIES + 1):
        try:
            resp = requests.post(
                TRANSCRIPT_URL,
                headers=headers,
                json={"document_id": uuid},
                timeout=30,
            )

            if resp.status_code == 200:
                return resp.json(), None

            if resp.status_code == 429:
                if attempt < MAX_RETRIES:
                    wait = RETRY_BACKOFF[attempt]
                    logger.warning(f"Rate limited (429), waiting {wait}s (attempt {attempt + 1})")
                    time.sleep(wait)
                    continue
                return None, "rate_limit_exhausted"

            if resp.status_code == 404:
                return None, "not_found"

            if resp.status_code >= 500:
                if attempt < MAX_RETRIES:
                    wait = RETRY_BACKOFF[attempt]
                    logger.warning(f"Server error {resp.status_code}, waiting {wait}s")
                    time.sleep(wait)
                    continue
                return None, f"server_error_{resp.status_code}"

            return None, f"http_{resp.status_code}"

        except requests.Timeout:
            if attempt < MAX_RETRIES:
                wait = RETRY_BACKOFF[attempt]
                logger.warning(f"Timeout, waiting {wait}s")
                time.sleep(wait)
                continue
            return None, "timeout"

        except requests.RequestException as e:
            return None, f"request_error: {e}"

    return None, "max_retries_exceeded"


def append_transcript_to_file(filepath, transcript_text, logger):
    """Append ## Transcript section to a markdown file."""
    with open(filepath, "a") as f:
        f.write("\n\n## Transcript\n\n")
        f.write(transcript_text)
        f.write("\n")


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def show_status(state):
    completed = len(state.get("completed", {}))
    skipped = len(state.get("skipped", {}))
    failed = len(state.get("failed", {}))
    total = len(state["backfill_queue"])
    remaining = total - completed - skipped

    print(f"Queue total:  {total}")
    print(f"Completed:    {completed}")
    print(f"Skipped:      {skipped}")
    print(f"Failed:       {failed}")
    print(f"Remaining:    {remaining}")
    print(f"Batches:      {state.get('batches_processed', 0)}")
    print(f"Last batch:   {state.get('last_batch', 'never')}")

    if remaining > 0:
        est_seconds = remaining / REQUESTS_PER_SECOND
        print(f"Est. time:    {int(est_seconds / 60)} minutes at {REQUESTS_PER_SECOND} req/sec")


def main():
    parser = argparse.ArgumentParser(description="Fast Granola transcript backfill")
    parser.add_argument("--limit", type=int, help="Max transcripts to process")
    parser.add_argument("--dry-run", action="store_true", help="Preview without processing")
    parser.add_argument("--status", action="store_true", help="Show current progress")
    args = parser.parse_args()

    state = load_state()

    if args.status:
        show_status(state)
        return

    logger = setup_logging()
    logger.info("=" * 60)
    logger.info("Starting accelerated transcript backfill")

    # Backup supabase.json before first run
    backup_path = SUPABASE_JSON.parent / "supabase.json.backup"
    if not backup_path.exists():
        shutil.copy2(SUPABASE_JSON, backup_path)
        logger.info(f"Backed up supabase.json to {backup_path}")

    # Load and validate token
    tokens = load_tokens()
    access_token, tokens = ensure_valid_token(tokens, logger)

    # Build work queue: items not yet completed or skipped
    completed = set(state.get("completed", {}).keys())
    skipped = set(state.get("skipped", {}).keys())
    done_set = completed | skipped

    work_queue = []
    for item in state["backfill_queue"]:
        fn = item["filename"]
        if fn in done_set:
            continue

        filepath = TRANSCRIPTS_DIR / fn
        if not filepath.exists():
            # File doesn't exist, skip it
            state.setdefault("skipped", {})[fn] = {
                "reason": "file_not_found",
                "timestamp": now_iso(),
            }
            continue

        # Check if file already has transcript
        content = filepath.read_text()
        if "## Transcript" in content:
            state.setdefault("skipped", {})[fn] = {
                "reason": "already_has_transcript",
                "timestamp": now_iso(),
            }
            continue

        work_queue.append(item)

    if args.limit:
        work_queue = work_queue[:args.limit]

    logger.info(f"Work queue: {len(work_queue)} items" + (f" (limited to {args.limit})" if args.limit else ""))

    if args.dry_run:
        for i, item in enumerate(work_queue[:20]):
            print(f"  {i + 1}. {item['filename']} ({item['uuid']})")
        if len(work_queue) > 20:
            print(f"  ... and {len(work_queue) - 20} more")
        return

    if not work_queue:
        logger.info("Nothing to process!")
        return

    # Process
    stats = {"completed": 0, "skipped": 0, "failed": 0, "rate_limited": 0}
    start_time = time.time()
    last_request_time = 0
    unsaved_changes = 0

    for i, item in enumerate(work_queue):
        fn = item["filename"]
        uuid = item["uuid"]
        filepath = TRANSCRIPTS_DIR / fn

        # Rate limiting
        elapsed = time.time() - last_request_time
        if elapsed < REQUEST_INTERVAL:
            time.sleep(REQUEST_INTERVAL - elapsed)

        # Check token every 100 requests (tokens last 6 hours, so this is plenty)
        if i > 0 and i % 100 == 0:
            access_token, tokens = ensure_valid_token(tokens, logger)

        # Fetch
        last_request_time = time.time()
        utterances, error = fetch_transcript(uuid, access_token, logger)

        if error:
            if "rate_limit" in error:
                stats["rate_limited"] += 1
                logger.error(f"Rate limit exhausted at item {i + 1}. Stopping.")
                state.setdefault("failed", {})[fn] = {
                    "reason": error,
                    "uuid": uuid,
                    "timestamp": now_iso(),
                }
                unsaved_changes += 1
                break

            stats["failed"] += 1
            state.setdefault("failed", {})[fn] = {
                "reason": error,
                "uuid": uuid,
                "timestamp": now_iso(),
            }
            unsaved_changes += 1
            logger.warning(f"[{i + 1}/{len(work_queue)}] FAILED {fn}: {error}")
            continue

        # Check if transcript has content
        if not utterances or len(utterances) < 2:
            stats["skipped"] += 1
            state.setdefault("skipped", {})[fn] = {
                "reason": "empty_or_minimal_transcript",
                "timestamp": now_iso(),
            }
            unsaved_changes += 1
            logger.info(f"[{i + 1}/{len(work_queue)}] SKIP {fn} (empty/minimal)")
            continue

        # Format and append
        transcript_text = format_transcript(utterances)

        if len(transcript_text) < 50:
            stats["skipped"] += 1
            state.setdefault("skipped", {})[fn] = {
                "reason": "transcript_too_short",
                "timestamp": now_iso(),
            }
            unsaved_changes += 1
            logger.info(f"[{i + 1}/{len(work_queue)}] SKIP {fn} (too short)")
            continue

        append_transcript_to_file(filepath, transcript_text, logger)
        stats["completed"] += 1
        state.setdefault("completed", {})[fn] = {
            "timestamp": now_iso(),
        }
        unsaved_changes += 1

        logger.info(
            f"[{i + 1}/{len(work_queue)}] OK {fn} "
            f"({len(utterances)} utterances, {len(transcript_text)} chars)"
        )

        # Periodic state save
        if unsaved_changes >= STATE_SAVE_INTERVAL:
            state["last_batch"] = now_iso()
            save_state(state)
            unsaved_changes = 0
            elapsed_total = time.time() - start_time
            rate = (i + 1) / elapsed_total
            remaining = len(work_queue) - i - 1
            eta_min = int(remaining / rate / 60) if rate > 0 else "?"
            logger.info(f"  State saved. Rate: {rate:.1f}/sec, ETA: ~{eta_min} min")

    # Final state save
    state["last_batch"] = now_iso()
    state["batches_processed"] = state.get("batches_processed", 0) + 1
    save_state(state)

    elapsed_total = time.time() - start_time
    logger.info("-" * 40)
    logger.info(f"Done in {elapsed_total:.0f}s ({elapsed_total / 60:.1f} min)")
    logger.info(f"Completed: {stats['completed']}, Skipped: {stats['skipped']}, Failed: {stats['failed']}")
    if stats["rate_limited"]:
        logger.info(f"Rate limited: {stats['rate_limited']} times")

    show_status(state)


if __name__ == "__main__":
    main()
