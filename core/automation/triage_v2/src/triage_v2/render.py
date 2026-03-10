from __future__ import annotations

from datetime import datetime, timezone
import html
import re
from typing import Iterable
from zoneinfo import ZoneInfo

from triage_v2.policy import load_policy
from triage_v2.types import SECTION_ORDER, ThreadRecord

EASTERN = ZoneInfo("America/New_York")
POLICY = load_policy()

SECTION_COLORS = {
    "Action Needed": "#111111",
    "Already Addressed": "#2f7d32",
    "Monitoring": "#9a6700",
    "FYI": "#1f5fb8",
    "Newsletters": "#6b7280",
    "Spam / Marketing": "#8b9099",
}

ENTRY_STYLES = {
    "Action Needed": (
        "margin:0 0 9px 0;background:#f7f7f7;border:1px solid #d1d5db;border-radius:6px;"
        "padding:10px 12px;font-size:15.5px;line-height:1.38;color:#111111;"
    ),
    "Already Addressed": (
        "margin:0 0 9px 0;background:#edf7ed;border-left:5px solid #37a148;border-radius:4px;"
        "padding:10px 12px;font-size:15.5px;line-height:1.38;color:#1f2937;"
    ),
    "Monitoring": (
        "margin:0 0 9px 0;background:#fff7e8;border-left:5px solid #d19a24;border-radius:4px;"
        "padding:10px 12px;font-size:15.5px;line-height:1.38;color:#111111;"
    ),
    "FYI": (
        "margin:0 0 9px 0;background:#f7fbff;border-left:5px solid #2166c2;border-radius:4px;"
        "padding:10px 12px;font-size:15.5px;line-height:1.38;color:#1f2937;"
    ),
    "Newsletters": (
        "margin:0;padding:6px 0;font-size:14.5px;line-height:1.34;color:#374151;"
    ),
    "Spam / Marketing": (
        "margin:0;padding:6px 0;font-size:14px;line-height:1.32;color:#4b5563;"
    ),
}

LINK_STYLE = "color:#4da3ff;text-decoration:none;"

INVISIBLE_RE = re.compile(r"[\u034f\u200b-\u200f\u2060\ufeff]+")
URL_RE = re.compile(r"https?://\S+")
PHONE_RE = re.compile(r"(?:\+?\d[\d().\-\s]{7,}\d)")
PIN_RE = re.compile(r"\bpin[:\s#-]*\d{3,}\b", re.IGNORECASE)

def _group(threads: Iterable[ThreadRecord]) -> dict[str, dict[str, list[ThreadRecord]]]:
    grouped = {section: {"work": [], "personal": []} for section in SECTION_ORDER}
    for thread in threads:
        if thread.bucket not in grouped:
            continue
        account = "work" if thread.account == "work" else "personal"
        grouped[thread.bucket][account].append(thread)

    for section in SECTION_ORDER:
        grouped[section]["work"].sort(key=lambda x: _section_sort_key(section, x))
        grouped[section]["personal"].sort(key=lambda x: _section_sort_key(section, x))

    return grouped


def _draft_link_parts(item: ThreadRecord) -> tuple[str, str]:
    if item.response_needed and item.draft_status == "ready":
        return ("Draft ready in Superhuman", item.thread_url)
    if item.response_needed and item.draft_status == "fallback_gmail" and item.draft_url:
        return ("Draft ready in Gmail", item.draft_url)
    if item.response_needed:
        return ("View thread", item.thread_url)
    return ("View", item.thread_url)


def _draft_link_markdown(item: ThreadRecord) -> str:
    text, url = _draft_link_parts(item)
    return f"[{text}]({url})"


def _draft_link_html(item: ThreadRecord) -> str:
    text, url = _draft_link_parts(item)
    return f"<a style='{LINK_STYLE}' href='{html.escape(url, quote=True)}'>{html.escape(text)}</a>"


