from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


MODULE_PATH = Path(__file__).resolve().parents[1] / "email-triage-render.py"
SPEC = importlib.util.spec_from_file_location("email_triage_render", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class EmailTriageRenderTest(unittest.TestCase):
    def test_markdown_uses_sender_name_and_full_action_details(self) -> None:
        records = [
            {
                "bucket": "Action Needed",
                "account": "work",
                "threadId": "thread-123",
                "sender_email": "person@example.com",
                "sender_name": "Person",
                "subject_latest": "Please approve",
                "summary_latest": "Person sent a document that needs approval today.",
                "suggested_response": "Tell Person you approve it and confirm timing.",
                "suggested_action": "Reply to Person and confirm timing.",
                "draft_status": "queued",
                "draft_authoring_mode": "fallback_deterministic",
                "draft_context_status": "stale",
                "superhuman_url": "https://mail.superhuman.com/matt@cornerboothholdings.com/thread/thread-123",
                "messageIds": ["m1"],
            }
        ]

        markdown = MODULE.render_markdown(records, "Tuesday March 10, 2026", "4:42 PM", "PM")
        self.assertIn("**From:** Person", markdown)
        self.assertIn("**Recommended response:** Tell Person you approve it and confirm timing.", markdown)
        self.assertIn("**Next step:** Reply to Person and confirm timing.", markdown)
        self.assertIn("[Draft ready](https://mail.superhuman.com/matt@cornerboothholdings.com/thread/thread-123)", markdown)
        self.assertIn("Draft status: queued", markdown)
        self.assertIn("**Draft note:** deterministic fallback, project refresh stale.", markdown)

    def test_newsletters_render_as_sender_summary_lines(self) -> None:
        records = [
            {
                "bucket": "Newsletters",
                "account": "personal",
                "threadId": "news-001",
                "sender_email": "emilysundberg@substack.com",
                "sender_name": "Feed Me",
                "subject_latest": "Feed Me: hospitality notes",
                "summary_latest": "Feed Me rounds up hospitality culture notes and restaurant chatter worth knowing this week.",
                "draft_status": "none",
                "unsubscribe_url": "https://feedme.example/unsubscribe",
                "superhuman_url": "https://mail.superhuman.com/lieber.matt@gmail.com/thread/news-001",
                "messageIds": ["m2"],
            }
        ]

        markdown = MODULE.render_markdown(records, "Tuesday March 10, 2026", "4:42 PM", "PM")
        self.assertIn("**Feed Me** -- Feed Me rounds up hospitality culture notes", markdown)
        self.assertNotIn("**Feed Me: hospitality notes**", markdown)
        self.assertIn("[Unsubscribe](https://feedme.example/unsubscribe)", markdown)

    def test_html_uses_colored_headers_and_summary_counts(self) -> None:
        records = [
            {
                "bucket": "FYI",
                "account": "work",
                "threadId": "fyi-001",
                "sender_email": "ops@example.com",
                "sender_name": "Ops Person",
                "subject_latest": "Status update",
                "summary_latest": "Ops Person confirmed the setup is complete and no reply is needed.",
                "draft_status": "none",
                "superhuman_url": "https://mail.superhuman.com/matt@cornerbootholdings.com/thread/fyi-001",
                "messageIds": ["m3"],
            }
        ]

        html = MODULE.render_html(records, "Tuesday March 10, 2026", "4:42 PM", "PM", last_triage="2026-03-10T10:00:04-04:00")
        self.assertIn("triage-html-profile:compact_ref_v1", html)
        self.assertIn("color:#1f5fb8", html)
        self.assertIn("Run type: PM | Since 10:00 AM triage | 1 new emails", html)
        self.assertIn("1 fyi", html)


if __name__ == "__main__":
    unittest.main()
