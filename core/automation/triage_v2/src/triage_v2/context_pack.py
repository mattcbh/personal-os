from __future__ import annotations

from email.utils import parseaddr
from pathlib import Path
import re


SECTION_RE_TEMPLATE = r"(^##\s+%s\s*$)(.*?)(?=^##\s+|\Z)"


def extract_top_priorities(goals_path: Path, *, limit: int = 3) -> list[str]:
    if not goals_path.exists():
        return []
    text = goals_path.read_text(encoding="utf-8")
    pattern = re.compile(
        SECTION_RE_TEMPLATE % re.escape("What are your top 3 priorities right now?"),
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(text)
    if not match:
        return []

    out: list[str] = []
    for raw_line in match.group(2).splitlines():
        line = raw_line.strip()
        if not re.match(r"^\d+\.\s+", line):
            continue
        out.append(re.sub(r"^\d+\.\s+", "", line).strip())
        if len(out) >= limit:
            break
    return out


def sender_context_snippets(
    *,
    sender_email: str,
    sender_name: str,
    people_path: Path,
    email_contacts_path: Path,
    limit: int = 6,
) -> list[str]:
    email = (sender_email or "").strip().lower()
    name = (sender_name or "").strip().lower()
    domain = email.split("@", 1)[1] if "@" in email else ""

    snippets: list[str] = []
    snippets.extend(_scan_sender_file(people_path, email=email, name=name, domain=domain, limit=limit))
    if len(snippets) < limit:
        snippets.extend(
            _scan_sender_file(
                email_contacts_path,
                email=email,
                name=name,
                domain=domain,
                limit=limit - len(snippets),
            )
        )

    deduped: list[str] = []
    seen: set[str] = set()
    for snippet in snippets:
        key = snippet.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(snippet)
        if len(deduped) >= limit:
            break
    return deduped


def load_text_excerpt(path: Path, *, char_limit: int) -> str:
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8")
    text = text.strip()
    if len(text) <= char_limit:
        return text
    clipped = text[: char_limit - 3].rstrip()
    if "\n" in clipped:
        clipped = clipped.rsplit("\n", 1)[0]
    elif " " in clipped:
        clipped = clipped.rsplit(" ", 1)[0]
    return clipped + "..."


def _scan_sender_file(
    path: Path,
    *,
    email: str,
    name: str,
    domain: str,
    limit: int,
) -> list[str]:
    if limit <= 0 or not path.exists():
        return []

    out: list[str] = []
    current_heading = ""
    lines = path.read_text(encoding="utf-8").splitlines()
    for raw_line in lines:
        stripped = raw_line.strip()
        if stripped.startswith("##") or stripped.startswith("###"):
            current_heading = stripped.lstrip("#").strip()
            continue
        if not stripped:
            continue
        if _line_matches_sender(stripped, email=email, name=name, domain=domain):
            prefix = f"{current_heading}: " if current_heading else ""
            out.append(prefix + stripped)
            if len(out) >= limit:
                break
    return out


def _line_matches_sender(line: str, *, email: str, name: str, domain: str) -> bool:
    lowered = line.lower()
    if email and email in lowered:
        return True
    if domain and f"*@{domain}" in lowered:
        return True
    if domain and domain in lowered:
        return True

    if name:
        name_email, parsed_name = parseaddr(name)
        del name_email
        candidate_name = (parsed_name or name).lower().strip('"')
        if candidate_name and candidate_name in lowered:
            return True
        name_tokens = [token for token in re.findall(r"[a-z0-9][a-z0-9'+-]{2,}", candidate_name) if len(token) >= 4]
        if name_tokens and all(token in lowered for token in name_tokens[:2]):
            return True
    return False
