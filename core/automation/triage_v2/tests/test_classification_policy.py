from __future__ import annotations

import unittest

from triage_v2.classification import classify_bucket
from triage_v2.types import MessageRecord


def _message(
    *,
    sender_email: str,
    sender_name: str,
    subject: str,
    snippet: str,
    body_preview: str = "",
    list_unsubscribe: str | None = None,
) -> MessageRecord:
    return MessageRecord(
        message_id="m1",
        account="work",
        thread_id="t1",
        received_at="2026-03-10T10:00:00Z",
        sender_email=sender_email,
        sender_name=sender_name,
        subject=subject,
        snippet=snippet,
        body_preview=body_preview,
        list_unsubscribe=list_unsubscribe,
        metadata={},
    )


class ClassificationPolicyTest(unittest.TestCase):
    def test_cora_briefs_is_newsletter(self) -> None:
        bucket = classify_bucket(
            _message(
                sender_email="daily@corabriefs.com",
                sender_name="Cora Briefs",
                subject="Morning Brief",
                snippet="Top items to watch this morning.",
                list_unsubscribe="https://cora.example/unsub",
            )
        )
        self.assertEqual(bucket, "Newsletters")

    def test_ramp_is_forced_to_fyi(self) -> None:
        bucket = classify_bucket(
            _message(
                sender_email="alerts@ramp.com",
                sender_name="Ramp",
                subject="Action required: transaction declined",
                snippet="Your card transaction was declined.",
            )
        )
        self.assertEqual(bucket, "FYI")

    def test_promotional_and_digest_senders_route_to_spam(self) -> None:
        cases = [
            ("messages-noreply@linkedin.com", "LinkedIn", "You have 6 pending invitations", "Birthday nudge and search appearances"),
            ("no-reply@amazon.com", "Amazon", "Leave a product review", "Share feedback for a recent order"),
            ("noreply@compass.com", "Compass", "2 new listings", "Saved search update"),
            ("updates@pef.xyz", "PEF", "Topic groups are moving to WhatsApp", "Community digest"),
            ("hello@doublegood.com", "Double Good", "New product update", "Promotional launch"),
            ("merchants@grubhub.com", "Grubhub", "40% off", "First-time user promo"),
            ("register@squareup.com", "Square", "Deposit notice", "Routine payout notification"),
        ]
        for sender_email, sender_name, subject, snippet in cases:
            with self.subTest(sender=sender_email):
                bucket = classify_bucket(
                    _message(
                        sender_email=sender_email,
                        sender_name=sender_name,
                        subject=subject,
                        snippet=snippet,
                        list_unsubscribe="https://example.com/unsub",
                    )
                )
                self.assertEqual(bucket, "Spam / Marketing")

    def test_editorial_sender_stays_newsletter(self) -> None:
        bucket = classify_bucket(
            _message(
                sender_email="newsletter@om.co",
                sender_name="On my Om",
                subject="On my Om: today's post",
                snippet="Om Malik writes about financing pressure in AI infrastructure.",
                list_unsubscribe="https://example.com/unsub",
            )
        )
        self.assertEqual(bucket, "Newsletters")

    def test_semafor_is_classified_as_newsletter(self) -> None:
        bucket = classify_bucket(
            _message(
                sender_email="flagship@news.semafor.com",
                sender_name="Semafor",
                subject="Semafor Flagship: markets and media",
                snippet="Semafor rounds up the morning's business and political signals.",
                list_unsubscribe="https://example.com/unsub",
            )
        )
        self.assertEqual(bucket, "Newsletters")

    def test_unknown_substack_sender_defaults_to_newsletter(self) -> None:
        bucket = classify_bucket(
            _message(
                sender_email="reed@substack.com",
                sender_name="Reed MacNaughton",
                subject="Largest Freddy's operator makes another buy",
                snippet="A newsletter write-up about another restaurant acquisition.",
                list_unsubscribe="https://example.com/unsub",
            )
        )
        self.assertEqual(bucket, "Newsletters")

    def test_hotel_feedback_survey_routes_to_spam(self) -> None:
        bucket = classify_bucket(
            _message(
                sender_email="no-reply@stay.examplehotel.com",
                sender_name="Example Hotel",
                subject="How was your stay at Example Hotel?",
                snippet="Take a minute to share your feedback about your recent stay.",
                body_preview="Complete our survey and let us know how we did during your visit.",
                list_unsubscribe="https://example.com/unsub",
            )
        )
        self.assertEqual(bucket, "Spam / Marketing")

    def test_headway_feedback_survey_routes_to_spam(self) -> None:
        bucket = classify_bucket(
            _message(
                sender_email="hello@updates.headway.co",
                sender_name="Headway",
                subject="How did we do?",
                snippet="Share feedback on your recent Headway experience.",
                body_preview="Take our survey and tell us how we did.",
                list_unsubscribe="https://example.com/unsub",
            )
        )
        self.assertEqual(bucket, "Spam / Marketing")

    def test_cold_pitch_routes_to_spam(self) -> None:
        bucket = classify_bucket(
            _message(
                sender_email="landon@example.com",
                sender_name="Landon Davis",
                subject="Website Contact Us submission",
                snippet="Custom PET cups with a 3-week turnaround for your stores.",
                body_preview="Sent via website contact us. We would love to help with custom PET cups.",
            )
        )
        self.assertEqual(bucket, "Spam / Marketing")

    def test_owner_contact_form_subject_override_routes_to_spam(self) -> None:
        bucket = classify_bucket(
            _message(
                sender_email="team@mg.owner.com",
                sender_name="Owner.com",
                subject="New Contact Us Form Submission",
                snippet="Someone asked whether the spicy molasses cookie contains nuts or soy.",
            )
        )
        self.assertEqual(bucket, "Spam / Marketing")

    def test_owner_reviews_routes_to_monitoring(self) -> None:
        bucket = classify_bucket(
            _message(
                sender_email="team@mg.owner.com",
                sender_name="Owner Reviews",
                subject="[Williamsburg] — New Customer Feedback From Owner",
                snippet="Owner.com sent a new 1-star customer feedback alert for Williamsburg.",
            )
        )
        self.assertEqual(bucket, "Monitoring")

    def test_owner_jobs_routes_to_spam(self) -> None:
        bucket = classify_bucket(
            _message(
                sender_email="team@mg.owner.com",
                sender_name="Owner Jobs",
                subject="New Job Application from samuel greene",
                snippet="A new job application was submitted for the server opening.",
            )
        )
        self.assertEqual(bucket, "Spam / Marketing")

    def test_23andme_sender_override_routes_to_spam(self) -> None:
        bucket = classify_bucket(
            _message(
                sender_email="donotreply@23andme.com",
                sender_name="23andMe",
                subject="Your DNA updates this month",
                snippet="Spring product roundup and genetics learning hub updates.",
                list_unsubscribe="https://23andme.example/unsub",
            )
        )
        self.assertEqual(bucket, "Spam / Marketing")

    def test_human_toast_vendor_reply_is_not_spam(self) -> None:
        bucket = classify_bucket(
            _message(
                sender_email="tara.fdaee@toasttab.com",
                sender_name="Tara Fdaee",
                subject="Re: Pies 'n' Thighs Toast Invoice",
                snippet="Here is the invoice detail from the thread you and Jason asked about.",
                body_preview="Sharing the invoice detail from the existing thread. No action needed right now.",
            )
        )
        self.assertEqual(bucket, "FYI")

    def test_human_marginedge_support_update_is_fyi(self) -> None:
        bucket = classify_bucket(
            _message(
                sender_email="support@marginedge.com",
                sender_name="MarginEdge Help-Bot",
                subject="[MarginEdge] Re: Help-Bot Support Request",
                snippet="Following up on the existing support request with a status update.",
                body_preview="This is an update on the open support request. No action is required from you right now.",
            )
        )
        self.assertEqual(bucket, "FYI")

    def test_park_slope_living_media_followup_is_fyi(self) -> None:
        bucket = classify_bucket(
            _message(
                sender_email="editor@parkslopeliving.com",
                sender_name="Park Slope Living",
                subject="Re: Media Opp: Park Slope Living // Pies Opening Coverage",
                snippet="Circling back with coverage context for the opening feature.",
                body_preview="Sharing background for the coverage thread. No action needed from Matt right now.",
            )
        )
        self.assertEqual(bucket, "FYI")

    def test_park_slope_living_invitation_is_fyi(self) -> None:
        bucket = classify_bucket(
            _message(
                sender_email="editor@parkslopeliving.com",
                sender_name="Park Slope Living",
                subject="Invitation: Park Slope Living x Sarah Sanneh Interview",
                snippet="Sharing details for the upcoming interview and invitation.",
                body_preview="Passing along interview details for the thread. No action is required from Matt right now.",
            )
        )
        self.assertEqual(bucket, "FYI")

    def test_shot_list_without_direct_ask_is_fyi(self) -> None:
        bucket = classify_bucket(
            _message(
                sender_email="photos@piesproject.com",
                sender_name="Photo Team",
                subject="Pies 'n' Thighs Shot List // March 5th",
                snippet="Sharing the final shot list for the March 5th session.",
                body_preview="Here is the final shot list for reference. No reply needed from Matt.",
            )
        )
        self.assertEqual(bucket, "FYI")

    def test_personal_noise_defaults_to_fyi(self) -> None:
        cases = [
            (
                "statements@fidelity.com",
                "Fidelity",
                "Your monthly statement is ready",
                "Your latest account statement is available online.",
            ),
            (
                "results@lenoxhillradiology.com",
                "Lenox Hill Radiology",
                "Your results are available",
                "Your imaging results are available in the portal.",
            ),
        ]
        for sender_email, sender_name, subject, snippet in cases:
            with self.subTest(sender=sender_email):
                bucket = classify_bucket(
                    _message(
                        sender_email=sender_email,
                        sender_name=sender_name,
                        subject=subject,
                        snippet=snippet,
                    )
                )
                self.assertEqual(bucket, "FYI")

    def test_google_drive_share_from_internal_colleague_stays_fyi(self) -> None:
        bucket = classify_bucket(
            _message(
                sender_email="drive-shares-dm-noreply@google.com",
                sender_name="Jason Hershfeld (via Google Drive)",
                subject='Share request for "CP_575_B.pdf"',
                snippet="Jason Hershfeld (jason@cornerboothholdings.com) is requesting access to CP_575_B.pdf.",
                body_preview="Jason Hershfeld (jason@cornerboothholdings.com) is requesting access to the file in Google Drive.",
            )
        )
        self.assertEqual(bucket, "FYI")


if __name__ == "__main__":
    unittest.main()