def _section_sort_key(section: str, item: ThreadRecord) -> tuple[object, ...]:
    if section == "Newsletters":
        return (_newsletter_priority_rank(item), -_priority_score(item), item.subject_latest.lower(), item.thread_id)
    return (-_priority_score(item), item.subject_latest.lower(), item.thread_id)


def _name_from_email(raw: str) -> str:
    text = raw.strip().lower()
    if not text or "@" not in text:
        return ""
    local = text.split("@", 1)[0].strip()
    if not local:
        return ""
    pieces = [p for p in re.split(r"[._+\-]+", local) if p]
    if not pieces:
        return ""
    return " ".join(piece.capitalize() for piece in pieces)


def sender_person(item: ThreadRecord) -> str:
    name = " ".join((item.sender_name or "").split()).strip().strip('"')
    if name and "@" not in name:
        lowered = name.lower()
        marker = " from "
        if marker in lowered:
            candidate = name[: lowered.index(marker)].strip(" -|")
            if candidate:
                name = candidate
        return name
    if name and "@" in name:
        resolved = _name_from_email(name)
        if resolved:
            return resolved
    resolved = _name_from_email(item.sender_email or "")
    if resolved:
        return resolved
    return "Unknown"


def _newsletter_priority_rank(item: ThreadRecord) -> tuple[int, str]:
    blob = " ".join(
        (
            (item.sender_name or "").lower(),
            (item.sender_email or "").lower(),
            (item.subject_latest or "").lower(),
        )
    )
    for index, hint in enumerate(POLICY.newsletter_sender_priority):
        if hint in blob:
            return (index, blob)
    return (len(POLICY.newsletter_sender_priority) + 1, blob)


def _ordinal(day: int) -> str:
    if 11 <= (day % 100) <= 13:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
    return f"{day}{suffix}"


def _date_label(dt: datetime) -> str:
    return f"{dt.strftime('%A')}, {dt.strftime('%B')} {_ordinal(dt.day)}, {dt.year}"


def _time_label(dt: datetime) -> str:
    return dt.strftime("%-I:%M %p ET")


def _summary(text: str, *, limit: int = 220) -> str:
    cleaned = html.unescape(text or "")
    cleaned = INVISIBLE_RE.sub(" ", cleaned)
    cleaned = URL_RE.sub("", cleaned)
    cleaned = PHONE_RE.sub("", cleaned)
    cleaned = PIN_RE.sub("", cleaned)

    lowered = cleaned.lower()
    for marker in (
        "join with google meet",
        "join by phone",
        "more phone numbers",
        "to respond to this message",
        "view options",
        "get outlook for ios",
    ):
        idx = lowered.find(marker)
        if idx >= 48:
            cleaned = cleaned[:idx]
            lowered = cleaned.lower()
            break

    for marker in (" sent from my iphone", " from: ", " on wed, ", " on thu, "):
        idx = lowered.find(marker)
        if idx >= 30:
            cleaned = cleaned[:idx]
            lowered = cleaned.lower()
            break

    cleaned = " ".join(cleaned.split()).strip(" -|;,:")
    if len(cleaned) <= limit:
        return cleaned
    clipped = cleaned[: limit - 3].rstrip()
    if " " in clipped:
        clipped = clipped.rsplit(" ", 1)[0]
    return clipped + "..."


def _priority_score(item: ThreadRecord) -> int:
    blob = " ".join(
        (
            (item.sender_name or "").lower(),
            (item.sender_email or "").lower(),
            (item.subject_latest or "").lower(),
            _summary(item.summary_latest, limit=260).lower(),
        )
    )
    score = 0

    for hint, weight in POLICY.priority_high_hints.items():
        if hint in blob:
            score += weight

    for hint, weight in POLICY.priority_low_hints.items():
        if hint in blob:
            score += weight

    score += int(POLICY.priority_bucket_bonus.get(item.bucket.lower(), 0))

    score += _project_priority_bonus(item.matched_project_priority)
    if item.matched_project_name:
        score += 250

    sender_email = (item.sender_email or "").lower()
    for domain_hint, bonus in POLICY.priority_domain_bonus.items():
        if domain_hint in sender_email:
            score += bonus

    return score


