from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any

from triage_v2.classification import clean_subject, normalize_text
from triage_v2.config import AppConfig
from triage_v2.context_pack import extract_top_priorities, sender_context_snippets
from triage_v2.llm_client import ClaudeCliJsonClient, LlmClientError
from triage_v2.project_context import ProjectBrief, build_project_excerpt
from triage_v2.types import Bucket, MessageRecord, ThreadMessage, ThreadRecord


ENRICHMENT_BATCH_SIZE = 4
SUMMARY_LIMIT = 220
RESPONSE_LIMIT = 220
ACTION_LIMIT = 180
BODY_LIMIT = 1500
THREAD_HISTORY_LIMIT = 2200
PROJECT_LIMIT = 1800
SENDER_CONTEXT_LIMIT = 5
REASSIGNABLE_BUCKETS = {
    Bucket.ACTION_NEEDED.value,
    Bucket.FYI.value,
    Bucket.MONITORING.value,
}
HARD_GUARD_BUCKETS = {
    Bucket.ALREADY_ADDRESSED.value,
    Bucket.MONITORING.value,
    Bucket.NEWSLETTERS.value,
    Bucket.SPAM_MARKETING.value,
}
ALLOWED_BUCKET_HINTS = {bucket.value for bucket in Bucket}
AUTOMATED_HINTS = (
    "noreply",
    "no-reply",
    "notification",
    "notifications",
    "mailer-daemon",
    "donotreply",
    "do-not-reply",
)
DOCUMENT_HINTS = (
    "invoice",
    "change order",
    "ea#",
    "estimate",
    "quote",
    "proposal",
    "bill",
    "contract",
    "agreement",
    "terms",
    "signature",
    "sign",
    "approve",
    "approval",
)
SCHEDULING_HINTS = (
    "coffee",
    "call",
    "availability",
    "schedule",
    "find time",
    "grab lunch",
    "grab coffee",
    "next week",
    "send some times",
    "what works",
    "free early next week",
    "pretty free",
)
NO_RESPONSE_HINTS = (
    "payment confirmation",
    "receipt",
    "delivered",
    "shipped",
    "on the way",
    "arriving tomorrow",
    "order confirmed",
    "security alert",
    "transaction report",
    "report card",
    "available online",
    "daily transaction report",
)
SUMMARY_STOPLINES = (
    "view this email in your browser",
    "manage notifications",
    "unsubscribe",
    "view in browser",
    "shop men women sale",
    "get 10% cash back",
)


@dataclass(frozen=True)
class EnrichmentInput:
    item: ThreadRecord
    latest_message: MessageRecord
    thread_messages: list[ThreadMessage]
    project: ProjectBrief | None

    @property
    def key(self) -> str:
        return f"{self.item.account}:{self.item.thread_id}"


@dataclass(frozen=True)
class ThreadEnrichment:
    summary_latest: str
    response_needed: bool
    suggested_response: str
    suggested_action: str
    bucket_hint: str


def enrich_threads(cfg: AppConfig, items: list[EnrichmentInput]) -> dict[str, ThreadEnrichment]:
    fallbacks = {item.key: deterministic_enrichment(item) for item in items}
    if not items or not cfg.claude_path.exists():
        return fallbacks

    client = ClaudeCliJsonClient(
        binary_path=cfg.claude_path,
        model=cfg.draft_authoring_model,
        timeout_seconds=max(cfg.draft_authoring_timeout_seconds, 90),
    )
    merged = dict(fallbacks)

    for start in range(0, len(items), ENRICHMENT_BATCH_SIZE):
        batch = items[start : start + ENRICHMENT_BATCH_SIZE]
        try:
            raw = _author_llm_batch(client=client, cfg=cfg, batch=batch)
        except Exception:
            continue
        if not isinstance(raw, list):
            continue
        for item in batch:
            parsed = _parse_llm_result(raw, key=item.key, fallback=fallbacks[item.key], item=item.item)
            merged[item.key] = parsed
    return merged


