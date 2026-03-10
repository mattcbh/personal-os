from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parseaddr
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any

from triage_v2.config import AppConfig
from triage_v2.llm_client import ClaudeCliJsonClient
from triage_v2.project_context import (
    ProjectBrief,
    ProjectContact,
    ProjectUpdate,
    RecentCommunication,
    NextAction,
    apply_project_update,
    build_project_excerpt,
    load_project_briefs,
    match_project_for_fields,
)


DEFAULT_REFRESH_STATE = {
    "last_successful_refresh_timestamp": None,
    "last_completed_refresh_timestamp": None,
    "last_meaningful_refresh_timestamp": None,
    "last_processed_event_timestamp": None,
    "last_processed_granola_sync_timestamp": None,
    "deferred_source_items": [],
    "warnings": [],
    "per_run_stats": [],
}
SOURCE_SNIPPET_LIMIT = 600
PROJECT_EXCERPT_LIMIT = 5000
MAX_WARNING_HISTORY = 20
MAX_RUN_STATS = 20
MAX_DEFERRED_SOURCE_ITEMS = 1000
SUMMARY_SECTION_RE = re.compile(r"(^##\s+Summary\s*$)(.*?)(?=^##\s+|\Z)", re.MULTILINE | re.DOTALL)
TRANSCRIPT_SECTION_RE = re.compile(r"(^##\s+Transcript\s*$)(.*?)(?=^##\s+|\Z)", re.MULTILINE | re.DOTALL)


@dataclass(frozen=True)
class SourceItem:
    item_id: str
    source_type: str
    timestamp: str
    title: str
    sender_name: str
    sender_email: str
    snippet: str
    body: str
    source_url: str | None = None
    participants: tuple[str, ...] = ()


def load_project_refresh_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return dict(DEFAULT_REFRESH_STATE)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return dict(DEFAULT_REFRESH_STATE)
    if not isinstance(raw, dict):
        return dict(DEFAULT_REFRESH_STATE)
    state = dict(DEFAULT_REFRESH_STATE)
    state.update(raw)
    if not isinstance(state.get("warnings"), list):
        state["warnings"] = []
    if not isinstance(state.get("per_run_stats"), list):
        state["per_run_stats"] = []
    if not isinstance(state.get("deferred_source_items"), list):
        state["deferred_source_items"] = []
    return state


def save_project_refresh_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def refresh_state_is_fresh(state: dict[str, Any], *, stale_hours: int) -> bool:
    for key in (
        "last_successful_refresh_timestamp",
        "last_meaningful_refresh_timestamp",
        "last_completed_refresh_timestamp",
    ):
        last = str(state.get(key) or "").strip()
        if not last:
            continue
        try:
            last_dt = _parse_iso(last)
        except Exception:
            continue
        if datetime.now(timezone.utc) - last_dt <= timedelta(hours=stale_hours):
            return True
    return False


