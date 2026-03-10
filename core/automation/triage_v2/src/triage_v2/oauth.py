from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import socket
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
from urllib import parse as urlparse
from urllib import request as urlrequest
import webbrowser

from triage_v2.providers.gmail_api import GmailApiClient


GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
DEFAULT_SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.settings.basic",
    "https://www.googleapis.com/auth/gmail.send",
]


class OAuthError(RuntimeError):
    pass


def _load_oauth_client(path: Path) -> dict[str, str]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, dict) and "installed" in raw and isinstance(raw["installed"], dict):
        section = raw["installed"]
        return {
            "client_id": str(section.get("client_id") or "").strip(),
            "client_secret": str(section.get("client_secret") or "").strip(),
            "redirect_uri": str((section.get("redirect_uris") or [""])[0] or "").strip(),
        }

    if isinstance(raw, dict) and "web" in raw and isinstance(raw["web"], dict):
        section = raw["web"]
        return {
            "client_id": str(section.get("client_id") or "").strip(),
            "client_secret": str(section.get("client_secret") or "").strip(),
            "redirect_uri": str((section.get("redirect_uris") or [""])[0] or "").strip(),
        }

    if isinstance(raw, dict):
        return {
            "client_id": str(raw.get("client_id") or "").strip(),
            "client_secret": str(raw.get("client_secret") or "").strip(),
            "redirect_uri": str(raw.get("redirect_uri") or "").strip(),
        }
    raise OAuthError("Invalid OAuth client JSON")


def _resolve_redirect_uri(redirect_uri_from_file: str, fallback_port: int) -> tuple[str, str, int, str]:
    redirect_uri = redirect_uri_from_file.strip() or f"http://127.0.0.1:{fallback_port}/oauth2callback"
    parsed = urlparse.urlparse(redirect_uri)

    if parsed.scheme not in {"http", "https"}:
        raise OAuthError(f"Unsupported redirect URI scheme: {redirect_uri}")

    host = (parsed.hostname or "").strip().lower()
    if host not in {"127.0.0.1", "localhost"}:
        raise OAuthError(
            "OAuth client redirect URI must use localhost or 127.0.0.1 for local auth. "
            f"Current redirect URI: {redirect_uri}"
        )

    # Desktop OAuth client files frequently use "http://localhost" without port/path.
    # Use fallback local callback endpoint in that case.
    if parsed.port is None:
        port = int(fallback_port)
        path = parsed.path or "/oauth2callback"
        effective_uri = f"http://{host}:{port}{path}"
        return effective_uri, host, port, path

    port = int(parsed.port)
    path = parsed.path or "/oauth2callback"
    return redirect_uri, host, port, path


def _check_port_available(host: str, port: int) -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind((host, port))
    except OSError as exc:
        raise OAuthError(f"Local callback port {host}:{port} is not available: {exc}") from exc
    finally:
        sock.close()


class _CallbackState:
    def __init__(self) -> None:
        self.code: str | None = None
        self.error: str | None = None
        self.event = threading.Event()


class _OAuthCallbackHandler(BaseHTTPRequestHandler):
    state: _CallbackState

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse.urlparse(self.path)
        expected_path = getattr(self.server, "expected_callback_path", "/oauth2callback")
        if parsed.path != expected_path:
            self.send_response(404)
            self.end_headers()
            return

        params = urlparse.parse_qs(parsed.query)
        code = (params.get("code") or [None])[0]
        error = (params.get("error") or [None])[0]

        self.state.code = code
        self.state.error = error
        self.state.event.set()

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        if code:
            self.wfile.write(b"<html><body><h2>Authentication complete.</h2>You can close this tab.</body></html>")
        else:
            self.wfile.write(b"<html><body><h2>Authentication failed.</h2>Check terminal output.</body></html>")

    def log_message(self, fmt: str, *args: Any) -> None:
        return


def _exchange_code_for_tokens(
    *,
    code: str,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
) -> dict[str, Any]:
    payload = urlparse.urlencode(
        {
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }
    ).encode("utf-8")

    req = urlrequest.Request(
        GOOGLE_TOKEN_URL,
        data=payload,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urlrequest.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode("utf-8")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise OAuthError("Token exchange did not return JSON object")
    if not data.get("access_token"):
        raise OAuthError(f"Token exchange missing access_token: {data}")
    return data


def perform_installed_app_oauth(
    *,
    oauth_client_path: Path,
    token_output_path: Path,
    account_label: str,
    port: int = 8765,
    scopes: list[str] | None = None,
    open_browser: bool = True,
) -> dict[str, Any]:
    creds = _load_oauth_client(oauth_client_path)
    client_id = creds["client_id"]
    client_secret = creds["client_secret"]
    if not client_id or not client_secret:
        raise OAuthError("OAuth client JSON missing client_id/client_secret")

    scope_list = scopes or DEFAULT_SCOPES
    redirect_uri, callback_host, callback_port, callback_path = _resolve_redirect_uri(
        creds.get("redirect_uri", ""),
        port,
    )

    _check_port_available(callback_host, callback_port)

    state = _CallbackState()
    handler_cls = type("OAuthCallbackHandler", (_OAuthCallbackHandler,), {"state": state})
    server = HTTPServer((callback_host, callback_port), handler_cls)
    server.expected_callback_path = callback_path  # type: ignore[attr-defined]

    server_thread = threading.Thread(target=server.handle_request, daemon=True)
    server_thread.start()

    auth_params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(scope_list),
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
    }
    auth_url = f"{GOOGLE_AUTH_URL}?{urlparse.urlencode(auth_params)}"

    if open_browser:
        webbrowser.open(auth_url)

    print(f"Open this URL to authorize {account_label}:\n{auth_url}\n")
    if not state.event.wait(timeout=300):
        server.server_close()
        raise OAuthError("Timed out waiting for OAuth callback")

    server.server_close()

    if state.error:
        raise OAuthError(f"OAuth callback returned error: {state.error}")
    if not state.code:
        raise OAuthError("OAuth callback did not return authorization code")

    token_data = _exchange_code_for_tokens(
        code=state.code,
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
    )

    access_token = str(token_data.get("access_token") or "").strip()
    refresh_token = str(token_data.get("refresh_token") or "").strip()
    expires_in = int(token_data.get("expires_in") or 3600)
    expiry = datetime.now(timezone.utc) + timedelta(seconds=max(60, expires_in))

    token_output_path.parent.mkdir(parents=True, exist_ok=True)
    stored = {
        "account": "",
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "token": access_token,
        "expiry": expiry.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "token_uri": GOOGLE_TOKEN_URL,
        "scopes": scope_list,
        "universe_domain": "googleapis.com",
    }
    token_output_path.write_text(json.dumps(stored, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

    try:
        client = GmailApiClient(token_output_path)
        profile = client._request_json("GET", "/profile")
        email = str(profile.get("emailAddress") or "").strip().lower()
        if email:
            stored["account"] = email
            token_output_path.write_text(json.dumps(stored, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    except Exception:
        pass

    return {
        "token_output_path": str(token_output_path),
        "account_label": account_label,
        "scopes": scope_list,
        "redirect_uri": redirect_uri,
    }