def deterministic_enrichment(item: EnrichmentInput) -> ThreadEnrichment:
    sender = _sender_label(item.item.sender_name, item.item.sender_email)
    subject = clean_subject(item.latest_message.subject) or item.item.subject_latest
    latest_body = _latest_visible_text(item.latest_message, item.thread_messages)
    text = normalize_text("\n".join(filter(None, [subject, item.latest_message.snippet, latest_body])))
    lowered = text.lower()
    directed_to_other_person = _appears_directed_to_other_person(latest_body)

    response_needed = _response_needed(
        bucket=item.item.bucket,
        sender_email=item.item.sender_email,
        subject=subject,
        text=lowered,
        latest_body=latest_body,
    )
    bucket_hint = item.item.bucket
    if item.item.bucket not in HARD_GUARD_BUCKETS:
        if directed_to_other_person and _monitoring_followup_needed(subject, lowered):
            response_needed = False
            bucket_hint = Bucket.MONITORING.value
        elif directed_to_other_person and _strong_action_signal(subject, lowered):
            response_needed = False
            bucket_hint = Bucket.FYI.value
        elif item.item.bucket == Bucket.ACTION_NEEDED.value and not response_needed:
            bucket_hint = Bucket.FYI.value
        elif item.item.bucket == Bucket.FYI.value and response_needed and _strong_action_signal(subject, lowered):
            bucket_hint = Bucket.ACTION_NEEDED.value
        elif item.item.bucket == Bucket.ACTION_NEEDED.value and _monitoring_followup_needed(subject, lowered):
            bucket_hint = Bucket.MONITORING.value

    summary = _deterministic_summary(
        sender=sender,
        sender_email=item.item.sender_email,
        subject=subject,
        latest_body=latest_body,
        text=lowered,
        bucket=item.item.bucket,
    )
    suggested_action = _deterministic_action(
        sender=sender,
        subject=subject,
        text=lowered,
        response_needed=response_needed,
        project=item.project,
        bucket=bucket_hint,
        directed_to_other_person=directed_to_other_person,
    )
    suggested_response = _deterministic_response(
        sender=sender,
        subject=subject,
        text=lowered,
        response_needed=response_needed,
        suggested_action=suggested_action,
        bucket=bucket_hint,
        directed_to_other_person=directed_to_other_person,
    )

    return ThreadEnrichment(
        summary_latest=_ensure_sender_in_summary(summary, item.item),
        response_needed=response_needed,
        suggested_response=suggested_response,
        suggested_action=suggested_action,
        bucket_hint=bucket_hint,
    )


def apply_bucket_hint(current_bucket: str, enrichment: ThreadEnrichment) -> str:
    if current_bucket in HARD_GUARD_BUCKETS:
        return current_bucket
    if enrichment.bucket_hint in REASSIGNABLE_BUCKETS:
        return enrichment.bucket_hint
    return current_bucket


def _author_llm_batch(
    *,
    client: ClaudeCliJsonClient,
    cfg: AppConfig,
    batch: list[EnrichmentInput],
) -> list[dict[str, Any]]:
    prompt = _build_enrichment_prompt(cfg=cfg, batch=batch)
    data = client.generate_json(
        prompt=prompt,
        system_prompt=(
            "You are Matt Lieber's chief of staff triaging email. "
            "Return a single JSON object only. Do not include markdown fences or commentary."
        ),
    )
    threads = data.get("threads")
    if not isinstance(threads, list):
        raise LlmClientError("threads missing from enrichment response")
    return [row for row in threads if isinstance(row, dict)]


