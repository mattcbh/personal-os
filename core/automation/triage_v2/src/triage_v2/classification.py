from __future__ import annotations

from collections import defaultdict
import html
import re
from typing import Iterable

from triage_v2.policy import load_policy
from triage_v2.sender_policy import match_sender_policy
from triage_v2.types import Bucket, MessageRecord, ThreadRecord


ACTION_KEYWORDS = (
    "can you",
    "could you",
    "would you",
    "please confirm",
    "please review",
    "please approve",
    "please sign",
    "please send",
    "action required",
    "needs your",
    "requires your action",
    "let me know",
    "what works",
    "are you free",
    "rsvp by",
    "response required",
)

MONITORING_KEYWORDS = (
    "for visibility",
    "fyi - tracking",
    "monitor",
)

SPAM_KEYWORDS = (
    "buy now",
    "limited-time",
    "discount",
    "promotion",
    "sponsored",
    "pending connection invitations",
    "birthday nudge",
    "saved search",
    "new listings",
    "leave a product review",
    "first-time user",
    "special offer",
    "sale ends",
)

NEWSLETTER_KEYWORDS = (
    "newsletter",
    "digest",
    "daily brief",
    "substack",
    "one great story",
    "money stuff",
)

COURTESY_KEYWORDS = (
    "thank you",
    "great to connect",
    "nice to meet",
)


_ws_re = re.compile(r"\s+")
_invisible_re = re.compile(r"[\u034f\u200b-\u200f\u2060\ufeff]+")
_url_re = re.compile(r"https?://\S+")
_phone_re = re.compile(r"(?:\+?\d[\d().\-\s]{7,}\d)")
_pin_re = re.compile(r"\bpin[:\s#-]*\d{3,}\b", re.IGNORECASE)
POLICY = load_policy()
GOOGLE_COLLABORATION_HINTS = (
    "share request",
    "document shared with you",
    "shared a document",
    "requesting access",
    "is requesting access",
    "added a comment",
    "commented on",
    "invited you to edit",
    "invited you to view",
    "invited you to comment",
)


def clean_subject(text: str) -> str:
    value = html.unescape(text or "")
    value = _invisible_re.sub(" ", value)
    value = _ws_re.sub(" ", value).strip()
    return value


def normalize_text(text: str) -> str:
    value = html.unescape(text or "")
    value = _invisible_re.sub(" ", value)
    value = _url_re.sub("", value)
    value = _phone_re.sub("", value)
    value = _pin_re.sub("", value)

    low = value.lower()
    for marker in (
        "join with google meet",
        "join by phone",
        "more phone numbers",
        "to respond to this message",
        "view options",
        "get outlook for ios",
    ):
        idx = low.find(marker)
        if idx >= 48:
            value = value[:idx]
            low = value.lower()
            break

    for marker in (" from: ", " sent from my iphone", " on wed, ", " on thu, "):
        idx = low.find(marker)
        if idx >= 80:
            value = value[:idx]
            break

    value = _ws_re.sub(" ", value).strip(" -|;,:")
    return value


def compress(text: str, limit: int = 240) -> str:
    clean = normalize_text(text)
    if len(clean) <= limit:
        return clean
    clipped = clean[: limit - 3].rstrip()
    if " " in clipped:
        clipped = clipped.rsplit(" ", 1)[0]
    return clipped + "..."


def has_keyword(text: str, words: Iterable[str]) -> bool:
    low = (text or "").lower()
    return any(word in low for word in words)


def _sender_blob(message: MessageRecord) -> str:
    return f"{message.sender_name} {message.sender_email}".lower()


def _content_blob(message: MessageRecord) -> str:
    subject = clean_subject(message.subject)
    snippet = normalize_text(message.snippet)
    body_preview = normalize_text(message.body_preview)
    return f"{subject}\n{snippet}\n{body_preview}".lower()


def _sender_override_bucket(message: MessageRecord) -> str | None:
    sender_blob = _sender_blob(message)
    for hint, bucket in POLICY.sender_bucket_overrides.items():
        if hint in sender_blob:
            return bucket
    return None


def _subject_override_bucket(message: MessageRecord) -> str | None:
    subject = clean_subject(message.subject).lower()
    if not subject:
        return None
    return POLICY.subject_bucket_overrides.get(subject)


def _matches_sender_hints(message: MessageRecord, hints: Iterable[str]) -> bool:
    sender_blob = _sender_blob(message)
    return any(hint in sender_blob for hint in hints)


def _looks_cold_pitch(text: str) -> bool:
    contact_form = "contact form" in text or "website contact us" in text
    salesy = any(
        hint in text
        for hint in (
            "would love to help",
            "we can help",
            "custom pet cups",
            "3-week turnaround",
            "increase sales",
            "promoting",
            "introductory offer",
            "reach out because",
            "thought you'd be the right person",
        )
    )
    return contact_form or salesy