def _project_priority_bonus(priority: str) -> int:
    value = (priority or "").strip().upper()
    if value == "P0":
        return 5000
    if value == "P1":
        return 2500
    if value == "P2":
        return 800
    return 0


def _detail_level_for_item(section: str, index: int, item: ThreadRecord) -> str:
    if item.response_needed:
        return "full"
    if section in {"Newsletters", "Spam / Marketing"}:
        return "line"
    return "full"


def _draft_note(item: ThreadRecord) -> str:
    if item.draft_authoring_mode != "fallback_deterministic":
        return ""
    if item.draft_context_status == "stale":
        return "deterministic fallback, project refresh stale."
    if item.draft_context_status == "authoring_error":
        return "deterministic fallback, authoring error."
    return ""


def _line_text(item: ThreadRecord, summary: str) -> str:
    return summary or _summary(item.subject_latest, limit=160)


def _compact_sender_label(item: ThreadRecord) -> str:
    return sender_person(item) or _summary(item.subject_latest, limit=80)


def _summary_counts(grouped: dict[str, dict[str, list[ThreadRecord]]]) -> str:
    parts: list[str] = []
    for section in SECTION_ORDER:
        count = len(grouped[section]["work"]) + len(grouped[section]["personal"])
        if count == 0:
            continue
        parts.append(f"{count} {section.lower()}")
    return " · ".join(parts)


def render_markdown(
    *,
    run_id: str,
    run_type: str,
    threads: list[ThreadRecord],
    generated_at: datetime | None = None,
) -> str:
    now = generated_at or datetime.now(timezone.utc)
    now_et = now.astimezone(EASTERN)
    grouped = _group(threads)
    total = sum(len(grouped[s]["work"]) + len(grouped[s]["personal"]) for s in SECTION_ORDER)

    lines: list[str] = []
    lines.append(f"**Run ID:** {run_id}")
    lines.append(f"**Run type:** {run_type.upper()}")
    lines.append(f"**Date:** Inbox Triage {_date_label(now_et)}")
    lines.append(f"**Ran at:** {_time_label(now_et)}")
    lines.append(f"**Total threads:** {total}")
    counts = _summary_counts(grouped)
    if counts:
        lines.append(f"**Summary:** {counts}")
    lines.append("")

    for section in SECTION_ORDER:
        work_items = grouped[section]["work"]
        personal_items = grouped[section]["personal"]
        count = len(work_items) + len(personal_items)
        if count == 0:
            continue
        lines.append(f"## {section} ({count})")
        lines.append("")

        for account_name, items in (("Work", work_items), ("Personal", personal_items)):
            if not items:
                continue
            lines.append(f"### {account_name}")
            lines.append("")
            for index, item in enumerate(items):
                detail = _detail_level_for_item(section, index, item)
                summary = _summary(item.summary_latest)
                if detail == "line":
                    line_text = _line_text(item, summary)
                    sender_label = _compact_sender_label(item)
                    if section in {"Newsletters", "Spam / Marketing"}:
                        line = f"- **{sender_label}** — {line_text} — [View]({item.thread_url})"
                        if item.unsubscribe_url:
                            line += f" | [Unsubscribe]({item.unsubscribe_url})"
                        else:
                            line += " | Unsubscribe unavailable"
                        lines.append(line)
                    else:
                        lines.append(f"- **{sender_label}** — {line_text} — {_draft_link_markdown(item)}")
                    continue

                lines.append(f"- **{item.subject_latest}**")
                lines.append(f"  - **From:** {sender_person(item)}")

                if summary:
                    lines.append(f"  - **Summary:** {summary}")

                if detail == "full" and item.response_needed and item.suggested_response:
                    lines.append(f"  - **Recommended response:** {item.suggested_response}")
                if detail == "full" and item.suggested_action:
                    lines.append(f"  - **Next step:** {item.suggested_action}")

                if detail == "full" and item.bucket == "Monitoring":
                    monitor = " | ".join(
                        p
                        for p in (
                            f"Owner: {item.monitoring_owner}" if item.monitoring_owner else "",
                            f"Deliverable: {item.monitoring_deliverable}" if item.monitoring_deliverable else "",
                            f"Deadline: {item.monitoring_deadline}" if item.monitoring_deadline else "",
                        )
                        if p
                    )
                    if monitor:
                        lines.append(f"  - **Monitoring:** {monitor}")

                if item.bucket in {"Newsletters", "Spam / Marketing"}:
                    if item.unsubscribe_url:
                        lines.append(f"  - [View]({item.thread_url}) | [Unsubscribe]({item.unsubscribe_url})")
                    else:
                        lines.append(f"  - [View]({item.thread_url}) | Unsubscribe unavailable")
                elif item.response_needed:
                    lines.append(f"  - {_draft_link_markdown(item)}")
                elif item.bucket == "Action Needed":
                    lines.append(f"  - [View thread]({item.thread_url})")
                else:
                    lines.append(f"  - [View]({item.thread_url})")

                note = _draft_note(item)
                if note and item.response_needed:
                    lines.append(f"  - **Draft note:** {note}")
                lines.append("")

    return "\n".join(lines).strip() + "\n"