def _build_enrichment_prompt(*, cfg: AppConfig, batch: list[EnrichmentInput]) -> str:
    priorities = extract_top_priorities(cfg.goals_path)
    payload = []
    for row in batch:
        payload.append(
            {
                "key": row.key,
                "account": row.item.account,
                "current_bucket": row.item.bucket,
                "sender": _sender_label(row.item.sender_name, row.item.sender_email),
                "sender_email": row.item.sender_email,
                "subject": row.item.subject_latest,
                "latest_message": _truncate(_latest_visible_text(row.latest_message, row.thread_messages), BODY_LIMIT),
                "recent_thread": _thread_history_excerpt(row.thread_messages),
                "sender_context": sender_context_snippets(
                    sender_email=row.item.sender_email,
                    sender_name=row.item.sender_name,
                    people_path=cfg.people_path,
                    email_contacts_path=cfg.email_contacts_path,
                    limit=SENDER_CONTEXT_LIMIT,
                ),
                "project_context": _truncate(build_project_excerpt(row.project), PROJECT_LIMIT) if row.project else "",
                "fallback_summary": deterministic_enrichment(row).summary_latest,
            }
        )

    lines = [
        "For each thread, return JSON only in this shape:",
        '{"threads":[{"key":"work:abc","summary_latest":"...","response_needed":true,"suggested_response":"...","suggested_action":"...","bucket_hint":"FYI"}]}',
        "",
        "Rules:",
        "- summary_latest must be one sentence, plain English, max 220 characters.",
        "- summary_latest must explicitly include the sender or brand name.",
        "- Write what the email means to Matt, not baity subject-line copy.",
        "- response_needed is true only when Matt should actually reply by email.",
        "- If the latest message is addressed to someone else (for example 'Hi Jack'), response_needed must be false.",
        "- suggested_response is a one-sentence recommendation for what Matt should send. Leave empty only when response_needed is false.",
        "- suggested_action is the operational next step, grounded in the email and context. Use it even when no email reply should be drafted.",
        "- bucket_hint must be one of: Action Needed, FYI, Already Addressed, Monitoring, Newsletters, Spam / Marketing.",
        "- Do not invent meetings, approvals, or facts that are not in the thread/context.",
        "- If an email is purely confirmational, transactional, or informational, prefer response_needed false and bucket_hint FYI.",
        "",
        "Top priorities:",
    ]
    if priorities:
        lines.extend(f"- {item}" for item in priorities)
    else:
        lines.append("- None available.")
    lines.extend(["", "Threads:", json.dumps(payload, ensure_ascii=True, indent=2)])
    return "\n".join(lines)


def _parse_llm_result(
    rows: list[dict[str, Any]],
    *,
    key: str,
    fallback: ThreadEnrichment,
    item: ThreadRecord,
) -> ThreadEnrichment:
    for row in rows:
        if str(row.get("key") or "").strip() != key:
            continue
        summary = _clean_text(str(row.get("summary_latest") or row.get("summary") or fallback.summary_latest), SUMMARY_LIMIT)
        if not summary:
            summary = fallback.summary_latest
        summary = _ensure_sender_in_summary(summary, item)
        response_needed = _coerce_bool(row.get("response_needed"), fallback.response_needed)
        raw_response = str(row.get("suggested_response") or (fallback.suggested_response if response_needed else ""))
        suggested_response = _clean_text(raw_response, RESPONSE_LIMIT)
        raw_action = str(row.get("suggested_action") or fallback.suggested_action)
        suggested_action = _clean_text(raw_action, ACTION_LIMIT)
        bucket_hint = str(row.get("bucket_hint") or fallback.bucket_hint).strip()
        if bucket_hint not in ALLOWED_BUCKET_HINTS:
            bucket_hint = fallback.bucket_hint
        if response_needed and not suggested_response:
            suggested_response = fallback.suggested_response
        if not response_needed:
            suggested_response = ""
        return ThreadEnrichment(
            summary_latest=summary,
            response_needed=response_needed,
            suggested_response=suggested_response,
            suggested_action=suggested_action,
            bucket_hint=bucket_hint,
        )
    return fallback


def _sender_label(sender_name: str, sender_email: str) -> str:
    cleaned = " ".join((sender_name or "").split()).strip().strip('"')
    if cleaned and "@" not in cleaned:
        return cleaned
    email = (sender_email or "").strip().lower()
    if "@" not in email:
        return "Unknown sender"
    domain = email.split("@", 1)[1]
    primary = domain.split(".")[0]
    if primary in {"mail", "email", "news", "info", "support", "notifications", "no-reply"} and "." in domain:
        primary = domain.split(".")[1]
    primary = primary.replace("-", " ").replace("_", " ").strip()
    return " ".join(part.capitalize() for part in primary.split()) or email


def _latest_visible_text(message: MessageRecord, thread_messages: list[ThreadMessage]) -> str:
    if thread_messages:
        latest = sorted(thread_messages, key=lambda row: row.received_at)[-1]
        if latest.body_text:
            return _clean_body(latest.body_text)
    return _clean_body(message.body_preview or message.snippet or message.subject)


def _thread_history_excerpt(thread_messages: list[ThreadMessage]) -> str:
    if not thread_messages:
        return ""
    ordered = sorted(thread_messages, key=lambda row: row.received_at)[-4:]
    parts = []
    for row in ordered:
        body = _truncate(_clean_body(row.body_text), 500)
        if not body:
            continue
        parts.append(
            "\n".join(
                [
                    f"From: {_sender_label(row.sender_name, row.sender_email)} <{row.sender_email}>",
                    f"Subject: {clean_subject(row.subject)}",
                    f"Body: {body}",
                ]
            )
        )
    return _truncate("\n\n---\n\n".join(parts), THREAD_HISTORY_LIMIT)


