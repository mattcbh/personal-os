import unittest

from core.automation.daily_digest_context import (
    DigestOrder,
    diff_groupings,
    extract_community_candidates,
    is_low_signal_text,
    order_identity_label,
)


class DailyDigestContextTests(unittest.TestCase):
    def test_low_signal_filter_drops_short_acks(self):
        self.assertTrue(is_low_signal_text("ok"))
        self.assertTrue(is_low_signal_text("Nice"))
        self.assertFalse(is_low_signal_text("Electrician available in Williamsburg if anyone needs one."))

    def test_diff_groupings_sorts_by_absolute_delta(self):
        current = {"online": 300.0, "catering": 500.0}
        prior = {"online": 100.0, "catering": 200.0, "doordash": 75.0}
        rows = diff_groupings(current, prior)
        self.assertEqual(rows[0]["key"], "catering")
        self.assertEqual(rows[0]["delta"], 300.0)
        self.assertEqual(rows[1]["key"], "online")
        self.assertEqual(rows[1]["delta"], 200.0)

    def test_order_identity_prefers_name_then_email_then_phone(self):
        order = DigestOrder(
            toast_order_id="1",
            order_date="2026-03-05",
            net_sales=100.0,
            channel="catering",
            channel_group="catering",
            order_source="ezcater",
            daypart="lunch",
            customer_name="Acme Corp",
            customer_email="orders@acme.com",
            customer_phone="555-1111",
            is_catering=True,
        )
        self.assertEqual(order_identity_label(order), "Acme Corp")

    def test_community_intel_filters_watchlist_and_dedupes(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            events_file = tmp / "events.jsonl"
            watchlist_file = tmp / "watchlist.json"
            watchlist_file.write_text('{"chat_ids":["chat-1"]}', encoding="utf-8")
            events_file.write_text(
                "\n".join(
                    [
                        '{"event_id":"a","platform":"beeper","network":"whatsapp","timestamp":"2026-03-06T09:00:00Z","chat_id":"chat-1","chat_title":"TRN","author":"A","text":"Need a new grease trap vendor in Brooklyn."}',
                        '{"event_id":"a","platform":"beeper","network":"whatsapp","timestamp":"2026-03-06T09:00:00Z","chat_id":"chat-1","chat_title":"TRN","author":"A","text":"Need a new grease trap vendor in Brooklyn."}',
                        '{"event_id":"b","platform":"beeper","network":"whatsapp","timestamp":"2026-03-06T09:05:00Z","chat_id":"chat-1","chat_title":"TRN","author":"B","text":"ok"}',
                        '{"event_id":"c","platform":"beeper","network":"whatsapp","timestamp":"2026-03-06T09:10:00Z","chat_id":"chat-2","chat_title":"Other","author":"C","text":"Off watchlist"}',
                    ]
                ),
                encoding="utf-8",
            )

            payload, _ = extract_community_candidates(
                events_file=events_file,
                watchlist_file=watchlist_file,
                date_iso="2026-03-06",
            )

            self.assertEqual(payload["candidate_count"], 1)
            self.assertEqual(payload["candidates"][0]["event_id"], "a")


if __name__ == "__main__":
    unittest.main()
