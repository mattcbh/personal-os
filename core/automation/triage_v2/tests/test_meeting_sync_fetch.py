from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


MODULE_PATH = (
    Path(__file__).resolve().parents[2] / "meeting-sync-fetch.py"
)
SPEC = importlib.util.spec_from_file_location("meeting_sync_fetch", MODULE_PATH)
assert SPEC is not None
assert SPEC.loader is not None
meeting_sync_fetch = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(meeting_sync_fetch)


class MeetingSyncFetchTest(unittest.TestCase):
    def test_parse_iso_datetime_accepts_calendar_dict_shape(self) -> None:
        dt = meeting_sync_fetch.parse_iso_datetime(
            {"dateTime": "2026-03-06T10:00:00+00:00", "timeZone": "America/New_York"}
        )
        self.assertEqual(dt.isoformat(), "2026-03-06T10:00:00+00:00")

    def test_format_meeting_date_accepts_calendar_dict_shape(self) -> None:
        date_part, time_part = meeting_sync_fetch.format_meeting_date(
            {"dateTime": "2026-03-06T15:30:00+00:00", "timeZone": "America/New_York"}
        )
        self.assertEqual(date_part, "2026-03-06")
        self.assertEqual(time_part, "10:30")


if __name__ == "__main__":
    unittest.main()
