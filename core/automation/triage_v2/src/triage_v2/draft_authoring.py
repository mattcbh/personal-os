from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
import re

from triage_v2.config import AppConfig
from triage_v2.context_pack import extract_top_priorities, load_text_excerpt, sender_context_snippets
from triage_v2.llm_client import ClaudeCliJsonClient, LlmClientError
from triage_v2.project_context import ProjectBrief, build_project_excerpt
from triage_v2.project_refresh import load_project_refresh_state, refresh_state_is_fresh
from triage_v2.types import ThreadMessage, ThreadRecord


THREAD_LIMIT = 8
PER_MESSAGE_LIMIT = 2000
TOTAL_THREAD_LIMIT = 12000
PROJECT_EXCERPT_LIMIT = 6000
POLICY_LIMIT = 2400
STYLE_LIMIT = 3800


@dataclass(frozen=True)
class DraftComposition:
    body_text: str
    draft_authoring_mode: str
    draft_context_status: str
    draft_authoring_error: str | None = None


def compose_thread_draft(
    *,
    cfg: AppConfig,
    item: ThreadRecord,
    thread_messages: list[ThreadMessage],
    project: ProjectBrief | None,
) -> DraftComposition:
    deterministic = deterministic_draft_body(
        sender_name=item.sender_name,
        sender_email=item.sender_email,
        subject=item.subject_latest,
        summary=item.summary_latest,
        suggested_response=item.suggested_response,
        suggested_action=item.suggested_action,
        project=project,
    )

    refresh_state = load_project_refresh_state(cfg.project_refresh_state_path)
    context_status = "unmatched" if project is None else "fresh"

    if not item.response_needed:
        return DraftComposition(
            body_text=deterministic,
            draft_authoring_mode="deterministic",
            draft_context_status=context_status,
        )

    if cfg.draft_authoring_mode != "llm_with_fallback":
        return DraftComposition(
            body_text=deterministic,
            draft_authoring_mode="deterministic",
            draft_context_status=context_status,
        )

    if project and not _project_context_is_fresh(
        project=project,
        refresh_state=refresh_state,
        stale_hours=cfg.project_refresh_stale_hours,
    ):
        return DraftComposition(
            body_text=deterministic,
            draft_authoring_mode="fallback_deterministic",
            draft_context_status="stale",
            draft_authoring_error="project refresh stale",
        )

    try:
        draft_text = _author_llm_draft(
            cfg=cfg,
            item=item,
            thread_messages=thread_messages,
            project=project,
        )
    except Exception as exc:
        return DraftComposition(
            body_text=deterministic,
            draft_authoring_mode="fallback_deterministic",
            draft_context_status="authoring_error",
            draft_authoring_error=_truncate(str(exc), 260),
        )

    return DraftComposition(
        body_text=draft_text,
        draft_authoring_mode="llm",
        draft_context_status=context_status,
    )


def deterministic_draft_body(
    *,
    sender_name: str,
    sender_email: str,
    subject: str,
    summary: str,
    suggested_response: str,
    suggested_action: str,
    project: ProjectBrief | None,
) -> str:
    first_name = _first_name(sender_name, sender_email)
    greeting = f"Hi {first_name}," if first_name else "Hi,"
    subj = _clean_text(subject, limit=120) or "your note"
    summ = _clean_text(summary, limit=170)
    response = _clean_text(suggested_response, limit=220).rstrip(".")
    action = _specific_action(
        suggested_action=suggested_action,
        subject=subject,
        summary=summary,
        project=project,
    ).rstrip(".")

    lines: list[str] = [greeting, ""]
    lines.append(f"I reviewed your note on {subj}.")
    if summ:
        lines.append(f"My read: {summ}.")

    if response:
        lines.append(response + ".")
    elif project:
        lines.append(f"For {project.name}, next step: I will {action}.")
        if project.next_actions:
            hint = _clean_text(project.next_actions[0].action, limit=130).rstrip(".")
            lines.append(f"I will keep this aligned with our current priority: {hint}.")
    else:
        lines.append(f"Next step: I will {action}.")

    lines.append("")
    lines.append("Best,")
    lines.append("Matt")
    return "\n".join(lines)


def _author_llm_draft(
    *,
    cfg: AppConfig,
    item: ThreadRecord,
    thread_messages: list[ThreadMessage],
    project: ProjectBrief | None,
) -> str:
    if cfg.draft_authoring_provider == "mock":
        return _mock_draft(item=item, project=project)
    if cfg.draft_authoring_provider != "claude_cli":
        raise RuntimeError(f"Unsupported draft authoring provider: {cfg.draft_authoring_provider}")

    prompt = _build_draft_prompt(cfg=cfg, item=item, thread_messages=thread_messages, project=project)
    client = ClaudeCliJsonClient(
        binary_path=cfg.claude_path,
        model=cfg.draft_authoring_model,
        timeout_seconds=cfg.draft_authoring_timeout_seconds,
    )
    data = client.generate_json(
        prompt=prompt,
        system_prompt=(
            "You write concise plain-text email replies for Matt Lieber. "
            "Return a single JSON object only. Do not include markdown fences or commentary."
        ),
    )
    draft_text = str(data.get("draft_text") or "").strip()
    if not draft_text:
        raise LlmClientError("draft_text missing from LLM response")
    return _normalize_email_body(draft_text)


