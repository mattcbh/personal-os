from __future__ import annotations

import json
import sqlite3
import time
from typing import Any

from triage_v2.config import AppConfig
from triage_v2.db import claim_next_task, complete_task, fail_task
from triage_v2.pipeline import run_pipeline


class Worker:
    def __init__(self, conn: sqlite3.Connection, cfg: AppConfig) -> None:
        self.conn = conn
        self.cfg = cfg

    def process_once(self) -> dict[str, Any] | None:
        task = claim_next_task(self.conn)
        if task is None:
            return None

        task_id = str(task["task_id"])
        payload = json.loads(task["payload_json"])
        task_type = str(task["task_type"])

        try:
            if task_type != "triage_run":
                raise ValueError(f"Unsupported task type: {task_type}")

            run_id = str(payload["run_id"])
            run_type = str(payload.get("run_type") or "manual")
            force_reconcile = bool(payload.get("force_reconcile"))
            result = run_pipeline(
                conn=self.conn,
                cfg=self.cfg,
                run_id=run_id,
                run_type=run_type,
                force_reconcile=force_reconcile,
            )
            complete_task(self.conn, task_id)
            return {
                "task_id": task_id,
                "task_type": task_type,
                "result": result,
            }
        except Exception as exc:
            fail_task(self.conn, task_id, str(exc))
            return {
                "task_id": task_id,
                "task_type": task_type,
                "error": str(exc),
            }

    def loop(self, sleep_seconds: float = 2.0, max_idle_cycles: int | None = None) -> int:
        idle_cycles = 0
        processed = 0
        while True:
            result = self.process_once()
            if result is None:
                idle_cycles += 1
                if max_idle_cycles is not None and idle_cycles >= max_idle_cycles:
                    return processed
                time.sleep(sleep_seconds)
                continue
            processed += 1
            idle_cycles = 0