def _clean_body(text: str) -> str:
    lines = []
    for raw_line in (text or "").replace("\r\n", "\n").replace("\r", "\n").splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue
        lowered = stripped.lower()
        if stripped.startswith(">"):
            continue
        if lowered.startswith("on ") and lowered.endswith(" wrote:"):
            break
        if lowered.startswith("from:") and lines:
            break
        if any(marker in lowered for marker in SUMMARY_STOPLINES):
            break
        lines.append(stripped)
    return normalize_text(" ".join(lines))


def _appears_directed_to_other_person(latest_body: str) -> bool:
    text = (latest_body or "").strip().lower()
    if not text:
        return False
    if text.startswith(("hi matt", "matt,", "matt -", "matt ", "matthew,", "hi matthew")):
        return False
    return bool(
        re.match(
            r"^(hi|hello|hey|good morning|good afternoon|good evening)\s+[a-z][a-z.'-]+[,!:]",
            text,
        )
        or re.match(r"^[a-z][a-z.'-]+[,!:]", text)
    )


def _monitoring_followup_needed(subject: str, text: str) -> bool:
    blob = f"{subject.lower()}\n{text}"
    return any(
        hint in blob
        for hint in (
            "blocked",
            "blocker",
            "stalled",
            "stalling",
            "subscription required",
            "before opening",
            "opening day",
            "ahead of the",
            "ownership invitation",
            "awaiting acceptance",
        )
    )


def _offline_or_operational_action(subject: str, text: str) -> bool:
    blob = f"{subject.lower()}\n{text}"
    return any(
        hint in blob
        for hint in (
            "transaction declined",
            "memo and receipt",
            "ownership invitation",
            "log into",
            "accept the",
            "review and sign",
            "wire",
            "capital call",
            "vote now",
            "subscription required",
        )
    )


def _response_needed(*, bucket: str, sender_email: str, subject: str, text: str, latest_body: str) -> bool:
    if bucket in HARD_GUARD_BUCKETS:
        return False
    if _looks_transactional(subject, text, sender_email):
        return False
    if _appears_directed_to_other_person(latest_body):
        return False
    if _has_explicit_ask(text):
        return True
    if _has_document_action(subject, text):
        return True
    if _has_scheduling_followup(text):
        return True
    return False


def _has_explicit_ask(text: str) -> bool:
    prompts = (
        "let me know",
        "can you",
        "could you",
        "would you",
        "please confirm",
        "please approve",
        "please review",
        "needs your",
        "requires your action",
        "what works",
        "are you free",
        "do you want",
        "i look forward to hearing from you",
    )
    if any(prompt in text for prompt in prompts):
        return True
    return "?" in text and not _looks_purely_informational_question(text)


def _looks_purely_informational_question(text: str) -> bool:
    return any(hint in text for hint in ("you can get", "would you like to shop", "looking for deals"))


def _has_document_action(subject: str, text: str) -> bool:
    blob = f"{subject.lower()}\n{text}"
    return any(hint in blob for hint in DOCUMENT_HINTS)


def _has_scheduling_followup(text: str) -> bool:
    return any(hint in text for hint in SCHEDULING_HINTS)


def _strong_action_signal(subject: str, text: str) -> bool:
    return _has_document_action(subject, text) or _has_scheduling_followup(text) or _has_explicit_ask(text)


def _looks_transactional(subject: str, text: str, sender_email: str) -> bool:
    sender_low = (sender_email or "").lower()
    subject_low = (subject or "").lower()
    if any(hint in sender_low for hint in AUTOMATED_HINTS) and any(hint in text for hint in NO_RESPONSE_HINTS):
        return True
    if any(hint in subject_low for hint in NO_RESPONSE_HINTS):
        return True
    return any(hint in text for hint in ("your account balance is", "your order has shipped", "payment of $"))


