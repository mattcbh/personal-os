#!/usr/bin/env python3
"""
Personal OS architecture drift audit.

Checks:
1) Missing runtime files referenced by the canonical manifest.
2) Path casing drift for canonical Knowledge folders.
3) References to retired components in documentation/config files.
4) Basic secret-pattern scan in repo content.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Iterable

try:
    import yaml  # type: ignore
except Exception:
    yaml = None


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "core" / "architecture" / "runtime-manifest.yaml"
HOME = Path.home()
RUNTIME_PERSONAL_ROOT = HOME / "Projects" / "automation-runtime-personal"
RUNTIME_WORK_ROOT = HOME / "Projects" / "automation-runtime-work"

TEXT_EXTENSIONS = {
    ".md",
    ".json",
    ".sh",
    ".py",
    ".yaml",
    ".yml",
    ".plist",
    ".txt",
}

DOC_EXTENSIONS = {
    ".md",
    ".json",
    ".yaml",
    ".yml",
    ".plist",
    ".txt",
}

IGNORE_DIRS = {
    ".git",
    ".obsidian",
    "__pycache__",
}

# Allowed historical/intentional references.
DRIFT_REFERENCE_ALLOWLIST = {
    "core/architecture/runtime-manifest.yaml",
    "scripts/audit_personal_os.py",
    "Knowledge/LEARNINGS/2026-02.md",
}

CASE_DRIFT_ALLOWLIST = {
    "scripts/audit_personal_os.py",
    "Knowledge/.granola-sync.json",
}

SECRET_PATH_ALLOWLIST = {
    "core/context/mcp-reference.md",
}

SECRET_PATTERNS = [
    re.compile(r"refresh_token=1//[A-Za-z0-9\-_]{20,}"),
    re.compile(r"client_secret=GOCSPX-[A-Za-z0-9\-_]+"),
    re.compile(r"GOCSPX-[A-Za-z0-9\-_]+"),
]

CASE_DRIFT_PATTERNS = [
    "Knowledge/Transcripts/",
    "Knowledge/Digests/",
]

PERSONAL_RUNTIME_IDS = {
    "daily-digest",
    "monthly-goals-review",
    "meeting-sync",
    "weekly-followup",
}

WORK_RUNTIME_IDS = {
    "project-refresh-morning",
    "project-refresh-evening",
    "email-triage-v2-morning",
    "email-triage-v2-evening",
    "email-monitor",
    "comms-ingest",
    "pnt-sync",
    "telegram-bridge",
    "email-triage-v2-local-fallback",
}

LOCAL_RUNTIME_IDS = {
    "system-health",
    "transcript-backfill",
    "superhuman-draft-queue-writer",
    "superhuman-draft-queue-watcher",
    "email-triage-v2-cutover-helper",
}


def iter_text_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in IGNORE_DIRS for part in path.parts):
            continue
        if path.suffix.lower() in TEXT_EXTENSIONS:
            yield path


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="latin-1")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def resolve_path(path_value: str) -> Path:
    if path_value.startswith("~"):
        return Path(path_value).expanduser()
    p = Path(path_value)
    if p.is_absolute():
        return p
    return ROOT / p


def repo_root_for_item(item_id: str) -> Path:
    if item_id in PERSONAL_RUNTIME_IDS:
        return RUNTIME_PERSONAL_ROOT
    if item_id in WORK_RUNTIME_IDS:
        return RUNTIME_WORK_ROOT
    return ROOT


def resolve_manifest_runtime_path(item_id: str, key: str, path_value: str) -> Path:
    if key == "launchd_plist" and item_id in PERSONAL_RUNTIME_IDS:
        return RUNTIME_PERSONAL_ROOT / ".generated" / "launchd" / Path(path_value).name
    if key == "launchd_plist" and item_id in WORK_RUNTIME_IDS:
        return RUNTIME_WORK_ROOT / ".generated" / "launchd" / Path(path_value).name
    if item_id in LOCAL_RUNTIME_IDS:
        return resolve_path(path_value)
    return repo_root_for_item(item_id) / path_value


def load_manifest_fallback(text: str) -> dict:
    """Minimal parser when PyYAML is unavailable."""
    sections = {"scheduled_jobs", "persistent_jobs", "manual_or_on_demand"}
    current_section: str | None = None
    current_entry: dict[str, str] | None = None

    out: dict[str, list[dict[str, str]]] = {k: [] for k in sections}
    retired: list[str] = []

    for raw_line in text.splitlines():
        line = raw_line.rstrip("\n")
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        if stripped in {f"{s}:" for s in sections}:
            if current_entry is not None and current_section in sections:
                out[current_section].append(current_entry)
            current_section = stripped[:-1]
            current_entry = None
            continue

        if stripped.startswith("retired_or_not_present_in_repo:"):
            if current_entry is not None and current_section in sections:
                out[current_section].append(current_entry)
            current_section = "retired"
            current_entry = None
            continue

        if current_section in sections and stripped.startswith("- id:"):
            if current_entry is not None:
                out[current_section].append(current_entry)
            current_entry = {"id": stripped.split(":", 1)[1].strip()}
            continue

        if current_section == "retired" and stripped.startswith("-"):
            retired.append(stripped[1:].strip())
            continue

        if current_entry is None:
            continue

        for key in ("script", "launchd_plist", "skill", "state_file"):
            prefix = f"{key}:"
            if stripped.startswith(prefix):
                current_entry[key] = stripped.split(":", 1)[1].strip()
                break

    if current_entry is not None and current_section in sections:
        out[current_section].append(current_entry)

    out["retired_or_not_present_in_repo"] = retired  # type: ignore[index]
    return out


def load_manifest() -> dict:
    if not MANIFEST.exists():
        return {}
    text = read_text(MANIFEST)
    if yaml is not None:
        data = yaml.safe_load(text)
        return data if isinstance(data, dict) else {}
    return load_manifest_fallback(text)


def iter_manifest_entries(manifest: dict) -> Iterable[dict]:
    for section in ("scheduled_jobs", "persistent_jobs", "manual_or_on_demand"):
        for item in manifest.get(section, []) or []:
            if isinstance(item, dict):
                yield item


def check_manifest_paths(manifest: dict) -> list[str]:
    findings: list[str] = []
    for item in iter_manifest_entries(manifest):
        item_id = item.get("id", "unknown")
        for key in ("script", "launchd_plist", "skill", "state_file"):
            value = item.get(key)
            if not isinstance(value, str) or not value.strip():
                continue
            if key == "launchd_plist" and item_id not in LOCAL_RUNTIME_IDS:
                continue
            resolved = resolve_manifest_runtime_path(item_id, key, value)
            if not resolved.exists():
                findings.append(f"[manifest] missing {key} for {item_id}: {value}")
    return findings


def check_case_drift(files: Iterable[Path]) -> list[str]:
    findings: list[str] = []
    for path in files:
        rp = rel(path)
        if rp in CASE_DRIFT_ALLOWLIST:
            continue
        text = read_text(path)
        for pattern in CASE_DRIFT_PATTERNS:
            if pattern in text:
                findings.append(f"[case-drift] {rp} contains '{pattern}'")
    return findings


def check_retired_references(files: Iterable[Path], manifest: dict) -> list[str]:
    retired = manifest.get("retired_or_not_present_in_repo", []) or []
    retired_components = [x for x in retired if isinstance(x, str) and x.strip()]
    if not retired_components:
        return []

    findings: list[str] = []
    for path in files:
        rp = rel(path)
        if rp in DRIFT_REFERENCE_ALLOWLIST:
            continue
        if path.suffix.lower() not in DOC_EXTENSIONS:
            continue
        text = read_text(path)
        for retired_name in retired_components:
            if retired_name in text:
                findings.append(f"[retired-ref] {rp} references '{retired_name}'")
    return findings


def check_secret_patterns(files: Iterable[Path]) -> list[str]:
    findings: list[str] = []
    for path in files:
        rp = rel(path)
        if rp in SECRET_PATH_ALLOWLIST:
            continue
        text = read_text(path)
        for regex in SECRET_PATTERNS:
            if regex.search(text):
                findings.append(f"[secret] {rp} matches '{regex.pattern}'")
                break
    return findings


def main() -> int:
    files = list(iter_text_files(ROOT))
    manifest = load_manifest()

    findings = {
        "manifest": check_manifest_paths(manifest),
        "case_drift": check_case_drift(files),
        "retired_refs": check_retired_references(files, manifest),
        "secrets": check_secret_patterns(files),
    }

    total = sum(len(v) for v in findings.values())
    print("Personal OS Audit")
    print(json.dumps({k: len(v) for k, v in findings.items()}, indent=2))

    for category, items in findings.items():
        if not items:
            continue
        print(f"\n## {category}")
        for item in items:
            print(f"- {item}")

    if findings["secrets"]:
        return 2
    if total:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
