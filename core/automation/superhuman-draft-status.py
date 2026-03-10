#!/usr/bin/env python3
"""
Persist and query Superhuman draft outcomes by thread.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_STATE_PATH = Path("/Users/homeserver/Obsidian/personal-os/core/state/superhuman-draft-status.json")


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"threads": {}, "compose": {}, "updated_at": None}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"threads": {}, "compose": {}, "updated_at": None}
    if not isinstance(raw, dict):
        return {"threads": {}, "compose": {}, "updated_at": None}
    if not isinstance(raw.get("threads"), dict):
        raw["threads"] = {}
    if not isinstance(raw.get("compose"), dict):
        raw["compose"] = {}
    return raw


def save_state(path: Path, state: dict[str, Any]) -> None:
    state["updated_at"] = now_iso()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def cmd_record(args: argparse.Namespace) -> int:
    state_path = Path(args.state_file)
    state = load_state(state_path)

    payload: dict[str, Any] = {
        "request_id": args.request_id,
        "mode": args.mode,
        "status": args.status,
        "account": args.account,
        "updated_at": now_iso(),
        "note": args.note or "",
    }

    if args.mode == "reply":
        if not args.thread_id:
            raise SystemExit("--thread-id is required when --mode reply")
        key = f"{args.account}:{args.thread_id}"
        payload["thread_id"] = args.thread_id
        state["threads"][key] = payload
        print(json.dumps({"ok": True, "key": key, "record": payload}, indent=2))
    else:
        compose_key = args.request_id or now_iso()
        state["compose"][compose_key] = payload
        print(json.dumps({"ok": True, "key": compose_key, "record": payload}, indent=2))

    save_state(state_path, state)
    return 0


def cmd_lookup(args: argparse.Namespace) -> int:
    state_path = Path(args.state_file)
    state = load_state(state_path)
    key = f"{args.account}:{args.thread_id}"
    rec = state.get("threads", {}).get(key)
    if not rec:
        print(json.dumps({"ok": True, "key": key, "status": "unknown"}, indent=2))
        return 0
    print(json.dumps({"ok": True, "key": key, **rec}, indent=2))
    return 0


def cmd_dump(args: argparse.Namespace) -> int:
    state_path = Path(args.state_file)
    state = load_state(state_path)
    print(json.dumps(state, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Superhuman draft status tracker")
    parser.add_argument(
        "--state-file",
        default=str(DEFAULT_STATE_PATH),
        help="Path to superhuman-draft-status.json",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    record = sub.add_parser("record", help="Record draft outcome")
    record.add_argument("--mode", choices=("reply", "compose"), required=True)
    record.add_argument("--status", choices=("queued_pending", "executing", "queued", "clipboard", "failed"), required=True)
    record.add_argument("--request-id", default="")
    record.add_argument("--account", required=True)
    record.add_argument("--thread-id", default="")
    record.add_argument("--note", default="")
    record.set_defaults(func=cmd_record)

    lookup = sub.add_parser("lookup", help="Lookup final draft status for a thread")
    lookup.add_argument("--account", required=True)
    lookup.add_argument("--thread-id", required=True)
    lookup.set_defaults(func=cmd_lookup)

    dump = sub.add_parser("dump", help="Dump status state")
    dump.set_defaults(func=cmd_dump)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