def run_project_refresh(cfg: AppConfig) -> dict[str, Any]:
    state = load_project_refresh_state(cfg.project_refresh_state_path)
    warnings: list[str] = []
    now = _now_iso()

    granola_result = _run_granola_local_sync(cfg, warnings)
    sync_failed = str(granola_result.get("status") or "").lower() in {"error", "missing"}
    briefs = load_project_briefs(cfg.projects_dir)

    last_event_ts = str(state.get("last_processed_event_timestamp") or "").strip() or None
    last_granola_ts = str(state.get("last_processed_granola_sync_timestamp") or "").strip() or None

    deferred_items = _load_deferred_source_items(state)
    comms_items = load_comms_source_items(cfg.comms_events_path, since_ts=last_event_ts)
    transcript_items = load_transcript_source_items(cfg.granola_sync_state_path, since_ts=last_granola_ts)
    source_items = _dedupe_source_items([*deferred_items, *comms_items, *transcript_items])

    overflow_items: list[SourceItem] = []
    max_source_items = max(1, int(cfg.project_refresh_max_source_items))
    if len(source_items) > max_source_items:
        overflow_items = source_items[:-max_source_items]
        source_items = source_items[-max_source_items:]
        warnings.append(
            f"source backlog capped at {max_source_items} items; deferred {len(overflow_items)} older items"
        )

    grouped: dict[str, list[SourceItem]] = {}
    brief_by_name = {brief.name: brief for brief in briefs}
    unmatched_count = 0
    for item in source_items:
        brief = match_project_for_fields(
            briefs,
            sender_email=item.sender_email,
            sender_name=item.sender_name,
            subject=item.title,
            summary=item.snippet,
            body=item.body,
            participants=item.participants,
            title=item.title,
        )
        if not brief:
            unmatched_count += 1
            continue
        grouped.setdefault(brief.name, []).append(item)

    batch_failures = 0
    updated_projects: list[str] = []
    people_added = 0
    provider = cfg.project_refresh_provider
    batch_size = max(1, int(cfg.project_refresh_batch_size))
    deferred_retry_items: list[SourceItem] = list(overflow_items)
    for project_name, items in grouped.items():
        brief = brief_by_name[project_name]
        for start in range(0, len(items), batch_size):
            batch = items[start : start + batch_size]
            try:
                update, contacts = _project_batch_update(cfg=cfg, project=brief, batch=batch, provider=provider)
                if update.recent_communications or update.next_actions or update.match_signals:
                    brief = apply_project_update(brief, update, updated_date=now[:10])
                    brief_by_name[project_name] = brief
                    if project_name not in updated_projects:
                        updated_projects.append(project_name)
                if contacts:
                    people_added += append_contacts_to_people(
                        cfg.people_path,
                        contacts,
                        project_name=project_name,
                        added_date=now[:10],
                    )
            except Exception as exc:
                batch_failures += 1
                deferred_retry_items.extend(batch)
                warnings.append(f"{project_name} batch {start // batch_size + 1}: {str(exc)[:220]}")

    state["warnings"] = (warnings + list(state.get("warnings") or []))[:MAX_WARNING_HISTORY]
    state["last_completed_refresh_timestamp"] = now
    if updated_projects or people_added:
        state["last_meaningful_refresh_timestamp"] = now
    state["per_run_stats"] = [
        {
            "timestamp": now,
            "deferred_input_items": len(deferred_items),
            "comms_items": len(comms_items),
            "transcript_items": len(transcript_items),
            "processed_items": len(source_items),
            "matched_projects": len(grouped),
            "updated_projects": len(updated_projects),
            "people_added": people_added,
            "batch_failures": batch_failures,
            "granola_synced": int(granola_result.get("synced") or 0),
            "granola_failed": int(granola_result.get("failed") or 0),
            "unmatched_items": unmatched_count,
            "deferred_output_items": len(_dedupe_source_items(deferred_retry_items)),
        },
        *list(state.get("per_run_stats") or []),
    ][:MAX_RUN_STATS]

    if comms_items:
        state["last_processed_event_timestamp"] = max(item.timestamp for item in comms_items)
    elif state.get("last_processed_event_timestamp") is None and last_event_ts:
        state["last_processed_event_timestamp"] = last_event_ts
    if transcript_items:
        state["last_processed_granola_sync_timestamp"] = max(item.timestamp for item in transcript_items)
    elif state.get("last_processed_granola_sync_timestamp") is None and last_granola_ts:
        state["last_processed_granola_sync_timestamp"] = last_granola_ts

    if batch_failures == 0 and not sync_failed:
        state["last_successful_refresh_timestamp"] = now

    state["deferred_source_items"] = [
        _serialize_source_item(item)
        for item in _dedupe_source_items(deferred_retry_items)[-MAX_DEFERRED_SOURCE_ITEMS:]
    ]

    save_project_refresh_state(cfg.project_refresh_state_path, state)
    return {
        "status": "succeeded" if batch_failures == 0 and not sync_failed else "partial_failure",
        "updated_projects": updated_projects,
        "comms_items": len(comms_items),
        "transcript_items": len(transcript_items),
        "deferred_items": len(state["deferred_source_items"]),
        "people_added": people_added,
        "warnings": warnings,
        "granola": granola_result,
        "state_path": str(cfg.project_refresh_state_path),
    }


