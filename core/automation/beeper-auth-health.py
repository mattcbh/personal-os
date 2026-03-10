#!/usr/bin/env python3
"""
Check mcp-remote OAuth token health for Beeper MCP configuration.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any


def compute_server_hash(server_url: str, resource: str, headers: dict[str, str]) -> str:
    parts = [server_url]
    if resource:
        parts.append(resource)
    if headers:
        parts.append(json.dumps(headers, sort_keys=True))
    return hashlib.md5("|".join(parts).encode("utf-8")).hexdigest()


def load_config(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("MCP config must be a JSON object")
    return raw


def parse_beeper_config(cfg: dict[str, Any]) -> tuple[str, str, dict[str, str], str]:
    beeper = cfg.get("mcpServers", {}).get("beeper")
    if not isinstance(beeper, dict):
        raise ValueError("beeper MCP server is not configured")

    args = beeper.get("args", [])
    if not isinstance(args, list):
        raise ValueError("beeper args must be a list")

    server_url = ""
    resource = ""
    for idx, arg in enumerate(args):
        if isinstance(arg, str) and arg.startswith("http"):
            server_url = arg
            break
    if not server_url:
        raise ValueError("beeper mcp-remote URL not found in args")

    for idx, arg in enumerate(args):
        if arg == "--resource" and idx + 1 < len(args):
            resource = str(args[idx + 1])
            break

    headers: dict[str, str] = {}
    for idx, arg in enumerate(args):
        if arg == "--header" and idx + 1 < len(args):
            header_val = str(args[idx + 1])
            if ":" not in header_val:
                continue
            key, val = header_val.split(":", 1)
            headers[key.strip()] = val.strip()

    config_root = (
        beeper.get("env", {}).get("MCP_REMOTE_CONFIG_DIR")
        or os.environ.get("MCP_REMOTE_CONFIG_DIR")
        or str(Path.home() / ".mcp-auth")
    )
    return server_url, resource, headers, config_root


def newest_token_file(config_root: Path, server_hash: str) -> Path | None:
    if not config_root.exists():
        return None

    candidates: list[Path] = []
    for entry in config_root.glob("mcp-remote-*"):
        token_file = entry / f"{server_hash}_tokens.json"
        if token_file.exists():
            candidates.append(token_file)

    if not candidates:
        return None
    return sorted(candidates, key=lambda p: p.stat().st_mtime, reverse=True)[0]


def evaluate_token(token_file: Path, warn_hours: float) -> dict[str, Any]:
    try:
        token = json.loads(token_file.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "ok": False,
            "status": "token_parse_error",
            "token_file": str(token_file),
            "error": str(exc),
        }

    expires_in = token.get("expires_in")
    has_refresh = bool(token.get("refresh_token"))

    if not isinstance(expires_in, (int, float)) or expires_in <= 0:
        return {
            "ok": True,
            "status": "token_present_unknown_expiry",
            "token_file": str(token_file),
            "has_refresh_token": has_refresh,
        }

    now_ts = time.time()
    mtime = token_file.stat().st_mtime
    remaining_seconds = (mtime + float(expires_in)) - now_ts
    remaining_hours = round(remaining_seconds / 3600.0, 2)

    if remaining_seconds <= 0:
        status = "expired"
    elif remaining_hours <= warn_hours:
        status = "expiring_soon"
    else:
        status = "authenticated"

    return {
        "ok": True,
        "status": status,
        "token_file": str(token_file),
        "remaining_hours": remaining_hours,
        "has_refresh_token": has_refresh,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Check Beeper MCP auth health")
    parser.add_argument("--mcp-config", required=True, help="Path to MCP config JSON")
    parser.add_argument("--warn-hours", type=float, default=72.0, help="Warning threshold in hours")
    args = parser.parse_args()

    config_path = Path(args.mcp_config)
    if not config_path.exists():
        print(json.dumps({"ok": False, "status": "missing_config", "path": str(config_path)}))
        return 1

    try:
        cfg = load_config(config_path)
        server_url, resource, headers, config_root = parse_beeper_config(cfg)
    except Exception as exc:
        print(json.dumps({"ok": False, "status": "invalid_beeper_config", "error": str(exc)}))
        return 1

    server_hash = compute_server_hash(server_url, resource, headers)
    token_file = newest_token_file(Path(config_root), server_hash)
    if token_file is None:
        print(
            json.dumps(
                {
                    "ok": True,
                    "status": "missing_token",
                    "server_hash": server_hash,
                    "config_root": config_root,
                    "server_url": server_url,
                }
            )
        )
        return 0

    result = evaluate_token(token_file, args.warn_hours)
    result["server_hash"] = server_hash
    result["config_root"] = config_root
    result["server_url"] = server_url
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