def _looks_operational_alert(text: str, sender_blob: str) -> bool:
    if any(hint in sender_blob for hint in POLICY.operational_fyi_sender_hints):
        return True
    return any(
        hint in text
        for hint in (
            "ownership invitation",
            "memo and receipt",
            "delivery status notification",
            "message could not be delivered",
            "subscription required",
            "transaction declined",
        )
    )


def _looks_automated_sender(message: MessageRecord) -> bool:
    sender_blob = _sender_blob(message)
    return bool(message.list_unsubscribe) or any(hint in sender_blob for hint in POLICY.automated_sender_hints)


def _looks_human_sender(message: MessageRecord) -> bool:
    sender_blob = _sender_blob(message)
    if bool(message.list_unsubscribe):
        return False
    return not any(hint in sender_blob for hint in POLICY.automated_sender_hints)


def _looks_unknown_substack_newsletter(message: MessageRecord) -> bool:
    sender_email = (message.sender_email or "").strip().lower()
    sender_blob = _sender_blob(message)
    return sender_email.endswith("@substack.com") or " substack" in sender_blob


def _has_explicit_action_request(text: str) -> bool:
    if has_keyword(text, ACTION_KEYWORDS):
        return True
    return "?" in text and not _looks_purely_informational_question(text)


def _looks_purely_informational_question(text: str) -> bool:
    return any(hint in text for hint in ("would you like to shop", "looking for deals", "you can get"))


def _looks_feedback_survey(message: MessageRecord, text: str) -> bool:
    sender_blob = _sender_blob(message)
    subject = clean_subject(message.subject).lower()
    blob = f"{sender_blob}\n{subject}\n{text}"
    if not any(keyword in blob for keyword in POLICY.feedback_survey_keywords):
        return False

    automated_sender = _looks_automated_sender(message)
    explicit_sender = any(hint in sender_blob for hint in POLICY.feedback_survey_sender_hints)
    return automated_sender or explicit_sender


def _looks_internal_collaboration_notification(message: MessageRecord, text: str) -> bool:
    sender_blob = _sender_blob(message)
    blob = f"{sender_blob}\n{text}"
    google_notification = any(
        hint in blob
        for hint in (
            "google drive",
            "google docs",
            "docs.google.com",
            "drive-shares-dm-noreply@google.com",
            "comments-noreply@docs.google.com",
        )
    )
    collaboration_event = any(hint in blob for hint in GOOGLE_COLLABORATION_HINTS)
    internal_actor = any(domain in blob for domain in POLICY.internal_collaboration_domains)
    return google_notification and collaboration_event and internal_actor


def thread_url(account_email: str, thread_id: str) -> str:
    return f"https://mail.superhuman.com/{account_email}/thread/{thread_id}"


def classify_bucket(message: MessageRecord) -> str:
    sender_policy = match_sender_policy(message.sender_email, message.sender_name)
    sender_blob = _sender_blob(message)
    text = _content_blob(message)

    subject_override_bucket = _subject_override_bucket(message)
    if subject_override_bucket:
        return subject_override_bucket

    override_bucket = _sender_override_bucket(message)
    if override_bucket:
        return override_bucket

    if sender_policy.default_bucket == Bucket.NEWSLETTERS.value:
        return Bucket.NEWSLETTERS.value

    if _matches_sender_hints(message, POLICY.editorial_sender_hints) or _looks_unknown_substack_newsletter(message):
        return Bucket.NEWSLETTERS.value

    if _looks_internal_collaboration_notification(message, text):
        return Bucket.FYI.value

    if _looks_feedback_survey(message, text):
        return Bucket.SPAM_MARKETING.value

    if sender_policy.default_bucket == Bucket.FYI.value and sender_policy.sender_kind in {"vendor", "internal", "personal"}:
        if bool(message.metadata.get("monitor")) or has_keyword(text, MONITORING_KEYWORDS):
            return Bucket.MONITORING.value
        if _has_explicit_action_request(text):
            return Bucket.ACTION_NEEDED.value
        return Bucket.FYI.value

    if _matches_sender_hints(message, POLICY.operational_fyi_sender_hints) and not has_keyword(text, ACTION_KEYWORDS):
        return Bucket.FYI.value

    if has_keyword(text, POLICY.system_alert_spam_keywords) and (
        "2fa" in sender_blob or "google voice" in sender_blob or "security" in sender_blob
    ):
        return Bucket.SPAM_MARKETING.value

    if (
        (bool(message.metadata.get("is_spam")) and not sender_policy.never_spam)
        or has_keyword(text, SPAM_KEYWORDS)
        or _matches_sender_hints(message, POLICY.promotional_sender_hints)
        or _looks_cold_pitch(text)
    ):
        return Bucket.SPAM_MARKETING.value

    if has_keyword(f"{sender_blob}\n{text}", NEWSLETTER_KEYWORDS):
        return Bucket.NEWSLETTERS.value

    if _has_explicit_action_request(text):
        return Bucket.ACTION_NEEDED.value

    if bool(message.metadata.get("monitor")) or has_keyword(text, MONITORING_KEYWORDS):
        return Bucket.MONITORING.value

    if _looks_operational_alert(text, sender_blob):
        return Bucket.FYI.value

    if _looks_automated_sender(message) and not sender_policy.never_spam:
        return Bucket.SPAM_MARKETING.value

    if sender_policy.default_bucket:
        return sender_policy.default_bucket

    return Bucket.FYI.value