def load_comms_source_items(path: Path, *, since_ts: str | None) -> list[SourceItem]:
    if not path.exists():
        return []

    cutoff = _parse_iso(since_ts) if since_ts else None
    out: list[SourceItem] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except Exception:
            continue
        if not isinstance(item, dict):
            continue
        timestamp = str(item.get("timestamp") or "").strip()
        if not timestamp:
            continue
        try:
            dt = _parse_iso(timestamp)
        except Exception:
            continue
        if cutoff and dt <= cutoff:
            continue

        channel = str(item.get("channel") or "").strip().lower()
        if channel == "email":
            sender_raw = str(item.get("sender") or "").strip()
            sender_name, sender_email = parseaddr(sender_raw)
            sender_email = sender_email.strip().lower()
            sender_name = (sender_name or sender_email or sender_raw).strip()
            out.append(
                SourceItem(
                    item_id=str(item.get("event_id") or item.get("message_id") or ""),
                    source_type="Email",
                    timestamp=timestamp,
                    title=str(item.get("subject") or "(no subject)").strip(),
                    sender_name=sender_name,
                    sender_email=sender_email,
                    snippet=_clean_inline(str(item.get("snippet") or "")),
                    body=_clean_inline(str(item.get("snippet") or "")),
                    source_url=(
                        str(item.get("source_url_superhuman") or item.get("source_url_gmail") or "").strip() or None
                    ),
                )
            )
            continue

        if channel == "chat":
            author = str(item.get("author") or "").strip()
            text = _clean_inline(str(item.get("text") or ""))
            if not text:
                continue
            out.append(
                SourceItem(
                    item_id=str(item.get("event_id") or item.get("message_id") or ""),
                    source_type="Beeper",
                    timestamp=timestamp,
                    title=str(item.get("chat_title") or author or "Beeper thread").strip(),
                    sender_name=author or str(item.get("chat_title") or "").strip() or "Unknown",
                    sender_email="",
                    snippet=text,
                    body=text,
                    source_url=None,
                    participants=tuple(
                        piece.strip()
                        for piece in (str(item.get("chat_title") or "").split(","))
                        if piece.strip()
                    ),
                )
            )
    return out


def load_transcript_source_items(path: Path, *, since_ts: str | None) -> list[SourceItem]:
    if not path.exists():
        return []
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    synced = state.get("synced_meetings") if isinstance(state, dict) else None
    if not isinstance(synced, dict):
        return []

    cutoff = _parse_iso(since_ts) if since_ts else None
    out: list[SourceItem] = []
    for meeting_id, meta in synced.items():
        if not isinstance(meta, dict):
            continue
        synced_at = str(meta.get("synced_at") or "").strip()
        if not synced_at:
            continue
        try:
            synced_dt = _parse_iso(synced_at)
        except Exception:
            continue
        if cutoff and synced_dt <= cutoff:
            continue

        filepath_str = str(meta.get("filepath") or "").strip()
        if not filepath_str:
            continue
        filepath = Path(filepath_str)
        if not filepath.is_file():
            continue
        parsed = _parse_transcript_markdown(filepath)
        if not parsed["title"]:
            continue
        out.append(
            SourceItem(
                item_id=f"transcript:{meeting_id}",
                source_type="Transcript",
                timestamp=synced_at,
                title=parsed["title"],
                sender_name=", ".join(parsed["participants"][:2]) if parsed["participants"] else parsed["title"],
                sender_email="",
                snippet=_truncate(parsed["summary"] or parsed["transcript"], SOURCE_SNIPPET_LIMIT),
                body=_truncate("\n".join(filter(None, [parsed["summary"], parsed["transcript"]])), SOURCE_SNIPPET_LIMIT),
                source_url=str(filepath),
                participants=tuple(parsed["participants"]),
            )
        )
    return sorted(out, key=lambda item: item.timestamp)


