from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from triage_v2.config import load_config
from triage_v2.context_pack import extract_top_priorities, sender_context_snippets
from triage_v2.draft_authoring import _thread_context_block
from triage_v2.project_context import (
    NextAction,
    ProjectUpdate,
    RecentCommunication,
    load_project_briefs,
    match_project_for_fields,
)
from triage_v2.project_refresh import run_project_refresh
from triage_v2.types import ThreadMessage


class ContextAndRefreshTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.projects_dir = self.root / "projects"
        self.context_dir = self.root / "context"
        self.policies_dir = self.root / "policies"
        self.state_dir = self.root / "state"
        self.transcripts_dir = self.root / "Knowledge" / "TRANSCRIPTS"
        for path in (
            self.projects_dir,
            self.context_dir,
            self.policies_dir,
            self.state_dir,
            self.transcripts_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)

        (self.root / "GOALS.md").write_text(
            """# Goals

## What are your top 3 priorities right now?
1. Park Project opening
2. Deal work
3. Hiring
""",
            encoding="utf-8",
        )
        (self.context_dir / "people.md").write_text(
            "## Key People\n\n- **Client Person** - Vendor partner\n",
            encoding="utf-8",
        )
        (self.context_dir / "email-contacts.md").write_text(
            "## Email Contacts\n\n| Name | Email / Domain | Context |\n|---|---|---|\n| Client Person | client@park-project.com | Park project vendor |\n| Park Project | *@park-project.com | Domain match |\n",
            encoding="utf-8",
        )
        (self.policies_dir / "email-drafting.md").write_text("Policy\n", encoding="utf-8")
        (self.context_dir / "writing-style.md").write_text("Style\n", encoding="utf-8")
        (self.projects_dir / "README.md").write_text(
            """# Projects

## Active Projects

| Project | Status | Priority | Goal | Brief |
|---------|--------|----------|------|-------|
| Park Project | Active | P0 | Open the next store | [park-project.md](park-project.md) |

## Archived Projects
""",
            encoding="utf-8",
        )
        (self.projects_dir / "park-project.md").write_text(
            """# Park Project

**Status:** Active
**Priority:** P0
**Goal:** Open the next store
**Last Updated:** 2026-03-05
**Match Signals:** Park Project, park-project.com, Client Person

## Summary
A buildout and launch project.

## Current Status
Waiting on approvals.

## Next Actions
| Action | Owner | Due | Source |
|--------|-------|-----|--------|
| Existing action | Matt | ASAP | Existing |

## Recent Communications

### 2026-03-05 — [Source: Email] Existing note
- Existing bullet
""",
            encoding="utf-8",
        )
        self.transcript_path = self.transcripts_dir / "2026-03-06 Vendor sync.md"
        self.transcript_path.write_text(
            """# Vendor sync

**Date:** 2026-03-06 09:00
**Meeting ID:** meeting-123
**Participants:** Client Person, Matt Lieber

## Summary

- Reviewed the Park Project payment flow
- Need approval on the invoice today

## Transcript

Client Person: Can you approve the invoice today?
""",
            encoding="utf-8",
        )
        (self.state_dir / "granola-sync.json").write_text(
            json.dumps(
                {
                    "last_sync": "2026-03-06T10:00:00Z",
                    "synced_meetings": {
                        "meeting-123": {
                            "title": "Vendor sync",
                            "date": "2026-03-06T09:00:00Z",
                            "synced_at": "2026-03-06T10:00:00Z",
                            "filepath": str(self.transcript_path),
                        }
                    },
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (self.state_dir / "project-refresh-state.json").write_text(
            json.dumps(
                {
                    "last_successful_refresh_timestamp": None,
                    "last_processed_event_timestamp": None,
                    "last_processed_granola_sync_timestamp": None,
                    "warnings": [],
                    "per_run_stats": [],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (self.state_dir / "comms-events.jsonl").write_text(
            "\n".join(
                [
                    json.dumps(
                        {
                            "event_id": "email:1",
                            "channel": "email",
                            "platform": "gmail",
                            "account": "work",
                            "timestamp": "2026-03-06T11:00:00Z",
                            "message_id": "m1",
                            "thread_id": "t1",
                            "sender": "Client Person <client@park-project.com>",
                            "subject": "Please approve Park Project invoice",
                            "snippet": "Can you approve this invoice today?",
                            "source_url_superhuman": "https://mail.superhuman.com/example/thread/t1",
                        }
                    ),
                    json.dumps(
                        {
                            "event_id": "chat:1",
                            "channel": "chat",
                            "platform": "beeper",
                            "network": "imessage",
                            "timestamp": "2026-03-06T12:00:00Z",
                            "chat_title": "Client Person",
                            "author": "Client Person",
                            "text": "Park Project is blocked until the invoice is approved.",
                        }
                    ),
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        self.env_keys = [
            "TRIAGE_V2_PROJECTS_DIR",
            "TRIAGE_V2_GOALS_PATH",
            "TRIAGE_V2_PEOPLE_PATH",
            "TRIAGE_V2_EMAIL_CONTACTS_PATH",
            "TRIAGE_V2_EMAIL_DRAFTING_POLICY_PATH",
            "TRIAGE_V2_WRITING_STYLE_PATH",
            "TRIAGE_V2_COMMS_EVENTS_PATH",
            "TRIAGE_V2_GRANOLA_SYNC_STATE_PATH",
            "TRIAGE_V2_PROJECT_REFRESH_STATE_PATH",
            "TRIAGE_V2_PROJECT_REFRESH_PROVIDER",
            "TRIAGE_V2_PROJECT_REFRESH_BATCH_SIZE",
            "TRIAGE_V2_SKIP_GRANOLA_LOCAL_SYNC",
        ]
        self.saved_env = {key: os.environ.get(key) for key in self.env_keys}
        os.environ["TRIAGE_V2_PROJECTS_DIR"] = str(self.projects_dir)
        os.environ["TRIAGE_V2_GOALS_PATH"] = str(self.root / "GOALS.md")
        os.environ["TRIAGE_V2_PEOPLE_PATH"] = str(self.context_dir / "people.md")
        os.environ["TRIAGE_V2_EMAIL_CONTACTS_PATH"] = str(self.context_dir / "email-contacts.md")
        os.environ["TRIAGE_V2_EMAIL_DRAFTING_POLICY_PATH"] = str(self.policies_dir / "email-drafting.md")
        os.environ["TRIAGE_V2_WRITING_STYLE_PATH"] = str(self.context_dir / "writing-style.md")
        os.environ["TRIAGE_V2_COMMS_EVENTS_PATH"] = str(self.state_dir / "comms-events.jsonl")
        os.environ["TRIAGE_V2_GRANOLA_SYNC_STATE_PATH"] = str(self.state_dir / "granola-sync.json")
        os.environ["TRIAGE_V2_PROJECT_REFRESH_STATE_PATH"] = str(self.state_dir / "project-refresh-state.json")
        os.environ["TRIAGE_V2_PROJECT_REFRESH_PROVIDER"] = "mock"
        os.environ["TRIAGE_V2_PROJECT_REFRESH_BATCH_SIZE"] = "1"
        os.environ["TRIAGE_V2_SKIP_GRANOLA_LOCAL_SYNC"] = "1"

    def tearDown(self) -> None:
        for key, value in self.saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self.tmp.cleanup()

    def test_extract_top_priorities(self) -> None:
        priorities = extract_top_priorities(self.root / "GOALS.md")
        self.assertEqual(priorities[:2], ["Park Project opening", "Deal work"])

    def test_sender_context_and_matching(self) -> None:
        briefs = load_project_briefs(self.projects_dir)
        self.assertEqual(len(briefs), 1)

        matched = match_project_for_fields(
            briefs,
            sender_email="client@park-project.com",
            sender_name="Client Person",
            subject="Please approve Park Project invoice",
            summary="Need approval today",
            body="Need approval today",
        )
        self.assertIsNotNone(matched)
        assert matched is not None
        self.assertEqual(matched.name, "Park Project")

        snippets = sender_context_snippets(
            sender_email="client@park-project.com",
            sender_name="Client Person",
            people_path=self.context_dir / "people.md",
            email_contacts_path=self.context_dir / "email-contacts.md",
        )
        self.assertTrue(any("Client Person" in snippet for snippet in snippets))

    def test_thread_context_block_is_bounded_and_strips_quotes(self) -> None:
        messages = [
            ThreadMessage(
                account="work",
                thread_id="t1",
                message_id="m1",
                received_at="2026-03-06T10:00:00Z",
                sender_email="client@park-project.com",
                sender_name="Client Person",
                subject="Subject",
                body_text="Latest update\n\nOn Wed, someone wrote:\n> quoted block",
            )
        ]
        block = _thread_context_block(messages)
        self.assertIn("Latest update", block)
        self.assertNotIn("quoted block", block)
        self.assertLessEqual(len(block), 12000)

    def test_project_refresh_updates_brief_from_events_and_transcript(self) -> None:
        cfg = load_config()
        result = run_project_refresh(cfg)
        self.assertEqual(result["status"], "succeeded")
        self.assertIn("Park Project", result["updated_projects"])

        brief_text = (self.projects_dir / "park-project.md").read_text(encoding="utf-8")
        self.assertIn("Please approve Park Project invoice", brief_text)
        self.assertIn("Vendor sync", brief_text)
        self.assertIn("Review Please approve Park Project invoice and reply with the next step", brief_text)

        refresh_state = json.loads((self.state_dir / "project-refresh-state.json").read_text(encoding="utf-8"))
        self.assertIsNotNone(refresh_state["last_successful_refresh_timestamp"])
        self.assertEqual(refresh_state["last_processed_event_timestamp"], "2026-03-06T12:00:00Z")
        self.assertEqual(refresh_state["last_processed_granola_sync_timestamp"], "2026-03-06T10:00:00Z")

    def test_project_refresh_advances_cursors_and_defers_failed_batches(self) -> None:
        cfg = load_config()
        call_count = {"value": 0}

        def flaky_update(*, cfg, project, batch, provider):
            call_count["value"] += 1
            if call_count["value"] == 1:
                raise RuntimeError("simulated batch failure")
            item = batch[0]
            return (
                ProjectUpdate(
                    recent_communications=(
                        RecentCommunication(
                            date=item.timestamp[:10],
                            source=item.source_type,
                            title=item.title,
                            bullets=("Recovered batch",),
                        ),
                    ),
                    next_actions=(
                        NextAction(
                            action=f"Review {item.title}",
                            owner="Matt",
                            due="ASAP",
                            source=f"{item.source_type} {item.timestamp[:10]}",
                        ),
                    ),
                ),
                [],
            )

        with mock.patch("triage_v2.project_refresh._project_batch_update", side_effect=flaky_update):
            first = run_project_refresh(cfg)

        self.assertEqual(first["status"], "partial_failure")

        refresh_state = json.loads((self.state_dir / "project-refresh-state.json").read_text(encoding="utf-8"))
        self.assertEqual(refresh_state["last_processed_event_timestamp"], "2026-03-06T12:00:00Z")
        self.assertEqual(refresh_state["last_processed_granola_sync_timestamp"], "2026-03-06T10:00:00Z")
        self.assertIsNone(refresh_state["last_successful_refresh_timestamp"])
        self.assertEqual(len(refresh_state["deferred_source_items"]), 1)
        self.assertIsNotNone(refresh_state["last_completed_refresh_timestamp"])

        second = run_project_refresh(cfg)
        self.assertEqual(second["status"], "succeeded")

        refresh_state = json.loads((self.state_dir / "project-refresh-state.json").read_text(encoding="utf-8"))
        self.assertIsNotNone(refresh_state["last_successful_refresh_timestamp"])
        self.assertEqual(refresh_state["deferred_source_items"], [])


if __name__ == "__main__":
    unittest.main()
