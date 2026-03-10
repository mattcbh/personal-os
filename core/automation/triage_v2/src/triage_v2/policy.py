from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import json
import os
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[5]
DEFAULT_POLICY_PATH = ROOT / "core" / "automation" / "triage_v2" / "policy.json"

DEFAULT_PRIORITY_HIGH_HINTS = {
    "gilli": 12000,
    "brown bag": 12000,
    "m&a": 12000,
    "acquisition": 10000,
    "dagmara": 9000,
    "abraham": 9000,
    "park slope": 3200,
    "pies dos": 3200,
    "pies n thighs": 3000,
    "security av/it": 3000,
    "authorization for final accessories": 3000,
    "wi-fi park slope": 2800,
    "jason hershfeld": 1800,
    "pnt_": 1600,
    "pnt": 900,
}

DEFAULT_PRIORITY_LOW_HINTS = {
    "accepted:": -700,
    "google meet": -600,
    "meet.google.com": -600,
    "creditwise": -500,
    "linkedin": -450,
    "cora briefs": -400,
    "new text message from": -400,
    "sms": -350,
    "newsletter": -350,
}

DEFAULT_PRIORITY_BUCKET_BONUS = {
    "Action Needed": 2000,
    "Monitoring": 1200,
    "Already Addressed": 700,
}

DEFAULT_PRIORITY_DOMAIN_BONUS = {
    "@cornerboothholdings.com": 120,
    "@heapsicecream.com": 90,
}

DEFAULT_AUTOMATED_SENDER_HINTS = (
    "noreply",
    "no-reply",
    "notification",
    "notifications",
    "account-services",
    "inform.bill",
    "toasttab",
    "linkedin",
    "capitalone",
)

DEFAULT_COURTESY_BLOCK_HINTS = (
    "invoice",
    "payment",
    "subscription",
    "confirmation",
    "receipt",
    "payroll",
    "statement",
    "review",
    "billing",
)

DEFAULT_SYSTEM_ALERT_SPAM_KEYWORDS = (
    "new text message from",
    "never share your",
    "verification code",
    "2fa",
    "google voice",
    "sign in alert",
)

DEFAULT_SENDER_BUCKET_OVERRIDES = {
    "cora briefs": "Newsletters",
    "@ramp.com": "FYI",
    "linkedin": "Spam / Marketing",
    "amazon": "Spam / Marketing",
    "compass": "Spam / Marketing",
    "pef": "Spam / Marketing",
    "double good": "Spam / Marketing",
    "grubhub": "Spam / Marketing",
    "square": "Spam / Marketing",
}

DEFAULT_EDITORIAL_SENDER_HINTS = (
    "on my om",
    "om malik",
    "casey newton",
    "platformer",
    "matt levine",
    "money stuff",
    "one great story",
    "new york mag",
    "new york magazine",
)

DEFAULT_OPERATIONAL_FYI_SENDER_HINTS = (
    "mail delivery subsystem",
    "mailer-daemon",
    "google business profile",
    "owner.com",
)

DEFAULT_PROMOTIONAL_SENDER_HINTS = (
    "linkedin",
    "amazon",
    "compass",
    "pef",
    "double good",
    "grubhub",
    "square",
)

DEFAULT_NEWSLETTER_SENDER_PRIORITY = (
    "cora briefs",
    "on my om",
    "om malik",
    "casey newton",
    "platformer",
    "matt levine",
    "money stuff",
    "one great story",
    "new york mag",
    "new york magazine",
)


@dataclass(frozen=True)
class TriagePolicy:
    priority_high_hints: dict[str, int]
    priority_low_hints: dict[str, int]
    priority_bucket_bonus: dict[str, int]
    priority_domain_bonus: dict[str, int]
    automated_sender_hints: tuple[str, ...]
    courtesy_block_hints: tuple[str, ...]
    system_alert_spam_keywords: tuple[str, ...]
    sender_bucket_overrides: dict[str, str]
    editorial_sender_hints: tuple[str, ...]
    operational_fyi_sender_hints: tuple[str, ...]
    promotional_sender_hints: tuple[str, ...]
    newsletter_sender_priority: tuple[str, ...]


