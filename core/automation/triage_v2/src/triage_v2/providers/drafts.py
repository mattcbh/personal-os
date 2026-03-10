from __future__ import annotations

import shlex
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from triage_v2.providers.gmail_api import GmailApiClient


@dataclass
class DraftResult:
    status: str
    adapter: str
    draft_url: str | None
    error_message: str | None = None


class DraftAdapter(ABC):
    @abstractmethod
    def create_reply_draft(
        self,
        *,
        account: str,
        account_email: str,
        thread_id: str,
        thread_url: str,
        body_text: str,
    ) -> DraftResult:
        raise NotImplementedError


class SuperhumanDraftAdapter(DraftAdapter):
    def __init__(self, script_path: Path, enabled: bool = False) -> None:
        self.script_path = script_path
        self.enabled = enabled

    def create_reply_draft(
        self,
        *,
        account: str,
        account_email: str,
        thread_id: str,
        thread_url: str,
        body_text: str,
    ) -> DraftResult:
        if not self.enabled:
            return DraftResult(
                status="failed",
                adapter="superhuman",
                draft_url=None,
                error_message="Superhuman adapter disabled",
            )

        if not self.script_path.exists():
            return DraftResult(
                status="failed",
                adapter="superhuman",
                draft_url=None,
                error_message=f"Missing script at {self.script_path}",
            )

        cmd = [
            str(self.script_path),
            "--queue",
            thread_id,
            body_text,
            account_email,
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120, check=False)
        except Exception as exc:
            return DraftResult(
                status="failed",
                adapter="superhuman",
                draft_url=None,
                error_message=str(exc),
            )

        output = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
        if proc.returncode != 0:
            return DraftResult(
                status="failed",
                adapter="superhuman",
                draft_url=None,
                error_message=output.strip()[:1000],
            )

        if "QUEUED:" in output:
            return DraftResult(
                status="ready",
                adapter="superhuman",
                draft_url=thread_url,
                error_message=None,
            )

        return DraftResult(
            status="failed",
            adapter="superhuman",
            draft_url=None,
            error_message="Queue output missing QUEUED marker",
        )


class GmailDraftAdapter(DraftAdapter):
    def __init__(self, *, work_home: Path, personal_home: Path) -> None:
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

    def create_reply_draft(
        self,
        *,
        account: str,
        account_email: str,
        thread_id: str,
        thread_url: str,
        body_text: str,
    ) -> DraftResult:
        del thread_url
        try:
            client = self._client(account)
            created = client.create_reply_draft(
                thread_id=thread_id,
                body_text=body_text,
                account_email=account_email,
            )
            return DraftResult(
                status="fallback_gmail",
                adapter="gmail",
                draft_url=str(created.get("url") or "").strip() or None,
                error_message=None,
            )
        except Exception as exc:
            return DraftResult(
                status="failed",
                adapter="gmail",
                draft_url=None,
                error_message=str(exc),
            )


class DraftRouter:
    def __init__(
        self,
        *,
        superhuman_adapter: SuperhumanDraftAdapter,
        gmail_adapter: GmailDraftAdapter,
        mode: str,
    ) -> None:
        self.superhuman = superhuman_adapter
        self.gmail = gmail_adapter
        self.mode = mode

    def create(
        self,
        *,
        account: str,
        account_email: str,
        thread_id: str,
        thread_url: str,
        body_text: str,
    ) -> list[DraftResult]:
        results: list[DraftResult] = []

        if self.mode == "gmail_only":
            results.append(
                self.gmail.create_reply_draft(
                    account=account,
                    account_email=account_email,
                    thread_id=thread_id,
                    thread_url=thread_url,
                    body_text=body_text,
                )
            )
            return results

        primary = self.superhuman.create_reply_draft(
            account=account,
            account_email=account_email,
            thread_id=thread_id,
            thread_url=thread_url,
            body_text=body_text,
        )
        results.append(primary)

        if primary.status in {"ready"}:
            return results

        fallback = self.gmail.create_reply_draft(
            account=account,
            account_email=account_email,
            thread_id=thread_id,
            thread_url=thread_url,
            body_text=body_text,
        )
        results.append(fallback)
        return results


def superhuman_enabled_from_env() -> bool:
    raw = (Path.home().joinpath(".triage-v2-superhuman-enabled")).exists()
    return raw


def command_preview(script_path: Path, thread_id: str, account_email: str) -> str:
    return shlex.join([str(script_path), "--queue", thread_id, "<body>", account_email])
