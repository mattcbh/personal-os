from __future__ import annotations

from dataclasses import dataclass
import json
import os
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from triage_v2.config import AppConfig
from triage_v2.types import MessageRecord, ThreadMessage
from triage_v2.providers.gmail_api import GmailApiClient, GmailApiError


def parse_iso(ts: str) -> datetime:
    text = ts.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@dataclass
class MailFetchResult:
    messages: list[MessageRecord]
    latest_history_id: str | None = None


class MailProvider(ABC):
    @abstractmethod
    def list_messages(
        self,
        account: str,
        *,
        since_ts: str | None,
        until_ts: str | None,
        since_history_id: str | None,
        force_reconcile: bool,
    ) -> MailFetchResult:
        raise NotImplementedError

    @abstractmethod
    def get_thread_messages(self, account: str, thread_id: str, *, limit: int = 8) -> list[ThreadMessage]:
        raise NotImplementedError


class FileMailProvider(MailProvider):
    def __init__(self, fixture_dir: Path) -> None:
        self.fixture_dir = fixture_dir

    def list_messages(
        self,
        account: str,
        *,
        since_ts: str | None,
        until_ts: str | None,
        since_history_id: str | None,
        force_reconcile: bool,
    ) -> MailFetchResult:
        path = self.fixture_dir / f"{account}.json"
        if not path.exists():
            return MailFetchResult(messages=[], latest_history_id=None)

        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            return MailFetchResult(messages=[], latest_history_id=None)

        since = parse_iso(since_ts) if since_ts else None
        until = parse_iso(until_ts) if until_ts else None

        out: list[MessageRecord] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            try:
                received_at = str(item.get("received_at") or "").strip()
                if not received_at:
                    continue
                received_dt = parse_iso(received_at)
                if since and received_dt <= since and not force_reconcile:
                    continue
                if until and received_dt > until:
                    continue

                sender_email = str(item.get("sender_email") or "").strip().lower()
                if not sender_email:
                    continue

                out.append(
                    MessageRecord(
                        message_id=str(item.get("message_id") or "").strip(),
                        account=account,
                        thread_id=str(item.get("thread_id") or "").strip(),
                        received_at=received_dt.replace(microsecond=0).isoformat(),
                        sender_email=sender_email,
                        sender_name=str(item.get("sender_name") or sender_email).strip(),
                        subject=str(item.get("subject") or "(no subject)").strip(),
                        snippet=str(item.get("snippet") or "").strip(),
                        body_preview=str(item.get("body_preview") or "").strip(),
                        list_unsubscribe=(
                            str(item.get("list_unsubscribe")).strip()
                            if item.get("list_unsubscribe")
                            else None
                        ),
                        metadata=dict(item.get("metadata") or {}),
                    )
                )
            except Exception:
                continue

        out.sort(key=lambda m: m.received_at)
        cleaned = [m for m in out if m.message_id and m.thread_id]
        return MailFetchResult(messages=cleaned, latest_history_id=None)

    def get_thread_messages(self, account: str, thread_id: str, *, limit: int = 8) -> list[ThreadMessage]:
        path = self.fixture_dir / f"{account}.json"
        if not path.exists():
            return []

        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            return []

        out: list[ThreadMessage] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            if str(item.get("thread_id") or "").strip() != thread_id:
                continue
            received_at = str(item.get("received_at") or "").strip()
            if not received_at:
                continue
            body_text = str(item.get("body_text") or item.get("body_preview") or item.get("snippet") or "").strip()
            out.append(
                ThreadMessage(
                    account=account,
                    thread_id=thread_id,
                    message_id=str(item.get("message_id") or "").strip(),
                    received_at=parse_iso(received_at).replace(microsecond=0).isoformat(),
                    sender_email=str(item.get("sender_email") or "").strip().lower(),
                    sender_name=str(item.get("sender_name") or item.get("sender_email") or "").strip(),
                    subject=str(item.get("subject") or "(no subject)").strip(),
                    body_text=body_text,
                )
            )
        out.sort(key=lambda m: m.received_at)
        return out[-limit:] if limit > 0 else out


