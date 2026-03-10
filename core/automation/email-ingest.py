#!/usr/bin/env python3
"""Compatibility wrapper for the email ingest helper.

The implementation now lives in automation-runtime-work. Keep this file so
repo-local tests and callers that still expect the old path continue to work.
"""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
from typing import Any


EXTERNAL_MODULE_PATH = (
    Path.home() / "Projects" / "automation-runtime-work" / "core" / "automation" / "email-ingest.py"
)


def _load_external_module():
    spec = importlib.util.spec_from_file_location("automation_runtime_work_email_ingest", EXTERNAL_MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load email ingest helper at {EXTERNAL_MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_MODULE = _load_external_module()

build_parser = _MODULE.build_parser
collect_account_events = _MODULE.collect_account_events
main = _MODULE.main

DEFAULT_STATE = _MODULE.DEFAULT_STATE
append_events = _MODULE.append_events
dedupe_preserve = _MODULE.dedupe_preserve
load_json = _MODULE.load_json
select_cutoff = _MODULE.select_cutoff
to_iso = _MODULE.to_iso
utc_now = _MODULE.utc_now
write_json = _MODULE.write_json


def run_ingest(args: argparse.Namespace) -> dict[str, Any]:
    state_path = Path(args.state_file)
    events_path = Path(args.events_file)

    state_raw = load_json(state_path, {})
    state = {**DEFAULT_STATE, **(state_raw if isinstance(state_raw, dict) else {})}
    warnings: list[str] = []

    cutoff = select_cutoff(state)
    since_iso = to_iso(cutoff)
    existing_seen = [value for value in state.get("seen_event_ids", []) if isinstance(value, str)]
    seen_event_ids = set(existing_seen)

    work_events = collect_account_events(
        account="work",
        cutoff=cutoff,
        seen_event_ids=seen_event_ids,
        args=args,
        warnings=warnings,
    )
    personal_events = collect_account_events(
        account="personal",
        cutoff=cutoff,
        seen_event_ids=seen_event_ids,
        args=args,
        warnings=warnings,
    )

    all_events = sorted([*work_events, *personal_events], key=lambda item: item.get("timestamp", ""))
    now_iso = to_iso(utc_now())

    if not args.dry_run:
        append_events(events_path, all_events)

    state["last_ingest_timestamp"] = now_iso
    state["runs"] = int(state.get("runs", 0)) + 1
    state["seen_event_ids"] = dedupe_preserve(existing_seen + [event["event_id"] for event in all_events], 3000)
    state["last_run_stats"] = {
        "new_email_events_work": len(work_events),
        "new_email_events_personal": len(personal_events),
        "total_new_events": len(all_events),
    }
    state["last_warnings"] = warnings
    if "last_failure" in state:
        state.pop("last_failure", None)
    if not args.dry_run:
        write_json(state_path, state)

    return {
        "ok": True,
        "since": since_iso,
        "now": now_iso,
        "new_email_events_work": len(work_events),
        "new_email_events_personal": len(personal_events),
        "total_new_events": len(all_events),
        "warnings": warnings,
        "dry_run": bool(args.dry_run),
    }


if __name__ == "__main__":
    raise SystemExit(main())
