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
    "Already Addressed": "#3f6b4f",
    "Monitoring": "#8b6a2f",
    "FYI": "#111111",
    "Newsletters": "#111111",
    "Spam / Marketing": "#111111",
}

ENTRY_STYLES = {
    "Action Needed": "margin:0 0 9px 0;background:#f7f7f7;border:1px solid #d1d5db;border-radius:6px;padding:10px 12px;font-size:15.5px;line-height:1.38;color:#111111;",
    "Already Addressed": "margin:0 0 9px 0;background:#eef3ee;border:1px solid #c7dccd;border-radius:6px;padding:10px 12px;font-size:15.5px;line-height:1.38;color:#1f2937;",
    "Monitoring": "margin:0 0 9px 0;background:#f6f0de;border:1px solid #ead7ad;border-radius:6px;padding:10px 12px;font-size:15.5px;line-height:1.38;color:#111111;",
    "FYI": "margin:0 0 8px 0;padding:0;font-size:15.5px;line-height:1.38;color:#1f2937;",
    "Newsletters": "margin:0 0 8px 0;padding:0;font-size:15.5px;line-height:1.38;color:#1f2937;",
    "Spam / Marketing": "margin:0 0 6px 0;padding:0;font-size:14px;line-height:1.34;color:#374151;",
}

LINK_STYLE = "color:#2f6fa3;text-decoration:none;"
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


def summary_for_record(rec: dict[str, Any]) -> str:
    for field in SUMMARY_FIELDS:
        val = clean_text(rec.get(field))
        if val:
            return clip_text(val)
    return ""


def non_link_email(sender: str) -> str:
    """
    Render sender emails in a way that avoids auto-linkification in HTML clients.
    """
    text = clean_text(sender)
    if not text:
        return ""
    return text.replace("@", "&#8204;@&#8204;").replace(".", "&#8204;.&#8204;")


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


def thread_url(account: str, thread_id: str) -> str:
    if account == "personal":
        return f"https://mail.superhuman.com/lieber.matt@gmail.com/thread/{thread_id}"
    return f"https://mail.superhuman.com/matt@cornerboothholdings.com/thread/{thread_id}"


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


def render_entry(rec: dict[str, Any], bucket: str) -> list[str]:
    account = str(rec.get("account") or "work").lower()
    tid = str(rec.get("threadId") or "").strip()
    sender = str(rec.get("sender_email") or "unknown sender").strip()
    subject = str(rec.get("subject_latest") or "(no subject)").strip()
    draft_status = str(rec.get("draft_status") or "none").strip().lower()
    unsub = rec.get("unsubscribe_url")
    link = thread_url(account, tid)

    lines: list[str] = [f"**{subject}** -- from {sender}"]
    summary = summary_for_record(rec)
    if summary:
        lines.append(summary)

    if bucket == "Action Needed":
        suggested_action = clean_text(rec.get("suggested_action"))
        if suggested_action:
            lines.append(f"Suggest: {clip_text(suggested_action, max_len=220)}")
    elif bucket == "Monitoring":
        owner = clean_text(rec.get("monitoring_owner"))
        deliverable = clean_text(rec.get("monitoring_deliverable"))
        deadline = clean_text(rec.get("monitoring_deadline"))
        if owner or deliverable or deadline:
            monitor_parts = []
            if owner:
                monitor_parts.append(f"Owner: {owner}")
            if deliverable:
                monitor_parts.append(f"Deliverable: {deliverable}")
            if deadline:
                monitor_parts.append(f"Deadline: {deadline}")
            lines.append(" | ".join(monitor_parts))

    if bucket == "Action Needed":
        if draft_status == "queued":
            lines.append(f"[Draft ready]({link})")
            lines.append("Draft status: queued")
        else:
            lines.append(f"[View thread]({link})")
            if draft_status == "clipboard":
                lines.append("Draft in clipboard.")
    elif bucket == "FYI":
        if draft_status == "queued":
            lines.append(f"[Courtesy draft ready]({link})")
            lines.append("Draft status: queued")
        else:
            lines.append(f"[View]({link})")
            if draft_status == "clipboard":
                lines.append("Draft in clipboard.")
            elif draft_status == "failed":
                lines.append("No draft.")
    elif bucket in {"Newsletters", "Spam / Marketing"}:
        if isinstance(unsub, str) and unsub.strip():
            unsub_val = unsub.strip()
            if unsub_val.startswith("http://") or unsub_val.startswith("https://"):
                lines.append(f"[View]({link}) | [Unsubscribe]({unsub_val})")
            else:
                lines.append(f"[View]({link}) | Unsubscribe unavailable")
        else:
            lines.append(f"[View]({link}) | Unsubscribe unavailable")
    else:
        lines.append(f"[View]({link})")

    return lines


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
                for entry_line in render_entry(rec, bucket):
                    lines.append(entry_line)
                lines.append("")

    return "\n".join(lines).strip() + "\n"


