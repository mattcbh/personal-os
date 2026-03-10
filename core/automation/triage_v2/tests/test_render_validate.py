from __future__ import annotations

import unittest

from triage_v2.render import render_html, render_markdown
from triage_v2.types import ThreadRecord
from triage_v2.validate import validate_threads


class RenderValidateTest(unittest.TestCase):
    def _action_sample(self) -> list[ThreadRecord]:
        return [
            ThreadRecord(
                account="work",
                thread_id="abc123",
                message_ids=["m1"],
                sender_email="person@example.com",
                sender_name="Person",
                subject_latest="Please approve",
                summary_latest="Person sent a document that needs your approval today.",
                bucket="Action Needed",
                response_needed=True,
                suggested_response="Tell Person whether you approve it and confirm timing.",
                suggested_action="Reply to Person with your decision and confirm timing.",
                draft_status="fallback_gmail",
                thread_url="https://mail.superhuman.com/matt@cornerboothholdings.com/thread/abc123",
                draft_url="https://mail.google.com/mail/u/matt@cornerboothholdings.com/#drafts?compose=r123",
                unsubscribe_url=None,
                accounted_reason="included",
                draft_authoring_mode="fallback_deterministic",
                draft_context_status="stale",
                draft_authoring_error="project refresh stale",
            )
        ]

    def _newsletter_sample(self) -> list[ThreadRecord]:
        return [
            ThreadRecord(
                account="work",
                thread_id="news001",
                message_ids=["m0"],
                sender_email="daily@corabriefs.com",
                sender_name="Cora Briefs",
                subject_latest="Morning Brief",
                summary_latest="Cora Briefs rounds up the work items to watch this morning.",
                bucket="Newsletters",
                draft_status="not_needed",
                thread_url="https://mail.superhuman.com/matt@cornerboothholdings.com/thread/news001",
                draft_url=None,
                unsubscribe_url="https://cora.example/unsubscribe",
                accounted_reason="included",
            ),
            ThreadRecord(
                account="personal",
                thread_id="news123",
                message_ids=["m2"],
                sender_email="emilysundberg@substack.com",
                sender_name="Feed Me",
                subject_latest="Feed Me: hospitality notes",
                summary_latest="Feed Me rounds up hospitality culture notes and restaurant chatter worth knowing this week.",
                bucket="Newsletters",
                draft_status="not_needed",
                thread_url="https://mail.superhuman.com/lieber.matt@gmail.com/thread/news123",
                draft_url=None,
                unsubscribe_url="https://feedme.example/unsubscribe",
                accounted_reason="included",
            ),
            ThreadRecord(
                account="personal",
                thread_id="news999",
                message_ids=["m3"],
                sender_email="newsletter@example.com",
                sender_name="Generic Sender",
                subject_latest="Weekly Product Update",
                summary_latest="Generic Sender rounds up product updates and feature launches from this week.",
                bucket="Newsletters",
                draft_status="not_needed",
                thread_url="https://mail.superhuman.com/lieber.matt@gmail.com/thread/news999",
                draft_url=None,
                unsubscribe_url="https://generic.example/unsubscribe",
                accounted_reason="included",
            ),
        ]

    def _fyi_samples(self) -> list[ThreadRecord]:
        return [
            ThreadRecord(
                account="work",
                thread_id="fyi123",
                message_ids=["m4"],
                sender_email="ops@example.com",
                sender_name="Ops Person",
                subject_latest="Status update",
                summary_latest="Ops Person confirmed the setup is complete and no reply is needed.",
                bucket="FYI",
                draft_status="not_needed",
                thread_url="https://mail.superhuman.com/matt@cornerboothholdings.com/thread/fyi123",
                accounted_reason="included",
            ),
            ThreadRecord(
                account="work",
                thread_id="fyi124",
                message_ids=["m5"],
                sender_email="ramp@ramp.com",
                sender_name="Ramp",
                subject_latest="Memo and receipt needed",
                summary_latest="Ramp says the charge needs a memo and receipt in the dashboard flow.",
                bucket="FYI",
                suggested_action="Upload the receipt and memo through Ramp; no email draft is needed.",
                draft_status="not_needed",
                thread_url="https://mail.superhuman.com/matt@cornerboothholdings.com/thread/fyi124",
                accounted_reason="included",
            ),
        ]

    def test_markdown_contains_gmail_draft_link_and_recommended_response(self) -> None:
        md = render_markdown(run_id="r1", run_type="manual", threads=self._action_sample())
        self.assertIn("Draft ready in Gmail", md)
        self.assertIn("**Recommended response:**", md)
        self.assertIn("**Draft note:** deterministic fallback, project refresh stale.", md)
        self.assertIn("mail.google.com", md)
        self.assertIn("**From:** Person", md)

    def test_newsletter_line_uses_summary_not_subject_and_orders_cora_first(self) -> None:
        md = render_markdown(run_id="r1", run_type="manual", threads=self._newsletter_sample())
        self.assertIn("Feed Me rounds up hospitality culture notes", md)
        self.assertNotIn("**Feed Me: hospitality notes** --", md)
        self.assertLess(md.index("**Cora Briefs**"), md.index("**Feed Me**"))
        self.assertLess(md.index("**Feed Me**"), md.index("**Generic Sender**"))

    def test_fyi_entries_keep_full_detail_format(self) -> None:
        md = render_markdown(run_id="r1", run_type="manual", threads=self._fyi_samples())
        self.assertIn("**From:** Ops Person", md)
        self.assertIn("**From:** Ramp", md)
        self.assertIn("**Summary:** Ops Person confirmed the setup is complete and no reply is needed.", md)
        self.assertIn("**Summary:** Ramp says the charge needs a memo and receipt in the dashboard flow.", md)
        self.assertIn("**Next step:** Upload the receipt and memo through Ramp; no email draft is needed.", md)

    def test_html_uses_colored_section_headers(self) -> None:
        html = render_html(run_id="r1", run_type="manual", threads=self._fyi_samples() + self._newsletter_sample())
        self.assertIn("color:#1f5fb8", html)
        self.assertIn("border-bottom:2px solid #1f5fb8", html)

    def test_validation_passes_sample(self) -> None:
        result = validate_threads(self._action_sample() + self._newsletter_sample())
        self.assertTrue(result.ok)
        self.assertEqual(result.errors, [])


if __name__ == "__main__":
    unittest.main()