def append_contacts_to_people(
    people_path: Path,
    contacts: list[ProjectContact],
    *,
    project_name: str,
    added_date: str,
) -> int:
    if not contacts:
        return 0
    existing = people_path.read_text(encoding="utf-8") if people_path.exists() else "## Key People\n"
    added = 0
    if "### Auto-added by Project Refresh" not in existing:
        suffix = "" if existing.endswith("\n") else "\n"
        existing = f"{existing}{suffix}\n### Auto-added by Project Refresh\n\n"

    for contact in contacts:
        email = (contact.contact or "").strip().lower()
        if email and email in existing.lower():
            continue
        if f"**{contact.name}**" in existing:
            continue
        line = f"- **{contact.name}** - {contact.role}. Contact: {contact.contact or 'Unknown'}. Context: {project_name}. Added {added_date}."
        insertion = existing.find("### Auto-added by Project Refresh")
        if insertion >= 0:
            header_end = existing.find("\n", insertion)
            existing = f"{existing[:header_end + 1]}\n{line}\n{existing[header_end + 1:]}"
        else:
            existing = existing.rstrip() + f"\n\n### Auto-added by Project Refresh\n\n{line}\n"
        added += 1

    if added:
        people_path.write_text(existing, encoding="utf-8")
    return added


def _project_batch_update(
    *,
    cfg: AppConfig,
    project: ProjectBrief,
    batch: list[SourceItem],
    provider: str,
) -> tuple[ProjectUpdate, list[ProjectContact]]:
    if provider == "mock":
        return _mock_project_update(project=project, batch=batch)
    if provider != "claude_cli":
        raise RuntimeError(f"Unsupported project refresh provider: {provider}")

    prompt = _build_project_refresh_prompt(project=project, batch=batch)
    client = ClaudeCliJsonClient(
        binary_path=cfg.claude_path,
        model=cfg.project_refresh_model,
        timeout_seconds=cfg.project_refresh_timeout_seconds,
    )
    payload = client.generate_json(
        prompt=prompt,
        system_prompt=(
            "You maintain structured project briefs. Return JSON only. "
            "Do not rewrite the whole brief. Only summarize the provided source items into structured updates."
        ),
    )
    return _parse_project_update_payload(payload)


def _build_project_refresh_prompt(*, project: ProjectBrief, batch: list[SourceItem]) -> str:
    source_lines = []
    for index, item in enumerate(batch, start=1):
        snippet = _truncate(item.snippet or item.body, SOURCE_SNIPPET_LIMIT)
        participants = f" | Participants: {', '.join(item.participants)}" if item.participants else ""
        sender = f" | From: {item.sender_name} <{item.sender_email}>" if item.sender_email else f" | From: {item.sender_name}"
        url = f" | Source URL: {item.source_url}" if item.source_url else ""
        source_lines.append(
            f"[{index}] {item.timestamp} | {item.source_type} | {item.title}{sender}{participants}{url}\n"
            f"Snippet: {snippet}"
        )

    return "\n".join(
        [
            "Update this project brief using only the new source items below.",
            "",
            "Return JSON only with this exact structure:",
            "{",
            '  "recent_communications": [{"date":"YYYY-MM-DD","source":"Email|Beeper|Transcript","title":"...","bullets":["..."]}],',
            '  "next_actions": [{"action":"...","owner":"Matt","due":"ASAP","source":"..."}],',
            '  "match_signals": ["..."],',
            '  "important_contacts": [{"name":"...","role":"...","contact":"...","context":"..."}]',
            "}",
            "",
            "Rules:",
            "- Only include materially relevant updates.",
            "- Keep bullets factual and concise.",
            "- Do not invent facts, deadlines, or people.",
            "- Prefer adding at most 5 next actions and 5 match signals.",
            "- Important contacts should only include people worth adding to a shared people file.",
            "",
            "Current project excerpt:",
            _truncate(build_project_excerpt(project, max_recent=8), PROJECT_EXCERPT_LIMIT),
            "",
            "New source items:",
            "\n\n".join(source_lines),
        ]
    ).strip()


