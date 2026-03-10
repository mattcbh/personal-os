#!/usr/bin/env python3
"""
Render triage markdown deterministically from normalized thread records.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import html
import json
from pathlib import Path
import re
from typing import Any

BUCKET_ORDER = [
    "Action Needed",
    "Already Addressed",
    "Monitoring",
    "FYI",
    "Newsletters",
    "Spam / Marketing",
]

ACCOUNT_LABEL = {
    "work": "Work",
    "personal": "Personal",
}

SECTION_COLORS = {
    "Action Needed": "#111111",
    "Already Addressed": "#2f7d32",
    "Monitoring": "#9a6700",
    "FYI": "#1f5fb8",
    "Newsletters": "#6b7280",
    "Spam / Marketing": "#8b9099",
}

ENTRY_STYLES = {
    "Action Needed": "margin:0 0 9px 0;background:#f7f7f7;border:1px solid #d1d5db;border-radius:6px;padding:10px 12px;font-size:15.5px;line-height:1.38;color:#111111;",
    "Already Addressed": "margin:0 0 9px 0;background:#edf7ed;border-left:5px solid #37a148;border-radius:4px;padding:10px 12px;font-size:15.5px;line-height:1.38;color:#1f2937;",
    "Monitoring": "margin:0 0 9px 0;background:#fff7e8;border-left:5px solid #d19a24;border-radius:4px;padding:10px 12px;font-size:15.5px;line-height:1.38;color:#111111;",
    "FYI": "margin:0 0 9px 0;background:#f7fbff;border-left:5px solid #2166c2;border-radius:4px;padding:10px 12px;font-size:15.5px;line-height:1.38;color:#1f2937;",
    "Newsletters": "margin:0;padding:6px 0;font-size:14.5px;line-height:1.34;color:#374151;",
    "Spam / Marketing": "margin:0;padding:6px 0;font-size:14px;line-height:1.32;color:#4b5563;",
}

LINK_STYLE = "color:#4da3ff;text-decoration:none;"
HTML_PROFILE = "compact_ref_v1"
SUMMARY_FIELDS = (
    "summary_latest",
    "summary",
    "summary_brief",
    "body_preview",
    "snippet",
    "reasoning",
    "what_changed",
)
INVISIBLE_RE = re.compile(r"[\u034f\u200b-\u200f\u2060\ufeff]+")
URL_RE = re.compile(r"https?://\S+")
PHONE_RE = re.compile(r"(?:\+?\d[\d().\-\s]{7,}\d)")
PIN_RE = re.compile(r"\bpin[:\s#-]*\d{3,}\b", re.IGNORECASE)


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    return " ".join(text.split())


def clip_text(text: str, max_len: int = 280) -> str:
    if len(text) <= max_len:
        return text
    clipped = text[: max_len - 3].rstrip()
    if " " in clipped:
        clipped = clipped.rsplit(" ", 1)[0]
    return clipped + "..."


def sanitize_summary(text: str, *, max_len: int = 220) -> str:
    cleaned = html.unescape(clean_text(text))
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
    return clip_text(cleaned, max_len=max_len)


def summary_for_record(rec: dict[str, Any], *, max_len: int = 220) -> str:
    for field in SUMMARY_FIELDS:
        val = clean_text(rec.get(field))
        if val:
            return sanitize_summary(val, max_len=max_len)
    return ""


def non_link_email(sender: str) -> str:
    """
    Render sender emails in a way that avoids auto-linkification in HTML clients.
    """
    text = clean_text(sender)
    if not text:
        return ""
    return text.replace("@", "&#8204;@&#8204;").replace(".", "&#8204;.&#8204;")


def name_from_email(raw: str) -> str:
    text = clean_text(raw).lower()
    if not text or "@" not in text:
        return ""
    local = text.split("@", 1)[0].strip()
    if not local:
        return ""
    parts = [part for part in re.split(r"[._+\-]+", local) if part]
    if not parts:
        return ""
    return " ".join(part.capitalize() for part in parts)


def sender_person(rec: dict[str, Any]) -> str:
    name = clean_text(rec.get("sender_name")).strip('"')
    if name and "@" not in name:
        lowered = name.lower()
        marker = " from "
        if marker in lowered:
            candidate = name[: lowered.index(marker)].strip(" -|")
            if candidate:
                return candidate
        return name
    if name and "@" in name:
        resolved = name_from_email(name)
        if resolved:
            return resolved
    resolved = name_from_email(clean_text(rec.get("sender_email")))
    if resolved:
        return resolved
    return "Unknown"


def short_date_label(date_label: str) -> str:
    text = clean_text(date_label)
    if not text:
        return ""
    for fmt in ("%A %B %d, %Y", "%B %d, %Y"):
        try:
            dt = datetime.strptime(text, fmt)
            return dt.strftime("%b %d").upper()
        except Exception:
            pass
    return ""


def since_triage_label(last_triage: str, new_count: int) -> str:
    ts = clean_text(last_triage)
    if not ts or ts.lower() == "null":
        return f"{new_count} new emails"
    try:
        dt = datetime.fromisoformat(ts)
        return f"Since {dt.strftime('%-I:%M %p')} triage | {new_count} new emails"
    except Exception:
        return f"Since previous triage | {new_count} new emails"


def thread_url(account: str, thread_id: str, rec: dict[str, Any] | None = None) -> str:
    if isinstance(rec, dict):
        direct = clean_text(rec.get("superhuman_url"))
        if direct.startswith("https://mail.superhuman.com/"):
            return direct
    if account == "personal":
        return f"https://mail.superhuman.com/lieber.matt@gmail.com/thread/{thread_id}"
    return f"https://mail.superhuman.com/matt@cornerboothholdings.com/thread/{thread_id}"


def draft_url(rec: dict[str, Any]) -> str:
    direct = clean_text(rec.get("draft_url"))
    if direct.startswith("http://") or direct.startswith("https://"):
        return direct
    account = str(rec.get("account") or "work").lower()
    tid = clean_text(rec.get("threadId"))
    return thread_url(account, tid, rec)


def normalize_bucket(raw: str) -> str:
    s = (raw or "").strip().lower()
    if s in {"action needed", "action_needed"}:
        return "Action Needed"
    if s in {"already addressed", "already_addressed"}:
        return "Already Addressed"
    if s in {"monitoring"}:
        return "Monitoring"
    if s in {"fyi"}:
        return "FYI"
    if s in {"newsletters", "newsletter"}:
        return "Newsletters"
    if s in {"spam / marketing", "spam/marketing", "spam", "marketing"}:
        return "Spam / Marketing"
    return raw or "FYI"


def load_records(path: Path) -> list[dict[str, Any]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("records file must contain a JSON array")
    out: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        out.append(item)
    return out


def grouped_records(records: list[dict[str, Any]]) -> dict[str, dict[str, list[dict[str, Any]]]]:
    by_bucket_account: dict[str, dict[str, list[dict[str, Any]]]] = {
        b: {"work": [], "personal": []} for b in BUCKET_ORDER
    }

    for rec in records:
        bucket = normalize_bucket(str(rec.get("bucket") or "FYI"))
        if bucket not in by_bucket_account:
            continue
        account = str(rec.get("account") or "work").lower()
        if account not in {"work", "personal"}:
            account = "work"
        tid = str(rec.get("threadId") or "").strip()
        if not tid:
            continue
        by_bucket_account[bucket][account].append(rec)

    return by_bucket_account


def line_text_for_record(rec: dict[str, Any]) -> str:
    summary = summary_for_record(rec, max_len=180)
    if summary:
        return summary
    return clip_text(clean_text(rec.get("subject_latest") or "(no subject)"), max_len=160)


def markdown_draft_link(rec: dict[str, Any], bucket: str) -> str:
    status = clean_text(rec.get("draft_status")).lower()
    target = draft_url(rec)
    if bucket == "Action Needed" and status in {"queued", "ready", "fallback_gmail"}:
        return f"[Draft ready]({target})"
    if bucket == "FYI" and status in {"queued", "ready", "fallback_gmail"}:
        return f"[Courtesy draft ready]({target})"
    if bucket == "Action Needed":
        return f"[View thread]({thread_url(str(rec.get('account') or 'work').lower(), clean_text(rec.get('threadId')), rec)})"
    return f"[View]({thread_url(str(rec.get('account') or 'work').lower(), clean_text(rec.get('threadId')), rec)})"


def html_draft_link(rec: dict[str, Any], bucket: str) -> str:
    status = clean_text(rec.get("draft_status")).lower()
    target = html.escape(draft_url(rec), quote=True)
    thread_target = html.escape(
        thread_url(str(rec.get("account") or "work").lower(), clean_text(rec.get("threadId")), rec),
        quote=True,
    )
    if bucket == "Action Needed" and status in {"queued", "ready", "fallback_gmail"}:
        label = "Draft ready in Gmail" if "mail.google.com" in target else "Draft ready"
        return f'<a href="{target}" style="{LINK_STYLE}">{label}</a>'
    if bucket == "FYI" and status in {"queued", "ready", "fallback_gmail"}:
        return f'<a href="{target}" style="{LINK_STYLE}">Courtesy draft ready</a>'
    if bucket == "Action Needed":
        return f'<a href="{thread_target}" style="{LINK_STYLE}">View thread</a>'
    return f'<a href="{thread_target}" style="{LINK_STYLE}">View</a>'


def draft_note(rec: dict[str, Any]) -> str:
    if clean_text(rec.get("draft_authoring_mode")) != "fallback_deterministic":
        return ""
    context_status = clean_text(rec.get("draft_context_status"))
    if context_status == "stale":
        return "deterministic fallback, project refresh stale."
    if context_status == "authoring_error":
        return "deterministic fallback, authoring error."
    return ""


def render_entry(rec: dict[str, Any], bucket: str) -> list[str]:
    account = str(rec.get("account") or "work").lower()
    tid = clean_text(rec.get("threadId"))
    sender_label = sender_person(rec)
    subject = clean_text(rec.get("subject_latest") or "(no subject)")
    draft_status = clean_text(rec.get("draft_status")).lower()
    unsub = rec.get("unsubscribe_url")
    link = thread_url(account, tid, rec)
    summary = summary_for_record(rec)

    if bucket in {"Newsletters", "Spam / Marketing"}:
        line = f"**{sender_label}** -- {line_text_for_record(rec)} -- [View]({link})"
        if isinstance(unsub, str) and unsub.strip().startswith(("http://", "https://")):
            line += f" | [Unsubscribe]({unsub.strip()})"
        else:
            line += " | Unsubscribe unavailable"
        return [line]

    lines: list[str] = [f"**{subject}**", f"**From:** {sender_label}"]
    if summary:
        lines.append(f"**Summary:** {summary}")

    recommended = clean_text(rec.get("suggested_response"))
    if bucket == "Action Needed" and recommended:
        lines.append(f"**Recommended response:** {clip_text(recommended, max_len=220)}")

    suggested_action = clean_text(rec.get("suggested_action"))
    if suggested_action:
        lines.append(f"**Next step:** {clip_text(suggested_action, max_len=220)}")

    if bucket == "Monitoring":
        owner = clean_text(rec.get("monitoring_owner"))
        deliverable = clean_text(rec.get("monitoring_deliverable"))
        deadline = clean_text(rec.get("monitoring_deadline"))
        monitor_parts = []
        if owner:
            monitor_parts.append(f"Owner: {owner}")
        if deliverable:
            monitor_parts.append(f"Deliverable: {deliverable}")
        if deadline:
            monitor_parts.append(f"Deadline: {deadline}")
        if monitor_parts:
            lines.append(f"**Monitoring:** {' | '.join(monitor_parts)}")

    lines.append(markdown_draft_link(rec, bucket))
    if draft_status in {"queued", "ready", "fallback_gmail"}:
        lines.append("Draft status: queued")
    elif draft_status == "clipboard":
        lines.append("Draft in clipboard.")
    elif draft_status == "failed":
        lines.append("No draft.")

    note = draft_note(rec)
    if note:
        lines.append(f"**Draft note:** {note}")

    return lines


def summary_counts(by_bucket_account: dict[str, dict[str, list[dict[str, Any]]]]) -> str:
    parts: list[str] = []
    for bucket in BUCKET_ORDER:
        total = len(by_bucket_account[bucket]["work"]) + len(by_bucket_account[bucket]["personal"])
        if total == 0:
            continue
        parts.append(f"{total} {bucket.lower()}")
    return " | ".join(parts)


def render_markdown(records: list[dict[str, Any]], date_label: str, time_label: str, run_type: str) -> str:
    by_bucket_account = grouped_records(records)
    new_count = sum(
        len(by_bucket_account[bucket]["work"]) + len(by_bucket_account[bucket]["personal"])
        for bucket in BUCKET_ORDER
    )

    lines: list[str] = []
    lines.append(f"# Inbox Triage -- {date_label}, {time_label}")
    lines.append("")
    lines.append(f"**Run type:** {run_type}")
    lines.append(f"**New emails:** {new_count}")
    counts = summary_counts(by_bucket_account)
    if counts:
        lines.append(f"**Summary:** {counts}")
    lines.append("")

    for bucket in BUCKET_ORDER:
        work_items = by_bucket_account[bucket]["work"]
        personal_items = by_bucket_account[bucket]["personal"]
        total = len(work_items) + len(personal_items)
        if total == 0:
            continue
        lines.append(f"## {bucket} ({total})")
        lines.append("")
        for account in ("work", "personal"):
            items = by_bucket_account[bucket][account]
            if not items:
                continue
            lines.append(f"### {ACCOUNT_LABEL[account]}")
            lines.append("")
            for rec in items:
                entry_lines = render_entry(rec, bucket)
                for index, entry_line in enumerate(entry_lines):
                    prefix = "- " if index == 0 else "  - "
                    lines.append(f"{prefix}{entry_line}")
                lines.append("")

    return "\n".join(lines).strip() + "\n"


def render_html_entry(rec: dict[str, Any], bucket: str) -> str:
    account = str(rec.get("account") or "work").lower()
    tid = clean_text(rec.get("threadId"))
    sender = html.escape(sender_person(rec))
    subject = html.escape(clean_text(rec.get("subject_latest") or "(no subject)"))
    draft_status = clean_text(rec.get("draft_status")).lower()
    unsub = rec.get("unsubscribe_url")
    link = html.escape(thread_url(account, tid, rec), quote=True)

    if bucket in {"Newsletters", "Spam / Marketing"}:
        body = (
            f"<b>{html.escape(sender_person(rec))}</b> -- {html.escape(line_text_for_record(rec))} -- "
            f'<a href="{link}" style="{LINK_STYLE}">View</a>'
        )
        if isinstance(unsub, str) and unsub.strip().startswith(("http://", "https://")):
            body += (
                " | "
                f'<a href="{html.escape(unsub.strip(), quote=True)}" style="{LINK_STYLE}">Unsubscribe</a>'
            )
        else:
            body += " | Unsubscribe unavailable"
        return f'<p style="{ENTRY_STYLES.get(bucket, ENTRY_STYLES["Spam / Marketing"])}">{body}</p>'

    content_lines = [
        f"<b>{subject}</b>",
        f"<span style=\"color:#1f2937;text-decoration:none;\"><b>From:</b> {sender}</span>",
    ]
    summary = summary_for_record(rec)
    if summary:
        content_lines.append(f"<span><b>Summary:</b> {html.escape(summary)}</span>")

    recommended = clean_text(rec.get("suggested_response"))
    if bucket == "Action Needed" and recommended:
        content_lines.append(
            f"<span><b>Recommended response:</b> {html.escape(clip_text(recommended, max_len=220))}</span>"
        )

    suggested_action = clean_text(rec.get("suggested_action"))
    if suggested_action:
        content_lines.append(f"<span><b>Next step:</b> {html.escape(clip_text(suggested_action, max_len=220))}</span>")

    if bucket == "Monitoring":
        owner = clean_text(rec.get("monitoring_owner"))
        deliverable = clean_text(rec.get("monitoring_deliverable"))
        deadline = clean_text(rec.get("monitoring_deadline"))
        monitor_parts = []
        if owner:
            monitor_parts.append(f"Owner: {owner}")
        if deliverable:
            monitor_parts.append(f"Deliverable: {deliverable}")
        if deadline:
            monitor_parts.append(f"Deadline: {deadline}")
        if monitor_parts:
            content_lines.append(f"<span><b>Monitoring:</b> {html.escape(' | '.join(monitor_parts))}</span>")

    content_lines.append(html_draft_link(rec, bucket))
    if draft_status in {"queued", "ready", "fallback_gmail"}:
        content_lines.append("Draft status: queued")
    elif draft_status == "clipboard":
        content_lines.append("Draft in clipboard.")
    elif draft_status == "failed":
        content_lines.append("No draft.")

    note = draft_note(rec)
    if note:
        content_lines.append(f"<span><b>Draft note:</b> {html.escape(note)}</span>")

    content = "<br>".join(content_lines)
    style = ENTRY_STYLES.get(
        bucket,
        "margin:0 0 12px 0;background:#ffffff;border-left:4px solid #9ca3af;padding:14px 16px;font-size:18px;color:#1a1a1a;",
    )
    return f'<p style="{style}">{content}</p>'


def render_html(
    records: list[dict[str, Any]],
    date_label: str,
    time_label: str,
    run_type: str,
    *,
    last_triage: str = "",
) -> str:
    by_bucket_account = grouped_records(records)
    new_count = sum(
        len(by_bucket_account[bucket]["work"]) + len(by_bucket_account[bucket]["personal"])
        for bucket in BUCKET_ORDER
    )

    lines: list[str] = []
    lines.append("<!doctype html>")
    lines.append("<html>")
    lines.append("<head>")
    lines.append('  <meta charset="utf-8" />')
    lines.append('  <meta name="viewport" content="width=device-width, initial-scale=1" />')
    lines.append(f"  <!-- triage-html-profile:{HTML_PROFILE} -->")
    lines.append("  <title>Inbox Triage</title>")
    lines.append("</head>")
    lines.append(
        '<body style="margin:0;padding:22px;background:#ffffff;color:#1a1a1a;'
        'font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,Helvetica,Arial,sans-serif;line-height:1.4;">'
    )
    lines.append('  <div style="max-width:760px;margin:0 auto;">')
    lines.append(
        f'    <p style="font-size:18px;font-weight:600;margin:0 0 12px 0;color:#374151;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">'
        f'Inbox Triage -- {html.escape(date_label)}, {html.escape(time_label)} ({new_count} new)</p>'
    )
    since_line = since_triage_label(last_triage, new_count)
    lines.append(
        f'    <p style="font-size:13.5px;color:#6b7280;margin:0 0 6px 0;">Run type: {html.escape(run_type)} | {html.escape(since_line)}</p>'
    )
    counts = summary_counts(by_bucket_account)
    if counts:
        lines.append(f'    <p style="font-size:13.5px;color:#6b7280;margin:0 0 12px 0;">{html.escape(counts)}</p>')

    for bucket in BUCKET_ORDER:
        work_items = by_bucket_account[bucket]["work"]
        personal_items = by_bucket_account[bucket]["personal"]
        total = len(work_items) + len(personal_items)
        if total == 0:
            continue
        header_color = SECTION_COLORS.get(bucket, "#111111")
        lines.append(
            '    <p style="display:block;width:100%;border-bottom:2px solid #111;'
            f'padding-bottom:4px;margin-top:16px;margin-bottom:8px;font-size:23px;font-weight:800;color:{header_color};">'
            f"{html.escape(bucket)} ({total})</p>"
        )
        for account in ("work", "personal"):
            items = by_bucket_account[bucket][account]
            if not items:
                continue
            lines.append(
                f'    <p style="font-size:16px;font-weight:700;margin:8px 0 4px 0;color:#555;">'
                f"{html.escape(ACCOUNT_LABEL[account])}</p>"
            )
            for rec in items:
                lines.append("    " + render_html_entry(rec, bucket))

    lines.append("  </div>")
    lines.append("</body>")
    lines.append("</html>")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Render triage digest from records JSON")
    parser.add_argument("--records", required=True, help="Path to records JSON")
    parser.add_argument("--output", required=True, help="Path to markdown output")
    parser.add_argument("--html-output", help="Path to HTML output")
    parser.add_argument("--date-label", required=True, help="Display date label")
    parser.add_argument("--time-label", required=True, help="Display time label")
    parser.add_argument("--run-type", required=True, help="Run type label")
    parser.add_argument("--last-triage", default="", help="Optional last triage timestamp")
    args = parser.parse_args()

    records = load_records(Path(args.records))
    md = render_markdown(records, args.date_label, args.time_label, args.run_type)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md, encoding="utf-8")
    if args.html_output:
        html_out = Path(args.html_output)
        html_out.parent.mkdir(parents=True, exist_ok=True)
        html_out.write_text(
            render_html(records, args.date_label, args.time_label, args.run_type, last_triage=args.last_triage),
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