class GmailApiProvider(MailProvider):
    def __init__(self, work_home: Path, personal_home: Path) -> None:
        self.work_token = work_home / "token.json"
        self.personal_token = personal_home / "token.json"
        self._clients: dict[str, GmailApiClient] = {}

    def _client(self, account: str) -> GmailApiClient:
        key = "work" if account == "work" else "personal"
        if key in self._clients:
            return self._clients[key]

        token_path = self.work_token if key == "work" else self.personal_token
        client = GmailApiClient(token_path)
        self._clients[key] = client
        return client

    def list_messages(
        self,
        account: str,
        *,
        since_ts: str | None,
        until_ts: str | None,
        since_history_id: str | None,
        force_reconcile: bool,
    ) -> MailFetchResult:
        client = self._client(account)
        since = parse_iso(since_ts) if since_ts else None
        until = parse_iso(until_ts) if until_ts else None

        message_ids: set[str] = set()
        history_ok = False

        if since_history_id and not force_reconcile:
            try:
                history_ids = client.list_message_ids_from_history(since_history_id)
                message_ids.update(history_ids)
                history_ok = True
            except GmailApiError:
                history_ok = False

        always_reconcile = os.environ.get("TRIAGE_V2_ALWAYS_RECONCILE", "1") != "0"
        if force_reconcile or not history_ok or always_reconcile:
            query_ids = client.list_message_ids_from_query(since_ts=since_ts, until_ts=until_ts)
            message_ids.update(query_ids)

        latest_history_id = client.get_latest_history_id()

        out: list[MessageRecord] = []
        metadata_none_ids: list[str] = []
        metadata_error_samples: list[str] = []
        for message_id in sorted(message_ids):
            try:
                meta = client.get_message_metadata(message_id)
            except GmailApiError as exc:
                # Messages can disappear between list/history and get (trash/delete/race).
                # Skip these IDs so one stale reference does not fail the whole run.
                if len(metadata_error_samples) < 5:
                    metadata_error_samples.append(f"{message_id}: {exc}")
                continue
            if not meta:
                if len(metadata_none_ids) < 10:
                    metadata_none_ids.append(message_id)
                continue

            received_at = str(meta.get("received_at") or "").strip()
            if not received_at:
                continue

            received_dt = parse_iso(received_at)
            if since and received_dt <= since and not force_reconcile:
                continue
            if until and received_dt > until:
                continue

            out.append(
                MessageRecord(
                    message_id=str(meta.get("message_id") or message_id).strip(),
                    account=account,
                    thread_id=str(meta.get("thread_id") or "").strip(),
                    received_at=received_dt.replace(microsecond=0).isoformat(),
                    sender_email=str(meta.get("sender_email") or "unknown@example.com").strip().lower(),
                    sender_name=str(meta.get("sender_name") or "Unknown").strip(),
                    subject=str(meta.get("subject") or "(no subject)").strip(),
                    snippet=str(meta.get("snippet") or "").strip(),
                    body_preview=str(meta.get("body_preview") or "").strip(),
                    list_unsubscribe=(
                        str(meta.get("list_unsubscribe")).strip() if meta.get("list_unsubscribe") else None
                    ),
                    metadata=dict(meta.get("metadata") or {}),
                )
            )

        out.sort(key=lambda m: m.received_at)
        cleaned = [m for m in out if m.message_id and m.thread_id]
        if message_ids and not cleaned:
            samples = []
            if metadata_none_ids:
                samples.append("metadata_none=" + ",".join(metadata_none_ids[:5]))
            if metadata_error_samples:
                samples.append("metadata_errors=" + " | ".join(metadata_error_samples[:3]))
            detail = "; ".join(samples) if samples else "no metadata samples captured"
            raise GmailApiError(
                f"Gmail returned {len(message_ids)} message IDs for {account}, but zero usable messages remained. {detail}"
            )
        return MailFetchResult(messages=cleaned, latest_history_id=latest_history_id)

    def get_thread_messages(self, account: str, thread_id: str, *, limit: int = 8) -> list[ThreadMessage]:
        client = self._client(account)
        rows = client.get_thread_messages(thread_id, limit=limit)
        return [
            ThreadMessage(
                account=account,
                thread_id=row.thread_id,
                message_id=row.message_id,
                received_at=row.received_at,
                sender_email=row.sender_email,
                sender_name=row.sender_name,
                subject=row.subject,
                body_text=row.body_text,
            )
            for row in rows
        ]


def provider_from_mode(cfg: AppConfig) -> MailProvider:
    if cfg.provider_mode == "gmail":
        return GmailApiProvider(cfg.gmail_work_home, cfg.gmail_personal_home)
    return FileMailProvider(cfg.fixture_dir)


def as_dict(message: MessageRecord) -> dict[str, Any]:
    return {
        "message_id": message.message_id,
        "account": message.account,
        "thread_id": message.thread_id,
        "received_at": message.received_at,
        "sender_email": message.sender_email,
        "sender_name": message.sender_name,
        "subject": message.subject,
        "snippet": message.snippet,
        "body_preview": message.body_preview,
        "list_unsubscribe": message.list_unsubscribe,
        "metadata": message.metadata,
    }
