from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Iterable

from triage_v2.types import ThreadRecord


ROOT = Path(__file__).resolve().parents[5]
PROJECTS_DIR = ROOT / "projects"
STOPWORDS = {
    "and",
    "the",
    "for",
    "with",
    "this",
    "that",
    "project",
    "active",
    "owner",
    "today",
    "tomorrow",
    "next",
    "action",
    "source",
    "status",
    "goal",
    "recent",
    "communication",
}
HEADER_FIELD_RE = re.compile(r"^\*\*(.+?):\*\*\s*(.+)$", re.MULTILINE)
RECENT_ENTRY_RE = re.compile(
    r"^###\s+(\d{4}-\d{2}-\d{2})\s+[-–—]\s+\[Source:\s*([^\]]+)\]\s*(.+)$",
    re.MULTILINE,
)
SECTION_RE_TEMPLATE = r"(^##\s+%s\s*$)(.*?)(?=^##\s+|\Z)"


@dataclass(frozen=True)
class NextAction:
    action: str
    owner: str
    due: str
    source: str


@dataclass(frozen=True)
class RecentCommunication:
    date: str
    source: str
    title: str
    bullets: tuple[str, ...]


@dataclass(frozen=True)
class ProjectBrief:
    name: str
    brief_path: Path
    status: str
    priority: str
    goal: str
    last_updated: str
    match_signals: tuple[str, ...]
    next_actions: tuple[NextAction, ...]
    summary: str
    current_status: str
    recent_communications: tuple[RecentCommunication, ...]


@dataclass(frozen=True)
class ProjectContact:
    name: str
    role: str
    contact: str
    context: str


@dataclass(frozen=True)
class ProjectReadmeEntry:
    name: str
    status: str
    priority: str
    goal: str
    brief_rel_path: str


@dataclass(frozen=True)
class ProjectUpdate:
    recent_communications: tuple[RecentCommunication, ...] = ()
    next_actions: tuple[NextAction, ...] = ()
    match_signals: tuple[str, ...] = ()


def load_project_briefs(projects_dir: Path = PROJECTS_DIR) -> list[ProjectBrief]:
    readme = projects_dir / "README.md"
    if not readme.exists():
        return []

    index = _active_project_index(readme.read_text(encoding="utf-8"))
    out: list[ProjectBrief] = []
    for rel, entry in index.items():
        path = (projects_dir / rel).resolve()
        if not path.exists() or not path.is_file():
            continue
        try:
            out.append(_parse_project_brief(path, entry))
        except Exception:
            continue
    return out


def load_project_brief(path: Path, projects_dir: Path = PROJECTS_DIR) -> ProjectBrief:
    readme = projects_dir / "README.md"
    index = _active_project_index(readme.read_text(encoding="utf-8")) if readme.exists() else {}
    rel = str(path.resolve().relative_to(projects_dir.resolve()))
    return _parse_project_brief(path, index.get(rel))


def match_project_for_thread(item: ThreadRecord, briefs: list[ProjectBrief]) -> ProjectBrief | None:
    return match_project_for_fields(
        briefs,
        sender_email=item.sender_email,
        sender_name=item.sender_name,
        subject=item.subject_latest,
        summary=item.summary_latest,
        body=item.summary_latest,
    )


def match_project_for_fields(
    briefs: list[ProjectBrief],
    *,
    sender_email: str = "",
    sender_name: str = "",
    subject: str = "",
    summary: str = "",
    body: str = "",
    participants: Iterable[str] | None = None,
    title: str = "",
) -> ProjectBrief | None:
    if not briefs:
        return None

    sender_email_low = (sender_email or "").lower().strip()
    sender_name_low = (sender_name or "").lower().strip()
    domain = sender_email_low.split("@", 1)[1] if "@" in sender_email_low else ""
    participant_blob = " ".join((participants or ())).lower()
    blob = " ".join(
        part
        for part in (
            sender_name_low,
            sender_email_low,
            (subject or "").lower(),
            (summary or "").lower(),
            (body or "").lower(),
            (title or "").lower(),
            participant_blob,
        )
        if part
    )

    best: ProjectBrief | None = None
    best_score = 0

    for brief in briefs:
        score = _score_project_match(brief, blob=blob, sender_email=sender_email_low, domain=domain)
        if score > best_score:
            best = brief
            best_score = score

    if best_score < 4:
        return None
    return best


def build_project_excerpt(project: ProjectBrief, *, max_recent: int = 8) -> str:
    lines = [
        f"Project: {project.name}",
        f"Priority: {project.priority or 'Unknown'}",
        f"Goal: {project.goal or 'Unknown'}",
        f"Last Updated: {project.last_updated or 'Unknown'}",
        "",
        "Summary:",
        project.summary or "None.",
        "",
        "Current Status:",
        project.current_status or "None.",
        "",
        "Next Actions:",
    ]
    if project.next_actions:
        for action in project.next_actions:
            lines.append(
                f"- {action.action} | Owner: {action.owner or 'Unknown'} | Due: {action.due or 'Unspecified'} | "
                f"Source: {action.source or 'Unknown'}"
            )
    else:
        lines.append("- None.")

    lines.extend(["", "Recent Communications:"])
    if project.recent_communications:
        for entry in project.recent_communications[:max_recent]:
            lines.append(f"- {entry.date} [{entry.source}] {entry.title}")
            for bullet in entry.bullets[:4]:
                lines.append(f"  - {bullet}")
    else:
        lines.append("- None.")

    return "\n".join(lines).strip()