def _mock_draft(*, item: ThreadRecord, project: ProjectBrief | None) -> str:
    first_name = _first_name(item.sender_name, item.sender_email)
    greeting = f"Hi {first_name}," if first_name else "Hi,"
    lines = [greeting, ""]
    lines.append(f"I saw your note about {item.subject_latest}.")
    if item.suggested_response:
        lines.append(item.suggested_response.rstrip(".") + ".")
    elif project:
        lines.append(f"I’m handling this in the context of {project.name}.")
        if project.next_actions:
            lines.append(f"My next step is {project.next_actions[0].action.lower().rstrip('.')}.")
    else:
        lines.append("I’m on it and will follow up with the next step shortly.")
    lines.append("")
    lines.append("Best,")
    lines.append("Matt")
    return "\n".join(lines)


def _project_context_is_fresh(
    *,
    project: ProjectBrief,
    refresh_state: dict[str, object],
    stale_hours: int,
) -> bool:
    if refresh_state_is_fresh(refresh_state, stale_hours=stale_hours):
        return True
    return _project_brief_is_recent(project, stale_hours=stale_hours)


def _project_brief_is_recent(project: ProjectBrief, *, stale_hours: int) -> bool:
    raw = (project.last_updated or "").strip()
    if not raw:
        return False

    for parser in (_parse_brief_datetime, _parse_brief_date):
        dt = parser(raw)
        if dt is None:
            continue
        if datetime.now(timezone.utc) - dt <= timedelta(hours=stale_hours):
            return True
    return False


def _parse_brief_datetime(raw: str) -> datetime | None:
    text = raw.strip()
    if not text or len(text) <= 10:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except Exception:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _parse_brief_date(raw: str) -> datetime | None:
    text = raw.strip()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return None
    try:
        dt = datetime.strptime(text, "%Y-%m-%d")
    except ValueError:
        return None
    # Date-only project briefs are treated as fresh through the end of that day in UTC.
    return dt.replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)


def _build_draft_prompt(
    *,
    cfg: AppConfig,
    item: ThreadRecord,
    thread_messages: list[ThreadMessage],
    project: ProjectBrief | None,
) -> str:
    priorities = extract_top_priorities(cfg.goals_path)
    sender_snippets = sender_context_snippets(
        sender_email=item.sender_email,
        sender_name=item.sender_name,
        people_path=cfg.people_path,
        email_contacts_path=cfg.email_contacts_path,
    )
    policy_text = load_text_excerpt(cfg.email_drafting_policy_path, char_limit=POLICY_LIMIT)
    style_text = load_text_excerpt(cfg.writing_style_path, char_limit=STYLE_LIMIT)
    thread_block = _thread_context_block(thread_messages)
    project_block = _truncate(build_project_excerpt(project, max_recent=8), PROJECT_EXCERPT_LIMIT) if project else ""

    priorities_block = "\n".join(f"- {item}" for item in priorities) if priorities else "- None available."
    sender_block = "\n".join(f"- {snippet}" for snippet in sender_snippets) if sender_snippets else "- No sender context found."

    parts = [
        "Write a reply draft for the latest message in this email thread.",
        "",
        "Return JSON only in this shape:",
        '{"draft_text":"plain text email body"}',
        "",
        "Rules:",
        "- Plain text only.",
        "- Write as Matt in a concise, direct voice.",
        "- Do not invent meetings, calls, prior conversations, or commitments.",
        "- If timing or scheduling is unclear, do not guess availability.",
        "- Acknowledge the email, answer or decide what you can, and state the next step.",
        "- No em dashes.",
        "",
        f"Latest sender: {item.sender_name} <{item.sender_email}>",
        f"Latest subject: {item.subject_latest}",
        f"Suggested response: {item.suggested_response or 'None'}",
        f"Suggested action: {item.suggested_action or 'None'}",
        "",
        "Top priorities:",
        priorities_block,
        "",
        "Sender context:",
        sender_block,
    ]

    if project_block:
        parts.extend(["", "Matched project context:", project_block])
    else:
        parts.extend(["", "Matched project context:", "No project matched."])

    parts.extend(
        [
            "",
            "Thread context (last messages, oldest to newest):",
            thread_block,
            "",
            "Email drafting policy:",
            policy_text or "Unavailable.",
            "",
            "Writing style:",
            style_text or "Unavailable.",
        ]
    )
    return "\n".join(parts).strip()


