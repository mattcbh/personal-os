from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import os
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[5]
RUNTIME_DEFAULT_PATH = ROOT / "core" / "context" / "email-contacts.md"
VAULT_DEFAULT_PATH = Path.home() / "Obsidian" / "personal-os" / "core" / "context" / "email-contacts.md"

HEADING_RE = re.compile(r"^(#{2,6})\s+(.*)$")


@dataclass(frozen=True)
class SenderPolicyMatch:
    sender_kind: str = "unknown"
    default_bucket: str = ""
    implicit_action_allowed: bool = False
    never_spam: bool = False
    matched_by: str = ""
    matched_value: str = ""


@dataclass(frozen=True)
class SenderPolicy:
    exact_emails: dict[str, SenderPolicyMatch]
    exact_names: dict[str, SenderPolicyMatch]
    domains: dict[str, SenderPolicyMatch]


def _default_contacts_path() -> Path:
    raw = os.environ.get("TRIAGE_V2_EMAIL_CONTACTS_PATH")
    if raw and raw.strip():
        return Path(raw).expanduser().resolve()
    if RUNTIME_DEFAULT_PATH.exists():
        return RUNTIME_DEFAULT_PATH
    return VAULT_DEFAULT_PATH


def _normalize_name(text: str) -> str:
    cleaned = " ".join((text or "").split()).strip().strip('"')
    cleaned = re.sub(r"\s+\(.*?\)$", "", cleaned)
    return cleaned.lower()


def _split_tokens(value: str) -> list[str]:
    tokens: list[str] = []
    for raw_piece in value.split(","):
        piece = raw_piece.strip().strip("`").strip()
        if not piece or piece == "—":
            continue
        tokens.append(piece)
    return tokens


def _rule_for_context(*, tier: str, section: str, notes: list[str], row_text: str) -> SenderPolicyMatch:
    blob = " ".join(filter(None, [tier, section, " ".join(notes), row_text])).lower()
    implicit_action_allowed = "implicit action classification" in blob

    sender_kind = "unknown"
    default_bucket = "FYI"
    never_spam = False

    if any(term in blob for term in ("newsletter", "substack", "digest", "brief", "tracked sources")):
        sender_kind = "newsletter_source"
        default_bucket = "Newsletters"
        never_spam = True
    elif any(term in blob for term in ("corner booth", "cbh team", "pnt team", "internal")):
        sender_kind = "internal"
        default_bucket = "FYI"
        never_spam = True
    elif any(term in blob for term in ("vendors & services", "vendor", "toast", "marginedge", "bill.com")):
        sender_kind = "vendor"
        default_bucket = "FYI"
        never_spam = True
    elif any(term in blob for term in ("inner circle", "professional network", "personal", "family", "friend")):
        sender_kind = "personal"
        default_bucket = "FYI"
        never_spam = True
    elif "tracked sources" in blob:
        sender_kind = "tracked_source"
        default_bucket = "FYI"

    return SenderPolicyMatch(
        sender_kind=sender_kind,
        default_bucket=default_bucket,
        implicit_action_allowed=implicit_action_allowed,
        never_spam=never_spam,
    )


@lru_cache(maxsize=4)
def load_sender_policy(path_text: str | None = None) -> SenderPolicy:
    path = Path(path_text).expanduser().resolve() if path_text else _default_contacts_path()
    exact_emails: dict[str, SenderPolicyMatch] = {}
    exact_names: dict[str, SenderPolicyMatch] = {}
    domains: dict[str, SenderPolicyMatch] = {}
    if not path.exists():
        return SenderPolicy(exact_emails=exact_emails, exact_names=exact_names, domains=domains)

    current_tier = ""
    current_section = ""
    notes: list[str] = []

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue

        heading_match = HEADING_RE.match(line)
        if heading_match:
            level, heading = heading_match.groups()
            if level == "##":
                current_tier = heading.strip()
                current_section = heading.strip()
            else:
                current_section = heading.strip()
            notes = []
            continue

        if line.startswith("|") and line.endswith("|"):
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            if len(cells) < 2:
                continue
            if set(cells[0]) <= {"-", ":"}:
                continue
            if cells[0].lower() in {"name", "sender / domain"}:
                continue

            name_cell = cells[0]
            contact_cell = cells[1]
            context_cell = " | ".join(cells[2:]) if len(cells) > 2 else ""
            row_text = " ".join(cell for cell in cells if cell)
            base_match = _rule_for_context(
                tier=current_tier,
                section=current_section,
                notes=notes,
                row_text=row_text,
            )

            normalized_name = _normalize_name(name_cell)
            if normalized_name and normalized_name not in exact_names:
                exact_names[normalized_name] = SenderPolicyMatch(
                    **{**base_match.__dict__, "matched_by": "name", "matched_value": normalized_name}
                )

            for token in _split_tokens(contact_cell):
                normalized = token.lower()
                if normalized.startswith("*@"):
                    domain = normalized[2:]
                    domains[domain] = SenderPolicyMatch(
                        **{**base_match.__dict__, "matched_by": "domain", "matched_value": domain}
                    )
                    continue
                if "@" in normalized:
                    exact_emails[normalized] = SenderPolicyMatch(
                        **{**base_match.__dict__, "matched_by": "email", "matched_value": normalized}
                    )
            continue

        if not line.startswith("|"):
            notes.append(line)
            if len(notes) > 6:
                notes = notes[-6:]

    return SenderPolicy(exact_emails=exact_emails, exact_names=exact_names, domains=domains)


def match_sender_policy(sender_email: str, sender_name: str) -> SenderPolicyMatch:
    policy = load_sender_policy(str(_default_contacts_path()))
    email = (sender_email or "").strip().lower()
    if email in policy.exact_emails:
        return policy.exact_emails[email]

    normalized_name = _normalize_name(sender_name)
    if normalized_name in policy.exact_names:
        return policy.exact_names[normalized_name]

    if "@" in email:
        domain = email.split("@", 1)[1]
        if domain in policy.domains:
            return policy.domains[domain]
        if domain == "substack.com":
            return SenderPolicyMatch(
                sender_kind="newsletter_source",
                default_bucket="Newsletters",
                implicit_action_allowed=False,
                never_spam=True,
                matched_by="domain",
                matched_value=domain,
            )

    return SenderPolicyMatch()
