from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import sqlite3
from typing import Any
import uuid

from triage_v2.config import AppConfig
from triage_v2.db import (
    enqueue_task,
    fetch_artifacts,
    fetch_coverage,
    fetch_entries,
    fetch_run,
    insert_run,
)
from triage_v2.pipeline import generate_run_id, retry_failed_drafts


class ApiHandler(BaseHTTPRequestHandler):
    server_version = "triage-v2-api/0.1"

    def _json_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        if not raw:
            return {}
        try:
            payload = json.loads(raw)
        except Exception:
            return {}
        return payload if isinstance(payload, dict) else {}

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        out = json.dumps(payload, ensure_ascii=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    @property
    def conn(self) -> sqlite3.Connection:
        return self.server.db_conn  # type: ignore[attr-defined]

    @property
    def cfg(self) -> AppConfig:
        return self.server.cfg  # type: ignore[attr-defined]

    def do_POST(self) -> None:
        if self.path == "/triage/runs":
            self._create_run()
            return
        if self.path == "/triage/drafts/retry":
            self._retry_drafts()
            return
        self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})

    def do_GET(self) -> None:
        if self.path.startswith("/triage/runs/"):
            suffix = self.path.removeprefix("/triage/runs/")
            if suffix.endswith("/digest"):
                run_id = suffix[:-7]
                self._get_digest(run_id)
                return
            self._get_run(suffix)
            return
        if self.path == "/healthz":
            self._send_json(HTTPStatus.OK, {"ok": True})
            return
        self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})

    def _create_run(self) -> None:
        body = self._json_body()
        run_type = str(body.get("run_type") or "manual").lower()
        force_reconcile = bool(body.get("force_reconcile", False))
        if run_type not in {"am", "pm", "manual"}:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid_run_type"})
            return

        run_id = generate_run_id()
        task_id = f"task-{uuid.uuid4().hex[:12]}"

        insert_run(self.conn, run_id, run_type, "queued", force_reconcile)
        enqueue_task(
            self.conn,
            task_id,
            "triage_run",
            {
                "run_id": run_id,
                "run_type": run_type,
                "force_reconcile": force_reconcile,
            },
        )

        self._send_json(
            HTTPStatus.ACCEPTED,
            {
                "run_id": run_id,
                "task_id": task_id,
                "status_url": f"/triage/runs/{run_id}",
            },
        )

    def _get_run(self, run_id: str) -> None:
        run = fetch_run(self.conn, run_id)
        if run is None:
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "run_not_found"})
            return
        coverage = fetch_coverage(self.conn, run_id)
        artifacts = fetch_artifacts(self.conn, run_id)
        self._send_json(
            HTTPStatus.OK,
            {
                "run": run,
                "coverage": coverage,
                "artifacts": artifacts,
            },
        )

    def _get_digest(self, run_id: str) -> None:
        run = fetch_run(self.conn, run_id)
        if run is None:
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "run_not_found"})
            return

        artifacts = fetch_artifacts(self.conn, run_id)
        if not artifacts:
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "digest_not_ready"})
            return

        markdown = ""
        html = ""
        try:
            markdown = open(artifacts["markdown_path"], "r", encoding="utf-8").read()
            html = open(artifacts["html_path"], "r", encoding="utf-8").read()
        except Exception:
            pass

        self._send_json(
            HTTPStatus.OK,
            {
                "run_id": run_id,
                "run_status": run["status"],
                "entries": fetch_entries(self.conn, run_id),
                "markdown": markdown,
                "html": html,
            },
        )

    def _retry_drafts(self) -> None:
        body = self._json_body()
        run_id = str(body.get("run_id") or "").strip()
        if not run_id:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "run_id_required"})
            return

        result = retry_failed_drafts(self.conn, self.cfg, run_id)
        self._send_json(HTTPStatus.OK, result)

    def log_message(self, fmt: str, *args: Any) -> None:
        # Suppress noisy default logs; Cloud Run will capture explicit app logs.
        return


def serve_api(conn: sqlite3.Connection, cfg: AppConfig, host: str, port: int) -> None:
    server = ThreadingHTTPServer((host, port), ApiHandler)
    server.db_conn = conn  # type: ignore[attr-defined]
    server.cfg = cfg  # type: ignore[attr-defined]
    server.serve_forever()
