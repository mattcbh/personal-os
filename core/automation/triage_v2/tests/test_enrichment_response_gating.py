from __future__ import annotations

import unittest

from triage_v2.enrichment import EnrichmentInput, deterministic_enrichment
from triage_v2.types import MessageRecord, ThreadMessage, ThreadRecord


class EnrichmentResponseGatingTest(unittest.TestCase):
    def test_message_directed_to_someone_else_becomes_monitoring_without_draft(self) -> None:
        item = ThreadRecord(
            account="work",
            thread_id="otter-1",
            message_ids=["m1"],
            sender_email="jason@restaurant.com",
            sender_name="Jason Hershfeld",
            subject_latest="Re: Pies 'n' Thighs - Park Slope / Owner.com Onboarding",
            summary_latest="Jason Hershfeld says the Otter setup is blocked before opening day.",
            bucket="Action Needed",
            thread_url="https://mail.superhuman.com/matt@cornerboothholdings.com/thread/otter-1",
        )
        latest_message = ThreadMessage(
            account="work",
            thread_id="otter-1",
            message_id="m1",
            received_at="2026-03-10T10:00:00Z",
            sender_email="jason@restaurant.com",
            sender_name="Jason Hershfeld",
            subject="Re: Pies 'n' Thighs - Park Slope / Owner.com Onboarding",
            body_text=(
                "Hi Jack,\n\n"
                "GBP and Toast are set up, but Otter still shows subscription required instead of ADD NOW. "
                "That is stalling the integration ahead of the March 21 opening.\n"
            ),
        )

        latest_record = MessageRecord(
            message_id="m1",
            account="work",
            thread_id="otter-1",
            received_at="2026-03-10T10:00:00Z",
            sender_email=item.sender_email,
            sender_name=item.sender_name,
            subject=item.subject_latest,
            snippet="Otter shows subscription required and the setup is stalled before opening day.",
            body_preview=latest_message.body_text,
        )

        result = deterministic_enrichment(
            EnrichmentInput(
                item=item,
                latest_message=latest_record,
                thread_messages=[latest_message],
                project=None,
            )
        )

        self.assertEqual(result.bucket_hint, "Monitoring")
        self.assertFalse(result.response_needed)
        self.assertEqual(result.suggested_response, "")
        self.assertIn("blocker", result.suggested_action.lower())
        self.assertEqual(result.operational_note, "")

    def test_clear_offline_signature_work_stays_action_needed_without_reply(self) -> None:
        item = ThreadRecord(
            account="work",
            thread_id="invoice-1",
            message_ids=["m2"],
            sender_email="darragh@example.com",
            sender_name="Darragh",
            subject_latest="PnT Park Slope signature required",
            summary_latest="Darragh sent a signature-required document for PnT Park Slope.",
            bucket="Action Needed",
            thread_url="https://mail.superhuman.com/matt@cornerboothholdings.com/thread/invoice-1",
        )
        latest_message = ThreadMessage(
            account="work",
            thread_id="invoice-1",
            message_id="m2",
            received_at="2026-03-10T11:00:00Z",
            sender_email="darragh@example.com",
            sender_name="Darragh",
            subject="PnT Park Slope signature required",
            body_text=(
                "The attached agreement is ready. Signature required before we can release the order."
            ),
        )

        latest_record = MessageRecord(
            message_id="m2",
            account="work",
            thread_id="invoice-1",
            received_at="2026-03-10T11:00:00Z",
            sender_email=item.sender_email,
            sender_name=item.sender_name,
            subject=item.subject_latest,
            snippet="The agreement is attached and signature is required before release.",
            body_preview=latest_message.body_text,
        )

        result = deterministic_enrichment(
            EnrichmentInput(
                item=item,
                latest_message=latest_record,
                thread_messages=[latest_message],
                project=None,
            )
        )

        self.assertEqual(result.bucket_hint, "Action Needed")
        self.assertFalse(result.response_needed)
        self.assertEqual(result.suggested_response, "")
        self.assertIn("sign", result.suggested_action.lower())
        self.assertEqual(result.operational_note, "")


if __name__ == "__main__":
    unittest.main()
