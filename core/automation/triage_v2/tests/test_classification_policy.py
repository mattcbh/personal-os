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


if __name__ == "__main__":
    unittest.main()