def _deterministic_summary(
    *,
    sender: str,
    sender_email: str,
    subject: str,
    latest_body: str,
    text: str,
    bucket: str,
) -> str:
    subject_low = (subject or "").lower()
    if bucket == Bucket.MONITORING.value:
        return _clean_text(f"{sender} flagged this as a status update for your visibility.", SUMMARY_LIMIT)
    if "thank you" in text or "thanks for" in text:
        return _clean_text(f"{sender} sent a thank-you note about your recent interaction.", SUMMARY_LIMIT)
    if "payment confirmation" in subject_low:
        amount = _extract_currency(latest_body)
        balance = _extract_balance(latest_body)
        detail = f" confirmed a payment"
        if amount:
            detail += f" of {amount}"
        if balance:
            detail += f" and says the balance is {balance}"
        return _clean_text(f"{sender}{detail}.", SUMMARY_LIMIT)
    if any(hint in subject_low for hint in ("delivered", "shipped", "on the way", "arriving tomorrow", "order confirmed")):
        detail = _shipping_detail(subject_low, latest_body)
        return _clean_text(f"{sender} {detail}.", SUMMARY_LIMIT)
    if "report card" in subject_low:
        return _clean_text(f"{sender} says the latest report card is available in the parent portal.", SUMMARY_LIMIT)
    if "security alert" in subject_low:
        return _clean_text(f"{sender} sent a security alert about account access.", SUMMARY_LIMIT)
    if _has_document_action(subject, text):
        doc = _document_label(subject, latest_body)
        if "approve" in text or "approval" in text or "action required" in text:
            return _clean_text(f"{sender} sent {doc} and is looking for your approval or timing.", SUMMARY_LIMIT)
        return _clean_text(f"{sender} sent {doc} and needs a decision or next step from you.", SUMMARY_LIMIT)
    if _has_scheduling_followup(text):
        return _clean_text(f"{sender} followed up to find time to meet or talk.", SUMMARY_LIMIT)
    if _has_explicit_ask(text):
        return _clean_text(f"{sender} followed up and is waiting on a response from you.", SUMMARY_LIMIT)
    snippet = _first_meaningful_sentence(latest_body or subject)
    if bucket in {Bucket.NEWSLETTERS.value, Bucket.SPAM_MARKETING.value}:
        return _clean_text(f"{sender} {_as_sender_sentence(snippet)}", SUMMARY_LIMIT)
    return _clean_text(f"{sender} {_as_sender_sentence(snippet)}", SUMMARY_LIMIT)


def _deterministic_action(
    *,
    sender: str,
    subject: str,
    text: str,
    response_needed: bool,
    project: ProjectBrief | None,
    bucket: str,
    directed_to_other_person: bool,
) -> str:
    if bucket == Bucket.MONITORING.value:
        if "subscription required" in text or "blocked" in text or "stall" in text:
            return _clean_text("Track the blocker with the named owner and confirm the resolution path before the deadline.", ACTION_LIMIT)
        return "Track the owner, deliverable, and follow-up deadline."
    if not response_needed:
        if directed_to_other_person and _monitoring_followup_needed(subject, text):
            return _clean_text("Track the named owner's reply and confirm the blocker gets resolved without drafting a new email.", ACTION_LIMIT)
        if _offline_or_operational_action(subject, text):
            if "memo and receipt" in text:
                return _clean_text("Upload the receipt and memo through the operational flow instead of drafting a reply.", ACTION_LIMIT)
            if "ownership invitation" in text:
                return _clean_text("Open the thread and complete the operational step directly from the email.", ACTION_LIMIT)
            return _clean_text("Handle the operational next step directly from the thread; no email draft needed.", ACTION_LIMIT)
        return ""
    if _has_document_action(subject, text):
        return _clean_text(f"Reply to {sender} with your decision and confirm timing.", ACTION_LIMIT)
    if _has_scheduling_followup(text):
        return _clean_text(f"Reply to {sender} with a proposed time and format.", ACTION_LIMIT)
    if project and project.next_actions:
        return _clean_text(project.next_actions[0].action, ACTION_LIMIT)
    return _clean_text(f"Reply to {sender} with the next step and timing.", ACTION_LIMIT)