def _parse_project_update_payload(payload: dict[str, Any]) -> tuple[ProjectUpdate, list[ProjectContact]]:
    recent_entries: list[RecentCommunication] = []
    next_actions: list[NextAction] = []
    match_signals: list[str] = []
    contacts: list[ProjectContact] = []

    raw_recent = payload.get("recent_communications")
    if isinstance(raw_recent, list):
        for item in raw_recent:
            if not isinstance(item, dict):
                continue
            date = str(item.get("date") or "").strip()
            source = str(item.get("source") or "").strip() or "Email"
            title = _clean_inline(str(item.get("title") or ""))
            bullets_raw = item.get("bullets")
            bullets = []
            if isinstance(bullets_raw, list):
                bullets = [_clean_inline(str(v)) for v in bullets_raw if _clean_inline(str(v))]
            if date and title and bullets:
                recent_entries.append(
                    RecentCommunication(date=date, source=source, title=title, bullets=tuple(bullets[:4]))
                )

    raw_actions = payload.get("next_actions")
    if isinstance(raw_actions, list):
        for item in raw_actions:
            if not isinstance(item, dict):
                continue
            action = _clean_inline(str(item.get("action") or ""))
            if not action:
                continue
            next_actions.append(
                NextAction(
                    action=action,
                    owner=_clean_inline(str(item.get("owner") or "Matt")) or "Matt",
                    due=_clean_inline(str(item.get("due") or "ASAP")) or "ASAP",
                    source=_clean_inline(str(item.get("source") or "Project refresh")) or "Project refresh",
                )
            )

    raw_signals = payload.get("match_signals")
    if isinstance(raw_signals, list):
        for value in raw_signals:
            cleaned = _clean_inline(str(value))
            if cleaned:
                match_signals.append(cleaned)

    raw_contacts = payload.get("important_contacts")
    if isinstance(raw_contacts, list):
        for item in raw_contacts:
            if not isinstance(item, dict):
                continue
            name = _clean_inline(str(item.get("name") or ""))
            if not name:
                continue
            contacts.append(
                ProjectContact(
                    name=name,
                    role=_clean_inline(str(item.get("role") or "Important contact")) or "Important contact",
                    contact=_clean_inline(str(item.get("contact") or "")),
                    context=_clean_inline(str(item.get("context") or "")),
                )
            )

    return (
        ProjectUpdate(
            recent_communications=tuple(recent_entries[: len(recent_entries)]),
            next_actions=tuple(next_actions[:5]),
            match_signals=tuple(match_signals[:5]),
        ),
        contacts[:3],
    )


def _mock_project_update(*, project: ProjectBrief, batch: list[SourceItem]) -> tuple[ProjectUpdate, list[ProjectContact]]:
    recent: list[RecentCommunication] = []
    actions: list[NextAction] = []
    for item in batch:
        recent.append(
            RecentCommunication(
                date=item.timestamp[:10],
                source=item.source_type,
                title=item.title,
                bullets=tuple(filter(None, [_truncate(item.snippet or item.body, 160)])),
            )
        )
        action = _derive_action_from_source(item, project)
        if action:
            actions.append(action)
    return ProjectUpdate(tuple(recent), tuple(actions[:5]), ()), []


def _derive_action_from_source(item: SourceItem, project: ProjectBrief) -> NextAction | None:
    blob = f"{item.title} {item.snippet} {item.body}".lower()
    if any(word in blob for word in ("approve", "review", "reply", "payment", "deadline", "due", "follow up")):
        return NextAction(
            action=f"Review {item.title} and reply with the next step",
            owner="Matt",
            due="ASAP",
            source=f"{item.source_type} {item.timestamp[:10]}",
        )
    if item.source_type == "Transcript" and project.name.lower() in blob:
        return NextAction(
            action=f"Review {item.title} takeaways and confirm follow-up",
            owner="Matt",
            due="ASAP",
            source=f"Transcript {item.timestamp[:10]}",
        )
    return None


def _run_granola_local_sync(cfg: AppConfig, warnings: list[str]) -> dict[str, Any]:
    if os.environ.get("TRIAGE_V2_SKIP_GRANOLA_LOCAL_SYNC", "0") == "1":
        return {"status": "skipped", "synced": 0, "failed": 0}
    if not cfg.meeting_sync_fetch_path.exists():
        warnings.append(f"meeting sync helper missing: {cfg.meeting_sync_fetch_path}")
        return {"status": "missing", "synced": 0, "failed": 0}

    try:
        result = subprocess.run(
            [sys.executable, str(cfg.meeting_sync_fetch_path), "--sync-local"],
            capture_output=True,
            text=True,
            check=False,
            timeout=180,
        )
    except Exception as exc:
        warnings.append(f"granola local sync invocation failed: {str(exc)[:220]}")
        return {"status": "error", "synced": 0, "failed": 0}

    stdout = (result.stdout or "").strip()
    if result.returncode != 0:
        warnings.append(f"granola local sync failed: {(result.stderr or stdout or 'unknown')[:220]}")
        return {"status": "error", "synced": 0, "failed": 0}
    try:
        payload = json.loads(stdout) if stdout else {}
    except Exception:
        warnings.append("granola local sync returned invalid JSON")
        return {"status": "error", "synced": 0, "failed": 0}
    if not isinstance(payload, dict):
        warnings.append("granola local sync returned unexpected payload")
        return {"status": "error", "synced": 0, "failed": 0}
    return payload


