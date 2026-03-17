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
                account="work",
                thread_id="news010",
                message_ids=["m10"],
                sender_email="flagship@news.semafor.com",
                sender_name="Semafor",
                subject_latest="Semafor Flagship",
                summary_latest="Semafor rounds up the business, media, and politics stories worth tracking this morning.",
                bucket="Newsletters",
                draft_status="not_needed",
                thread_url="https://mail.superhuman.com/matt@cornerboothholdings.com/thread/news010",
                draft_url=None,
                unsubscribe_url="https://semafor.example/unsubscribe",
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

    def _action_priority_samples(self) -> list[ThreadRecord]:
        return [
            ThreadRecord(
                account="work",
                thread_id="act-alan",
                message_ids=["a1"],
                sender_email="alan@brownbagny.com",
                sender_name="Alan Patricof",
                subject_latest="BBS diligence next steps",
                summary_latest="Alan followed up on Brown Bag diligence and needs you to keep the acquisition process moving.",
                bucket="Action Needed",
                response_needed=True,
                suggested_response="Reply to Alan with the diligence next step and timing.",
                suggested_action="Reply to Alan with the diligence next step and timing.",
                draft_status="fallback_gmail",
                thread_url="https://mail.superhuman.com/matt@cornerboothholdings.com/thread/act-alan",
                draft_url="https://mail.google.com/mail/u/matt@cornerbootholdings.com/#drafts?compose=alan1",
                accounted_reason="included",
                matched_project_name="Brown Bag Sandwich Co. Acquisition",
                matched_project_priority="P0",
            ),
            ThreadRecord(
                account="work",
                thread_id="act-darragh",
                message_ids=["a2"],
                sender_email="darragh@example.com",
                sender_name="Darragh",
                subject_latest="Invoice for PnT Park Slope",
                summary_latest="Darragh sent the latest PnT Park Slope invoice and it still needs payment processing.",
                bucket="Action Needed",
                response_needed=False,
                suggested_action="Review the invoice, confirm payment timing, and process it without drafting a reply.",
                draft_status="not_needed",
                thread_url="https://mail.superhuman.com/matt@cornerboothholdings.com/thread/act-darragh",
                accounted_reason="included",
                matched_project_name="PnT Park Slope",
                matched_project_priority="P0",
            ),
            ThreadRecord(
                account="work",
                thread_id="act-csg",
                message_ids=["a3"],
                sender_email="ops@courtstreetgrocers.com",
                sender_name="CSC",
                subject_latest="Court Street Grocers insurance item",
                summary_latest="CSC needs a decision on the Project Carroll / CSG insurance follow-up.",
                bucket="Action Needed",
                response_needed=True,
                suggested_response="Reply with the decision on the insurance item and next timing.",
                suggested_action="Reply with the decision on the insurance item and next timing.",
                draft_status="fallback_gmail",
                thread_url="https://mail.superhuman.com/matt@cornerboothholdings.com/thread/act-csg",
                draft_url="https://mail.google.com/mail/u/matt@cornerbootholdings.com/#drafts?compose=csg1",
                accounted_reason="included",
                matched_project_name="Project Carroll / CSG",
                matched_project_priority="P1",
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
                operational_note="This lives in an operational workflow rather than an email reply thread.",
                draft_status="not_needed",
                thread_url="https://mail.superhuman.com/matt@cornerboothholdings.com/thread/fyi124",
                accounted_reason="included",
            ),
        ]

    def _already_addressed_sample(self) -> list[ThreadRecord]:
        return [
            ThreadRecord(
                account="work",
                thread_id="handled-1",
                message_ids=["m10"],
                sender_email="jason@cornerbootholdings.com",
                sender_name="Jason Hershfeld",
                subject_latest="Re: Toast direct integrations",
                summary_latest="Jason Hershfeld confirmed the direct integrations are intentional and you already replied in-thread.",
                bucket="Already Addressed",
                draft_status="not_needed",
                thread_url="https://mail.superhuman.com/matt@cornerbootholdings.com/thread/handled-1",
                accounted_reason="included",
            )
        ]

    def _priority_fyi_samples(self) -> list[ThreadRecord]:
        return [
            ThreadRecord(
                account="personal",
                thread_id="fyi-daniel",
                message_ids=["m6"],
                sender_email="daniel@treble.vc",
                sender_name="Daniel Gulati",
                subject_latest="Confidential Treble Fund Update- January/February 2026",
                summary_latest="Daniel Gulati shared an investor update for Treble with portfolio performance and fund marks.",
                bucket="FYI",
                draft_status="not_needed",
                thread_url="https://mail.superhuman.com/lieber.matt@gmail.com/thread/fyi-daniel",
                accounted_reason="included",
            ),
            ThreadRecord(
                account="personal",
                thread_id="fyi-celia",
                message_ids=["m7"],
                sender_email="cmtedde@gmail.com",
                sender_name="Celia Tedde",
                subject_latest="Re: Lily Lieber BM Homework",
                summary_latest="Celia Tedde sent Lily's latest Bat Mitzvah homework and practice notes.",
                bucket="FYI",
                draft_status="not_needed",
                thread_url="https://mail.superhuman.com/lieber.matt@gmail.com/thread/fyi-celia",
                accounted_reason="included",
            ),
            ThreadRecord(
                account="work",
                thread_id="fyi-jason-drive",
                message_ids=["m8"],
                sender_email="drive-shares-dm-noreply@google.com",
                sender_name="Jason Hershfeld (via Google Drive)",
                subject_latest='Share request for "CP_575_B.pdf"',
                summary_latest="Jason Hershfeld is requesting access to a Google Drive file that Matt owns.",
                bucket="FYI",
                draft_status="not_needed",
                thread_url="https://mail.superhuman.com/matt@cornerboothholdings.com/thread/fyi-jason-drive",
                accounted_reason="included",
            ),
            ThreadRecord(
                account="work",
                thread_id="fyi-ordinary",
                message_ids=["m9"],
                sender_email="ops@example.com",
                sender_name="Ops Person",
                subject_latest="Status update",
                summary_latest="Ops Person confirmed the setup is complete and no reply is needed.",
                bucket="FYI",
                draft_status="not_needed",
                thread_url="https://mail.superhuman.com/matt@cornerboothholdings.com/thread/fyi-ordinary",
                accounted_reason="included",
            ),
        ]

    def _spam_priority_samples(self) -> list[ThreadRecord]:
        return [
            ThreadRecord(
                account="work",
                thread_id="spam-owner",
                message_ids=["s1"],
                sender_email="owner@owner.com",
                sender_name="Owner.com",
                subject_latest="New Contact Us Form Submission",
                summary_latest="Owner.com forwarded a website contact-form submission.",
                bucket="Spam / Marketing",
                draft_status="not_needed",
                thread_url="https://mail.superhuman.com/matt@cornerboothholdings.com/thread/spam-owner",
                accounted_reason="included",
            ),
            ThreadRecord(
                account="personal",
                thread_id="spam-23andme",
                message_ids=["s2"],
                sender_email="donotreply@23andme.com",
                sender_name="23andMe",
                subject_latest="Your DNA updates this month",
                summary_latest="23andMe sent a routine product update with no required action.",
                bucket="Spam / Marketing",
                draft_status="not_needed",
                thread_url="https://mail.superhuman.com/lieber.matt@gmail.com/thread/spam-23andme",
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
        self.assertLess(md.index("**Semafor**"), md.index("**Feed Me**"))
        self.assertLess(md.index("**Cora Briefs**"), md.index("**Semafor**"))
        self.assertLess(md.index("**Feed Me**"), md.index("**Generic Sender**"))

    def test_action_needed_order_prefers_project_rank_then_finance_followthrough(self) -> None:
        md = render_markdown(run_id="r1", run_type="manual", threads=self._action_priority_samples())
        self.assertLess(md.index("**BBS diligence next steps**"), md.index("**Invoice for PnT Park Slope**"))
        self.assertLess(md.index("**Invoice for PnT Park Slope**"), md.index("**Court Street Grocers insurance item**"))

    def test_fyi_entries_keep_full_detail_format(self) -> None:
        md = render_markdown(run_id="r1", run_type="manual", threads=self._fyi_samples())
        self.assertIn("**From:** Ops Person", md)
        self.assertIn("**From:** Ramp", md)
        self.assertIn("**Summary:** Ops Person confirmed the setup is complete and no reply is needed.", md)
        self.assertIn("**Summary:** Ramp says the charge needs a memo and receipt in the dashboard flow.", md)
        self.assertIn("**Operational note:** This lives in an operational workflow rather than an email reply thread.", md)
        self.assertNotIn("**Next step:**", md)

    def test_already_addressed_entries_do_not_render_action_copy(self) -> None:
        md = render_markdown(run_id="r1", run_type="manual", threads=self._already_addressed_sample())
        self.assertIn("## Already Addressed (1)", md)
        self.assertNotIn("**Next step:**", md)
        self.assertNotIn("**Operational note:**", md)

    def test_fyi_priority_order_prefers_investor_then_bat_mitzvah_then_internal_collaboration(self) -> None:
        md = render_markdown(run_id="r1", run_type="manual", threads=self._priority_fyi_samples())
        self.assertLess(md.index("**Confidential Treble Fund Update- January/February 2026**"), md.index("**Re: Lily Lieber BM Homework**"))
        self.assertLess(md.index("**Re: Lily Lieber BM Homework**"), md.index('**Share request for "CP_575_B.pdf"**'))
        self.assertLess(md.index('**Share request for "CP_575_B.pdf"**'), md.index("**Status update**"))

    def test_spam_priority_order_pushes_owner_contact_forms_to_bottom(self) -> None:
        md = render_markdown(run_id="r1", run_type="manual", threads=self._spam_priority_samples())
        self.assertLess(md.index("**23andMe**"), md.index("**Owner.com**"))

    def test_html_uses_colored_section_headers(self) -> None:
        html = render_html(run_id="r1", run_type="manual", threads=self._fyi_samples() + self._newsletter_sample())
        self.assertIn("color:#1f5fb8", html)
        self.assertIn("border-bottom:2px solid #1f5fb8", html)

    def test_validation_passes_sample(self) -> None:
        result = validate_threads(self._action_sample() + self._newsletter_sample() + self._already_addressed_sample())
        self.assertTrue(result.ok)
        self.assertEqual(result.errors, [])


if __name__ == "__main__":
    unittest.main()
