from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS account_checkpoints (
            account TEXT PRIMARY KEY,
            history_id TEXT,
            last_message_ts TEXT,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS triage_runs (
            run_id TEXT PRIMARY KEY,
            run_type TEXT NOT NULL,
            status TEXT NOT NULL,
            send_status TEXT NOT NULL,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            force_reconcile INTEGER NOT NULL DEFAULT 0,
            error_message TEXT
        );

        CREATE TABLE IF NOT EXISTS messages_raw (
            message_id TEXT PRIMARY KEY,
            account TEXT NOT NULL,
            thread_id TEXT NOT NULL,
            received_at TEXT NOT NULL,
            sender_email TEXT NOT NULL,
            sender_name TEXT NOT NULL,
            subject TEXT NOT NULL,
            snippet TEXT NOT NULL,
            body_preview TEXT,
            list_unsubscribe TEXT,
            metadata_json TEXT NOT NULL,
            ingested_at TEXT NOT NULL,
            run_id TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS triage_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            account TEXT NOT NULL,
            thread_id TEXT NOT NULL,
            bucket TEXT NOT NULL,
            sender_email TEXT NOT NULL,
            sender_name TEXT NOT NULL,
            subject_latest TEXT NOT NULL,
            summary_latest TEXT NOT NULL,
            response_needed INTEGER NOT NULL DEFAULT 0,
            suggested_response TEXT,
            suggested_action TEXT,
            monitoring_owner TEXT,
            monitoring_deliverable TEXT,
            monitoring_deadline TEXT,
            draft_status TEXT NOT NULL,
            draft_authoring_mode TEXT NOT NULL DEFAULT 'deterministic',
            draft_context_status TEXT NOT NULL DEFAULT 'unmatched',
            draft_authoring_error TEXT,
            thread_url TEXT NOT NULL,
            draft_url TEXT,
            unsubscribe_url TEXT,
            accounted_reason TEXT NOT NULL,
            message_ids_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_triage_entries_run_id ON triage_entries(run_id);
        CREATE INDEX IF NOT EXISTS idx_triage_entries_thread ON triage_entries(account, thread_id);

        CREATE TABLE IF NOT EXISTS draft_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            account TEXT NOT NULL,
            thread_id TEXT NOT NULL,
            adapter TEXT NOT NULL,
            status TEXT NOT NULL,
            draft_url TEXT,
            error_message TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS coverage_reports (
            run_id TEXT PRIMARY KEY,
            expected_count INTEGER NOT NULL,
            accounted_count INTEGER NOT NULL,
            missing_count INTEGER NOT NULL,
            duplicate_count INTEGER NOT NULL,
            pass INTEGER NOT NULL,
            expected_message_ids_json TEXT NOT NULL,
            accounted_message_ids_json TEXT NOT NULL,
            missing_message_ids_json TEXT NOT NULL,
            duplicate_thread_keys_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS run_artifacts (
            run_id TEXT PRIMARY KEY,
            markdown_path TEXT NOT NULL,
            html_path TEXT NOT NULL,
            json_path TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS queue_tasks (
            task_id TEXT PRIMARY KEY,
            task_type TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            status TEXT NOT NULL,
            attempts INTEGER NOT NULL DEFAULT 0,
            available_at TEXT NOT NULL,
            last_error TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_queue_tasks_status_available ON queue_tasks(status, available_at);
        """
    )
    _ensure_column(conn, "triage_entries", "draft_authoring_mode", "TEXT NOT NULL DEFAULT 'deterministic'")
    _ensure_column(conn, "triage_entries", "draft_context_status", "TEXT NOT NULL DEFAULT 'unmatched'")
    _ensure_column(conn, "triage_entries", "draft_authoring_error", "TEXT")
    _ensure_column(conn, "triage_entries", "response_needed", "INTEGER NOT NULL DEFAULT 0")
    _ensure_column(conn, "triage_entries", "suggested_response", "TEXT")
    conn.commit()


def upsert_checkpoint(
    conn: sqlite3.Connection,
    account: str,
    last_message_ts: str,
    history_id: str | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO account_checkpoints(account, history_id, last_message_ts, updated_at)
        VALUES(?, ?, ?, ?)
        ON CONFLICT(account) DO UPDATE SET
          history_id=COALESCE(?, account_checkpoints.history_id),
          last_message_ts=excluded.last_message_ts,
          updated_at=excluded.updated_at
        """,
        (account, history_id, last_message_ts, now_iso(), history_id),
    )


def get_checkpoint(conn: sqlite3.Connection, account: str) -> dict[str, str | None]:
    row = conn.execute(
        "SELECT history_id, last_message_ts FROM account_checkpoints WHERE account = ?",
        (account,),
    ).fetchone()
    if not row:
        return {"history_id": None, "last_message_ts": None}
    return {
        "history_id": str(row["history_id"]) if row["history_id"] else None,
        "last_message_ts": str(row["last_message_ts"]) if row["last_message_ts"] else None,
    }


def get_last_checkpoint_ts(conn: sqlite3.Connection, account: str) -> str | None:
    return get_checkpoint(conn, account).get("last_message_ts")


def insert_run(
    conn: sqlite3.Connection,
    run_id: str,
    run_type: str,
    status: str,
    force_reconcile: bool,
) -> None:
    conn.execute(
        """
        INSERT INTO triage_runs(run_id, run_type, status, send_status, started_at, force_reconcile, error_message)
        VALUES(?, ?, ?, 'pending', ?, ?, NULL)
        """,
        (run_id, run_type, status, now_iso(), 1 if force_reconcile else 0),
    )
    conn.commit()


def update_run_status(
    conn: sqlite3.Connection,
    run_id: str,
    status: str,
    *,
    send_status: str | None = None,
    error_message: str | None = None,
    finished: bool = False,
) -> None:
    sets = ["status = ?", "error_message = ?"]
    values: list[Any] = [status, error_message]
    if send_status is not None:
        sets.append("send_status = ?")
        values.append(send_status)
    if finished:
        sets.append("finished_at = ?")
        values.append(now_iso())

    values.append(run_id)
    sql = f"UPDATE triage_runs SET {', '.join(sets)} WHERE run_id = ?"
    conn.execute(sql, tuple(values))
    conn.commit()


def insert_messages(conn: sqlite3.Connection, run_id: str, messages: list[dict[str, Any]]) -> None:
    now = now_iso()
    for msg in messages:
        conn.execute(
            """
            INSERT OR IGNORE INTO messages_raw(
              message_id, account, thread_id, received_at,
              sender_email, sender_name, subject, snippet,
              body_preview, list_unsubscribe, metadata_json, ingested_at, run_id
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                msg["message_id"],
                msg["account"],
                msg["thread_id"],
                msg["received_at"],
                msg["sender_email"],
                msg.get("sender_name") or msg["sender_email"],
                msg.get("subject") or "(no subject)",
                msg.get("snippet") or "",
                msg.get("body_preview") or "",
                msg.get("list_unsubscribe"),
                json.dumps(msg.get("metadata") or {}, ensure_ascii=True),
                now,
                run_id,
            ),
        )
    conn.commit()


def clear_entries_for_run(conn: sqlite3.Connection, run_id: str) -> None:
    conn.execute("DELETE FROM triage_entries WHERE run_id = ?", (run_id,))
    conn.execute("DELETE FROM draft_attempts WHERE run_id = ?", (run_id,))
    conn.execute("DELETE FROM coverage_reports WHERE run_id = ?", (run_id,))
    conn.execute("DELETE FROM run_artifacts WHERE run_id = ?", (run_id,))
    conn.commit()


def insert_entries(conn: sqlite3.Connection, run_id: str, entries: list[dict[str, Any]]) -> None:
    created_at = now_iso()
    for entry in entries:
        conn.execute(
            """
            INSERT INTO triage_entries(
              run_id, account, thread_id, bucket,
              sender_email, sender_name, subject_latest, summary_latest,
              response_needed, suggested_response, suggested_action,
              monitoring_owner, monitoring_deliverable, monitoring_deadline,
              draft_status, draft_authoring_mode, draft_context_status, draft_authoring_error,
              thread_url, draft_url, unsubscribe_url,
              accounted_reason, message_ids_json, created_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                entry["account"],
                entry["thread_id"],
                entry["bucket"],
                entry["sender_email"],
                entry.get("sender_name") or entry["sender_email"],
                entry["subject_latest"],
                entry["summary_latest"],
                1 if bool(entry.get("response_needed")) else 0,
                entry.get("suggested_response", ""),
                entry.get("suggested_action", ""),
                entry.get("monitoring_owner", ""),
                entry.get("monitoring_deliverable", ""),
                entry.get("monitoring_deadline", ""),
                entry.get("draft_status", "not_needed"),
                entry.get("draft_authoring_mode", "deterministic"),
                entry.get("draft_context_status", "unmatched"),
                entry.get("draft_authoring_error"),
                entry["thread_url"],
                entry.get("draft_url"),
                entry.get("unsubscribe_url"),
                entry.get("accounted_reason", "included"),
                json.dumps(entry.get("message_ids", []), ensure_ascii=True),
                created_at,
            ),
        )
    conn.commit()


def insert_draft_attempt(
    conn: sqlite3.Connection,
    run_id: str,
    account: str,
    thread_id: str,
    adapter: str,
    status: str,
    draft_url: str | None,
    error_message: str | None,
) -> None:
    conn.execute(
        """
        INSERT INTO draft_attempts(
          run_id, account, thread_id, adapter, status, draft_url, error_message, created_at
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (run_id, account, thread_id, adapter, status, draft_url, error_message, now_iso()),
    )
    conn.commit()


def insert_coverage_report(conn: sqlite3.Connection, run_id: str, report: dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT INTO coverage_reports(
          run_id, expected_count, accounted_count, missing_count, duplicate_count,
          pass, expected_message_ids_json, accounted_message_ids_json,
          missing_message_ids_json, duplicate_thread_keys_json, created_at
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id,
            int(report["expected_count"]),
            int(report["accounted_count"]),
            int(report["missing_count"]),
            int(report["duplicate_count"]),
            1 if bool(report["pass"]) else 0,
            json.dumps(report["expected_message_ids"], ensure_ascii=True),
            json.dumps(report["accounted_message_ids"], ensure_ascii=True),
            json.dumps(report["missing_message_ids"], ensure_ascii=True),
            json.dumps(report["duplicate_thread_keys"], ensure_ascii=True),
            now_iso(),
        ),
    )
    conn.commit()


def insert_artifact_paths(
    conn: sqlite3.Connection,
    run_id: str,
    markdown_path: str,
    html_path: str,
    json_path: str,
) -> None:
    conn.execute(
        """
        INSERT INTO run_artifacts(run_id, markdown_path, html_path, json_path, created_at)
        VALUES(?, ?, ?, ?, ?)
        """,
        (run_id, markdown_path, html_path, json_path, now_iso()),
    )
    conn.commit()


def enqueue_task(conn: sqlite3.Connection, task_id: str, task_type: str, payload: dict[str, Any]) -> None:
    timestamp = now_iso()
    conn.execute(
        """
        INSERT INTO queue_tasks(task_id, task_type, payload_json, status, attempts, available_at, last_error, created_at, updated_at)
        VALUES(?, ?, ?, 'queued', 0, ?, NULL, ?, ?)
        """,
        (task_id, task_type, json.dumps(payload, ensure_ascii=True), timestamp, timestamp, timestamp),
    )
    conn.commit()


def claim_next_task(conn: sqlite3.Connection) -> sqlite3.Row | None:
    row = conn.execute(
        """
        SELECT * FROM queue_tasks
        WHERE status = 'queued' AND available_at <= ?
        ORDER BY created_at ASC
        LIMIT 1
        """,
        (now_iso(),),
    ).fetchone()
    if not row:
        return None
    conn.execute(
        "UPDATE queue_tasks SET status = 'running', attempts = attempts + 1, updated_at = ? WHERE task_id = ?",
        (now_iso(), row["task_id"]),
    )
    conn.commit()
    return row


def complete_task(conn: sqlite3.Connection, task_id: str) -> None:
    conn.execute(
        "UPDATE queue_tasks SET status = 'done', updated_at = ?, last_error = NULL WHERE task_id = ?",
        (now_iso(), task_id),
    )
    conn.commit()


def fail_task(conn: sqlite3.Connection, task_id: str, error_message: str) -> None:
    conn.execute(
        "UPDATE queue_tasks SET status = 'failed', last_error = ?, updated_at = ? WHERE task_id = ?",
        (error_message[:1000], now_iso(), task_id),
    )
    conn.commit()


def fetch_run(conn: sqlite3.Connection, run_id: str) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM triage_runs WHERE run_id = ?", (run_id,)).fetchone()
    if not row:
        return None
    return dict(row)


def fetch_coverage(conn: sqlite3.Connection, run_id: str) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM coverage_reports WHERE run_id = ?", (run_id,)).fetchone()
    if not row:
        return None
    data = dict(row)
    for key in (
        "expected_message_ids_json",
        "accounted_message_ids_json",
        "missing_message_ids_json",
        "duplicate_thread_keys_json",
    ):
        data[key[:-5]] = json.loads(data[key])
        del data[key]
    data["pass"] = bool(data["pass"])
    return data


def fetch_artifacts(conn: sqlite3.Connection, run_id: str) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM run_artifacts WHERE run_id = ?", (run_id,)).fetchone()
    if not row:
        return None
    return dict(row)


def fetch_entries(conn: sqlite3.Connection, run_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM triage_entries WHERE run_id = ? ORDER BY account, thread_id",
        (run_id,),
    ).fetchall()
    items: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        item["message_ids"] = json.loads(item.pop("message_ids_json"))
        item["response_needed"] = bool(item.get("response_needed"))
        items.append(item)
    return items


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    existing = {str(row[1]) for row in rows}
    if column in existing:
        return
    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")