def render_html(
    *,
    run_id: str,
    run_type: str,
    threads: list[ThreadRecord],
    generated_at: datetime | None = None,
) -> str:
    now = generated_at or datetime.now(timezone.utc)
    now_et = now.astimezone(EASTERN)
    grouped = _group(threads)
    total = sum(len(grouped[s]["work"]) + len(grouped[s]["personal"]) for s in SECTION_ORDER)

    parts: list[str] = []
    parts.append("<!doctype html>")
    parts.append("<html>")
    parts.append("<head>")
    parts.append("  <meta charset='utf-8' />")
    parts.append("  <meta name='viewport' content='width=device-width, initial-scale=1' />")
    parts.append("  <title>Inbox Triage</title>")
    parts.append("</head>")
    parts.append(
        "<body style='margin:0;padding:22px;background:#ffffff;color:#1a1a1a;"
        "font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,Helvetica,Arial,sans-serif;line-height:1.4;'>"
    )
    parts.append("<div style='max-width:760px;margin:0 auto;'>")
    parts.append(
        f"<h1 style='font-size:24px;line-height:1.2;margin:0 0 14px 0;color:#1a1a1a;'>"
        f"Inbox Triage \u2014 {_date_label(now_et)}, {_time_label(now_et)} ({total} new)</h1>"
    )
    parts.append(
        f"<p style='font-size:13.5px;color:#6b7280;margin:0 0 6px 0;'>"
        f"Run ID: {html.escape(run_id)} | Run type: {html.escape(run_type.upper())}</p>"
    )
    parts.append(
        f"<p style='font-size:13.5px;color:#6b7280;margin:0 0 12px 0;'>"
        f"{html.escape(_summary_counts(grouped))}</p>"
    )

    for section in SECTION_ORDER:
        work_items = grouped[section]["work"]
        personal_items = grouped[section]["personal"]
        count = len(work_items) + len(personal_items)
        if count == 0:
            continue

        header_color = SECTION_COLORS.get(section, "#111111")
        parts.append(
            f"<p style='display:block;width:100%;border-bottom:2px solid {header_color};padding-bottom:4px;"
            f"margin-top:16px;margin-bottom:8px;font-size:23px;font-weight:800;color:{header_color};'>"
            f"{html.escape(section)} ({count})</p>"
        )

        for account_name, items in (("Work", work_items), ("Personal", personal_items)):
            if not items:
                continue
            parts.append(f"<p style='font-size:16px;font-weight:700;margin:8px 0 4px 0;color:#555;'>{account_name}</p>")
            for index, item in enumerate(items):
                detail = _detail_level_for_item(section, index, item)
                summary = _summary(item.summary_latest)
                thread_link = html.escape(item.thread_url, quote=True)

                if detail == "line":
                    line_text = html.escape(_line_text(item, summary))
                    sender_label = html.escape(_compact_sender_label(item))
                    if section in {"Newsletters", "Spam / Marketing"}:
                        body = (
                            f"<b>{sender_label}</b> \u2014 {line_text} \u2014 "
                            f"<a style='{LINK_STYLE}' href='{thread_link}'>View</a>"
                        )
                        if item.unsubscribe_url:
                            body += (
                                " | "
                                f"<a style='{LINK_STYLE}' href='{html.escape(item.unsubscribe_url, quote=True)}'>"
                                "Unsubscribe</a>"
                            )
                        else:
                            body += " | Unsubscribe unavailable"
                        style = ENTRY_STYLES.get(section, ENTRY_STYLES["Spam / Marketing"])
                        parts.append(f"<p style='{style}'>{body}</p>")
                        continue

                    body = f"<b>{sender_label}</b> \u2014 {line_text} \u2014 {_draft_link_html(item)}"
                    style = ENTRY_STYLES.get(section, ENTRY_STYLES["FYI"])
                    parts.append(f"<p style='{style}'>{body}</p>")
                    continue

                content_lines = [
                    f"<b>{html.escape(item.subject_latest)}</b>",
                    f"<span style='color:#1f2937;text-decoration:none;'><b>From:</b> {html.escape(sender_person(item))}</span>",
                ]
                if summary:
                    content_lines.append(f"<span><b>Summary:</b> {html.escape(summary)}</span>")

                if detail == "full" and item.response_needed and item.suggested_response:
                    content_lines.append(f"<span><b>Recommended response:</b> {html.escape(item.suggested_response)}</span>")
                if detail == "full" and item.suggested_action:
                    content_lines.append(f"<span><b>Next step:</b> {html.escape(item.suggested_action)}</span>")
                if detail == "full" and item.bucket == "Monitoring":
                    monitor = " | ".join(
                        p
                        for p in (
                            f"Owner: {item.monitoring_owner}" if item.monitoring_owner else "",
                            f"Deliverable: {item.monitoring_deliverable}" if item.monitoring_deliverable else "",
                            f"Deadline: {item.monitoring_deadline}" if item.monitoring_deadline else "",
                        )
                        if p
                    )
                    if monitor:
                        content_lines.append(f"<span><b>Monitoring:</b> {html.escape(monitor)}</span>")

                if item.bucket in {"Newsletters", "Spam / Marketing"}:
                    if item.unsubscribe_url:
                        content_lines.append(
                            f"<a style='{LINK_STYLE}' href='{thread_link}'>View</a>"
                            " | "
                            f"<a style='{LINK_STYLE}' href='{html.escape(item.unsubscribe_url, quote=True)}'>"
                            "Unsubscribe</a>"
                        )
                    else:
                        content_lines.append(f"<a style='{LINK_STYLE}' href='{thread_link}'>View</a> | Unsubscribe unavailable")
                elif item.response_needed:
                    content_lines.append(_draft_link_html(item))
                elif item.bucket == "Action Needed":
                    content_lines.append(f"<a style='{LINK_STYLE}' href='{thread_link}'>View thread</a>")
                else:
                    content_lines.append(f"<a style='{LINK_STYLE}' href='{thread_link}'>View</a>")

                note = _draft_note(item)
                if note and item.response_needed:
                    content_lines.append(f"<span><b>Draft note:</b> {html.escape(note)}</span>")
                style = ENTRY_STYLES.get(
                    section,
                    "margin:0 0 8px 0;padding:0;font-size:15px;line-height:1.36;color:#1f2937;",
                )
                parts.append(f"<p style='{style}'>{'<br>'.join(content_lines)}</p>")

    parts.append("</div>")
    parts.append("</body>")
    parts.append("</html>")
    return "\n".join(parts) + "\n"