def render_html_entry(rec: dict[str, Any], bucket: str) -> str:
    account = str(rec.get("account") or "work").lower()
    tid = str(rec.get("threadId") or "").strip()
    sender = non_link_email(str(rec.get("sender_email") or "unknown sender").strip())
    subject = html.escape(str(rec.get("subject_latest") or "(no subject)").strip())
    draft_status = str(rec.get("draft_status") or "none").strip().lower()
    unsub = rec.get("unsubscribe_url")
    link = html.escape(thread_url(account, tid), quote=True)

    content_lines = [f"<b>{subject}</b> -- from <span style=\"color:#1f2937;text-decoration:none;\">{sender}</span>"]
    summary = summary_for_record(rec)
    if summary:
        content_lines.append(html.escape(summary))

    if bucket == "Action Needed":
        suggested_action = clean_text(rec.get("suggested_action"))
        if suggested_action:
            content_lines.append(f"Suggest: {html.escape(clip_text(suggested_action, max_len=220))}")
    elif bucket == "Monitoring":
        owner = clean_text(rec.get("monitoring_owner"))
        deliverable = clean_text(rec.get("monitoring_deliverable"))
        deadline = clean_text(rec.get("monitoring_deadline"))
        if owner or deliverable or deadline:
            monitor_parts = []
            if owner:
                monitor_parts.append(f"Owner: {owner}")
            if deliverable:
                monitor_parts.append(f"Deliverable: {deliverable}")
            if deadline:
                monitor_parts.append(f"Deadline: {deadline}")
            content_lines.append(html.escape(" | ".join(monitor_parts)))

    if bucket == "Action Needed":
        if draft_status == "queued":
            content_lines.append(f'<a href="{link}" style="{LINK_STYLE}">Draft ready</a>')
            content_lines.append("Draft status: queued")
        else:
            content_lines.append(f'<a href="{link}" style="{LINK_STYLE}">View thread</a>')
            if draft_status == "clipboard":
                content_lines.append("Draft in clipboard.")
    elif bucket == "FYI":
        if draft_status == "queued":
            content_lines.append(f'<a href="{link}" style="{LINK_STYLE}">Courtesy draft ready</a>')
            content_lines.append("Draft status: queued")
        else:
            content_lines.append(f'<a href="{link}" style="{LINK_STYLE}">View</a>')
            if draft_status == "clipboard":
                content_lines.append("Draft in clipboard.")
    elif bucket in {"Newsletters", "Spam / Marketing"}:
        if isinstance(unsub, str) and unsub.strip():
            unsub_val = unsub.strip()
            if unsub_val.startswith("http://") or unsub_val.startswith("https://"):
                unsub_url = html.escape(unsub_val, quote=True)
                content_lines.append(
                    f'<a href="{link}" style="{LINK_STYLE}">View</a> | '
                    f'<a href="{unsub_url}" style="{LINK_STYLE}">Unsubscribe</a>'
                )
            else:
                content_lines.append(f'<a href="{link}" style="{LINK_STYLE}">View</a> | Unsubscribe unavailable')
        else:
            content_lines.append(f'<a href="{link}" style="{LINK_STYLE}">View</a> | Unsubscribe unavailable')
    else:
        content_lines.append(f'<a href="{link}" style="{LINK_STYLE}">View</a>')

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
    short_date = short_date_label(date_label)
    since_line = since_triage_label(last_triage, new_count)
    lines.append(
        '    <p style="font-size:13px;font-weight:700;color:#3f3f46;margin:0 0 4px 0;">'
        f'Note to self <span style="float:right;color:#6b7280;">{html.escape(short_date)}</span></p>'
    )
    lines.append(
        f'    <p style="font-size:13.5px;color:#6b7280;margin:0 0 14px 0;">{html.escape(since_line)}</p>'
    )
    lines.append(
        f'    <p style="font-size:13.5px;color:#6b7280;margin:0 0 10px 0;">Run type: {html.escape(run_type)}</p>'
    )

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
