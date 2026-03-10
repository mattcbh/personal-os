"""Credential and command wrapper for the gws CLI backend."""

from __future__ import annotations

import json
import os
import shlex
import subprocess
from pathlib import Path
from typing import Any


class GoogleAuthManager:
    """Manage per-account gws credential wiring for MCP tool calls."""

    def __init__(
        self,
        credentials_path: str | None = None,
        token_path: str | None = None,
    ) -> None:
        gmail_mcp_home = Path(os.getenv("GMAIL_MCP_HOME", str(Path.home() / ".gmail-mcp")))
        self.gmail_mcp_home = gmail_mcp_home
        self.credentials_path = Path(credentials_path or gmail_mcp_home / "gcp-oauth.keys.json")
        self.token_path = Path(token_path or gmail_mcp_home / "token.json")

        # gws expects an "authorized_user" credentials file. We synthesize it
        # from the existing token.json so current account setup remains usable.
        self.gws_credentials_path = gmail_mcp_home / "gws-authorized-user.json"
        self.gws_config_home = gmail_mcp_home / "gws-config"
        self._authenticated_email: str | None = None

    def _load_token_json(self) -> dict[str, Any]:
        if not self.token_path.exists():
            raise FileNotFoundError(
                f"Missing token file at {self.token_path}. Run OAuth setup first."
            )
        data = json.loads(self.token_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"Invalid token JSON at {self.token_path}")
        return data

    def _ensure_gws_credentials_file(self) -> Path:
        token = self._load_token_json()

        client_id = str(token.get("client_id") or "").strip()
        client_secret = str(token.get("client_secret") or "").strip()
        refresh_token = str(token.get("refresh_token") or "").strip()
        if not client_id or not client_secret or not refresh_token:
            raise ValueError(
                f"token.json missing required client_id/client_secret/refresh_token at {self.token_path}"
            )

        payload = {
            "type": "authorized_user",
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
        }

        self.gws_credentials_path.parent.mkdir(parents=True, exist_ok=True)
        current: dict[str, Any] | None = None
        if self.gws_credentials_path.exists():
            try:
                loaded = json.loads(self.gws_credentials_path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    current = loaded
            except Exception:
                current = None

        if current != payload:
            self.gws_credentials_path.write_text(
                json.dumps(payload, indent=2, ensure_ascii=True) + "\n",
                encoding="utf-8",
            )

        return self.gws_credentials_path

    def _gws_env(self) -> dict[str, str]:
        credentials_file = self._ensure_gws_credentials_file()
        self.gws_config_home.mkdir(parents=True, exist_ok=True)

        env = os.environ.copy()
        env["GOOGLE_WORKSPACE_CLI_CREDENTIALS_FILE"] = str(credentials_file)
        # Isolate token cache per account/server instance.
        env["XDG_CONFIG_HOME"] = str(self.gws_config_home)
        return env

    def run_gws(
        self,
        *args: str,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Run a gws command and return parsed JSON output."""
        cmd = ["gws", *args]
        if params is not None:
            cmd.extend(["--params", json.dumps(params, ensure_ascii=True)])
        if body is not None:
            cmd.extend(["--json", json.dumps(body, ensure_ascii=True)])

        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            env=self._gws_env(),
            check=False,
        )

        stdout = (proc.stdout or "").strip()
        stderr = (proc.stderr or "").strip()
        if proc.returncode != 0:
            detail = stderr or stdout or "unknown gws error"
            raise RuntimeError(
                f"gws command failed ({proc.returncode}): {shlex.join(cmd)}\n{detail}"
            )

        if not stdout:
            return {}

        data = json.loads(stdout)
        if isinstance(data, dict) and "error" in data:
            raise RuntimeError(f"gws API error for {shlex.join(cmd)}: {data['error']}")
        if not isinstance(data, dict):
            raise RuntimeError(
                f"Unexpected non-object JSON from gws for {shlex.join(cmd)}: {type(data).__name__}"
            )
        return data

    def get_authenticated_email(self) -> str:
        """Return authenticated mailbox email (cached)."""
        if self._authenticated_email is None:
            profile = self.run_gws(
                "gmail",
                "users",
                "getProfile",
                params={"userId": "me"},
            )
            email = str(profile.get("emailAddress") or "").strip()
            if not email:
                raise RuntimeError("Unable to determine authenticated Gmail address")
            self._authenticated_email = email
        return self._authenticated_email
