from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from triage_v2.providers.gmail_api import GmailApiClient


class FakeGmailApiClient(GmailApiClient):
    def __init__(self, token_path: Path, response: dict[str, object]) -> None:
        self._response = response
        super().__init__(token_path)

    def _request_json(self, method: str, path: str, *, params=None, body=None, retry: int = 4):  # type: ignore[override]
        return self._response


class GmailApiClientTest(unittest.TestCase):
    def test_get_message_metadata_parses_metadata_response(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            token_path = Path(tmpdir) / "token.json"
            token_path.write_text(
                json.dumps({"token": "test-token", "account": "matt@example.com"}) + "\n",
                encoding="utf-8",
            )
            client = FakeGmailApiClient(
                token_path,
                {
                    "id": "msg-123",
                    "threadId": "thread-456",
                    "internalDate": "1772791200000",
                    "labelIds": ["INBOX", "UNREAD"],
                    "snippet": "Please approve this invoice.",
                    "payload": {
                        "headers": [
                            {"name": "From", "value": "Client Person <client@example.com>"},
                            {"name": "Subject", "value": "Invoice approval"},
                            {"name": "List-Unsubscribe", "value": "<https://unsubscribe.example.com/x>"},
                        ]
                    },
                },
            )

            meta = client.get_message_metadata("msg-123")

            self.assertIsNotNone(meta)
            assert meta is not None
            self.assertEqual(meta["message_id"], "msg-123")
            self.assertEqual(meta["thread_id"], "thread-456")
            self.assertEqual(meta["sender_email"], "client@example.com")
            self.assertEqual(meta["sender_name"], "Client Person")
            self.assertEqual(meta["subject"], "Invoice approval")
            self.assertEqual(meta["body_preview"], "Please approve this invoice.")
            self.assertEqual(meta["metadata"]["gmail_label_ids"], ["INBOX", "UNREAD"])


if __name__ == "__main__":
    unittest.main()