def _parse_transcript_markdown(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    title_match = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else path.stem

    participants = []
    people_match = re.search(r"^\*\*Participants:\*\*\s*(.+)$", text, re.MULTILINE)
    if people_match:
        participants = [piece.strip() for piece in people_match.group(1).split(",") if piece.strip()]

    summary_match = SUMMARY_SECTION_RE.search(text)
    summary = _collapse_block(summary_match.group(2) if summary_match else "")
    transcript_match = TRANSCRIPT_SECTION_RE.search(text)
    transcript = _collapse_block(transcript_match.group(2) if transcript_match else "")

    return {
        "title": title,
        "participants": participants,
        "summary": summary,
        "transcript": transcript,
    }


def _collapse_block(text: str) -> str:
    lines = []
    for raw_line in (text or "").splitlines():
        stripped = raw_line.strip()
        if stripped.startswith("- "):
            lines.append(stripped[2:].strip())
        elif stripped and not stripped.startswith("#"):
            lines.append(stripped)
    return _clean_inline(" ".join(lines))


def _clean_inline(text: str) -> str:
    return " ".join((text or "").split()).strip()


def _truncate(text: str, limit: int) -> str:
    value = _clean_inline(text)
    if len(value) <= limit:
        return value
    clipped = value[: limit - 3].rstrip()
    if " " in clipped:
        clipped = clipped.rsplit(" ", 1)[0]
    return clipped + "..."


def _parse_iso(value: str) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _serialize_source_item(item: SourceItem) -> dict[str, Any]:
    return {
        "item_id": item.item_id,
        "source_type": item.source_type,
        "timestamp": item.timestamp,
        "title": item.title,
        "sender_name": item.sender_name,
        "sender_email": item.sender_email,
        "snippet": item.snippet,
        "body": item.body,
        "source_url": item.source_url,
        "participants": list(item.participants),
    }


def _deserialize_source_item(payload: dict[str, Any]) -> SourceItem | None:
    if not isinstance(payload, dict):
        return None
    timestamp = str(payload.get("timestamp") or "").strip()
    item_id = str(payload.get("item_id") or "").strip()
    if not timestamp or not item_id:
        return None
    try:
        _parse_iso(timestamp)
    except Exception:
        return None
    participants = payload.get("participants")
    if not isinstance(participants, list):
        participants = []
    return SourceItem(
        item_id=item_id,
        source_type=str(payload.get("source_type") or "").strip() or "Unknown",
        timestamp=timestamp,
        title=str(payload.get("title") or "").strip() or "(untitled)",
        sender_name=str(payload.get("sender_name") or "").strip(),
        sender_email=str(payload.get("sender_email") or "").strip(),
        snippet=str(payload.get("snippet") or "").strip(),
        body=str(payload.get("body") or "").strip(),
        source_url=str(payload.get("source_url") or "").strip() or None,
        participants=tuple(str(piece).strip() for piece in participants if str(piece).strip()),
    )


def _load_deferred_source_items(state: dict[str, Any]) -> list[SourceItem]:
    items: list[SourceItem] = []
    for raw in state.get("deferred_source_items") or []:
        item = _deserialize_source_item(raw)
        if item is not None:
            items.append(item)
    return _dedupe_source_items(items)


def _dedupe_source_items(items: list[SourceItem]) -> list[SourceItem]:
    seen: set[str] = set()
    ordered: list[SourceItem] = []
    for item in sorted(items, key=lambda value: (value.timestamp, value.item_id)):
        if item.item_id in seen:
            continue
        seen.add(item.item_id)
        ordered.append(item)
    return ordered
