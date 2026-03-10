from __future__ import annotations

import argparse
import json
from pathlib import Path
import sqlite3
import sys
import uuid

from triage_v2.api import serve_api
from triage_v2.config import AppConfig, ensure_directories, load_config
from triage_v2.db import (
    connect,
    enqueue_task,
    fetch_artifacts,
    fetch_coverage,
    fetch_run,
    init_db,
    insert_run,
)
from triage_v2.pipeline import generate_run_id, load_required_fixture, verify_missed_fixture
from triage_v2.project_refresh import run_project_refresh
from triage_v2.oauth import perform_installed_app_oauth
from triage_v2.providers.gmail_api import GmailApiClient
from triage_v2.worker import Worker


def _setup_conn() -> tuple[sqlite3.Connection, argparse.Namespace, AppConfig]:
    parser = argparse.ArgumentParser(description="Inbox triage v2")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init-db", help="Create/upgrade local triage-v2 sqlite schema")
    sub.add_parser("refresh-projects", help="Refresh project briefs from comms + Granola transcripts")

    enqueue = sub.add_parser("enqueue-run", help="Create run + queue task")
    enqueue.add_argument("--run-type", choices=("am", "pm", "manual"), default="manual")
    enqueue.add_argument("--force-reconcile", action="store_true")

    run_now = sub.add_parser("run-now", help="Queue and process one run immediately")
    run_now.add_argument("--run-type", choices=("am", "pm", "manual"), default="manual")
    run_now.add_argument("--force-reconcile", action="store_true")

    sub.add_parser("worker-once", help="Process one queued task")

    loop = sub.add_parser("worker-loop", help="Continuously process queued tasks")
    loop.add_argument("--sleep-seconds", type=float, default=2.0)

    serve = sub.add_parser("serve-api", help="Serve triage API")
    serve.add_argument("--host", default="0.0.0.0")
    serve.add_argument("--port", type=int, default=8080)

    status = sub.add_parser("run-status", help="Show run status and coverage")
    status.add_argument("--run-id", required=True)

    verify = sub.add_parser("verify-fixture", help="Verify a run against required missed-email fixture")
    verify.add_argument("--run-id", required=True)
    verify.add_argument(
        "--fixture",
        default="/Users/homeserver/Obsidian/personal-os/core/state/email-triage-v2/missed-email-fixture.json",
        help="Path to JSON fixture containing required message IDs",
    )

    sub.add_parser("check-gmail-auth", help="Validate Gmail OAuth tokens for work and personal accounts")

    oauth_init = sub.add_parser("oauth-init", help="Run direct Google OAuth and write Gmail token.json for an account")
    oauth_init.add_argument("--account", choices=("work", "personal"), required=True)
    oauth_init.add_argument(
        "--oauth-client",
        default="/Users/homeserver/.config/personal-os-secrets/google-oauth/gcp-oauth.keys.json",
        help="Path to OAuth client JSON (installed app)",
    )
    oauth_init.add_argument("--port", type=int, default=8765, help="Local callback port")
    oauth_init.add_argument(
        "--no-open-browser",
        action="store_true",
        help="Print auth URL without auto-opening browser",
    )

    args = parser.parse_args()
    cfg = load_config()
    ensure_directories(cfg)

    conn = connect(cfg.db_path)
    init_db(conn)

    return conn, args, cfg


def _enqueue(conn: sqlite3.Connection, run_type: str, force_reconcile: bool) -> tuple[str, str]:
    run_id = generate_run_id()
    task_id = f"task-{uuid.uuid4().hex[:12]}"
    insert_run(conn, run_id, run_type, "queued", force_reconcile)
    enqueue_task(
        conn,
        task_id,
        "triage_run",
        {
            "run_id": run_id,
            "run_type": run_type,
            "force_reconcile": force_reconcile,
        },
    )
    return run_id, task_id


def main() -> int:
    conn, args, cfg = _setup_conn()

    if args.cmd == "init-db":
        print(json.dumps({"ok": True, "db_path": str(cfg.db_path)}))
        return 0

    if args.cmd == "refresh-projects":
        result = run_project_refresh(cfg)
        print(json.dumps(result, ensure_ascii=True, indent=2))
        return 0

    if args.cmd == "enqueue-run":
        run_id, task_id = _enqueue(conn, args.run_type, bool(args.force_reconcile))
        print(json.dumps({"run_id": run_id, "task_id": task_id, "status": "queued"}, ensure_ascii=True))
        return 0

    if args.cmd == "run-now":
        run_id, task_id = _enqueue(conn, args.run_type, bool(args.force_reconcile))
        worker = Worker(conn, cfg)
        result = worker.process_once()
        print(
            json.dumps(
                {
                    "run_id": run_id,
                    "task_id": task_id,
                    "worker_result": result,
                },
                ensure_ascii=True,
                indent=2,
            )
        )
        return 0

    if args.cmd == "worker-once":
        worker = Worker(conn, cfg)
        result = worker.process_once()
        print(json.dumps({"result": result}, ensure_ascii=True, indent=2))
        return 0

    if args.cmd == "worker-loop":
        worker = Worker(conn, cfg)
        processed = worker.loop(sleep_seconds=float(args.sleep_seconds))
        print(json.dumps({"processed": processed}, ensure_ascii=True))
        return 0

    if args.cmd == "serve-api":
        serve_api(conn, cfg, host=args.host, port=int(args.port))
        return 0

    if args.cmd == "run-status":
        run = fetch_run(conn, args.run_id)
        coverage = fetch_coverage(conn, args.run_id)
        artifacts = fetch_artifacts(conn, args.run_id)
        print(
            json.dumps(
                {
                    "run": run,
                    "coverage": coverage,
                    "artifacts": artifacts,
                },
                ensure_ascii=True,
                indent=2,
            )
        )
        return 0

    if args.cmd == "verify-fixture":
        fixture_ids = load_required_fixture(Path(args.fixture))
        result = verify_missed_fixture(conn, args.run_id, fixture_ids)
        print(json.dumps(result, ensure_ascii=True, indent=2))
        return 0

    if args.cmd == "check-gmail-auth":
        checks = []
        for account in cfg.enabled_accounts:
            token_path = (
                cfg.gmail_work_home / "token.json"
                if account == "work"
                else cfg.gmail_personal_home / "token.json"
            )
            try:
                client = GmailApiClient(token_path)
                hid = client.get_latest_history_id()
                checks.append(
                    {
                        "account": account,
                        "status": "ok",
                        "token_path": str(token_path),
                        "history_id_present": bool(hid),
                    }
                )
            except Exception as exc:
                checks.append(
                    {
                        "account": account,
                        "status": "error",
                        "token_path": str(token_path),
                        "error": str(exc),
                        "reauth_hint": (
                            "Run: python3 -m triage_v2 oauth-init --account "
                            + account
                            + " --oauth-client /path/to/your-google-oauth-client.json"
                        ),
                    }
                )
        print(json.dumps({"checks": checks}, ensure_ascii=True, indent=2))
        return 0

    if args.cmd == "oauth-init":
        token_path = (
            cfg.gmail_work_home / "token.json"
            if args.account == "work"
            else cfg.gmail_personal_home / "token.json"
        )
        result = perform_installed_app_oauth(
            oauth_client_path=Path(args.oauth_client),
            token_output_path=token_path,
            account_label=args.account,
            port=int(args.port),
            open_browser=not bool(args.no_open_browser),
        )
        print(json.dumps(result, ensure_ascii=True, indent=2))
        return 0

    print(f"Unknown command: {args.cmd}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