def _deterministic_response(
    *,
    sender: str,
    subject: str,
    text: str,
    response_needed: bool,
    suggested_action: str,
    bucket: str,
    directed_to_other_person: bool,
) -> str:
    if bucket == Bucket.MONITORING.value or not response_needed:
        return ""
    if directed_to_other_person:
        return ""
    if _has_document_action(subject, text):
        return _clean_text(
            f"Tell {sender} your decision, confirm timing, and ask for anything still needed to keep it moving.",
            RESPONSE_LIMIT,
        )
    if _has_scheduling_followup(text):
        return _clean_text(
            f"Tell {sender} you want to connect and propose a concrete time for coffee or a call.",
            RESPONSE_LIMIT,
        )
    if "additional information" in text or "hearing from you" in text:
        return _clean_text(
            f"Tell {sender} whether you want to keep talking and what information or next step you want from them.",
            RESPONSE_LIMIT,
        )
    if suggested_action:
        return _clean_text(
            f"Tell {sender} the next step you want and when they should expect your follow-up.",
            RESPONSE_LIMIT,
        )
    return _clean_text(f"Reply to {sender} with a direct next step.", RESPONSE_LIMIT)


def _first_meaningful_sentence(text: str) -> str:
    cleaned = normalize_text(text)
    if not cleaned:
        return "sent an update."
    parts = re.split(r"(?<=[.!?])\s+", cleaned)
    for part in parts:
        candidate = _clean_text(part, SUMMARY_LIMIT)
        if not candidate:
            continue
        lowered = candidate.lower()
        if lowered.startswith(("hi ", "hello ", "dear ")):
            continue
        if _subject_only_requires_fallback(candidate):
            continue
        return _normalize_sentence_start(candidate)
    return _normalize_sentence_start(cleaned)


def _subject_only_requires_fallback(text: str) -> bool:
    lowered = text.lower().strip()
    if not lowered:
        return True
    if len(lowered.split()) <= 3:
        return True
    return False


def _ensure_sender_in_summary(summary: str, item: ThreadRecord) -> str:
    sender = _sender_label(item.sender_name, item.sender_email)
    cleaned = _clean_text(summary, SUMMARY_LIMIT)
    if not cleaned:
        return _clean_text(f"{sender} sent an update.", SUMMARY_LIMIT)
    if sender.lower() in cleaned.lower():
        return cleaned
    adjusted = _normalize_sentence_start(cleaned)
    return _clean_text(f"{sender} {adjusted}", SUMMARY_LIMIT)


def _document_label(subject: str, latest_body: str) -> str:
    blob = f"{subject} {latest_body}".lower()
    if "change order" in blob:
        return "a change order"
    if "invoice" in blob:
        return "an invoice"
    if "ea#" in blob:
        return "an extra work authorization"
    if "bill" in blob:
        return "a bill"
    if "agreement" in blob or "contract" in blob:
        return "an agreement"
    return "a document"


def _shipping_detail(subject_low: str, latest_body: str) -> str:
    if "delivered" in subject_low:
        return "says your order was delivered"
    if "arriving tomorrow" in subject_low:
        return "says your order arrives tomorrow"
    if "shipped" in subject_low or "on the way" in subject_low:
        return "says your order is on the way"
    if "order confirmed" in subject_low:
        return "confirmed your order"
    return _normalize_sentence_start(_first_meaningful_sentence(latest_body))


def _extract_currency(text: str) -> str:
    match = re.search(r"\$\d[\d,]*(?:\.\d{2})?", text or "")
    return match.group(0) if match else ""


def _extract_balance(text: str) -> str:
    match = re.search(r"balance is\s+(\$\d[\d,]*(?:\.\d{2})?)", (text or "").lower())
    return match.group(1) if match else ""


def _normalize_sentence_start(text: str) -> str:
    stripped = (text or "").strip()
    if not stripped:
        return "sent an update."
    if len(stripped) > 1 and stripped[0].isupper() and stripped[1].islower():
        return stripped[0].lower() + stripped[1:]
    return stripped


def _as_sender_sentence(text: str) -> str:
    stripped = (text or "").strip()
    if not stripped:
        return "sent an update."
    lowered = stripped.lower()
    if lowered.startswith(("says ", "shares ", "covers ", "rounds up ", "offers ", "confirms ", "sent ")):
        return lowered
    return "shares " + _normalize_sentence_start(stripped)


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    clipped = text[: limit - 3].rstrip()
    if " " in clipped:
        clipped = clipped.rsplit(" ", 1)[0]
    return clipped + "..."


def _clean_text(text: str, limit: int) -> str:
    cleaned = normalize_text(text or "").strip(" -|;,:")
    if len(cleaned) <= limit:
        return cleaned
    return _truncate(cleaned, limit)


def _coerce_bool(value: Any, fallback: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "yes", "1"}:
            return True
        if lowered in {"false", "no", "0"}:
            return False
    return fallback
