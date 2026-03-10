from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock


MODULE_PATH = Path(__file__).resolve().parents[2] / "email-ingest.py"
SPEC = importlib.util.spec_from_file_location("email_ingest", MODULE_PATH)
assert SPEC is not None
assert SPEC.loader is not None
email_ingest = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(email_ingest)


class EmailIngestTest(unittest.TestCase):
    def test_run_ingest_updates_state_and_appends_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            state_path = root / "comms-state.json"
            events_path = root / "comms-events.jsonl"
            state_path.write_text(
                json.dumps(
                    {
                        "last_ingest_timestamp": "2026-03-05T12:00:00Z",
                        "seen_event_ids": ["email:work:existing"],
                        "runs": 1,
                        "last_run_stats": {},
                        "last_warnings": [],
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            work_events = [
                {
                    "event_id": "email:work:m1",
                    "channel": "email",
                    "platform": "gmail",
                    "account": "work",
                    "timestamp": "2026-03-06T10:00:00Z",
                    "message_id": "m1",
                    "thread_id": "t1",
                    "sender": "Alice <alice@example.com>",
                    "subject": "Hello",
                    "snippet": "Hello there",
                    "source_url_superhuman": "https://mail.superhuman.com/work/thread/t1",
                    "source_url_gmail": "https://mail.google.com/mail/u/work/#inbox/t1",
                }
            ]
            personal_events = [
                {
                    "event_id": "email:personal:p1",
                    "channel": "email",
                    "platform": "gmail",
                    "account": "personal",
                    "timestamp": "2026-03-06T11:00:00Z",
                    "message_id": "p1",
                    "thread_id": "t2",
                    "sender": "Bob <bob@example.com>",
                    "subject": "Personal note",
                    "snippet": "Checking in",
                    "source_url_superhuman": "https://mail.superhuman.com/personal/thread/t2",
                    "source_url_gmail": "https://mail.google.com/mail/u/personal/#inbox/t2",
                }
            ]

            args = email_ingest.build_parser().parse_args(
                [
                    "--state-file",
                    str(state_path),
                    "--events-file",
                    str(events_path),
                ]
            )

            with mock.patch.object(
                email_ingest,
                "collect_account_events",
                side_effect=[work_events, personal_events],
            ):
                result = email_ingest.run_ingest(args)

            self.assertTrue(result["ok"])
            self.assertEqual(result["new_email_events_work"], 1)
            self.assertEqual(result["new_email_events_personal"], 1)

            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(state["runs"], 2)
            self.assertEqual(state["last_run_stats"]["total_new_events"], 2)
            self.assertEqual(
                state["seen_event_ids"],
                ["email:work:existing", "email:work:m1", "email:personal:p1"],
            )

            lines = events_path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 2)
            self.assertEqual(json.loads(lines[0])["event_id"], "email:work:m1")
            self.assertEqual(json.loads(lines[1])["event_id"], "email:personal:p1")


if __name__ == "__main__":
    unittest.main()
