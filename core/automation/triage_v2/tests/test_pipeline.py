from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import unittest

from triage_v2.config import ensure_directories, load_config
from triage_v2.db import connect, fetch_coverage, init_db, insert_run
from triage_v2.pipeline import run_pipeline


class PipelineTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.state_dir = self.root / "state"
        self.fixture_dir = self.root / "fixtures"
        self.projects_dir = self.root / "projects"
        self.context_dir = self.root / "context"
        self.policies_dir = self.root / "policies"
        self.gmail_work_home = self.root / "gmail-work"
        self.gmail_personal_home = self.root / "gmail-personal"
        self.project_refresh_state_path = self.root / "project-refresh-state.json"

        for path in (
            self.fixture_dir,
            self.projects_dir,
            self.context_dir,
            self.policies_dir,
            self.gmail_work_home,
            self.gmail_personal_home,
        ):
            path.mkdir(parents=True, exist_ok=True)

        (self.fixture_dir / "personal.json").write_text(
            json.dumps(
                [
                    {
                        "message_id": "p-100",
                        "thread_id": "t-personal-amit",
                        "received_at": "2026-03-06T01:05:00Z",
                        "sender_email": "amitmshah74@gmail.com",
                        "sender_name": "Amit Shah",
                        "subject": "Re: connections",
                        "snippet": "Hi Matt, It was great chatting with you earlier this week and learning more about your use case. Please let me know if you need any additional information.",
                        "body_text": "Hi Matt,\n\nIt was great chatting with you earlier this week and learning more about your use case. Please let me know if you need any additional information. I look forward to hearing from you.\n\nBest,\nAmit",
                        "metadata": {},
                    },
                    {
                        "message_id": "p-200",
                        "thread_id": "t-personal-ezpass",
                        "received_at": "2026-03-06T01:10:00Z",
                        "sender_email": "customerservice@e-zpassny.com",
                        "sender_name": "E-ZPass New York Customer Service",
                        "subject": "E-ZPass NY: Bank Account Payment Confirmation",
                        "snippet": "A payment of $48.71 was applied to E-ZPass NY account xxxxxx4982. Your account balance is $0.00.",
                        "body_text": "Dear LIEBER LIEBER,\n\nA payment of $48.71 was applied to E-ZPass NY account xxxxxx4982. Your account balance is $0.00.\n\nThank you,\nE-ZPass NY Service Center",
                        "metadata": {},
                    },
                    {
                        "message_id": "p-300",
                        "thread_id": "t-personal-backcountry",
                        "received_at": "2026-03-06T01:15:00Z",
                        "sender_email": "backcountry@b.backcountry.com",
                        "sender_name": "Backcountry",
                        "subject": "Your Order is Arriving Tomorrow",
                        "snippet": "Your new gear has made some serious headway.",
                        "body_text": "Your new gear has made some serious headway and should arrive tomorrow. Track your shipment in your Backcountry account.",
                        "metadata": {},
                    },
                    {
                        "message_id": "p-400",
                        "thread_id": "t-personal-feedme",
                        "received_at": "2026-03-06T01:20:00Z",
                        "sender_email": "emilysundberg@substack.com",
                        "sender_name": "Feed Me",
                        "subject": "Feed Me: hospitality notes",
                        "snippet": "Emily Sundberg writes about hospitality culture and the latest restaurant chatter.",
                        "body_text": "Feed Me rounds up hospitality culture news, media chatter, and a few restaurant observations worth knowing this week.",
                        "list_unsubscribe": "https://feedme.example/unsubscribe",
                        "metadata": {},
                    },
                ],
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (self.fixture_dir / "work.json").write_text(
            json.dumps(
                [
                    {
                        "message_id": "w-100",
                        "thread_id": "t-work-001",
                        "received_at": "2026-03-06T00:10:00Z",
                        "sender_email": "matt@cornerboothholdings.com",
                        "sender_name": "Matt Lieber",
                        "subject": "Re: Park project invoice",
                        "snippet": "Looping back on this.",
                        "body_text": "Looping back on this. Send me the updated invoice and I can review it today.",
                        "metadata": {},
                    },
                    {
                        "message_id": "w-101",
                        "thread_id": "t-work-001",
                        "received_at": "2026-03-06T00:20:00Z",
                        "sender_email": "client@park-project.com",
                        "sender_name": "Client Person",
                        "subject": "Please approve Park project invoice",
                        "snippet": "Can you approve this invoice today?",
                        "body_text": "Can you approve the Park project invoice today so we can release payment?\n\nOn Wed, someone wrote:\n> old quoted text",
                        "metadata": {},
                    },
                    {
                        "message_id": "w-200",
                        "thread_id": "t-work-002",
                        "received_at": "2026-03-06T00:30:00Z",
                        "sender_email": "other@example.com",
                        "sender_name": "Other Sender",
                        "subject": "Please review terms",
                        "snippet": "Can you review this?",
                        "body_text": "Can you review this today?",
                        "metadata": {},
                    },
                    {
                        "message_id": "w-300",
                        "thread_id": "t-work-003",
                        "received_at": "2026-03-06T00:35:00Z",
                        "sender_email": "gilli@brownbagny.com",
                        "sender_name": "Gilli Rozynek",
                        "subject": "Rich<>Matt",
                        "snippet": "Matt and his team are looking closely at Brown Bag and I thought you two should meet.",
                        "body_text": "Hi Rich, I wanted to introduce you to Matt Lieber from Corner Booth Holdings. Matt and his team are looking closely at Brown Bag and I thought you two should meet.",
                        "metadata": {},
                    },
                    {
                        "message_id": "w-301",
                        "thread_id": "t-work-003",
                        "received_at": "2026-03-06T00:45:00Z",
                        "sender_email": "rich@380cap.com",
                        "sender_name": "Richard Kim",
                        "subject": "Re: Rich<>Matt",
                        "snippet": "Matt good to meet. You in NY? Pretty free early next week. Coffee or call works well for me.",
                        "body_text": "Matt good to meet. You in NY? Pretty free early next week. Coffee or call works well for me.",
                        "metadata": {},
                    },
                    {
                        "message_id": "w-400",
                        "thread_id": "t-work-004",
                        "received_at": "2026-03-06T00:50:00Z",
                        "sender_email": "matt@cornerboothholdings.com",
                        "sender_name": "Matt Lieber",
                        "subject": "Re: Pies N Thighs: Vendor Aging as of 02-24-26",
                        "snippet": "Yes, please go ahead.",
                        "body_text": "Yes, please go ahead with the $28000 transfer and process week 2 payments.",
                        "metadata": {},
                    },
                    {
                        "message_id": "w-401",
                        "thread_id": "t-work-004",
                        "received_at": "2026-03-06T00:55:00Z",
                        "sender_email": "pies-n-thighs@systematiq.co",
                        "sender_name": "Jillian",
                        "subject": "Re: Pies N Thighs: Vendor Aging as of 02-24-26",
                        "snippet": "Got it, we will go ahead and proceed with the $28000 transfer and process Week 2 payments.",
                        "body_text": "Good Morning Matt, Got it, we will go ahead and proceed with the $28000 transfer and process Week 2 payments.",
                        "metadata": {},
                    },
                    {
                        "message_id": "w-500",
                        "thread_id": "t-work-cora",
                        "received_at": "2026-03-06T01:00:00Z",
                        "sender_email": "daily@corabriefs.com",
                        "sender_name": "Cora Briefs",
                        "subject": "Morning Brief",
                        "snippet": "Daily work roundup with the top items to watch this morning.",
                        "body_text": "Daily work roundup with the top items to watch this morning.",
                        "list_unsubscribe": "https://cora.example/unsub",
                        "metadata": {},
                    },
                    {
                        "message_id": "w-600",
                        "thread_id": "t-work-ramp",
                        "received_at": "2026-03-06T01:05:00Z",
                        "sender_email": "alerts@ramp.com",
                        "sender_name": "Ramp",
                        "subject": "Action required: transaction declined",
                        "snippet": "A card transaction was declined because the account is over limit.",
                        "body_text": "A card transaction was declined because the account is over limit.",
                        "metadata": {},
                    },
                    {
                        "message_id": "w-700",
                        "thread_id": "t-work-otter",
                        "received_at": "2026-03-06T01:10:00Z",
                        "sender_email": "jason@piesnthighs.com",
                        "sender_name": "Jason Hershfeld",
                        "subject": "Re: Pies 'n' Thighs - Park Slope / Owner.com Onboarding",
                        "snippet": "Otter shows subscription required and the setup is stalled before opening day.",
                        "body_text": "Hi Jack,\n\nGBP and Toast are set up, but Otter still shows subscription required instead of ADD NOW. That is stalling the integration ahead of the March 21 opening.",
                        "metadata": {},
                    },
                ],
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        (self.projects_dir / "README.md").write_text(
            """# Projects

## Active Projects

| Project | Status | Priority | Goal | Brief |
|---------|--------|----------|------|-------|
| Park Project | Active | P0 | Open the next store | [park-project.md](park-project.md) |
| Brown Bag Sandwich Co. | Active | P0 | Acquire and integrate one additional aligned brand | [brown-bag-acquisition.md](brown-bag-acquisition.md) |

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
**Match Signals:** Park Project, park-project.com, Park project invoice

## Summary
A live buildout project.

## Current Status
Waiting on vendor approvals and cash timing.

## Next Actions
| Action | Owner | Due | Source |
|--------|-------|-----|--------|
| Confirm invoice timing | Matt | ASAP | Existing |

## Recent Communications

### 2026-03-05 — [Source: Email] Existing update
- Prior status note
""",
            encoding="utf-8",
        )
        (self.projects_dir / "brown-bag-acquisition.md").write_text(
            """# Brown Bag Sandwich Co. Acquisition

**Status:** Active
**Priority:** P0
**Goal:** Acquire and integrate one additional aligned brand
**Last Updated:** 2026-03-05
**Match Signals:** Brown Bag, Gilli, brownbagny.com, acquisition

## Summary
Active acquisition work with Gilli and Brown Bag.

## Current Status
High-priority deal process.

## Next Actions
| Action | Owner | Due | Source |
|--------|-------|-----|--------|
| Keep deal momentum with Gilli | Matt | ASAP | Existing |

## Recent Communications

### 2026-03-05 — [Source: Email] Existing Brown Bag update
- Deal remains one of the top priorities
""",
            encoding="utf-8",
        )
        (self.root / "GOALS.md").write_text(
            """# Goals

## What are your top 3 priorities right now?
1. Park Project opening
2. Acquisition work
3. Hiring
""",
            encoding="utf-8",
        )
        (self.context_dir / "people.md").write_text(
            "## Key People\n\n- **Client Person** - Vendor contact for Park Project\n",
            encoding="utf-8",
        )
        (self.context_dir / "email-contacts.md").write_text(
            "## Email Contacts\n\n| Name | Email / Domain | Context |\n|---|---|---|\n| Client Person | client@park-project.com | Park Project vendor |\n",
            encoding="utf-8",
        )
        (self.policies_dir / "email-drafting.md").write_text(
            "Draft policy: plain text, do not invent facts.\n",
            encoding="utf-8",
        )
        (self.context_dir / "writing-style.md").write_text(
            "Be direct. No em dashes.\n",
            encoding="utf-8",
        )

        self.env_keys = [
            "TRIAGE_V2_STATE_DIR",
            "TRIAGE_V2_FIXTURE_DIR",
            "TRIAGE_V2_PROVIDER_MODE",
            "TRIAGE_V2_SENDER_MODE",
            "TRIAGE_V2_DRAFT_MODE",
            "TRIAGE_V2_SUPERHUMAN_ENABLED",
            "TRIAGE_V2_PROJECTS_DIR",
            "TRIAGE_V2_GOALS_PATH",
            "TRIAGE_V2_PEOPLE_PATH",
            "TRIAGE_V2_EMAIL_CONTACTS_PATH",
            "TRIAGE_V2_EMAIL_DRAFTING_POLICY_PATH",
            "TRIAGE_V2_WRITING_STYLE_PATH",
            "TRIAGE_V2_PROJECT_REFRESH_STATE_PATH",
            "TRIAGE_V2_DRAFT_AUTHORING_PROVIDER",
            "TRIAGE_V2_DRAFT_AUTHORING_MODE",
            "TRIAGE_V2_GMAIL_WORK_HOME",
            "TRIAGE_V2_GMAIL_PERSONAL_HOME",
            "TRIAGE_V2_CLAUDE_PATH",
        ]
        self.saved_env = {key: os.environ.get(key) for key in self.env_keys}

        os.environ["TRIAGE_V2_STATE_DIR"] = str(self.state_dir)
        os.environ["TRIAGE_V2_FIXTURE_DIR"] = str(self.fixture_dir)
        os.environ["TRIAGE_V2_PROVIDER_MODE"] = "file"
        os.environ["TRIAGE_V2_SENDER_MODE"] = "local_outbox"
        os.environ["TRIAGE_V2_DRAFT_MODE"] = "superhuman_preferred"
        os.environ["TRIAGE_V2_SUPERHUMAN_ENABLED"] = "0"
        os.environ["TRIAGE_V2_PROJECTS_DIR"] = str(self.projects_dir)
        os.environ["TRIAGE_V2_GOALS_PATH"] = str(self.root / "GOALS.md")
        os.environ["TRIAGE_V2_PEOPLE_PATH"] = str(self.context_dir / "people.md")
        os.environ["TRIAGE_V2_EMAIL_CONTACTS_PATH"] = str(self.context_dir / "email-contacts.md")
        os.environ["TRIAGE_V2_EMAIL_DRAFTING_POLICY_PATH"] = str(self.policies_dir / "email-drafting.md")
        os.environ["TRIAGE_V2_WRITING_STYLE_PATH"] = str(self.context_dir / "writing-style.md")
        os.environ["TRIAGE_V2_PROJECT_REFRESH_STATE_PATH"] = str(self.project_refresh_state_path)
        os.environ["TRIAGE_V2_DRAFT_AUTHORING_PROVIDER"] = "mock"
        os.environ["TRIAGE_V2_DRAFT_AUTHORING_MODE"] = "llm_with_fallback"
        os.environ["TRIAGE_V2_GMAIL_WORK_HOME"] = str(self.gmail_work_home)
        os.environ["TRIAGE_V2_GMAIL_PERSONAL_HOME"] = str(self.gmail_personal_home)
        os.environ["TRIAGE_V2_CLAUDE_PATH"] = str(self.root / "missing-claude")

        self.cfg = load_config()
        ensure_directories(self.cfg)
        self.conn = connect(self.cfg.db_path)
        init_db(self.conn)

    def tearDown(self) -> None:
        self.conn.close()
        for key, value in self.saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self.tmp.cleanup()

    def _write_refresh_state(self, *, fresh: bool) -> None:
        timestamp = "2099-03-06T01:30:00+00:00" if fresh else "2026-03-04T01:30:00+00:00"
        self.project_refresh_state_path.write_text(
            json.dumps(
                {
                    "last_successful_refresh_timestamp": timestamp,
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

    def _rewrite_project_last_updated(self, value: str) -> None:
        path = self.projects_dir / "park-project.md"
        text = path.read_text(encoding="utf-8")
        text = text.replace("**Last Updated:** 2026-03-05", f"**Last Updated:** {value}")
        path.write_text(text, encoding="utf-8")

    def test_pipeline_run_generates_artifacts_and_coverage(self) -> None:
        self._write_refresh_state(fresh=True)
        run_id = "test-run-1"
        insert_run(self.conn, run_id, "manual", "queued", True)
        result = run_pipeline(
            conn=self.conn,
            cfg=self.cfg,
            run_id=run_id,
            run_type="manual",
            force_reconcile=True,
        )

        self.assertEqual(result["status"], "succeeded")
        self.assertGreaterEqual(result["entries"], 1)

        coverage = fetch_coverage(self.conn, run_id)
        self.assertIsNotNone(coverage)
        assert coverage is not None
        self.assertTrue(coverage["pass"])
        self.assertEqual(coverage["missing_count"], 0)

        outbox = self.cfg.outbox_dir / f"outbox-{run_id}.json"
        self.assertTrue(outbox.exists())
        payload = json.loads(outbox.read_text(encoding="utf-8"))
        self.assertEqual(payload["run_id"], run_id)

    def test_action_needed_uses_llm_authoring_when_project_context_fresh(self) -> None:
        self._write_refresh_state(fresh=True)
        run_id = "test-run-llm"
        insert_run(self.conn, run_id, "manual", "queued", True)
        result = run_pipeline(
            conn=self.conn,
            cfg=self.cfg,
            run_id=run_id,
            run_type="manual",
            force_reconcile=True,
        )
        self.assertEqual(result["status"], "succeeded")

        rows = json.loads((self.cfg.artifact_dir / f"{run_id}.entries.json").read_text(encoding="utf-8"))
        matched = next(row for row in rows if row["thread_id"] == "t-work-001")
        unmatched = next(row for row in rows if row["thread_id"] == "t-work-002")

        self.assertEqual(matched["draft_authoring_mode"], "llm")
        self.assertEqual(matched["draft_context_status"], "fresh")
        self.assertIsNone(matched["draft_authoring_error"])
        self.assertEqual(unmatched["draft_authoring_mode"], "llm")
        self.assertEqual(unmatched["draft_context_status"], "unmatched")

    def test_action_needed_falls_back_when_project_refresh_is_stale(self) -> None:
        self._write_refresh_state(fresh=False)
        self._rewrite_project_last_updated("2026-03-01")
        run_id = "test-run-stale"
        insert_run(self.conn, run_id, "manual", "queued", True)
        result = run_pipeline(
            conn=self.conn,
            cfg=self.cfg,
            run_id=run_id,
            run_type="manual",
            force_reconcile=True,
        )
        self.assertEqual(result["status"], "succeeded")

        rows = json.loads((self.cfg.artifact_dir / f"{run_id}.entries.json").read_text(encoding="utf-8"))
        matched = next(row for row in rows if row["thread_id"] == "t-work-001")
        unmatched = next(row for row in rows if row["thread_id"] == "t-work-002")

        self.assertEqual(matched["draft_authoring_mode"], "fallback_deterministic")
        self.assertEqual(matched["draft_context_status"], "stale")
        self.assertIn("stale", matched["draft_authoring_error"])
        self.assertEqual(unmatched["draft_authoring_mode"], "llm")
        self.assertEqual(unmatched["draft_context_status"], "unmatched")

    def test_recent_project_brief_still_counts_as_fresh_when_global_refresh_is_stale(self) -> None:
        self._write_refresh_state(fresh=False)
        self._rewrite_project_last_updated("2099-03-06")
        run_id = "test-run-brief-fresh"
        insert_run(self.conn, run_id, "manual", "queued", True)
        result = run_pipeline(
            conn=self.conn,
            cfg=self.cfg,
            run_id=run_id,
            run_type="manual",
            force_reconcile=True,
        )
        self.assertEqual(result["status"], "succeeded")

        rows = json.loads((self.cfg.artifact_dir / f"{run_id}.entries.json").read_text(encoding="utf-8"))
        matched = next(row for row in rows if row["thread_id"] == "t-work-001")
        self.assertEqual(matched["draft_authoring_mode"], "llm")
        self.assertEqual(matched["draft_context_status"], "fresh")
        self.assertIsNone(matched["draft_authoring_error"])

    def test_high_priority_intro_reply_is_upgraded_to_action_needed(self) -> None:
        self._write_refresh_state(fresh=True)
        run_id = "test-run-rich"
        insert_run(self.conn, run_id, "manual", "queued", True)
        result = run_pipeline(
            conn=self.conn,
            cfg=self.cfg,
            run_id=run_id,
            run_type="manual",
            force_reconcile=True,
        )
        self.assertEqual(result["status"], "succeeded")

        rows = json.loads((self.cfg.artifact_dir / f"{run_id}.entries.json").read_text(encoding="utf-8"))
        rich = next(row for row in rows if row["thread_id"] == "t-work-003")
        self.assertEqual(rich["bucket"], "Action Needed")
        self.assertTrue(rich["response_needed"])
        self.assertIn("coffee or a call", rich["suggested_response"].lower())

    def test_acknowledgement_after_my_reply_is_classified_already_addressed(self) -> None:
        self._write_refresh_state(fresh=True)
        run_id = "test-run-jillian"
        insert_run(self.conn, run_id, "manual", "queued", True)
        result = run_pipeline(
            conn=self.conn,
            cfg=self.cfg,
            run_id=run_id,
            run_type="manual",
            force_reconcile=True,
        )
        self.assertEqual(result["status"], "succeeded")

        rows = json.loads((self.cfg.artifact_dir / f"{run_id}.entries.json").read_text(encoding="utf-8"))
        jillian = next(row for row in rows if row["thread_id"] == "t-work-004")
        self.assertEqual(jillian["bucket"], "Already Addressed")
        self.assertEqual(jillian["draft_status"], "not_needed")

    def test_amit_followup_gets_response_guidance_and_draft(self) -> None:
        self._write_refresh_state(fresh=True)
        run_id = "test-run-amit"
        insert_run(self.conn, run_id, "manual", "queued", True)
        result = run_pipeline(
            conn=self.conn,
            cfg=self.cfg,
            run_id=run_id,
            run_type="manual",
            force_reconcile=True,
        )
        self.assertEqual(result["status"], "succeeded")

        rows = json.loads((self.cfg.artifact_dir / f"{run_id}.entries.json").read_text(encoding="utf-8"))
        amit = next(row for row in rows if row["thread_id"] == "t-personal-amit")
        self.assertEqual(amit["bucket"], "Action Needed")
        self.assertTrue(amit["response_needed"])
        self.assertIn("amit shah", amit["summary_latest"].lower())
        self.assertIn("what information", amit["suggested_response"].lower())
        self.assertEqual(amit["draft_status"], "failed")

    def test_ezpass_confirmation_is_fyi_without_response(self) -> None:
        self._write_refresh_state(fresh=True)
        run_id = "test-run-ezpass"
        insert_run(self.conn, run_id, "manual", "queued", True)
        result = run_pipeline(
            conn=self.conn,
            cfg=self.cfg,
            run_id=run_id,
            run_type="manual",
            force_reconcile=True,
        )
        self.assertEqual(result["status"], "succeeded")

        rows = json.loads((self.cfg.artifact_dir / f"{run_id}.entries.json").read_text(encoding="utf-8"))
        ezpass = next(row for row in rows if row["thread_id"] == "t-personal-ezpass")
        self.assertEqual(ezpass["bucket"], "FYI")
        self.assertFalse(ezpass["response_needed"])
        self.assertIn("e-zpass", ezpass["summary_latest"].lower())
        self.assertEqual(ezpass["draft_status"], "not_needed")

    def test_policy_overrides_and_monitoring_flow_through_pipeline(self) -> None:
        self._write_refresh_state(fresh=True)
        run_id = "test-run-policy-overrides"
        insert_run(self.conn, run_id, "manual", "queued", True)
        result = run_pipeline(
            conn=self.conn,
            cfg=self.cfg,
            run_id=run_id,
            run_type="manual",
            force_reconcile=True,
        )
        self.assertEqual(result["status"], "succeeded")

        rows = json.loads((self.cfg.artifact_dir / f"{run_id}.entries.json").read_text(encoding="utf-8"))
        cora = next(row for row in rows if row["thread_id"] == "t-work-cora")
        ramp = next(row for row in rows if row["thread_id"] == "t-work-ramp")
        otter = next(row for row in rows if row["thread_id"] == "t-work-otter")

        self.assertEqual(cora["bucket"], "Newsletters")
        self.assertEqual(ramp["bucket"], "FYI")
        self.assertFalse(ramp["response_needed"])
        self.assertEqual(otter["bucket"], "Monitoring")
        self.assertFalse(otter["response_needed"])
        self.assertEqual(otter["suggested_response"], "")

    def test_shipping_update_and_newsletter_get_semantic_summaries(self) -> None:
        self._write_refresh_state(fresh=True)
        run_id = "test-run-semantic"
        insert_run(self.conn, run_id, "manual", "queued", True)
        result = run_pipeline(
            conn=self.conn,
            cfg=self.cfg,
            run_id=run_id,
            run_type="manual",
            force_reconcile=True,
        )
        self.assertEqual(result["status"], "succeeded")

        rows = json.loads((self.cfg.artifact_dir / f"{run_id}.entries.json").read_text(encoding="utf-8"))
        backcountry = next(row for row in rows if row["thread_id"] == "t-personal-backcountry")
        feed_me = next(row for row in rows if row["thread_id"] == "t-personal-feedme")

        self.assertEqual(backcountry["bucket"], "FYI")
        self.assertFalse(backcountry["response_needed"])
        self.assertIn("backcountry", backcountry["summary_latest"].lower())
        self.assertIn("arrive", backcountry["summary_latest"].lower())

        self.assertEqual(feed_me["bucket"], "Newsletters")
        self.assertFalse(feed_me["response_needed"])
        self.assertIn("feed me", feed_me["summary_latest"].lower())
        self.assertNotEqual(feed_me["summary_latest"], feed_me["subject_latest"])


if __name__ == "__main__":
    unittest.main()