def apply_project_update(
    project: ProjectBrief,
    update: ProjectUpdate,
    *,
    updated_date: str,
) -> ProjectBrief:
    text = project.brief_path.read_text(encoding="utf-8")

    merged_recent = merge_recent_communications(project.recent_communications, update.recent_communications)
    merged_actions = merge_next_actions(project.next_actions, update.next_actions)
    merged_signals = merge_match_signals(project.match_signals, update.match_signals)

    text = _replace_header_value(text, "Last Updated", updated_date)
    text = _replace_header_value(text, "Match Signals", ", ".join(merged_signals))
    text = _replace_section(text, "Next Actions", render_next_actions(merged_actions))
    text = _replace_section(text, "Recent Communications", render_recent_communications(merged_recent))

    project.brief_path.write_text(text, encoding="utf-8")
    return load_project_brief(project.brief_path, project.brief_path.parent)


def merge_recent_communications(
    existing: Iterable[RecentCommunication],
    new_entries: Iterable[RecentCommunication],
) -> tuple[RecentCommunication, ...]:
    seen: set[str] = set()
    merged: list[RecentCommunication] = []
    for entry in list(new_entries) + list(existing):
        key = _recent_key(entry)
        if key in seen:
            continue
        seen.add(key)
        merged.append(entry)
    merged.sort(key=lambda item: (item.date, item.title.lower()), reverse=True)
    return tuple(merged)


def merge_next_actions(existing: Iterable[NextAction], new_actions: Iterable[NextAction]) -> tuple[NextAction, ...]:
    merged: list[NextAction] = []
    seen: set[str] = set()
    for action in list(new_actions) + list(existing):
        normalized = _normalize_key_text(action.action)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        merged.append(action)
    return tuple(merged)


def merge_match_signals(existing: Iterable[str], new_signals: Iterable[str]) -> tuple[str, ...]:
    merged: list[str] = []
    seen: set[str] = set()
    for raw in list(existing) + list(new_signals):
        value = _clean_inline(raw)
        if not value:
            continue
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        merged.append(value)
    return tuple(merged)


def render_next_actions(actions: Iterable[NextAction]) -> str:
    rows = [
        "| Action | Owner | Due | Source |",
        "|--------|-------|-----|--------|",
    ]
    for action in actions:
        rows.append(
            "| {action} | {owner} | {due} | {source} |".format(
                action=_escape_table_cell(action.action),
                owner=_escape_table_cell(action.owner),
                due=_escape_table_cell(action.due),
                source=_escape_table_cell(action.source),
            )
        )
    return "\n".join(rows)


def render_recent_communications(entries: Iterable[RecentCommunication]) -> str:
    blocks: list[str] = []
    for entry in entries:
        blocks.append(f"### {entry.date} — [Source: {entry.source}] {entry.title}")
        for bullet in entry.bullets:
            blocks.append(f"- {bullet}")
        blocks.append("")
    return "\n".join(blocks).strip()


def _active_project_index(text: str) -> dict[str, ProjectReadmeEntry]:
    active = _section(text, "## Active Projects", "## Archived Projects")
    out: dict[str, ProjectReadmeEntry] = {}
    for raw_line in active.splitlines():
        line = raw_line.strip()
        if not line.startswith("|"):
            continue
        cols = [c.strip() for c in line.strip("|").split("|")]
        if len(cols) < 5:
            continue
        if cols[0].lower() == "project" or set(cols[0]) <= {"-"}:
            continue
        match = re.search(r"\[[^\]]+\]\(([^)]+\.md)\)", cols[4])
        if not match:
            continue
        rel = match.group(1).strip()
        out[rel] = ProjectReadmeEntry(
            name=cols[0],
            status=cols[1],
            priority=cols[2],
            goal=cols[3],
            brief_rel_path=rel,
        )
    return out


def _parse_project_brief(path: Path, readme_entry: ProjectReadmeEntry | None) -> ProjectBrief:
    text = path.read_text(encoding="utf-8")
    header_values = {str(name).strip(): _clean_inline(value) for name, value in HEADER_FIELD_RE.findall(text)}
    name = _extract_name(text, path, readme_entry)
    summary = _collapse_block(_extract_section(text, "Summary"), limit=800)
    current_status = _collapse_block(_extract_section(text, "Current Status"), limit=900)
    recent = tuple(_extract_recent_communications(_extract_section(text, "Recent Communications")))
    next_actions = tuple(_extract_next_actions(_extract_section(text, "Next Actions")))

    signals = _extract_match_signals(header_values.get("Match Signals", ""), name)
    status = header_values.get("Status") or (readme_entry.status if readme_entry else "")
    priority = header_values.get("Priority") or (readme_entry.priority if readme_entry else "")
    goal = header_values.get("Goal") or (readme_entry.goal if readme_entry else "")
    last_updated = header_values.get("Last Updated", "")

    return ProjectBrief(
        name=name,
        brief_path=path,
        status=status,
        priority=priority,
        goal=goal,
        last_updated=last_updated,
        match_signals=tuple(signals),
        next_actions=next_actions,
        summary=summary,
        current_status=current_status,
        recent_communications=recent,
    )


