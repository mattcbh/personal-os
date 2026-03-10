from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3
from typing import Any
import uuid
from zoneinfo import ZoneInfo

from triage_v2.classification import ACTION_KEYWORDS, group_to_threads, normalize_text
from triage_v2.config import AppConfig
from triage_v2.coverage import build_coverage_report
from triage_v2.db import (
    clear_entries_for_run,
    fetch_entries,
    get_checkpoint,
    insert_artifact_paths,
    insert_coverage_report,
    insert_draft_attempt,
    insert_entries,
    insert_messages,
    update_run_status,
    upsert_checkpoint,
)
from triage_v2.draft_authoring import DraftComposition, compose_thread_draft, deterministic_draft_body
from triage_v2.enrichment import EnrichmentInput, apply_bucket_hint, enrich_threads
from triage_v2.project_context import load_project_briefs, match_project_for_fields, match_project_for_thread
from triage_v2.providers.drafts import DraftRouter, GmailDraftAdapter, SuperhumanDraftAdapter
from triage_v2.providers.mail import as_dict, provider_from_mode
from triage_v2.providers.sender import sender_from_mode
from triage_v2.render import render_html, render_markdown
from triage_v2.types import Bucket, ThreadMessage, ThreadRecord
from triage_v2.validate import validate_threads

EASTERN = ZoneInfo("America/New_York")
ACKNOWLEDGEMENT_HINTS = (
    "got it",
    "sounds good",
    "we will go ahead",
    "we'll go ahead",
    "we will proceed",
    "we'll proceed",
    "we will process",
    "we'll process",
    "will take care of it",
    "just sent an invite",
)
SCHEDULING_REPLY_HINTS = (
    "let me know what works",
    "what works for you",
    "pretty free",
    "fairly open",
    "happy to chat",
    "coffee or call",
    "works well for me",
    "free outside of that window",
    "send over an invite",
)
AUTOMATED_SENDER_HINTS = ("noreply", "no-reply", "notification", "notifications", "calendar")


def generate_run_id() -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"triagev2-{ts}-{uuid.uuid4().hex[:8]}"


def _run_window_start(last_checkpoint: str | None) -> str:
    if last_checkpoint:
        return last_checkpoint
    cold_start = datetime.now(timezone.utc) - timedelta(hours=24)
    return cold_start.replace(microsecond=0).isoformat()


def _thread_to_dict(item: ThreadRecord) -> dict[str, Any]:
    return {
        "account": item.account,
        "thread_id": item.thread_id,
        "bucket": item.bucket,
        "sender_email": item.sender_email,
        "sender_name": item.sender_name,
        "subject_latest": item.subject_latest,
        "summary_latest": item.summary_latest,
        "response_needed": item.response_needed,
        "suggested_response": item.suggested_response,
        "suggested_action": item.suggested_action,
        "monitoring_owner": item.monitoring_owner,
        "monitoring_deliverable": item.monitoring_deliverable,
        "monitoring_deadline": item.monitoring_deadline,
        "draft_status": item.draft_status,
        "draft_authoring_mode": item.draft_authoring_mode,
        "draft_context_status": item.draft_context_status,
        "draft_authoring_error": item.draft_authoring_error,
        "thread_url": item.thread_url,
        "draft_url": item.draft_url,
        "unsubscribe_url": item.unsubscribe_url,
        "accounted_reason": item.accounted_reason,
        "message_ids": item.message_ids,
    }


