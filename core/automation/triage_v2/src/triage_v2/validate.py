from __future__ import annotations

import re
from typing import NamedTuple

from triage_v2.types import SECTION_ORDER, ThreadRecord


THREAD_URL_RE = re.compile(r"^https://mail\.superhuman\.com/[^/\s]+/thread/[^/\s]+$")
GMAIL_DRAFT_URL_RE = re.compile(r"^https://mail\.google\.com/mail/u/[^/\s]+/#drafts\?compose=[^&\s]+$")


class ValidationResult(NamedTuple):
    ok: bool
    errors: list[str]


def validate_threads(threads: list[ThreadRecord]) -> ValidationResult:
    errors: list[str] = []
    seen_keys: set[str] = set()

    for item in threads:
        key = f"{item.account}:{item.thread_id}"
        if key in seen_keys:
            errors.append(f"Duplicate thread key: {key}")
        seen_keys.add(key)

        if item.bucket not in SECTION_ORDER:
            errors.append(f"Unsupported bucket '{item.bucket}' for {key}")

        if not item.message_ids:
            errors.append(f"Thread {key} has no message IDs")

        if not str(item.summary_latest or "").strip():
            errors.append(f"Thread {key} is missing summary text")

        if item.response_needed and not str(item.suggested_response or "").strip():
            errors.append(f"Thread {key} needs a response but has no suggested response")

        if item.bucket == "Already Addressed":
            if str(item.suggested_action or "").strip():
                errors.append(f"Thread {key} is already addressed but still has suggested action text")
            if str(item.operational_note or "").strip():
                errors.append(f"Thread {key} is already addressed but still has operational note text")

        if item.bucket == "FYI" and str(item.suggested_action or "").strip():
            errors.append(f"Thread {key} is FYI but still has next-step action text")

        if not THREAD_URL_RE.match(item.thread_url):
            errors.append(f"Malformed Superhuman thread URL for {key}: {item.thread_url}")

        if item.draft_status == "fallback_gmail":
            if not item.draft_url or not GMAIL_DRAFT_URL_RE.match(item.draft_url):
                errors.append(f"Invalid Gmail fallback draft URL for {key}")

    return ValidationResult(ok=not errors, errors=errors)