def _score_project_match(brief: ProjectBrief, *, blob: str, sender_email: str, domain: str) -> int:
    score = 0
    signals = list(brief.match_signals) + [brief.name]

    for signal in signals:
        s = signal.strip().lower()
        if not s:
            continue

        if "@" in s:
            raw_domain = s[2:] if s.startswith("*@") else s.split("@", 1)[1]
            if s == sender_email or (raw_domain and domain == raw_domain):
                score += 8
                continue
            if raw_domain and raw_domain in blob:
                score += 3
                continue

        if len(s) >= 4 and s in blob:
            score += 3
            continue

        for token in re.findall(r"[a-z0-9][a-z0-9&'+-]{2,}", s):
            if token in STOPWORDS:
                continue
            if token in blob:
                score += 1

    if brief.priority == "P0" and brief.name.lower() in blob:
        score += 1
    return score


def _extract_name(text: str, path: Path, readme_entry: ProjectReadmeEntry | None) -> str:
    match = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    if match:
        return match.group(1).strip()
    if readme_entry:
        return readme_entry.name.strip()
    return path.stem.replace("-", " ").strip().title()


def _extract_match_signals(raw: str, project_name: str) -> list[str]:
    out: list[str] = []
    if raw:
        out.extend([part.strip() for part in raw.split(",") if part.strip()])
    for token in re.findall(r"[A-Za-z0-9][A-Za-z0-9&'+-]{2,}", project_name):
        out.append(token)
    return list(merge_match_signals((), out))


def _extract_next_actions(section_text: str) -> list[NextAction]:
    out: list[NextAction] = []
    for raw_line in section_text.splitlines():
        line = raw_line.strip()
        if not line.startswith("|"):
            continue
        cols = [c.strip() for c in line.strip("|").split("|")]
        if len(cols) < 4:
            continue
        if cols[0].lower() == "action" or set(cols[0]) <= {"-"}:
            continue
        action = cols[0].strip()
        if not action:
            continue
        out.append(
            NextAction(
                action=action,
                owner=cols[1].strip(),
                due=cols[2].strip(),
                source=cols[3].strip(),
            )
        )
    return out


def _extract_recent_communications(section_text: str) -> list[RecentCommunication]:
    matches = list(RECENT_ENTRY_RE.finditer(section_text))
    if not matches:
        return []

    out: list[RecentCommunication] = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(section_text)
        block = section_text[start:end]
        bullets = []
        for raw_line in block.splitlines():
            stripped = raw_line.strip()
            if stripped.startswith("- "):
                bullets.append(stripped[2:].strip())
        out.append(
            RecentCommunication(
                date=match.group(1).strip(),
                source=match.group(2).strip(),
                title=_clean_inline(match.group(3)),
                bullets=tuple(bullets),
            )
        )
    return out


def _section(text: str, start: str, end: str) -> str:
    i = text.find(start)
    if i < 0:
        return text
    j = text.find(end, i + len(start))
    if j < 0:
        return text[i:]
    return text[i:j]


def _extract_section(text: str, heading: str) -> str:
    pattern = re.compile(SECTION_RE_TEMPLATE % re.escape(heading), re.MULTILINE | re.DOTALL)
    match = pattern.search(text)
    if not match:
        return ""
    return match.group(2).strip()


def _replace_section(text: str, heading: str, new_body: str) -> str:
    replacement = f"## {heading}\n\n{new_body.strip()}\n\n"
    pattern = re.compile(SECTION_RE_TEMPLATE % re.escape(heading), re.MULTILINE | re.DOTALL)
    if pattern.search(text):
        return pattern.sub(replacement, text, count=1)
    suffix = "" if text.endswith("\n") else "\n"
    return f"{text}{suffix}\n{replacement}"


def _replace_header_value(text: str, field: str, value: str) -> str:
    pattern = re.compile(rf"^(\*\*{re.escape(field)}:\*\*\s*).+$", re.MULTILINE)
    if pattern.search(text):
        return pattern.sub(lambda match: f"{match.group(1)}{value}", text, count=1)
    return text


def _collapse_block(text: str, *, limit: int) -> str:
    value = " ".join((text or "").split()).strip()
    if len(value) <= limit:
        return value
    clipped = value[: limit - 3].rstrip()
    if " " in clipped:
        clipped = clipped.rsplit(" ", 1)[0]
    return clipped + "..."


def _recent_key(entry: RecentCommunication) -> str:
    return "|".join((entry.date, entry.source.lower(), _normalize_key_text(entry.title)))


def _normalize_key_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _escape_table_cell(text: str) -> str:
    return (text or "").replace("|", "\\|").strip()


def _clean_inline(text: str) -> str:
    return " ".join((text or "").split()).strip()