def _merge_int_dict(raw: Any, defaults: dict[str, int]) -> dict[str, int]:
    merged = {str(key).strip().lower(): int(value) for key, value in defaults.items()}
    if not isinstance(raw, dict):
        return merged
    for key, value in raw.items():
        try:
            text_key = str(key).strip().lower()
            if not text_key:
                continue
            merged[text_key] = int(value)
        except Exception:
            continue
    return merged


def _merge_text_list(raw: Any, defaults: tuple[str, ...]) -> tuple[str, ...]:
    values = [item.lower() for item in defaults]
    seen = {item for item in values}
    if not isinstance(raw, list):
        return tuple(values)
    for item in raw:
        text = str(item).strip().lower()
        if not text or text in seen:
            continue
        values.append(text)
        seen.add(text)
    return tuple(values)


def _merge_bucket_overrides(raw: Any, defaults: dict[str, str]) -> dict[str, str]:
    merged = {str(key).strip().lower(): str(value).strip() for key, value in defaults.items()}
    if not isinstance(raw, dict):
        return merged
    for key, value in raw.items():
        text_key = str(key).strip().lower()
        text_value = str(value).strip()
        if not text_key or not text_value:
            continue
        merged[text_key] = text_value
    return merged


@lru_cache(maxsize=1)
def load_policy() -> TriagePolicy:
    path = Path(os.environ.get("TRIAGE_V2_POLICY_FILE", str(DEFAULT_POLICY_PATH))).expanduser().resolve()
    data: dict[str, Any] = {}
    if path.exists():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                data = raw
        except Exception:
            data = {}

    priority = data.get("priority", {})
    draft = data.get("draft", {})
    classification = data.get("classification", {})
    render = data.get("render", {})

    return TriagePolicy(
        priority_high_hints=_merge_int_dict(priority.get("high_hints"), DEFAULT_PRIORITY_HIGH_HINTS),
        priority_low_hints=_merge_int_dict(priority.get("low_hints"), DEFAULT_PRIORITY_LOW_HINTS),
        priority_bucket_bonus=_merge_int_dict(priority.get("bucket_bonus"), DEFAULT_PRIORITY_BUCKET_BONUS),
        priority_domain_bonus=_merge_int_dict(priority.get("domain_bonus"), DEFAULT_PRIORITY_DOMAIN_BONUS),
        automated_sender_hints=_merge_text_list(draft.get("automated_sender_hints"), DEFAULT_AUTOMATED_SENDER_HINTS),
        courtesy_block_hints=_merge_text_list(draft.get("courtesy_block_hints"), DEFAULT_COURTESY_BLOCK_HINTS),
        system_alert_spam_keywords=_merge_text_list(
            classification.get("system_alert_spam_keywords"),
            DEFAULT_SYSTEM_ALERT_SPAM_KEYWORDS,
        ),
        sender_bucket_overrides=_merge_bucket_overrides(
            classification.get("sender_bucket_overrides"),
            DEFAULT_SENDER_BUCKET_OVERRIDES,
        ),
        editorial_sender_hints=_merge_text_list(
            classification.get("editorial_sender_hints"),
            DEFAULT_EDITORIAL_SENDER_HINTS,
        ),
        operational_fyi_sender_hints=_merge_text_list(
            classification.get("operational_fyi_sender_hints"),
            DEFAULT_OPERATIONAL_FYI_SENDER_HINTS,
        ),
        promotional_sender_hints=_merge_text_list(
            classification.get("promotional_sender_hints"),
            DEFAULT_PROMOTIONAL_SENDER_HINTS,
        ),
        newsletter_sender_priority=_merge_text_list(
            render.get("newsletter_sender_priority"),
            DEFAULT_NEWSLETTER_SENDER_PRIORITY,
        ),
    )
