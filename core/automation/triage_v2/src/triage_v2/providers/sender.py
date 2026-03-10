from __future__ import annotations

import json
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path

from triage_v2.config import AppConfig
from triage_v2.providers.gmail_api import GmailApiClient, encode_mime_base64url


class DigestSender(ABC):
    @abstractmethod
    def send(self, *, run_id: str, subject: str, markdown_body: str, html_body: str) -> dict[str, str]:
        raise NotImplementedError


class LocalOutboxSender(DigestSender):
    def __init__(self, outbox_dir: Path) -> None:
        self.outbox_dir = outbox_dir
        self.outbox_dir.mkdir(parents=True, exist_ok=True)

    def send(self, *, run_id: str, subject: str, markdown_body: str, html_body: str) -> dict[str, str]:
        ts = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        out_path = self.outbox_dir / f"outbox-{run_id}.json"
        payload = {
            "run_id": run_id,
            "sent_at": ts,
            "subject": subject,
            "markdown": markdown_body,
            "html": html_body,
            "transport": "local_outbox",
            "message_id": f"local-{run_id}",
        }
        out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
        return {
            "status": "sent",
            "message_id": payload["message_id"],
            "transport": "local_outbox",
            "artifact": str(out_path),
        }


class GmailApiSender(DigestSender):
    def __init__(self, *, token_path: Path, sender_email: str, digest_to: str) -> None:
        self.client = GmailApiClient(token_path)
        self.sender_email = sender_email
        self.digest_to = digest_to

    def send(self, *, run_id: str, subject: str, markdown_body: str, html_body: str) -> dict[str, str]:
        msg = EmailMessage()
        msg["To"] = self.digest_to
        msg["From"] = self.sender_email
        msg["Subject"] = subject
        msg.set_content(markdown_body)
        msg.add_alternative(html_body, subtype="html")

        raw = encode_mime_base64url(msg.as_bytes())
        resp = self.client.send_message(raw_mime_b64url=raw)
        msg_id = str(resp.get("id") or f"gmail-{run_id}")

        return {
            "status": "sent",
            "message_id": msg_id,
            "transport": "gmail_api",
        }


def sender_from_mode(cfg: AppConfig) -> DigestSender:
    if cfg.sender_mode == "gmail":
        sender_account = "personal" if cfg.digest_sender_account == "personal" else "work"
        if sender_account == "personal":
            token_path = cfg.gmail_personal_home / "token.json"
            sender_email = cfg.default_personal_account
        else:
            token_path = cfg.gmail_work_home / "token.json"
            sender_email = cfg.default_work_account

        return GmailApiSender(
            token_path=token_path,
            sender_email=sender_email,
            digest_to=cfg.digest_to,
        )

    return LocalOutboxSender(cfg.outbox_dir)