def suggested_action(message: MessageRecord) -> str:
    subject = compress(clean_subject(message.subject), limit=120)
    text = f"{clean_subject(message.subject)}\n{normalize_text(message.snippet)}\n{normalize_text(message.body_preview)}".lower()

    if any(k in text for k in ("invoice", "quote", "change order", "co#", "estimate", "ea#")):
        return f"Review {subject} and confirm approval and payment timing."
    if any(k in text for k in ("contract", "agreement", "terms", "signature", "sign")):
        return f"Review {subject} and reply with approval or requested edits."
    if any(k in text for k in ("meeting", "call", "zoom", "availability", "schedule", "tomorrow", "7am")):
        return f"Reply on {subject} with confirmed timing and owner."
    if any(k in text for k in ("deadline", "due", "asap", "urgent", "follow up", "reminder")):
        return f"Reply on {subject} with committed timeline and next action."
    if "approve" in text or "approval" in text:
        return f"Review {subject} and approve or decline today."
    return f"Reply on {subject} with concrete next steps."


def needs_draft(bucket: str, message: MessageRecord) -> bool:
    if bucket == Bucket.ACTION_NEEDED.value:
        return True
    if bucket == Bucket.FYI.value:
        sender = (message.sender_email or "").lower()
        if any(hint in sender for hint in POLICY.automated_sender_hints):
            return False
        text = f"{normalize_text(message.subject)} {normalize_text(message.snippet)}".lower()
        if any(hint in text for hint in POLICY.courtesy_block_hints):
            return False
        return has_keyword(text, COURTESY_KEYWORDS)
    return False


def group_to_threads(
    *,
    messages: list[MessageRecord],
    work_account_email: str,
    personal_account_email: str,
) -> list[ThreadRecord]:
    grouped: dict[tuple[str, str], list[MessageRecord]] = defaultdict(list)
    for msg in messages:
        grouped[(msg.account, msg.thread_id)].append(msg)

    out: list[ThreadRecord] = []
    for (account, thread_id), items in grouped.items():
        ordered = sorted(items, key=lambda x: x.received_at)
        latest = ordered[-1]
        bucket = classify_bucket(latest)

        account_email = work_account_email if account == "work" else personal_account_email
        unsub = latest.list_unsubscribe if bucket in {Bucket.NEWSLETTERS.value, Bucket.SPAM_MARKETING.value} else None

        monitoring_owner = ""
        monitoring_deliverable = ""
        monitoring_deadline = ""
        if bucket == Bucket.MONITORING.value:
            monitoring_owner = latest.metadata.get("monitoring_owner", "TBD")
            monitoring_deliverable = latest.metadata.get("monitoring_deliverable", latest.subject)
            monitoring_deadline = latest.metadata.get("monitoring_deadline", "Next business day")

        thread = ThreadRecord(
            account=account,
            thread_id=thread_id,
            message_ids=[m.message_id for m in ordered],
            sender_email=latest.sender_email,
            sender_name=latest.sender_name,
            subject_latest=clean_subject(latest.subject) or "(no subject)",
            summary_latest=compress(latest.snippet or latest.body_preview or latest.subject),
            bucket=bucket,
            suggested_action=suggested_action(latest) if bucket == Bucket.ACTION_NEEDED.value else "",
            monitoring_owner=str(monitoring_owner),
            monitoring_deliverable=str(monitoring_deliverable),
            monitoring_deadline=str(monitoring_deadline),
            draft_status="not_needed",
            thread_url=thread_url(account_email, thread_id),
            draft_url=None,
            unsubscribe_url=unsub,
            accounted_reason="included",
        )
        out.append(thread)

    out.sort(key=lambda t: (t.bucket, t.account, t.thread_id))
    return out