def run_pipeline(
    *,
    conn: sqlite3.Connection,
    cfg: AppConfig,
    run_id: str,
    run_type: str,
    force_reconcile: bool = False,
) -> dict[str, Any]:
    update_run_status(conn, run_id, "running", send_status="pending")
    clear_entries_for_run(conn, run_id)

    provider = provider_from_mode(cfg)
    sender = sender_from_mode(cfg)

    superhuman_enabled = os.environ.get("TRIAGE_V2_SUPERHUMAN_ENABLED", "0") == "1"
    draft_router = DraftRouter(
        superhuman_adapter=SuperhumanDraftAdapter(cfg.superhuman_script_path, enabled=superhuman_enabled),
        gmail_adapter=GmailDraftAdapter(
            work_home=cfg.gmail_work_home,
            personal_home=cfg.gmail_personal_home,
        ),
        mode=cfg.draft_mode,
    )
    project_briefs = load_project_briefs(cfg.projects_dir)

    until_ts = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    all_messages = []

    for account in cfg.enabled_accounts:
        try:
            checkpoint = get_checkpoint(conn, account)
            since_ts = _run_window_start(checkpoint.get("last_message_ts"))
            fetch_result = provider.list_messages(
                account,
                since_ts=since_ts,
                until_ts=until_ts,
                since_history_id=checkpoint.get("history_id"),
                force_reconcile=force_reconcile,
            )
            msgs = fetch_result.messages
            all_messages.extend(msgs)

            latest_ts = msgs[-1].received_at if msgs else (checkpoint.get("last_message_ts") or until_ts)
            if latest_ts:
                upsert_checkpoint(conn, account, latest_ts, history_id=fetch_result.latest_history_id)
        except Exception as exc:
            msg = f"Ingest failed for {account} account: {exc}"
            update_run_status(conn, run_id, "failed", send_status="blocked", error_message=msg, finished=True)
            return {
                "run_id": run_id,
                "status": "failed",
                "reason": "ingest_failed",
                "errors": [msg],
            }

    insert_messages(conn, run_id, [as_dict(m) for m in all_messages])

    threads = group_to_threads(
        messages=all_messages,
        work_account_email=cfg.default_work_account,
        personal_account_email=cfg.default_personal_account,
    )
    thread_messages_cache: dict[tuple[str, str], list[ThreadMessage]] = {}
    latest_messages: dict[tuple[str, str], Any] = {}
    project_matches: dict[tuple[str, str], Any] = {}
    enrichment_inputs: list[EnrichmentInput] = []

    for item in threads:
        key = (item.account, item.thread_id)
        latest_message = _latest_message_for_thread(all_messages, item)
        latest_messages[key] = latest_message
        account_email = _account_email_for(cfg, item.account)
        thread_messages = _load_thread_messages(
            provider=provider,
            item=item,
            cache=thread_messages_cache,
        )
        project = _match_project_for_thread_context(
            item=item,
            latest_message=latest_message,
            thread_messages=thread_messages,
            project_briefs=project_briefs,
        )
        project_matches[key] = project
        if project:
            item.matched_project_name = project.name
            item.matched_project_priority = project.priority
        item.bucket = _refine_bucket_with_thread_context(
            item=item,
            latest_message=latest_message,
            thread_messages=thread_messages,
            account_email=account_email,
            matched_project_priority=item.matched_project_priority,
        )
        enrichment_inputs.append(
            EnrichmentInput(
                item=item,
                latest_message=latest_message,
                thread_messages=thread_messages,
                project=project,
            )
        )

    enrichments = enrich_threads(cfg, enrichment_inputs)
    for enrichment_input in enrichment_inputs:
        key = (enrichment_input.item.account, enrichment_input.item.thread_id)
        enrichment = enrichments.get(enrichment_input.key)
        if not enrichment:
            continue
        item = enrichment_input.item
        item.summary_latest = enrichment.summary_latest
        item.response_needed = enrichment.response_needed
        item.suggested_response = enrichment.suggested_response
        item.suggested_action = enrichment.suggested_action
        item.bucket = apply_bucket_hint(item.bucket, enrichment)

    for item in threads:
        key = (item.account, item.thread_id)
        if not item.response_needed:
            item.draft_status = "not_needed"
            item.draft_authoring_mode = "deterministic"
            item.draft_context_status = "unmatched"
            item.draft_authoring_error = None
            continue

        account_email = cfg.default_work_account if item.account == "work" else cfg.default_personal_account
        composition = _compose_with_thread_context(
            cfg=cfg,
            provider=provider,
            item=item,
            project=project_matches.get(key),
            thread_messages=thread_messages_cache.get(key),
        )
        item.draft_authoring_mode = composition.draft_authoring_mode
        item.draft_context_status = composition.draft_context_status
        item.draft_authoring_error = composition.draft_authoring_error

        attempts = draft_router.create(
            account=item.account,
            account_email=account_email,
            thread_id=item.thread_id,
            thread_url=item.thread_url,
            body_text=composition.body_text,
        )

        final_status = "failed"
        final_url = None
        for attempt in attempts:
            insert_draft_attempt(
                conn,
                run_id,
                item.account,
                item.thread_id,
                attempt.adapter,
                attempt.status,
                attempt.draft_url,
                attempt.error_message,
            )
            if attempt.status in {"ready", "fallback_gmail"}:
                final_status = attempt.status
                final_url = attempt.draft_url
                break
            final_status = attempt.status
            final_url = attempt.draft_url

        item.draft_status = final_status
        item.draft_url = final_url

    coverage = build_coverage_report([m.message_id for m in all_messages], threads)
    validation = validate_threads(threads)

    entries = [_thread_to_dict(item) for item in threads]
    insert_entries(conn, run_id, entries)

    coverage_payload = {
        "expected_count": coverage.expected_count,
        "accounted_count": coverage.accounted_count,
        "missing_count": coverage.missing_count,
        "duplicate_count": coverage.duplicate_count,
        "pass": coverage.passed,
        "expected_message_ids": coverage.expected_message_ids,
        "accounted_message_ids": coverage.accounted_message_ids,
        "missing_message_ids": coverage.missing_message_ids,
        "duplicate_thread_keys": coverage.duplicate_thread_keys,
    }
    insert_coverage_report(conn, run_id, coverage_payload)

    markdown = render_markdown(run_id=run_id, run_type=run_type, threads=threads)
    html = render_html(run_id=run_id, run_type=run_type, threads=threads)

    json_path = cfg.artifact_dir / f"{run_id}.entries.json"
    md_path = cfg.artifact_dir / f"{run_id}.md"
    html_path = cfg.artifact_dir / f"{run_id}.html"

    json_path.write_text(json.dumps(entries, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    md_path.write_text(markdown, encoding="utf-8")
    html_path.write_text(html, encoding="utf-8")

    insert_artifact_paths(conn, run_id, str(md_path), str(html_path), str(json_path))

    if not validation.ok:
        msg = "; ".join(validation.errors[:5])
        update_run_status(conn, run_id, "failed", send_status="blocked", error_message=msg, finished=True)
        return {
            "run_id": run_id,
            "status": "failed",
            "reason": "validation_failed",
            "errors": validation.errors,
            "coverage": coverage_payload,
        }

    if coverage.missing_count > 0 or coverage.duplicate_count > 0:
        msg = (
            f"Coverage invariant failed (missing={coverage.missing_count}, "
            f"duplicates={coverage.duplicate_count})"
        )
        update_run_status(conn, run_id, "failed", send_status="blocked", error_message=msg, finished=True)
        return {
            "run_id": run_id,
            "status": "failed",
            "reason": "coverage_failed",
            "errors": [msg],
            "coverage": coverage_payload,
        }

    subject = _subject_for_run(run_type, len(threads))
    try:
        send_result = sender.send(run_id=run_id, subject=subject, markdown_body=markdown, html_body=html)
    except Exception as exc:
        msg = f"Digest send failed: {exc}"
        update_run_status(conn, run_id, "failed", send_status="failed", error_message=msg, finished=True)
        return {
            "run_id": run_id,
            "status": "failed",
            "reason": "send_failed",
            "errors": [msg],
            "coverage": coverage_payload,
            "entries": len(entries),
        }
    update_run_status(conn, run_id, "succeeded", send_status=send_result.get("status", "sent"), finished=True)

    return {
        "run_id": run_id,
        "status": "succeeded",
        "coverage": coverage_payload,
        "send": send_result,
        "entries": len(entries),
    }


def retry_failed_drafts(conn: sqlite3.Connection, cfg: AppConfig, run_id: str) -> dict[str, Any]:
    rows = fetch_entries(conn, run_id)
    if not rows:
        return {"run_id": run_id, "retried": 0, "updated": 0}

    superhuman_enabled = os.environ.get("TRIAGE_V2_SUPERHUMAN_ENABLED", "0") == "1"
    router = DraftRouter(
        superhuman_adapter=SuperhumanDraftAdapter(cfg.superhuman_script_path, enabled=superhuman_enabled),
        gmail_adapter=GmailDraftAdapter(
            work_home=cfg.gmail_work_home,
            personal_home=cfg.gmail_personal_home,
        ),
        mode=cfg.draft_mode,
    )
    provider = provider_from_mode(cfg)
    project_briefs = load_project_briefs(cfg.projects_dir)

    retried = 0
    updated = 0
    for row in rows:
        if row.get("draft_status") not in {"failed", "fallback_gmail"}:
            continue
        retried += 1
        account = row["account"]
        account_email = cfg.default_work_account if account == "work" else cfg.default_personal_account
        stub = ThreadRecord(
            account=account,
            thread_id=row["thread_id"],
            message_ids=list(row.get("message_ids") or []),
            sender_email=str(row.get("sender_email") or ""),
            sender_name=str(row.get("sender_name") or ""),
            subject_latest=str(row.get("subject_latest") or ""),
            summary_latest=str(row.get("summary_latest") or ""),
            bucket=str(row.get("bucket") or "FYI"),
            response_needed=bool(row.get("response_needed")),
            suggested_response=str(row.get("suggested_response") or ""),
            suggested_action=str(row.get("suggested_action") or ""),
            monitoring_owner="",
            monitoring_deliverable="",
            monitoring_deadline="",
            draft_status=str(row.get("draft_status") or "failed"),
            thread_url=str(row.get("thread_url") or ""),
            draft_url=row.get("draft_url"),
            unsubscribe_url=row.get("unsubscribe_url"),
            accounted_reason=str(row.get("accounted_reason") or "included"),
            draft_authoring_mode=str(row.get("draft_authoring_mode") or "deterministic"),
            draft_context_status=str(row.get("draft_context_status") or "unmatched"),
            draft_authoring_error=row.get("draft_authoring_error"),
        )
        project = match_project_for_thread(stub, project_briefs)
        composition = _compose_with_thread_context(cfg=cfg, provider=provider, item=stub, project=project)

        attempts = router.create(
            account=account,
            account_email=account_email,
            thread_id=row["thread_id"],
            thread_url=row["thread_url"],
            body_text=composition.body_text,
        )

        for attempt in attempts:
            insert_draft_attempt(
                conn,
                run_id,
                account,
                row["thread_id"],
                attempt.adapter,
                attempt.status,
                attempt.draft_url,
                attempt.error_message,
            )
            if attempt.status in {"ready", "fallback_gmail"}:
                conn.execute(
                    """
                    UPDATE triage_entries
                    SET draft_status = ?, draft_url = ?, draft_authoring_mode = ?,
                        draft_context_status = ?, draft_authoring_error = ?
                    WHERE run_id = ? AND account = ? AND thread_id = ?
                    """,
                    (
                        attempt.status,
                        attempt.draft_url,
                        composition.draft_authoring_mode,
                        composition.draft_context_status,
                        composition.draft_authoring_error,
                        run_id,
                        account,
                        row["thread_id"],
                    ),
                )
                conn.commit()
                updated += 1
                break

    return {"run_id": run_id, "retried": retried, "updated": updated}


def _compose_with_thread_context(
    *,
    cfg: AppConfig,
    provider: Any,
    item: ThreadRecord,
    project: Any,
    thread_messages: list[Any] | None = None,
) -> DraftComposition:
    thread_messages = list(thread_messages or [])
    if item.response_needed and not thread_messages:
        try:
            thread_messages = provider.get_thread_messages(item.account, item.thread_id, limit=8)
        except Exception as exc:
            body = deterministic_draft_body(
                sender_name=item.sender_name,
                sender_email=item.sender_email,
                subject=item.subject_latest,
                summary=item.summary_latest,
                suggested_response=item.suggested_response,
                suggested_action=item.suggested_action,
                project=project,
            )
            return DraftComposition(
                body_text=body,
                draft_authoring_mode="fallback_deterministic",
                draft_context_status="authoring_error",
                draft_authoring_error=f"thread fetch failed: {str(exc)[:220]}",
            )
    return compose_thread_draft(cfg=cfg, item=item, thread_messages=thread_messages, project=project)


def _latest_message_for_thread(messages: list[Any], thread: ThreadRecord) -> Any:
    candidates = [m for m in messages if m.account == thread.account and m.thread_id == thread.thread_id]
    return max(candidates, key=lambda x: x.received_at)


def _account_email_for(cfg: AppConfig, account: str) -> str:
    return cfg.default_work_account if account == "work" else cfg.default_personal_account


def _load_thread_messages(
    *,
    provider: Any,
    item: ThreadRecord,
    cache: dict[tuple[str, str], list[ThreadMessage]],
) -> list[ThreadMessage]:
    key = (item.account, item.thread_id)
    if key in cache:
        return cache[key]
    try:
        cache[key] = provider.get_thread_messages(item.account, item.thread_id, limit=8)
    except Exception:
        cache[key] = []
    return cache[key]


def _match_project_for_thread_context(
    *,
    item: ThreadRecord,
    latest_message: Any,
    thread_messages: list[ThreadMessage],
    project_briefs: list[Any],
) -> Any:
    project = match_project_for_thread(item, project_briefs)
    if project or not thread_messages:
        return project

    participants = []
    subject_parts = []
    body_parts = []
    for row in thread_messages:
        if row.sender_name:
            participants.append(row.sender_name)
        if row.subject:
            subject_parts.append(row.subject)
        if row.body_text:
            body_parts.append(row.body_text)

    return match_project_for_fields(
        project_briefs,
        sender_email=latest_message.sender_email,
        sender_name=latest_message.sender_name,
        subject=" \n".join(subject_parts),
        summary=item.summary_latest,
        body="\n".join(body_parts),
        participants=participants,
        title=item.subject_latest,
    )


def _refine_bucket_with_thread_context(
    *,
    item: ThreadRecord,
    latest_message: Any,
    thread_messages: list[ThreadMessage],
    account_email: str,
    matched_project_priority: str,
) -> str:
    if item.bucket in {
        Bucket.ACTION_NEEDED.value,
        Bucket.MONITORING.value,
        Bucket.NEWSLETTERS.value,
        Bucket.SPAM_MARKETING.value,
    }:
        return item.bucket

    latest_text = _latest_message_text(latest_message)
    if _looks_like_acknowledgement(latest_text) and _has_prior_outbound(
        thread_messages, account_email, latest_message.received_at
    ):
        return Bucket.ALREADY_ADDRESSED.value

    if (
        item.bucket == Bucket.FYI.value
        and _is_high_priority_project(matched_project_priority)
        and _looks_like_scheduling_followup(latest_text)
    ):
        return Bucket.ACTION_NEEDED.value

    return item.bucket


def _thread_text_blob(latest_message: Any, thread_messages: list[ThreadMessage]) -> str:
    parts = [
        normalize_text(latest_message.subject),
        normalize_text(latest_message.snippet),
        normalize_text(latest_message.body_preview),
    ]
    for row in thread_messages[-4:]:
        parts.append(normalize_text(row.subject))
        parts.append(normalize_text(row.body_text))
    return "\n".join(part for part in parts if part).lower()


def _latest_message_text(latest_message: Any) -> str:
    return "\n".join(
        part
        for part in (
            normalize_text(latest_message.subject),
            normalize_text(latest_message.snippet),
            normalize_text(latest_message.body_preview),
        )
        if part
    ).lower()


def _has_prior_outbound(thread_messages: list[ThreadMessage], account_email: str, latest_received_at: str) -> bool:
    account_email = (account_email or "").strip().lower()
    for row in thread_messages:
        if row.received_at >= latest_received_at:
            continue
        if (row.sender_email or "").strip().lower() == account_email:
            return True
    return False


def _looks_like_acknowledgement(text: str) -> bool:
    if "?" in text:
        return False
    if any(keyword in text for keyword in ACTION_KEYWORDS):
        return False
    return any(hint in text for hint in ACKNOWLEDGEMENT_HINTS)


def _looks_like_scheduling_followup(text: str) -> bool:
    if any(hint in text for hint in SCHEDULING_REPLY_HINTS):
        return True
    if "?" not in text:
        return False
    return any(token in text for token in ("call", "coffee", "next week", "monday", "tuesday", "invite"))


def _is_high_priority_project(priority: str) -> bool:
    value = (priority or "").strip().upper()
    return value in {"P0", "P1"}


def _subject_for_run(run_type: str, thread_count: int) -> str:
    del run_type, thread_count
    dt = datetime.now(timezone.utc).astimezone(EASTERN)
    day = dt.day
    if 11 <= (day % 100) <= 13:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
    date_label = f"{dt.strftime('%A')}, {dt.strftime('%B')} {day}{suffix}, {dt.year}"
    time_label = dt.strftime("%-I:%M %p ET")
    return f"Inbox Triage {date_label} - {time_label}"


def load_required_fixture(path: Path) -> list[str]:
    if not path.exists():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, list):
        return sorted({str(v).strip() for v in raw if str(v).strip()})
    if isinstance(raw, dict):
        vals = raw.get("missing_message_ids", [])
        if isinstance(vals, list):
            return sorted({str(v).strip() for v in vals if str(v).strip()})
    return []


def verify_missed_fixture(conn: sqlite3.Connection, run_id: str, fixture_ids: list[str]) -> dict[str, Any]:
    entries = fetch_entries(conn, run_id)
    accounted: set[str] = set()
    for row in entries:
        for mid in row.get("message_ids", []):
            accounted.add(str(mid))
    missing = sorted(set(fixture_ids) - accounted)
    return {
        "run_id": run_id,
        "fixture_total": len(fixture_ids),
        "matched": len(fixture_ids) - len(missing),
        "missing": missing,
        "pass": len(missing) == 0,
    }