def _thread_context_block(thread_messages: list[ThreadMessage]) -> str:
    if not thread_messages:
        return "- No thread body available."

    ordered = sorted(thread_messages, key=lambda item: item.received_at)
    recent = ordered[-THREAD_LIMIT:]

    selected: list[str] = []
    total = 0
    for message in reversed(recent):
        body = _clean_message_body(message.body_text)
        if not body:
            continue
        body = _truncate(body, PER_MESSAGE_LIMIT)
        block = (
            f"From: {message.sender_name} <{message.sender_email}>\n"
            f"At: {message.received_at}\n"
            f"Subject: {message.subject}\n"
            f"Body:\n{body}"
        )
        if total + len(block) > TOTAL_THREAD_LIMIT and selected:
            continue
        selected.append(block)
        total += len(block)
    if not selected:
        return "- No thread body available."
    return "\n\n---\n\n".join(reversed(selected))


def _clean_message_body(text: str) -> str:
    value = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    cleaned_lines: list[str] = []
    for raw_line in value.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped:
            cleaned_lines.append("")
            continue
        lowered = stripped.lower()
        if stripped.startswith(">"):
            continue
        if lowered.startswith("on ") and lowered.endswith(" wrote:"):
            break
        if lowered.startswith("from:") and cleaned_lines:
            break
        if lowered.startswith("sent from my iphone"):
            continue
        cleaned_lines.append(stripped)

    text_out = "\n".join(cleaned_lines)
    text_out = re.sub(r"\n{3,}", "\n\n", text_out).strip()
    return text_out


def _normalize_email_body(text: str) -> str:
    lines = [line.rstrip() for line in text.replace("\r\n", "\n").replace("\r", "\n").splitlines()]
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    normalized = "\n".join(lines).strip()
    if not normalized:
        raise LlmClientError("Draft body was empty after normalization")
    return normalized + "\n"


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    clipped = text[: limit - 3].rstrip()
    if " " in clipped:
        clipped = clipped.rsplit(" ", 1)[0]
    return clipped + "..."


def _clean_text(text: str, *, limit: int = 220) -> str:
    value = " ".join((text or "").split()).strip()
    if len(value) <= limit:
        return value
    clipped = value[: limit - 3].rstrip()
    if " " in clipped:
        clipped = clipped.rsplit(" ", 1)[0]
    return clipped + "..."


def _first_name(sender_name: str, sender_email: str) -> str:
    name = " ".join((sender_name or "").split()).strip().strip('"')
    if name and "@" not in name:
        token = name.split(" ", 1)[0].strip()
        if token:
            return token
    email = (sender_email or "").strip().lower()
    if "@" in email:
        local = email.split("@", 1)[0]
        parts = [piece for piece in re.split(r"[._+\-]+", local) if piece]
        if parts:
            return parts[0].capitalize()
    return ""


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    low = (text or "").lower()
    return any(keyword in low for keyword in keywords)


def _is_generic_action(text: str) -> bool:
    low = (text or "").lower()
    patterns = (
        "next-step confirmation",
        "next step confirmation",
        "reply to ",
        "respond to ",
    )
    return any(pattern in low for pattern in patterns)


def _default_action(subject: str, summary: str, project: ProjectBrief | None) -> str:
    text = f"{subject}\n{summary}".lower()

    if _contains_any(text, ("invoice", "quote", "change order", "co#", "estimate", "ea#")):
        return "review the numbers and confirm approval and payment timing"
    if _contains_any(text, ("contract", "agreement", "terms", "sign", "signature")):
        return "review the terms and send approval or revisions"
    if _contains_any(text, ("meeting", "call", "time", "schedule", "availability", "zoom")):
        return "confirm timing and lock the next meeting step"
    if _contains_any(text, ("deadline", "due", "asap", "urgent", "follow up", "reminder")):
        return "confirm ownership and timeline for completion"
    if _contains_any(text, ("payment", "funding", "cash flow", "capital", "tax")):
        return "confirm the funding and payment plan today"
    if project and project.next_actions:
        return f"move the next {project.name} action and confirm execution details"
    return "confirm concrete next steps and timing"


def _specific_action(
    *,
    suggested_action: str,
    subject: str,
    summary: str,
    project: ProjectBrief | None,
) -> str:
    action = _clean_text(suggested_action, limit=180).rstrip(".")
    if action and not _is_generic_action(action):
        low = action.lower()
        if low.startswith("reply on ") and " with " in low:
            action = "reply with " + action[low.find(" with ") + 6 :]
        if action and action[0].isupper():
            action = action[0].lower() + action[1:]
        return action
    return _default_action(subject, summary, project)
