from __future__ import annotations

import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import unittest


MODULE_PATH = Path(__file__).resolve().parents[3] / "scripts" / "system_health_audit.py"
SPEC = importlib.util.spec_from_file_location("system_health_audit", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class SystemHealthAuditTests(unittest.TestCase):
    def test_duplicate_things_ids_are_grouped(self) -> None:
        tasks = [
            MODULE.TaskRecord(
                path="things-sync/today.md",
                line_no=4,
                title="Task one",
                normalized_title="task one",
                token_set=frozenset({"task", "one"}),
                things_id="abc123",
                when_date=None,
            ),
            MODULE.TaskRecord(
                path="things-sync/inbox.md",
                line_no=7,
                title="Task one copy",
                normalized_title="task one copy",
                token_set=frozenset({"task", "one", "copy"}),
                things_id="abc123",
                when_date=None,
            ),
        ]

        duplicates = MODULE.find_duplicate_things_ids(tasks)

        self.assertEqual(list(duplicates.keys()), ["abc123"])
        self.assertEqual(len(duplicates["abc123"]), 2)

    def test_similar_task_titles_are_flagged(self) -> None:
        left = MODULE.TaskRecord(
            path="things-sync/today.md",
            line_no=10,
            title="File 633 2nd st LLC Biennial Statement this month",
            normalized_title=MODULE.normalize_task_title(
                "File 633 2nd st LLC Biennial Statement this month"
            ),
            token_set=MODULE.tokenize_title(
                MODULE.normalize_task_title(
                    "File 633 2nd st LLC Biennial Statement this month"
                )
            ),
            things_id="id-1",
            when_date="2028-03-01",
        )
        right = MODULE.TaskRecord(
            path="things-sync/today.md",
            line_no=18,
            title="File a NY LLC Biennial Statement for 633 2nd ST LLC",
            normalized_title=MODULE.normalize_task_title(
                "File a NY LLC Biennial Statement for 633 2nd ST LLC"
            ),
            token_set=MODULE.tokenize_title(
                MODULE.normalize_task_title(
                    "File a NY LLC Biennial Statement for 633 2nd ST LLC"
                )
            ),
            things_id="id-2",
            when_date="2028-03-15",
        )

        findings = MODULE.find_similar_task_pairs([left, right])

        self.assertEqual(len(findings), 1)
        self.assertGreaterEqual(findings[0]["token_overlap"], 0.75)

    def test_text_hygiene_flags_spacing_and_invisible_characters(self) -> None:
        with TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            note = tmp / "note.md"
            note.write_text(
                "- [ ] Fix punctuation , please\n"
                "Normal text with a\u200bhidden char.\n",
                encoding="utf-8",
            )

            findings = MODULE.collect_text_hygiene_findings([note])

            kinds = {item["kind"] for item in findings}
            self.assertIn("space-before-punctuation", kinds)
            self.assertIn("invisible-character", kinds)

    def test_collect_task_records_parses_things_markdown(self) -> None:
        with TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            today = tmp / "today.md"
            today.write_text(
                "# Today\n\n"
                "- [ ] Review launchd job `[things:ABC123]`\n"
                "- [x] Close duplicate task `[things:XYZ999]`\n",
                encoding="utf-8",
            )

            tasks = MODULE.collect_task_records(tmp)

            self.assertEqual(len(tasks), 2)
            self.assertEqual(tasks[0].things_id, "ABC123")
            self.assertEqual(tasks[1].things_id, "XYZ999")

    def test_detect_host_role_respects_env_override(self) -> None:
        old = MODULE.os.environ.get("SYSTEM_HEALTH_ROLE")
        try:
            MODULE.os.environ["SYSTEM_HEALTH_ROLE"] = "brain"
            self.assertEqual(MODULE.detect_host_role(), "brain")
            MODULE.os.environ["SYSTEM_HEALTH_ROLE"] = "laptop"
            self.assertEqual(MODULE.detect_host_role(), "laptop")
        finally:
            if old is None:
                MODULE.os.environ.pop("SYSTEM_HEALTH_ROLE", None)
            else:
                MODULE.os.environ["SYSTEM_HEALTH_ROLE"] = old

    def test_path_is_symlink_backed_when_parent_is_symlink(self) -> None:
        with TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            real_dir = tmp / "real"
            real_dir.mkdir()
            (real_dir / "child.txt").write_text("x", encoding="utf-8")
            linked_dir = tmp / "linked"
            linked_dir.symlink_to(real_dir, target_is_directory=True)

            self.assertTrue(MODULE.path_is_symlink_backed(linked_dir / "child.txt"))


if __name__ == "__main__":
    unittest.main()
