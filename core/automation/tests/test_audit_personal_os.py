from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest


MODULE_PATH = Path(__file__).resolve().parents[3] / "scripts" / "audit_personal_os.py"
SPEC = importlib.util.spec_from_file_location("audit_personal_os", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class AuditPersonalOsTests(unittest.TestCase):
    def test_personal_runtime_script_resolves_outside_vault(self) -> None:
        path = MODULE.resolve_manifest_runtime_path(
            "daily-digest",
            "script",
            "core/automation/daily-digest.sh",
        )
        self.assertEqual(
            path,
            Path.home() / "Projects" / "automation-runtime-personal" / "core/automation/daily-digest.sh",
        )

    def test_work_runtime_launchd_resolves_to_generated_plist(self) -> None:
        path = MODULE.resolve_manifest_runtime_path(
            "project-refresh-morning",
            "launchd_plist",
            "core/automation/launchd-plists/com.brain.project-refresh-morning.plist",
        )
        self.assertEqual(
            path,
            Path.home()
            / "Projects"
            / "automation-runtime-work"
            / ".generated"
            / "launchd"
            / "com.brain.project-refresh-morning.plist",
        )

    def test_local_script_stays_in_vault(self) -> None:
        path = MODULE.resolve_manifest_runtime_path(
            "system-health",
            "script",
            "core/automation/system-health.sh",
        )
        self.assertEqual(
            path,
            Path(__file__).resolve().parents[3] / "core/automation/system-health.sh",
        )


if __name__ == "__main__":
    unittest.main()
