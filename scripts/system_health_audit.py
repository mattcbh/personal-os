#!/usr/bin/env python3
"""
Coordinator audit for the Personal OS system health check.

This script is designed to run on the Mac Mini ("brain") as the daily
cross-system check. It stays repo-local but audits the wider system:

- launchd load state for documented jobs
- runtime repo health scripts
- PnT runtime basics
- vault drift audit
- symlink / state integrity
- sync freshness for key state surfaces
- content hygiene for duplicate tasks and obvious typo-like issues
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import platform
import re
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
HOME = Path.home()
LOCAL_TZ = datetime.now().astimezone().tzinfo or timezone.utc
RUNTIME_PERSONAL = HOME / "Projects" / "automation-runtime-personal"
RUNTIME_WORK = HOME / "Projects" / "automation-runtime-work"
MACHINE_CONFIG = HOME / "Projects" / "automation-machine-config"
PNT_REPO = HOME / "Projects" / "pnt-data-warehouse"
PNT_LOG_DIR = HOME / "Library" / "Logs" / "pnt-data-warehouse"
HOST_ROLE_ENV = "SYSTEM_HEALTH_ROLE"

INVISIBLE_CHARACTERS = {
    "\u200b": "ZERO WIDTH SPACE",
    "\u200c": "ZERO WIDTH NON-JOINER",
    "\u200d": "ZERO WIDTH JOINER",
    "\ufeff": "BYTE ORDER MARK",
    "\ufffd": "REPLACEMENT CHARACTER",
}

TEXT_SCAN_ROOTS = (
    ROOT / "things-sync",
    ROOT / "projects",
    ROOT / "core" / "architecture",
    ROOT / "core" / "automation",
    ROOT / "core" / "policies",
)

TOP_LEVEL_TEXT_FILES = (
    ROOT / "AGENTS.md",
    ROOT / "README.md",
    ROOT / "GOALS.md",
    ROOT / "BACKLOG.md",
)

THINGS_LAST_SYNC_FILES = (
    ROOT / "things-sync" / "today.md",
    ROOT / "things-sync" / "inbox.md",
    ROOT / "things-sync" / "upcoming.md",
    ROOT / "things-sync" / "anytime.md",
    ROOT / "things-sync" / "someday.md",
    ROOT / "things-sync" / "logbook.md",
)

FRESHNESS_RULES = (
    ("daily-digest outputs", ROOT / "Knowledge" / "DIGESTS", 36),
    ("work comms events", ROOT / "core" / "state" / "comms-events.jsonl", 6),
    ("email monitor state", ROOT / "core" / "state" / "email-monitor-state.json", 6),
    ("project refresh state", ROOT / "core" / "state" / "project-refresh-state.json", 24),
    ("PnT sync state", ROOT / "core" / "state" / "pnt-sync-state.json", 36),
    ("Granola sync state", ROOT / "core" / "state" / "granola-sync.json", 36),
    ("system health state", ROOT / "core" / "state" / "system-health.json", 36),
)

BRAIN_LOCAL_STATE_ALLOWLIST = {
    "core/state/cfo-state.json",
    "core/state/granola-sync.json",
    "core/state/pending-tasks.md",
    "core/state/system-health.json",
    "core/state/telegram-brain.json",
    "core/state/transcript-backfill.json",
}

PNT_REQUIRED_FILES = (
    "scripts/daily_sync.sh",
    "scripts/systematiq_monitor.py",
    "scripts/weekly_flash.sh",
)

PNT_REQUIRED_LABELS = (
    "com.pnt.daily-sync",
    "com.pnt.systematiq-monitor",
    "com.pnt.weekly-flash",
)

PNT_OPTIONAL_LABEL_MESSAGES = {
    "com.pnt.weekly-flash-preview": "optional launchd not loaded: {label}",
    "com.pnt.weekly-se-sync": "optional launchd not loaded: {label}",
    "com.pnt.backfill-monitor": (
        "optional launchd not loaded: {label} "
        "(expected unless a bounded backfill campaign is active)"
    ),
    "com.pnt.metabase": "optional launchd not loaded: {label}",
    "com.pnt.chart-server": "optional launchd not loaded: {label}",
    "com.pnt.cloudflared-tunnel": "optional launchd not loaded: {label}",
    "com.pnt.cloudflared-charts": (
        "optional launchd not loaded: {label} "
        "(expected; named Cloudflare tunnel is the primary public ingress)"
    ),
    "com.pnt.cloudflared-metabase": (
        "optional launchd not loaded: {label} "
        "(expected; named Cloudflare tunnel is the primary public ingress)"
    ),
}

BIRTHDAY_TASK_RE = re.compile(r"\bbirthday\b", re.IGNORECASE)

PNT_RUNTIME_ONLY_PATTERNS = (
    re.compile(r"^PnT_Monthly_PL_.*\.html$"),
    re.compile(r"^PnT_Weekly_Flash_.*\.png$"),
    re.compile(r"^data/.*-session\.json$"),
    re.compile(r"^data/qbo-tokens\.json$"),
    re.compile(r"^data/systematiq-monitor-last-run\.json$"),
    re.compile(r"^data/screenshots/"),
    re.compile(r"^data/.*-exports/"),
)

TASK_LINE_RE = re.compile(
    r"^- \[[ xX]\] (?P<title>.*?)(?:\s+`?\[things:(?P<things_id>[^`\]]+)\]`?)?\s*$"
)
LAST_SYNC_RE = re.compile(r"^\*Last synced:\s*(?P<stamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2})\*$")
DOUBLED_WORD_RE = re.compile(r"\b([A-Za-z][A-Za-z'/-]+)\s+\1\b", re.IGNORECASE)
SPACE_BEFORE_PUNCT_RE = re.compile(r"\s+[,.!?;:](?:\s|$)")
REPEATED_PUNCT_RE = re.compile(r"(\.\.+|,,+|;;+|!!+|\?\?+)")
@dataclass(frozen=True)
class TaskRecord:
    path: str
    line_no: int
    title: str
    normalized_title: str
    token_set: frozenset[str]
    things_id: str | None
    when_date: str | None


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def detect_host_role() -> str:
    override = os.environ.get(HOST_ROLE_ENV, "").strip().lower()
    if override in {"brain", "laptop"}:
        return override

    node = platform.node().lower()
    if HOME.name == "homeserver" or "mac-mini" in node or "brain" in node:
        return "brain"
    return "laptop"


def _load_audit_module():
    module_path = ROOT / "scripts" / "audit_personal_os.py"
    spec = importlib.util.spec_from_file_location("audit_personal_os", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to import {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[attr-defined]
    return module


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="latin-1")


def section(name: str) -> dict:
    return {
        "name": name,
        "status": "ok",
        "failure_count": 0,
        "warning_count": 0,
        "failures": [],
        "warnings": [],
        "notes": [],
        "details": {},
    }


def add_failure(target: dict, message: str) -> None:
    target["failure_count"] += 1
    target["status"] = "warning"
    target["failures"].append(message)


def add_warning(target: dict, message: str) -> None:
    target["warning_count"] += 1
    if target["status"] == "ok":
        target["status"] = "warning"
    target["warnings"].append(message)


def add_note(target: dict, message: str) -> None:
    target["notes"].append(message)


def run_command(
    command: list[str],
    cwd: Path | None = None,
    timeout: float | None = 20,
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            cwd=str(cwd) if cwd else None,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        return subprocess.CompletedProcess(command, 124, stdout, stderr)


def parse_command_output(text: str) -> dict[str, int]:
    counts = {"ok": 0, "warn": 0, "fail": 0}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith("OK"):
            counts["ok"] += 1
        elif line.startswith("WARN"):
            counts["warn"] += 1
        elif line.startswith("FAIL"):
            counts["fail"] += 1
    return counts


def load_manifest() -> dict:
    return _load_audit_module().load_manifest()


def load_launchd_snapshot() -> dict[str, str]:
    result = run_command(["launchctl", "list"])
    snapshot: dict[str, str] = {}
    if result.returncode != 0:
        return snapshot
    for line in result.stdout.splitlines():
        parts = line.split(None, 2)
        if len(parts) != 3 or parts[2] == "Label":
            continue
        snapshot[parts[2]] = parts[0]
    return snapshot


def latest_mtime(path: Path) -> datetime | None:
    if not path.exists():
        return None
    if path.is_file():
        return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)

    latest_ts: float | None = None
    for child in path.rglob("*"):
        if child.is_file():
            child_ts = child.stat().st_mtime
            latest_ts = child_ts if latest_ts is None else max(latest_ts, child_ts)
    if latest_ts is None:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    return datetime.fromtimestamp(latest_ts, tz=timezone.utc)


def parse_last_synced(path: Path) -> datetime | None:
    if not path.exists():
        return None
    for raw_line in read_text(path).splitlines():
        match = LAST_SYNC_RE.match(raw_line.strip())
        if match:
            naive = datetime.strptime(match.group("stamp"), "%Y-%m-%d %H:%M")
            return naive.replace(tzinfo=LOCAL_TZ).astimezone(timezone.utc)
    return None


def path_is_symlink_backed(path: Path) -> bool:
    current = path
    while True:
        if current.is_symlink():
            return True
        if current == ROOT or current.parent == current:
            return False
        current = current.parent


def normalize_task_title(text: str) -> str:
    lowered = (
        text.lower()
        .replace("’", "'")
        .replace("“", '"')
        .replace("”", '"')
        .replace("&", " and ")
        .replace("+", " ")
        .replace("/", " ")
    )
    lowered = re.sub(r"`?\[things:[^`\]]+\]`?", " ", lowered)
    lowered = re.sub(r"[^a-z0-9]+", " ", lowered)
    lowered = re.sub(r"\b(the|a|an|to|for|my|me|and|of|on|at|with|about)\b", " ", lowered)
    lowered = re.sub(r"\s+", " ", lowered).strip()
    return lowered


def tokenize_title(text: str) -> frozenset[str]:
    return frozenset(token for token in text.split() if len(token) >= 3)


def collect_task_records(things_root: Path) -> list[TaskRecord]:
    tasks: list[TaskRecord] = []
    if not things_root.exists():
        return tasks

    for path in sorted(things_root.rglob("*.md")):
        if path.name == "logbook.md":
            continue
        lines = read_text(path).splitlines()
        for index, raw_line in enumerate(lines, start=1):
            match = TASK_LINE_RE.match(raw_line)
            if not match:
                continue
            title = match.group("title").strip()
            things_id = match.group("things_id")
            normalized = normalize_task_title(title)
            when_date = None
            probe = index
            while probe < len(lines):
                follow = lines[probe]
                if follow.startswith("- [") or (follow and not follow.startswith("  ")):
                    break
                stripped = follow.strip()
                if stripped.startswith("- When:"):
                    when_date = stripped.split(":", 1)[1].strip()
                    break
                probe += 1
            tasks.append(
                TaskRecord(
                    path=rel(path),
                    line_no=index,
                    title=title,
                    normalized_title=normalized,
                    token_set=tokenize_title(normalized),
                    things_id=things_id,
                    when_date=when_date,
                )
            )
    return tasks


def find_duplicate_things_ids(tasks: Iterable[TaskRecord]) -> dict[str, list[TaskRecord]]:
    by_id: dict[str, list[TaskRecord]] = {}
    for task in tasks:
        if not task.things_id or task.things_id == "new":
            continue
        by_id.setdefault(task.things_id, []).append(task)
    return {key: value for key, value in by_id.items() if len(value) > 1}


def find_same_file_duplicate_ids(tasks: Iterable[TaskRecord]) -> dict[str, list[TaskRecord]]:
    duplicates: dict[str, list[TaskRecord]] = {}
    for things_id, records in find_duplicate_things_ids(tasks).items():
        by_path = Counter(record.path for record in records)
        if any(count > 1 for count in by_path.values()):
            duplicates[things_id] = records
    return duplicates


def find_inconsistent_id_titles(tasks: Iterable[TaskRecord]) -> dict[str, list[TaskRecord]]:
    inconsistent: dict[str, list[TaskRecord]] = {}
    for things_id, records in find_duplicate_things_ids(tasks).items():
        titles = {record.normalized_title for record in records if record.normalized_title}
        if len(titles) > 1:
            inconsistent[things_id] = records
    return inconsistent


def find_similar_task_pairs(tasks: list[TaskRecord]) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    token_frequency = Counter(
        token for task in tasks for token in task.token_set if token not in {"task", "review", "follow"}
    )
    token_index: dict[str, list[int]] = {}
    for idx, task in enumerate(tasks):
        for token in task.token_set:
            token_index.setdefault(token, []).append(idx)

    seen_pairs: set[tuple[int, int]] = set()
    seen_task_keys: set[tuple[str, str]] = set()
    for idx, left in enumerate(tasks):
        if not left.normalized_title or not left.token_set:
            continue

        informative_tokens = sorted(
            left.token_set,
            key=lambda token: (token_frequency.get(token, 0), token),
        )[:3]
        candidate_indexes: set[int] = set()
        for token in informative_tokens:
            candidate_indexes.update(token_index.get(token, []))

        for candidate_idx in sorted(candidate_indexes):
            if candidate_idx <= idx:
                continue
            pair_key = (idx, candidate_idx)
            if pair_key in seen_pairs:
                continue
            seen_pairs.add(pair_key)

            right = tasks[candidate_idx]
            if not right.normalized_title:
                continue
            if left.things_id and right.things_id and left.things_id == right.things_id:
                continue
            if BIRTHDAY_TASK_RE.search(left.title) and BIRTHDAY_TASK_RE.search(right.title):
                continue

            shared = left.token_set & right.token_set
            union = left.token_set | right.token_set
            if not union:
                continue

            jaccard = len(shared) / len(union)
            ratio = SequenceMatcher(None, left.normalized_title, right.normalized_title).ratio()

            if ratio < 0.84 and jaccard < 0.60:
                continue
            if len(shared) < 3 and ratio < 0.90:
                continue
            if ratio < 0.87 and jaccard < 0.75:
                continue

            left_when = parse_when_date(left.when_date)
            right_when = parse_when_date(right.when_date)
            if left_when and right_when:
                date_gap_days = abs((left_when - right_when).days)
                if date_gap_days > 120:
                    continue

            left_key = left.things_id or left.normalized_title
            right_key = right.things_id or right.normalized_title
            task_key = tuple(sorted((left_key, right_key)))
            if task_key in seen_task_keys:
                continue
            seen_task_keys.add(task_key)

            findings.append(
                {
                    "left": {
                        "path": left.path,
                        "line_no": left.line_no,
                        "title": left.title,
                        "things_id": left.things_id,
                    },
                    "right": {
                        "path": right.path,
                        "line_no": right.line_no,
                        "title": right.title,
                        "things_id": right.things_id,
                    },
                    "sequence_ratio": round(ratio, 3),
                    "token_overlap": round(jaccard, 3),
                }
            )
            if len(findings) >= 250:
                return findings
    return findings


def collect_text_paths() -> list[Path]:
    seen: set[Path] = set()
    files: list[Path] = []
    for path in TOP_LEVEL_TEXT_FILES:
        if path.exists():
            seen.add(path)
            files.append(path)
    for root in TEXT_SCAN_ROOTS:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.md")):
            if path.name == "logbook.md":
                continue
            if path not in seen:
                seen.add(path)
                files.append(path)
    return files


def collect_text_hygiene_findings(files: Iterable[Path]) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    for path in files:
        for line_no, raw_line in enumerate(read_text(path).splitlines(), start=1):
            stripped = raw_line.strip()
            if not stripped:
                continue

            for char, label in INVISIBLE_CHARACTERS.items():
                if char in raw_line:
                    findings.append(
                        {
                            "kind": "invisible-character",
                            "path": rel(path),
                            "line_no": line_no,
                            "message": f"contains {label}",
                        }
                    )

            doubled = DOUBLED_WORD_RE.search(raw_line)
            if doubled:
                findings.append(
                    {
                        "kind": "doubled-word",
                        "path": rel(path),
                        "line_no": line_no,
                        "message": f"possible doubled word '{doubled.group(1)}'",
                    }
                )

            if stripped.startswith(("#", "- [")) and SPACE_BEFORE_PUNCT_RE.search(raw_line):
                findings.append(
                    {
                        "kind": "space-before-punctuation",
                        "path": rel(path),
                        "line_no": line_no,
                        "message": "space before punctuation in heading/task text",
                    }
                )

            if stripped.startswith(("#", "- [")) and REPEATED_PUNCT_RE.search(raw_line):
                findings.append(
                    {
                        "kind": "repeated-punctuation",
                        "path": rel(path),
                        "line_no": line_no,
                        "message": "repeated punctuation in heading/task text",
                    }
                )
    return findings


def parse_when_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def check_launchd(role: str) -> dict:
    target = section("launchd")
    if role != "brain":
        target["details"] = {"skipped": True, "reason": f"launchd production checks only run on brain ({role})"}
        return target

    manifest = load_manifest()
    launchd = load_launchd_snapshot()
    if not launchd:
        add_failure(target, "launchctl list returned no parsable labels")
        return target

    expected_labels: list[tuple[str, str]] = []
    for key, kind in (("scheduled_jobs", "scheduled"), ("persistent_jobs", "persistent")):
        for item in manifest.get(key, []) or []:
            if not isinstance(item, dict) or item.get("enabled", True) is False:
                continue
            label = str(item.get("launchd_label") or "").strip()
            plist = str(item.get("launchd_plist") or "").strip()
            if label:
                expected_labels.append((kind, label))
            elif plist:
                expected_labels.append((kind, Path(plist).stem))

    missing: list[str] = []
    persistent_not_running: list[str] = []
    loaded_count = 0

    for kind, label in expected_labels:
        pid = launchd.get(label)
        if pid is None:
            missing.append(label)
            continue
        loaded_count += 1
        if kind == "persistent" and pid in {"-", "0"}:
            persistent_not_running.append(label)

    if missing:
        add_failure(target, f"missing launchd labels: {', '.join(missing)}")
    if persistent_not_running:
        add_failure(
            target,
            "persistent jobs without active PID: " + ", ".join(persistent_not_running),
        )

    telegram = run_command(["pgrep", "-f", "/core/automation/telegram-bridge.py"])
    telegram_count = len([line for line in telegram.stdout.splitlines() if line.strip()])
    if telegram_count > 1:
        add_failure(target, f"telegram-bridge duplicate processes detected: {telegram_count}")

    target["details"] = {
        "expected_labels": len(expected_labels),
        "loaded_labels": loaded_count,
        "missing_labels": missing,
        "persistent_not_running": persistent_not_running,
        "telegram_bridge_process_count": telegram_count,
        "duplicate_telegram_bridge_processes": telegram_count > 1,
    }
    return target


def check_runtime_script(name: str, repo_root: Path, role: str) -> dict:
    target = section(name)
    if role != "brain":
        target["details"] = {"skipped": True, "reason": f"{name} production health only runs on brain ({role})"}
        return target

    script_path = repo_root / "scripts" / "check-health.sh"

    if not repo_root.exists():
        add_failure(target, f"runtime repo missing: {repo_root}")
        return target
    if not script_path.exists():
        add_failure(target, f"health script missing: {script_path}")
        return target

    result = run_command(["bash", str(script_path)], cwd=repo_root, timeout=30)
    counts = parse_command_output(result.stdout)
    excerpt = [line for line in result.stdout.splitlines() if line.strip()][-25:]

    if result.returncode != 0 or counts["fail"] > 0:
        add_failure(target, f"{name} check-health failed (exit {result.returncode})")
    elif counts["warn"] > 0:
        add_warning(target, f"{name} check-health reported warnings")

    target["details"] = {
        "repo_root": str(repo_root),
        "script": str(script_path),
        "exit_code": result.returncode,
        "counts": counts,
        "output_excerpt": excerpt,
    }
    return target


def check_authoring_workspace(role: str) -> dict:
    target = section("authoring-workspace")
    if role != "laptop":
        target["details"] = {"skipped": True, "reason": f"authoring workspace checks only run on laptop ({role})"}
        return target

    repos = {
        "personal-os": ROOT,
        "automation-machine-config": MACHINE_CONFIG,
        "automation-runtime-personal": RUNTIME_PERSONAL,
        "automation-runtime-work": RUNTIME_WORK,
        "pnt-data-warehouse": PNT_REPO,
    }
    repo_details: dict[str, object] = {}

    for name, path in repos.items():
        info: dict[str, object] = {"path": str(path)}
        if not path.exists():
            add_failure(target, f"repo missing: {name} ({path})")
            info["exists"] = False
            repo_details[name] = info
            continue

        info["exists"] = True
        git_dir = path / ".git"
        if not git_dir.exists():
            add_failure(target, f"not a git repo: {name} ({path})")
            info["git_repo"] = False
            repo_details[name] = info
            continue

        info["git_repo"] = True
        branch = run_command(["git", "-C", str(path), "branch", "--show-current"]).stdout.strip()
        upstream = run_command(["git", "-C", str(path), "rev-parse", "--abbrev-ref", "@{u}"]).stdout.strip()
        status_lines = run_command(["git", "-C", str(path), "status", "--short"]).stdout.splitlines()
        dirty_count = len([line for line in status_lines if line.strip()])

        if dirty_count > 0:
            add_warning(target, f"repo has uncommitted changes: {name} ({dirty_count})")

        info.update(
            {
                "branch": branch,
                "upstream": upstream,
                "dirty_count": dirty_count,
                "dirty_excerpt": status_lines[:20],
            }
        )
        repo_details[name] = info

    target["details"] = {"repos": repo_details}
    return target


def pnt_path_is_runtime_only(path: str) -> bool:
    return any(pattern.search(path) for pattern in PNT_RUNTIME_ONLY_PATTERNS)


def check_pnt_runtime(role: str) -> dict:
    target = section("pnt-runtime")
    if role != "brain":
        target["details"] = {"skipped": True, "reason": f"PnT production runtime checks only run on brain ({role})"}
        return target

    launchd = load_launchd_snapshot()
    details: dict[str, object] = {
        "repo_root": str(PNT_REPO),
        "log_dir": str(PNT_LOG_DIR),
    }

    if not PNT_REPO.exists():
        add_failure(target, f"pnt-data-warehouse repo missing: {PNT_REPO}")
        target["details"] = details
        return target

    git_dir = PNT_REPO / ".git"
    if not git_dir.exists():
        add_failure(target, f"pnt-data-warehouse is not a git repo: {PNT_REPO}")

    branch = run_command(["git", "-C", str(PNT_REPO), "branch", "--show-current"]).stdout.strip()
    head = run_command(["git", "-C", str(PNT_REPO), "rev-parse", "--short", "HEAD"]).stdout.strip()
    upstream = run_command(
        ["git", "-C", str(PNT_REPO), "rev-parse", "--abbrev-ref", "@{u}"]
    ).stdout.strip()

    if not branch:
        add_failure(target, "pnt-data-warehouse branch could not be determined")
    if not upstream:
        add_failure(target, "pnt-data-warehouse branch has no upstream")

    if not (PNT_REPO / ".env.toast").exists():
        add_failure(target, "pnt-data-warehouse runtime env missing (.env.toast)")
    if not PNT_LOG_DIR.exists():
        add_failure(target, f"pnt-data-warehouse log directory missing: {PNT_LOG_DIR}")

    missing_files = [
        path for path in PNT_REQUIRED_FILES if not (PNT_REPO / path).exists()
    ]
    for path in missing_files:
        add_failure(target, f"pnt-data-warehouse required file missing: {path}")

    missing_labels = [label for label in PNT_REQUIRED_LABELS if label not in launchd]
    for label in missing_labels:
        add_failure(target, f"required launchd not loaded: {label}")

    optional_missing: list[str] = []
    for label, message in PNT_OPTIONAL_LABEL_MESSAGES.items():
        if label not in launchd:
            optional_missing.append(label)
            rendered = message.format(label=label)
            if "(expected" in rendered:
                add_note(target, rendered)
            else:
                add_warning(target, rendered)

    git_status = run_command(["git", "-C", str(PNT_REPO), "status", "--short"]).stdout.splitlines()
    runtime_only = 0
    source_changes = 0
    for raw_line in git_status:
        if len(raw_line) < 4:
            continue
        changed_path = raw_line[3:].strip()
        if pnt_path_is_runtime_only(changed_path):
            runtime_only += 1
        else:
            source_changes += 1

    if runtime_only:
        add_warning(target, f"PnT runtime artifacts present in working tree ({runtime_only} entries)")
    if source_changes:
        add_failure(target, f"PnT source changes present in working tree ({source_changes} entries)")

    details.update(
        {
            "branch": branch,
            "head": head,
            "upstream": upstream,
            "missing_required_files": missing_files,
            "missing_required_labels": missing_labels,
            "missing_optional_labels": optional_missing,
            "runtime_artifact_changes": runtime_only,
            "source_changes": source_changes,
        }
    )
    target["details"] = details
    return target


def check_local_syntax() -> dict:
    target = section("local-syntax")
    python_result = run_command(
        ["python3", "-m", "compileall", str(ROOT / "scripts"), str(ROOT / "core" / "automation")]
    )
    if python_result.returncode != 0:
        add_failure(target, "python syntax compile failed for local automation code")

    shell_failures: list[str] = []
    for shell_file in sorted((ROOT / "scripts").glob("*.sh")) + sorted((ROOT / "core" / "automation").glob("*.sh")):
        result = run_command(["bash", "-n", str(shell_file)])
        if result.returncode != 0:
            shell_failures.append(rel(shell_file))

    if shell_failures:
        add_failure(target, "shell syntax check failed: " + ", ".join(shell_failures))

    target["details"] = {
        "python_compile_exit_code": python_result.returncode,
        "python_compile_excerpt": [line for line in python_result.stdout.splitlines() if line.strip()][-20:],
        "shell_syntax_failures": shell_failures,
    }
    return target


def check_vault_audit() -> dict:
    target = section("vault-audit")
    audit_script = ROOT / "scripts" / "audit_personal_os.py"
    result = run_command(["python3", str(audit_script)], cwd=ROOT)

    counts: dict[str, int] = {}
    json_match = re.search(r"\{[\s\S]*?\}", result.stdout)
    if json_match:
        try:
            counts = json.loads(json_match.group(0))
        except json.JSONDecodeError:
            counts = {}
    total = sum(int(value) for value in counts.values())

    if result.returncode != 0:
        add_failure(target, f"audit_personal_os exited with code {result.returncode}")
    if total > 0:
        add_failure(target, f"audit_personal_os findings detected: {counts}")

    target["details"] = {
        "script": str(audit_script),
        "exit_code": result.returncode,
        "counts": counts,
        "output_excerpt": [line for line in result.stdout.splitlines() if line.strip()][-30:],
    }
    return target


def check_state_links(role: str) -> dict:
    target = section("state-links")
    if role != "brain":
        target["details"] = {"skipped": True, "reason": f"state-link integrity only runs on brain ({role})"}
        return target

    state_dir = ROOT / "core" / "state"
    live_sync_vault = not (ROOT / ".git").exists()

    manifest = load_manifest()
    manifest_state_paths = sorted(
        {
            item
            for section_name in ("scheduled_jobs", "persistent_jobs", "manual_or_on_demand")
            for entry in manifest.get(section_name, []) or []
            if isinstance(entry, dict)
            for item in (
                ([entry.get("state_file")] if entry.get("state_file") else [])
                + list(entry.get("state_files", []) or [])
            )
            if isinstance(item, str) and item.startswith("core/state/")
        }
    )

    broken_links: list[str] = []
    regular_state_files: list[str] = []
    existing_manifest_paths: list[str] = []
    healthy_links = 0

    for rel_path in manifest_state_paths:
        path = ROOT / rel_path
        if not path.exists() and not path.is_symlink():
            continue
        existing_manifest_paths.append(rel_path)
        if path_is_symlink_backed(path):
            if path.resolve(strict=False).exists():
                healthy_links += 1
            else:
                broken_links.append(rel_path)
        elif live_sync_vault and rel_path not in BRAIN_LOCAL_STATE_ALLOWLIST:
            regular_state_files.append(rel_path)

    for path in broken_links:
        add_failure(target, f"broken state symlink: {path}")
    for path in regular_state_files:
        add_warning(target, f"production state path is not a symlink: {path}")

    target["details"] = {
        "live_sync_vault": live_sync_vault,
        "manifest_state_paths": manifest_state_paths,
        "existing_manifest_paths": existing_manifest_paths,
        "healthy_symlink_count": healthy_links,
        "broken_symlinks": broken_links,
        "non_symlink_state_paths": regular_state_files,
    }
    return target


def check_freshness(now: datetime) -> dict:
    target = section("freshness")
    stale_items: list[dict[str, object]] = []
    missing_items: list[str] = []

    role = detect_host_role()
    if role == "brain":
        for label, path, max_age_hours in FRESHNESS_RULES:
            latest = latest_mtime(path)
            if latest is None:
                missing_items.append(label)
                add_warning(target, f"{label} missing at {path}")
                continue
            age_hours = round((now - latest).total_seconds() / 3600, 2)
            if age_hours > max_age_hours:
                stale_items.append(
                    {
                        "label": label,
                        "path": str(path),
                        "age_hours": age_hours,
                        "max_age_hours": max_age_hours,
                    }
                )
                add_warning(
                    target,
                    f"{label} is stale ({age_hours}h > {max_age_hours}h)",
                )

    sync_timestamps: dict[str, str | None] = {}
    stale_sync_files: list[str] = []
    for path in THINGS_LAST_SYNC_FILES:
        stamp = parse_last_synced(path)
        sync_timestamps[rel(path)] = stamp.isoformat() if stamp else None
        if stamp is None:
            continue
        age_hours = round((now - stamp).total_seconds() / 3600, 2)
        if age_hours > 72:
            stale_sync_files.append(rel(path))
            add_warning(target, f"Things sync snapshot is stale: {rel(path)} ({age_hours}h)")

    target["details"] = {
        "role": role,
        "stale_items": stale_items,
        "missing_items": missing_items,
        "things_last_synced": sync_timestamps,
        "stale_things_sync_files": stale_sync_files,
    }
    return target


def check_content_hygiene() -> dict:
    target = section("content-hygiene")
    tasks = collect_task_records(ROOT / "things-sync")
    same_file_duplicate_ids = find_same_file_duplicate_ids(tasks)
    inconsistent_id_titles = find_inconsistent_id_titles(tasks)
    similar_pairs = find_similar_task_pairs(tasks)
    text_findings = collect_text_hygiene_findings(collect_text_paths())

    for things_id, records in same_file_duplicate_ids.items():
        locations = ", ".join(f"{record.path}:{record.line_no}" for record in records)
        add_failure(target, f"duplicate Things id {things_id}: {locations}")

    for things_id, records in inconsistent_id_titles.items():
        titles = ", ".join(sorted({record.title for record in records}))
        add_warning(target, f"Things id {things_id} has inconsistent titles: {titles}")

    if similar_pairs:
        add_warning(target, f"potential duplicate task titles detected ({len(similar_pairs)})")

    if text_findings:
        kind_counts = Counter(item["kind"] for item in text_findings)
        formatted = ", ".join(f"{kind}={count}" for kind, count in sorted(kind_counts.items()))
        add_warning(target, f"content hygiene findings detected: {formatted}")

    target["details"] = {
        "task_count": len(tasks),
        "same_file_duplicate_things_ids": {
            key: [
                {"path": record.path, "line_no": record.line_no, "title": record.title}
                for record in value
            ]
            for key, value in same_file_duplicate_ids.items()
        },
        "inconsistent_things_id_titles": {
            key: [
                {"path": record.path, "line_no": record.line_no, "title": record.title}
                for record in value
            ]
            for key, value in inconsistent_id_titles.items()
        },
        "similar_task_pairs": similar_pairs[:25],
        "similar_task_pair_count": len(similar_pairs),
        "text_hygiene_findings": text_findings[:50],
        "text_hygiene_finding_count": len(text_findings),
    }
    return target


def build_report(now: datetime | None = None) -> dict:
    current = now or _utc_now()
    role = detect_host_role()
    checks = {
        "launchd": check_launchd(role),
        "runtime_personal": check_runtime_script("runtime-personal", RUNTIME_PERSONAL, role),
        "runtime_work": check_runtime_script("runtime-work", RUNTIME_WORK, role),
        "authoring_workspace": check_authoring_workspace(role),
        "pnt_runtime": check_pnt_runtime(role),
        "local_syntax": check_local_syntax(),
        "vault_audit": check_vault_audit(),
        "state_links": check_state_links(role),
        "freshness": check_freshness(current),
        "content_hygiene": check_content_hygiene(),
    }

    total_failures = sum(item["failure_count"] for item in checks.values())
    total_warnings = sum(item["warning_count"] for item in checks.values())
    overall_status = "ok" if total_failures == 0 and total_warnings == 0 else "warning"

    summary_lines: list[str] = []
    for name, item in checks.items():
        if item["failures"]:
            summary_lines.append(f"{name}: {item['failures'][0]}")
        elif item["warnings"]:
            summary_lines.append(f"{name}: {item['warnings'][0]}")

    report = {
        "timestamp_utc": current.isoformat(),
        "host": platform.node(),
        "host_role": role,
        "overall_status": overall_status,
        "summary": {
            "failure_count": total_failures,
            "warning_count": total_warnings,
            "headline": f"{total_failures} failures, {total_warnings} warnings",
            "lines": summary_lines[:12],
        },
        # Preserve legacy top-level keys for downstream compatibility.
        "launchd": checks["launchd"]["details"],
        "telegram_bridge": {
            "process_count": checks["launchd"]["details"].get("telegram_bridge_process_count", 0),
            "duplicate_processes": checks["launchd"]["details"].get(
                "duplicate_telegram_bridge_processes", False
            ),
        },
        "audit_personal_os": {
            "exit_code": checks["vault_audit"]["details"].get("exit_code", 0),
            "counts": checks["vault_audit"]["details"].get("counts", {}),
        },
        "checks": checks,
    }
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the Personal OS system health audit.")
    parser.add_argument("--state-file", type=Path, help="Write JSON report to this path.")
    args = parser.parse_args(argv)

    report = build_report()
    rendered = json.dumps(report, indent=2) + "\n"

    if args.state_file:
        args.state_file.parent.mkdir(parents=True, exist_ok=True)
        args.state_file.write_text(rendered, encoding="utf-8")

    sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
