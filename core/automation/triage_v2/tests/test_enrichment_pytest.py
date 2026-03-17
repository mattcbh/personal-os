from __future__ import annotations

from triage_v2.enrichment import EnrichmentInput, apply_bucket_hint, deterministic_enrichment
from triage_v2.types import MessageRecord, ThreadRecord


def _thread(
    *,
    bucket: str,
    sender_name: str,
    sender_email: str,
    subject: str,
    snippet: str,
) -> EnrichmentInput:
    item = ThreadRecord(
        account="personal",
        thread_id="t1",
        message_ids=["m1"],
        sender_email=sender_email,
        sender_name=sender_name,
        subject_latest=subject,
        summary_latest=snippet,
        bucket=bucket,
        thread_url="https://mail.superhuman.com/lieber.matt@gmail.com/thread/t1",
    )
    message = MessageRecord(
        message_id="m1",
        account="personal",
        thread_id="t1",
        received_at="2026-03-06T01:00:00Z",
        sender_email=sender_email,
        sender_name=sender_name,
        subject=subject,
        snippet=snippet,
        body_preview=snippet,
    )
    return EnrichmentInput(item=item, latest_message=message, thread_messages=[], project=None)


def test_deterministic_enrichment_downgrades_transactional_confirmation():
    row = _thread(
        bucket="Action Needed",
        sender_name="E-ZPass New York Customer Service",
        sender_email="customerservice@e-zpassny.com",
        subject="E-ZPass NY: Bank Account Payment Confirmation",
        snippet="A payment of $48.71 was applied to your account and your balance is $0.00.",
    )

    enrichment = deterministic_enrichment(row)

    assert enrichment.response_needed is False
    assert apply_bucket_hint(row.item.bucket, enrichment) == "FYI"
    assert "e-zpass" in enrichment.summary_latest.lower()
    assert enrichment.suggested_action == ""
    assert enrichment.operational_note == ""


def test_deterministic_enrichment_keeps_sender_in_newsletter_summary():
    row = _thread(
        bucket="Newsletters",
        sender_name="Feed Me",
        sender_email="emilysundberg@substack.com",
        subject="Feed Me: hospitality notes",
        snippet="Rounds up hospitality culture news and restaurant chatter worth knowing this week.",
    )

    enrichment = deterministic_enrichment(row)

    assert enrichment.response_needed is False
    assert enrichment.summary_latest.lower().startswith("feed me")
    assert enrichment.bucket_hint == "Newsletters"
    assert enrichment.operational_note == ""
