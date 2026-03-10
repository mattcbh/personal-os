#!/usr/bin/env python3
"""
Resolve sender identity from email-contacts.md using deterministic precedence:
1) exact email, 2) domain rule, 3) fallback unknown.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

CONTACTS_FILE = Path("/Users/homeserver/Obsidian/personal-os/core/context/email-contacts.md")
TABLE_ROW_RE = re.compile(r"^\|(.+)\|(.+)\|(.+)\|$")


def parse_contacts(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    lines = path.read_text(encoding="utf-8").splitlines()
    for raw in lines:
        line = raw.strip()
        if not line.startswith("|"):
            continue
        if line.startswith("|---") or line.lower().startswith("| name "):
            continue
        m = TABLE_ROW_RE.match(line)
        if not m:
            continue
        name = m.group(1).strip()
        email_col = m.group(2).strip()
        context = m.group(3).strip()
        tokens = [t.strip().lower() for t in email_col.split(",") if t.strip()]
        rows.append({"name": name, "tokens": tokens, "context": context, "raw_email_field": email_col})
    return rows


def resolve_identity(contacts: list[dict[str, Any]], email: str, name: str) -> dict[str, Any]:
    email_lc = email.strip().lower()
    domain = ""
    if "@" in email_lc:
        domain = email_lc.split("@", 1)[1]

    exact_matches: list[dict[str, Any]] = []
    domain_matches: list[dict[str, Any]] = []
    name_matches: list[dict[str, Any]] = []

    for row in contacts:
        tokens = row["tokens"]
        if email_lc and email_lc in tokens:
            exact_matches.append(row)
            continue
        for t in tokens:
            if t.startswith("*@") and domain and domain == t[2:]:
                domain_matches.append(row)
                break
        if name and row["name"].strip().lower() == name.strip().lower():
            name_matches.append(row)

    if exact_matches:
        primary = exact_matches[0]
        return {
            "status": "resolved",
            "match_type": "exact_email",
            "canonical_name": primary["name"],
            "canonical_context": primary["context"],
            "email": email_lc,
            "domain": domain,
            "ambiguous_name_candidates": [r["name"] for r in name_matches if r["name"] != primary["name"]],
        }
    if domain_matches:
        primary = domain_matches[0]
        return {
            "status": "resolved",
            "match_type": "domain",
            "canonical_name": primary["name"],
            "canonical_context": primary["context"],
            "email": email_lc,
            "domain": domain,
            "ambiguous_name_candidates": [r["name"] for r in name_matches],
        }
    return {
        "status": "unresolved",
        "match_type": "none",
        "canonical_name": "",
        "canonical_context": "",
        "email": email_lc,
        "domain": domain,
        "ambiguous_name_candidates": [r["name"] for r in name_matches],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Resolve email sender identity from contacts file")
    parser.add_argument("--contacts-file", default=str(CONTACTS_FILE))
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", default="")
    args = parser.parse_args()

    contacts = parse_contacts(Path(args.contacts_file))
    result = resolve_identity(contacts, args.email, args.name)
    print(json.dumps(result, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
