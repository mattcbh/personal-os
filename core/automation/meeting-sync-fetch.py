#!/usr/bin/env python3
"""Compatibility wrapper for the meeting sync helper.

The implementation now lives in automation-runtime-personal. Keep this file so
repo-local tests and callers that still expect the old path continue to work.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path


EXTERNAL_MODULE_PATH = (
    Path.home() / "Projects" / "automation-runtime-personal" / "core" / "automation" / "meeting-sync-fetch.py"
)


def _load_external_module():
    spec = importlib.util.spec_from_file_location("automation_runtime_personal_meeting_sync_fetch", EXTERNAL_MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load meeting sync helper at {EXTERNAL_MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_MODULE = _load_external_module()

parse_iso_datetime = _MODULE.parse_iso_datetime
format_meeting_date = _MODULE.format_meeting_date
main = _MODULE.main


if __name__ == "__main__":
    raise SystemExit(main())
