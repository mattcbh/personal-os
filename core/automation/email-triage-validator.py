#!/usr/bin/env python3
"""
Email triage state and report validator.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


DEFAULT_TRIAGE_STATE = {
    "last_triage_timestamp": None,
    "processed_message_ids": [],
    "last_triage_type": None,
    "emails_processed": 0,
    "last_run_status": "never",
    "last_run_error": None,
    "last_run_at": None,
}

DEFAULT_MONITOR_STATE = {
    "watched_threads": [],
    "alerted_ids": [],
}

SUPERHUMAN_RE = re.compile(r"https://mail\.superhuman\.com/[^)\s]+/thread/[^)\s]+")
SUPERHUMAN_MD_LINK_RE = re.compile(
    r"\[[^\]]+\]\(https://mail\.superhuman\.com/[^)\s]+/thread/[^)\s]+\)"
)
SUPERHUMAN_THREAD_URL_RE = re.compile(
    r"^https://mail\.superhuman\.com/(?P<account>[^/\s]+)/thread/(?P<thread_id>[^)\s/]+)$"
)
UNSUBSCRIBE_MD_LINK_RE = re.compile(r"\[Unsubscribe[^\]]*\]\(([^)\s]+)\)")
THREAD_LINE_RE = re.compile(r"^\s*Thread:\s*https://mail\.superhuman\.com/[^)\s]+/thread/[^)\s]+\s*$")
SECTION_RE = re.compile(r"^##\s+(.+?)\s*(?:\(\d+\))?\s*$")
WORK_RE = re.compile(r"^###\s+Work\s*$")
PERSONAL_RE = re.compile(r"^###\s+Personal\s*$")
NUMBERED_RE = re.compile(r"^\d+\.\s")
HR_RE = re.compile(r"^\s*---+\s*$")
COUNT_SUMMARY_RE = re.compile(r"\b\d+\+\b")
ACTION_NONE_RE = re.compile(r"\b(no action needed|none required now|no action required)\b", re.IGNORECASE)
DRAFT_READY_LABEL_RE = re.compile(r"\[(Draft ready|Courtesy draft ready)\]\(", re.IGNORECASE)
QUEUED_STATUS_RE = re.compile(r"Draft status:\s*queued\b", re.IGNORECASE)
SCORE_TAG_RE = re.compile(r"\[\d{1,3}\]")
ACCOUNT_TAG_RE = re.compile(r"\[(WORK|PERSONAL)\]", re.IGNORECASE)


@dataclass
class ValidationResult:
    ok: bool
    errors: list[str]
    warnings: list[str]


def read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    return data


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def ensure_schema(
    data: dict[str, Any] | None,
    defaults: dict[str, Any],
    *,
    list_keys: Iterable[str] = (),
    nullable_keys: Iterable[str] = (),
) -> dict[str, Any]:
    fixed = dict(defaults)
    if isinstance(data, dict):
        fixed.update(data)

    for key in list_keys:
        val = fixed.get(key)
        if not isinstance(val, list):
            fixed[key] = []
    for key in nullable_keys:
        if key not in fixed:
            fixed[key] = None
    if "emails_processed" in defaults and not isinstance(fixed.get("emails_processed"), int):
        try:
            fixed["emails_processed"] = int(fixed.get("emails_processed") or 0)
        except Exception:
            fixed["emails_processed"] = 0
    return fixed


def normalize_section_name(name: str) -> str:
    low = name.lower().strip()
    low = low.replace("—", "-")
    low = re.sub(r"\s+", " ", low)
    aliases = {
        "action needed": "Action Needed",
        "already addressed": "Already Addressed",
        "monitoring": "Monitoring",
        "fyi": "FYI",
        "newsletters": "Newsletters",
        "spam / marketing": "Spam / Marketing",
        "spam/marketing": "Spam / Marketing",
    }
    return aliases.get(low, name.strip())


def find_sections(lines: list[str]) -> list[tuple[str, int]]:
    sections: list[tuple[str, int]] = []
    for idx, line in enumerate(lines):
        m = SECTION_RE.match(line.strip())
        if not m:
            continue
        sections.append((normalize_section_name(m.group(1)), idx))
    return sections


def validate_report(markdown_path: Path, contract: dict[str, Any]) -> ValidationResult:
    errors: list[str] = []
    warnings: list[str] = []
    thread_usage: dict[str, int] = {}
    link_rules = contract.get("link_rules", {})
    allowed_prefixes = tuple(link_rules.get("superhuman_url_prefixes", []))

    if not markdown_path.exists():
        return ValidationResult(False, [f"Missing markdown report: {markdown_path}"], warnings)

    text = markdown_path.read_text(encoding="utf-8")
    lines = text.splitlines()

    if contract.get("quality_rules", {}).get("no_numbered_lists", True):
        for i, line in enumerate(lines, start=1):
            if NUMBERED_RE.match(line.strip()):
                errors.append(f"Line {i}: numbered list item is not allowed")

    if contract.get("quality_rules", {}).get("no_horizontal_rules", True):
        for i, line in enumerate(lines, start=1):
            if HR_RE.match(line):
                errors.append(f"Line {i}: horizontal rule is not allowed")

    for i, line in enumerate(lines, start=1):
        if SCORE_TAG_RE.search(line):
            errors.append(f"Line {i}: score tags like [85] are not allowed")
        if ACCOUNT_TAG_RE.search(line):
            errors.append(f"Line {i}: [WORK]/[PERSONAL] prefixes are not allowed")

    sections = find_sections(lines)
    expected_order = contract.get("section_order", [])
    expected_idx = {name: i for i, name in enumerate(expected_order)}
    seen_positions: list[int] = []
    seen_names: list[str] = []
    for section_name, _ in sections:
        if section_name in expected_idx:
            seen_positions.append(expected_idx[section_name])
            seen_names.append(section_name)
    if seen_positions != sorted(seen_positions):
        errors.append(
            "Section order is invalid. "
            f"Seen order: {seen_names}; expected order: {expected_order}"
        )

    # Validate section body details.
    section_bounds: list[tuple[str, int, int]] = []
    for i, (name, start) in enumerate(sections):
        end = sections[i + 1][1] if i + 1 < len(sections) else len(lines)
        section_bounds.append((name, start, end))

    for section_name, start, end in section_bounds:
        body = lines[start + 1 : end]
        body_text = "\n".join(body)

        if section_name in {"Newsletters", "Spam / Marketing"}:
            if COUNT_SUMMARY_RE.search(body_text):
                errors.append(f"{section_name}: count-only summaries like '25+' are not allowed")
            if "," in body_text and "- **" not in body_text and "[View](" not in body_text:
                errors.append(f"{section_name}: appears as comma-separated summary instead of individual entries")

        has_work = any(WORK_RE.match(line.strip()) for line in body)
        has_personal = any(PERSONAL_RE.match(line.strip()) for line in body)
        if body and not (has_work or has_personal):
            warnings.append(f"{section_name}: missing Work/Personal subsection labels")

        item_blocks = extract_item_blocks(body)
        for block in item_blocks:
            block_text = "\n".join(block)
            superhuman_links = SUPERHUMAN_RE.findall(block_text)
            superhuman_md_links = SUPERHUMAN_MD_LINK_RE.findall(block_text)
            block_thread_keys: set[str] = set()

            if section_name in {
                "Action Needed",
                "Already Addressed",
                "Monitoring",
                "FYI",
                "Newsletters",
                "Spam / Marketing",
            }:
                if not superhuman_links:
                    errors.append(f"{section_name}: entry missing Superhuman thread link")
                if not superhuman_md_links:
                    errors.append(f"{section_name}: entry must use markdown link syntax for Superhuman URL")
                if len(superhuman_links) > 1:
                    errors.append(f"{section_name}: entry has more than one Superhuman thread link")
                if len(superhuman_md_links) != len(superhuman_links):
                    errors.append(
                        f"{section_name}: entry mixes plain URLs with markdown links; Superhuman link must be markdown only"
                    )
                if any(THREAD_LINE_RE.match(line.strip()) for line in block):
                    errors.append(f"{section_name}: entry must not use raw 'Thread:' lines; use markdown links only")

            for link in superhuman_links:
                if allowed_prefixes and not link.startswith(allowed_prefixes):
                    errors.append(f"{section_name}: Superhuman link uses unexpected prefix: {link}")

                thread_match = SUPERHUMAN_THREAD_URL_RE.match(link)
                if not thread_match:
                    errors.append(f"{section_name}: malformed Superhuman thread link: {link}")
                    continue
                thread_key = f"{thread_match.group('account')}:{thread_match.group('thread_id')}"
                block_thread_keys.add(thread_key)

            if section_name in {"Newsletters", "Spam / Marketing"}:
                if "[Unsubscribe](" not in block_text and "Unsubscribe unavailable" not in block_text:
                    errors.append(
                        f"{section_name}: entry missing Unsubscribe link (or explicit 'Unsubscribe unavailable')"
                    )
                for unsub_link in UNSUBSCRIBE_MD_LINK_RE.findall(block_text):
                    if unsub_link in superhuman_links:
                        errors.append(
                            f"{section_name}: Unsubscribe link incorrectly equals Superhuman thread link: {unsub_link}"
                        )
                    if "mail.superhuman.com/" in unsub_link and "/thread/" in unsub_link:
                        errors.append(
                            f"{section_name}: Unsubscribe must not point to a Superhuman thread URL: {unsub_link}"
                        )
                    if "mail.google.com/mail" in unsub_link and ("#inbox" in unsub_link or "#all" in unsub_link):
                        errors.append(
                            f"{section_name}: Unsubscribe must not point to a Gmail inbox URL: {unsub_link}"
                        )

            if section_name == "Action Needed":
                if ACTION_NONE_RE.search(block_text):
                    errors.append("Action Needed: entry contradicts bucket by stating no action is required")
                if "[Draft ready]" in block_text and "[View thread]" in block_text:
                    errors.append("Action Needed: entry includes both Draft ready and View thread links")

            if DRAFT_READY_LABEL_RE.search(block_text) and not QUEUED_STATUS_RE.search(block_text):
                errors.append(
                    f"{section_name}: draft-ready label used without explicit 'Draft status: queued'"
                )
            for thread_key in block_thread_keys:
                thread_usage[thread_key] = thread_usage.get(thread_key, 0) + 1

    duplicates = [thread_key for thread_key, count in thread_usage.items() if count > 1]
    for thread_key in sorted(duplicates):
        errors.append(f"Duplicate Superhuman thread used across multiple entries: {thread_key}")

    return ValidationResult(not errors, errors, warnings)


def extract_item_blocks(lines: list[str]) -> list[list[str]]:
    blocks: list[list[str]] = []
    current: list[str] = []
    for line in lines:
        stripped = line.strip()
        is_section = stripped.startswith("## ") or stripped.startswith("### ")
        if is_section:
            if current:
                blocks.append(current)
                current = []
            continue
        if not stripped:
            if current:
                blocks.append(current)
                current = []
            continue
        if current:
            current.append(line)
        else:
            current = [line]
    if current:
        blocks.append(current)
    return blocks


def load_contract(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("contract is not an object")
        return raw
    except Exception as exc:
        raise SystemExit(f"Failed to read contract file {path}: {exc}") from exc


def cmd_state(args: argparse.Namespace) -> int:
    triage_path = Path(args.triage_state)
    monitor_path = Path(args.monitor_state)

    triage = ensure_schema(
        read_json(triage_path),
        DEFAULT_TRIAGE_STATE,
        list_keys=("processed_message_ids",),
        nullable_keys=("last_triage_timestamp", "last_triage_type", "last_run_error", "last_run_at"),
    )
    monitor = ensure_schema(
        read_json(monitor_path),
        DEFAULT_MONITOR_STATE,
        list_keys=("watched_threads", "alerted_ids"),
    )

    if args.write:
        write_json(triage_path, triage)
        write_json(monitor_path, monitor)

    print(json.dumps({"triage": triage, "monitor": monitor}, indent=2))
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    contract = load_contract(Path(args.contract))
    result = validate_report(Path(args.markdown), contract)
    payload = {"ok": result.ok, "errors": result.errors, "warnings": result.warnings}
    print(json.dumps(payload, indent=2))
    return 0 if result.ok or args.allow_warnings else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Email triage validator")
    sub = parser.add_subparsers(dest="cmd", required=True)

    state = sub.add_parser("state", help="Validate or initialize state files")
    state.add_argument("--triage-state", required=True, help="Path to email-triage-state.json")
    state.add_argument("--monitor-state", required=True, help="Path to email-monitor-state.json")
    state.add_argument("--write", action="store_true", help="Write repaired/default schema to disk")
    state.set_defaults(func=cmd_state)

    report = sub.add_parser("report", help="Validate markdown digest format")
    report.add_argument("--markdown", required=True, help="Path to triage markdown digest")
    report.add_argument("--contract", required=True, help="Path to contract JSON")
    report.add_argument(
        "--allow-warnings",
        action="store_true",
        help="Do not fail on warnings",
    )
    report.set_defaults(func=cmd_report)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
