from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess


class LlmClientError(RuntimeError):
    pass


class ClaudeCliJsonClient:
    def __init__(self, *, binary_path: Path, model: str, timeout_seconds: int) -> None:
        self.binary_path = binary_path
        self.model = model
        self.timeout_seconds = timeout_seconds

    def generate_json(self, *, prompt: str, system_prompt: str) -> dict:
        if not self.binary_path.exists():
            raise LlmClientError(f"Claude CLI not found at {self.binary_path}")

        cmd = [
            str(self.binary_path),
            "-p",
            prompt,
            "--model",
            self.model,
            "--permission-mode",
            "bypassPermissions",
            "--system-prompt",
            system_prompt,
            "--disable-slash-commands",
            "--no-session-persistence",
        ]
        env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
                timeout=self.timeout_seconds,
                env=env,
            )
        except subprocess.TimeoutExpired as exc:
            raise LlmClientError(f"Claude CLI timed out after {self.timeout_seconds}s") from exc
        except Exception as exc:
            raise LlmClientError(f"Claude CLI invocation failed: {exc}") from exc

        if result.returncode != 0:
            stderr = (result.stderr or "").strip()
            stdout = (result.stdout or "").strip()
            detail = stderr or stdout or f"exit code {result.returncode}"
            raise LlmClientError(f"Claude CLI failed: {detail[:500]}")

        raw = (result.stdout or "").strip()
        if not raw:
            raise LlmClientError("Claude CLI returned empty output")
        return _extract_json_object(raw)


def _extract_json_object(raw: str) -> dict:
    raw = raw.strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start < 0 or end < 0 or end <= start:
            raise LlmClientError("Claude CLI did not return JSON")
        try:
            data = json.loads(raw[start : end + 1])
        except json.JSONDecodeError as exc:
            raise LlmClientError(f"Claude CLI returned invalid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise LlmClientError("Claude CLI JSON response was not an object")
    return data
