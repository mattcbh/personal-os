from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
import json
import random
import re
import time
from pathlib import Path
from typing import Any
from urllib import error as urlerror
from urllib import parse as urlparse
from urllib import request as urlrequest

from triage_v2.types import ThreadMessage


GMAIL_API_BASE = "https://gmail.googleapis.com/gmail/v1/users/me"
FROM_EMAIL_RE = re.compile(r"<([^>]+)>")
UNSUB_URL_RE = re.compile(r"https?://[^>,\s]+")


class GmailApiError(RuntimeError):
    pass


class GmailApiClient:
    def __init__(self, token_path: Path) -> None:
        self.token_path = token_path
        if not self.token_path.exists():
            raise GmailApiError(f"Missing Gmail token file: {self.token_path}")

        self.token_data = self._load_token_data()
        self.account_email = str(self.token_data.get("account") or "").strip().lower()

    def _load_token_data(self) -> dict[str, Any]:
        try:
            raw = json.loads(self.token_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise GmailApiError(f"Unable to parse token file {self.token_path}: {exc}") from exc
        if not isinstance(raw, dict):
            raise GmailApiError(f"Token file is not a JSON object: {self.token_path}")
        return raw

    def _load_fallback_credential_sources(self) -> list[dict[str, Any]]:
        sources: list[dict[str, Any]] = []

        for name in ("credentials.json", "gcp-oauth.keys.json"):
            path = self.token_path.parent / name
            if not path.exists():
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if isinstance(data, dict):
                sources.append(data)
        return sources

    def _save_token_data(self) -> None:
        self.token_path.write_text(json.dumps(self.token_data, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

    @staticmethod
    def _parse_expiry(text: str | None) -> datetime | None:
        if not text:
            return None
        value = text.strip()
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(value)
        except Exception:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    def _token_expired(self) -> bool:
        token = str(self.token_data.get("token") or "").strip()
        if not token:
            return True
        expiry = self._parse_expiry(self.token_data.get("expiry"))
        if expiry is None:
            return False
        return datetime.now(timezone.utc) >= (expiry - timedelta(minutes=2))

    def _refresh_access_token(self) -> str:
        sources = [self.token_data] + self._load_fallback_credential_sources()
        last_error: str | None = None

        for source in sources:
            refresh_token = str(source.get("refresh_token") or "").strip()
            client_id = str(source.get("client_id") or self.token_data.get("client_id") or "").strip()
            client_secret = str(source.get("client_secret") or self.token_data.get("client_secret") or "").strip()
            token_uri = str(source.get("token_uri") or self.token_data.get("token_uri") or "https://oauth2.googleapis.com/token").strip()

            if not refresh_token or not client_id or not client_secret:
                continue

            payload = urlparse.urlencode(
                {
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "client_id": client_id,
                    "client_secret": client_secret,
                }
            ).encode("utf-8")

            req = urlrequest.Request(
                token_uri,
                data=payload,
                method="POST",
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

            try:
                with urlrequest.urlopen(req, timeout=20) as resp:
                    body = resp.read().decode("utf-8")
            except urlerror.HTTPError as exc:
                last_error = exc.read().decode("utf-8", errors="replace")
                continue
            except Exception as exc:
                last_error = str(exc)
                continue

            try:
                data = json.loads(body)
            except Exception as exc:
                last_error = f"OAuth refresh returned invalid JSON: {exc}"
                continue

            access_token = str(data.get("access_token") or "").strip()
            if not access_token:
                last_error = "OAuth refresh response missing access_token"
                continue

            # Persist successful source values into canonical token file.
            self.token_data["refresh_token"] = refresh_token
            self.token_data["client_id"] = client_id
            self.token_data["client_secret"] = client_secret
            self.token_data["token_uri"] = token_uri
            self.token_data["token"] = access_token
            expires_in = int(data.get("expires_in") or 3600)
            expiry = datetime.now(timezone.utc) + timedelta(seconds=max(60, expires_in))
            self.token_data["expiry"] = expiry.replace(microsecond=0).isoformat().replace("+00:00", "Z")
            self._save_token_data()
            return access_token

        raise GmailApiError(f"OAuth refresh failed for all credential sources: {last_error or 'unknown error'}")

    def _get_access_token(self) -> str:
        self.token_data = self._load_token_data()
        if self._token_expired():
            return self._refresh_access_token()

        token = str(self.token_data.get("token") or "").strip()
        if token:
            return token
        return self._refresh_access_token()

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
        retry: int = 4,
    ) -> dict[str, Any]:
        token = self._get_access_token()

        url = f"{GMAIL_API_BASE}{path}"
        if params:
            clean = {k: v for k, v in params.items() if v is not None and v != ""}
            if clean:
                url += "?" + urlparse.urlencode(clean, doseq=True)

        payload = None
        headers = {"Authorization": f"Bearer {token}"}
        if body is not None:
            payload = json.dumps(body, ensure_ascii=True).encode("utf-8")
            headers["Content-Type"] = "application/json"

        req = urlrequest.Request(url, data=payload, method=method.upper(), headers=headers)

        for attempt in range(1, retry + 1):
            try:
                with urlrequest.urlopen(req, timeout=30) as resp:
                    raw = resp.read().decode("utf-8")
                    if not raw:
                        return {}
                    data = json.loads(raw)
                    return data if isinstance(data, dict) else {}
            except urlerror.HTTPError as exc:
                status = exc.code
                response_text = exc.read().decode("utf-8", errors="replace")

                if status == 401 and attempt < retry:
                    token = self._refresh_access_token()
                    headers["Authorization"] = f"Bearer {token}"
                    req = urlrequest.Request(url, data=payload, method=method.upper(), headers=headers)
                    continue

                if status in {429, 500, 502, 503, 504} and attempt < retry:
                    sleep_s = (2 ** (attempt - 1)) + random.random()
                    time.sleep(min(8.0, sleep_s))
                    continue

                raise GmailApiError(f"Gmail API {method} {path} failed ({status}): {response_text[:500]}") from exc
            except Exception as exc:
                if attempt < retry:
                    time.sleep(min(8.0, (2 ** (attempt - 1)) + random.random()))
                    continue
                raise GmailApiError(f"Gmail API {method} {path} failed: {exc}") from exc

        raise GmailApiError(f"Gmail API {method} {path} failed after retries")

    def get_latest_history_id(self) -> str | None:
        data = self._request_json("GET", "/profile")
        hid = str(data.get("historyId") or "").strip()
        return hid or None

    def list_message_ids_from_query(
        self,
        *,
        since_ts: str | None,
        until_ts: str | None,
    ) -> list[str]:
        q_parts = ["-label:sent", "-label:draft"]
        if since_ts:
            try:
                dt = _parse_iso(since_ts)
                # 60s overlap to reduce checkpoint boundary misses.
                q_parts.append(f"after:{max(0, int(dt.timestamp()) - 60)}")
            except Exception:
                pass
        if until_ts:
            try:
                dt = _parse_iso(until_ts)
                q_parts.append(f"before:{int(dt.timestamp()) + 1}")
            except Exception:
                pass

        q = " ".join(q_parts)
        ids: list[str] = []
        page_token: str | None = None

        while True:
            data = self._request_json(
                "GET",
                "/messages",
                params={
                    "q": q,
                    "maxResults": 500,
                    "pageToken": page_token,
                },
            )
            messages = data.get("messages")
            if isinstance(messages, list):
                for item in messages:
                    if not isinstance(item, dict):
                        continue
                    mid = str(item.get("id") or "").strip()
                    if mid:
                        ids.append(mid)

            page_token = str(data.get("nextPageToken") or "").strip() or None
            if not page_token:
                break

        return ids

    def list_message_ids_from_history(self, start_history_id: str) -> list[str]:
        ids: list[str] = []
        page_token: str | None = None

        while True:
            data = self._request_json(
                "GET",
                "/history",
                params={
                    "startHistoryId": start_history_id,
                    "historyTypes": ["messageAdded"],
                    "labelId": "INBOX",
                    "maxResults": 500,
                    "pageToken": page_token,
                },
            )
            history = data.get("history")
            if isinstance(history, list):
                for item in history:
                    if not isinstance(item, dict):
                        continue
                    added = item.get("messagesAdded")
                    if not isinstance(added, list):
                        continue
                    for a in added:
                        if not isinstance(a, dict):
                            continue
                        msg = a.get("message")
                        if not isinstance(msg, dict):
                            continue
                        mid = str(msg.get("id") or "").strip()
                        if mid:
                            ids.append(mid)

            page_token = str(data.get("nextPageToken") or "").strip() or None
            if not page_token:
                break

        return ids

    def get_message_metadata(self, message_id: str) -> dict[str, Any] | None:
        data = self._request_json(
            "GET",
            f"/messages/{message_id}",
            params={
                "format": "metadata",
                "metadataHeaders": ["From", "Subject", "List-Unsubscribe"],
            },
        )

        if not data:
            return None

        label_ids = data.get("labelIds")
        if isinstance(label_ids, list):
            labels = {str(v) for v in label_ids}
            # Keep mail that arrived in inbox even if archived/deleted later.
            if "SENT" in labels or "DRAFT" in labels:
                return None

        thread_id = str(data.get("threadId") or "").strip()
        internal_ms = str(data.get("internalDate") or "").strip()
        if not thread_id or not internal_ms.isdigit():
            return None

        received_dt = datetime.fromtimestamp(int(internal_ms) / 1000.0, tz=timezone.utc)
        payload = data.get("payload") if isinstance(data.get("payload"), dict) else {}
        headers = payload.get("headers") if isinstance(payload.get("headers"), list) else []
        hdr_map = _headers_map(headers)

        from_header = hdr_map.get("from", "")
        sender_email, sender_name = _parse_from_header(from_header)
        if not sender_email:
            sender_email = "unknown@example.com"
            sender_name = "Unknown"

        return {
            "message_id": str(data.get("id") or message_id),
            "thread_id": thread_id,
            "received_at": received_dt.replace(microsecond=0).isoformat(),
            "sender_email": sender_email,
            "sender_name": sender_name,
            "subject": hdr_map.get("subject", "(no subject)"),
            "snippet": str(data.get("snippet") or "").strip(),
            "body_preview": str(data.get("snippet") or "").strip(),
            "list_unsubscribe": _extract_unsubscribe_url(hdr_map.get("list-unsubscribe")),
            "metadata": {
                "gmail_label_ids": sorted({str(v) for v in (label_ids or [])}),
            },
        }

    def get_thread_messages(self, thread_id: str, *, limit: int = 8) -> list[ThreadMessage]:
        data = self._request_json(
            "GET",
            f"/threads/{thread_id}",
            params={"format": "full"},
        )

        messages = data.get("messages")
        if not isinstance(messages, list):
            return []

        out: list[ThreadMessage] = []
        for item in messages:
            if not isinstance(item, dict):
                continue
            internal_ms = str(item.get("internalDate") or "").strip()
            if not internal_ms.isdigit():
                continue

            payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
            headers = payload.get("headers") if isinstance(payload.get("headers"), list) else []
            hdr_map = _headers_map(headers)
            from_header = hdr_map.get("from", "")
            sender_email, sender_name = _parse_from_header(from_header)
            if not sender_email:
                sender_email = "unknown@example.com"
                sender_name = "Unknown"

            body_text = _extract_message_text(payload)
            if not body_text:
                body_text = str(item.get("snippet") or "").strip()

            received_dt = datetime.fromtimestamp(int(internal_ms) / 1000.0, tz=timezone.utc)
            out.append(
                ThreadMessage(
                    account="",
                    thread_id=str(item.get("threadId") or thread_id).strip(),
                    message_id=str(item.get("id") or "").strip(),
                    received_at=received_dt.replace(microsecond=0).isoformat(),
                    sender_email=sender_email,
                    sender_name=sender_name,
                    subject=hdr_map.get("subject", "(no subject)"),
                    body_text=body_text,
                )
            )

        out.sort(key=lambda message: message.received_at)
        if limit > 0:
            return out[-limit:]
        return out

    def send_message(self, *, raw_mime_b64url: str) -> dict[str, Any]:
        return self._request_json(
            "POST",
            "/messages/send",
            body={"raw": raw_mime_b64url},
        )

    def get_thread_reply_context(self, thread_id: str) -> dict[str, str]:
        data = self._request_json(
            "GET",
            f"/threads/{thread_id}",
            params={
                "format": "metadata",
                "metadataHeaders": ["From", "Reply-To", "Subject", "Message-ID", "References"],
            },
        )

        messages = data.get("messages")
        if not isinstance(messages, list) or not messages:
            raise GmailApiError(f"Thread {thread_id} has no messages")

        best: dict[str, str] = {}
        for item in reversed(messages):
            if not isinstance(item, dict):
                continue
            payload = item.get("payload")
            if not isinstance(payload, dict):
                continue
            headers = payload.get("headers")
            if not isinstance(headers, list):
                continue
            hdr_map = _headers_map(headers)
            if not hdr_map:
                continue

            if not best:
                best = hdr_map

            sender_email, _ = _parse_from_header(hdr_map.get("from", ""))
            if sender_email and sender_email != self.account_email:
                best = hdr_map
                break

        if not best:
            raise GmailApiError(f"Unable to determine reply context for thread {thread_id}")

        from_header = best.get("from", "")
        reply_to_header = best.get("reply-to", "") or from_header
        reply_to_email, _ = _parse_from_header(reply_to_header)
        if not reply_to_email:
            reply_to_email, _ = _parse_from_header(from_header)

        return {
            "to_email": reply_to_email,
            "subject": _reply_subject(best.get("subject", "(no subject)")),
            "in_reply_to": best.get("message-id", ""),
            "references": best.get("references", ""),
        }

    def create_reply_draft(
        self,
        *,
        thread_id: str,
        body_text: str,
        account_email: str | None = None,
    ) -> dict[str, str]:
        context = self.get_thread_reply_context(thread_id)
        msg = EmailMessage()

        from_email = (account_email or self.account_email or "").strip()
        if from_email:
            msg["From"] = from_email

        to_email = context.get("to_email", "").strip()
        if to_email:
            msg["To"] = to_email

        subject = context.get("subject", "").strip()
        if subject:
            msg["Subject"] = subject

        in_reply_to = context.get("in_reply_to", "").strip()
        if in_reply_to:
            msg["In-Reply-To"] = in_reply_to

        references = context.get("references", "").strip()
        if references:
            msg["References"] = references

        clean_body = body_text.strip() if body_text else "Thanks for the note."
        msg.set_content(clean_body + "\n")
        raw = encode_mime_base64url(msg.as_bytes())

        data = self._request_json(
            "POST",
            "/drafts",
            body={
                "message": {
                    "threadId": thread_id,
                    "raw": raw,
                }
            },
        )
        draft_id = str(data.get("id") or "").strip()
        if not draft_id:
            raise GmailApiError(f"Gmail draft API response missing draft id for thread {thread_id}")

        hint = (account_email or self.account_email or "0").strip()
        account_segment = urlparse.quote(hint if hint else "0", safe="@._+-")
        compose_id = urlparse.quote(draft_id, safe="")
        return {
            "id": draft_id,
            "url": f"https://mail.google.com/mail/u/{account_segment}/#drafts?compose={compose_id}",
        }


def _parse_iso(text: str) -> datetime:
    value = text.strip()
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _headers_map(headers: list[dict[str, Any]]) -> dict[str, str]:
    out: dict[str, str] = {}
    for h in headers:
        if not isinstance(h, dict):
            continue
        name = str(h.get("name") or "").strip().lower()
        value = str(h.get("value") or "").strip()
        if name:
            out[name] = value
    return out


def _parse_from_header(raw: str) -> tuple[str, str]:
    text = raw.strip()
    if not text:
        return "", ""

    match = FROM_EMAIL_RE.search(text)
    email = ""
    if match:
        email = match.group(1).strip().lower()
        name = text[: match.start()].strip().strip('"').strip()
        return email, (name or email)

    tokens = [tok.strip('"<>(),; ') for tok in re.split(r"\s+", text)]
    for tok in tokens:
        if "@" in tok and "." in tok:
            email = tok.lower()
            break
    return email, email


def _extract_message_text(payload: dict[str, Any]) -> str:
    mime_type = str(payload.get("mimeType") or "").lower()
    body = payload.get("body") if isinstance(payload.get("body"), dict) else {}
    data = _decode_body_data(str(body.get("data") or ""))
    if mime_type.startswith("text/plain") and data:
        return data
    if mime_type.startswith("text/html") and data:
        return _html_to_text(data)

    parts = payload.get("parts")
    if isinstance(parts, list):
        plain_parts: list[str] = []
        html_parts: list[str] = []
        for part in parts:
            if not isinstance(part, dict):
                continue
            extracted = _extract_message_text(part)
            if not extracted:
                continue
            part_mime = str(part.get("mimeType") or "").lower()
            if part_mime.startswith("text/plain"):
                plain_parts.append(extracted)
            else:
                html_parts.append(extracted)
        if plain_parts:
            return "\n\n".join(piece for piece in plain_parts if piece).strip()
        if html_parts:
            return "\n\n".join(piece for piece in html_parts if piece).strip()

    if data:
        return data
    return ""


def _decode_body_data(raw: str) -> str:
    if not raw:
        return ""
    value = raw.strip().replace("-", "+").replace("_", "/")
    value += "=" * (-len(value) % 4)
    try:
        decoded = base64.b64decode(value)
    except Exception:
        return ""
    try:
        return decoded.decode("utf-8")
    except UnicodeDecodeError:
        return decoded.decode("latin-1", errors="replace")


def _html_to_text(raw_html: str) -> str:
    text = re.sub(r"(?is)<(script|style).*?>.*?</\\1>", " ", raw_html)
    text = re.sub(r"(?i)<br\\s*/?>", "\n", text)
    text = re.sub(r"(?i)</p>", "\n", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = text.replace("&nbsp;", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _extract_unsubscribe_url(raw: str | None) -> str | None:
    if not raw:
        return None
    text = raw.strip()
    match = UNSUB_URL_RE.search(text)
    if not match:
        return None
    return match.group(0)


def _reply_subject(raw: str) -> str:
    subject = raw.strip() or "(no subject)"
    if subject.lower().startswith("re:"):
        return subject
    return f"Re: {subject}"


def encode_mime_base64url(message_bytes: bytes) -> str:
    return base64.urlsafe_b64encode(message_bytes).decode("utf-8").rstrip("=")
