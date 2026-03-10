from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class RunType(str, Enum):
    AM = "am"
    PM = "pm"
    MANUAL = "manual"


class RunStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    FAILED = "failed"
    SUCCEEDED = "succeeded"


class DraftStatus(str, Enum):
    READY = "ready"
    FAILED = "failed"
    FALLBACK_GMAIL = "fallback_gmail"
    NOT_NEEDED = "not_needed"


class Bucket(str, Enum):
    ACTION_NEEDED = "Action Needed"
    ALREADY_ADDRESSED = "Already Addressed"
    MONITORING = "Monitoring"
    FYI = "FYI"
    NEWSLETTERS = "Newsletters"
    SPAM_MARKETING = "Spam / Marketing"


SECTION_ORDER = [
    Bucket.ACTION_NEEDED.value,
    Bucket.ALREADY_ADDRESSED.value,
    Bucket.MONITORING.value,
    Bucket.FYI.value,
    Bucket.NEWSLETTERS.value,
    Bucket.SPAM_MARKETING.value,
]


@dataclass
class MessageRecord:
    message_id: str
    account: str
    thread_id: str
    received_at: str
    sender_email: str
    sender_name: str
    subject: str
    snippet: str
    body_preview: str = ""
    list_unsubscribe: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ThreadMessage:
    account: str
    thread_id: str
    message_id: str
    received_at: str
    sender_email: str
    sender_name: str
    subject: str
    body_text: str


@dataclass
class ThreadRecord:
    account: str
    thread_id: str
    message_ids: list[str]
    sender_email: str
    sender_name: str
    subject_latest: str
    summary_latest: str
    bucket: str
    response_needed: bool = False
    suggested_response: str = ""
    suggested_action: str = ""
    monitoring_owner: str = ""
    monitoring_deliverable: str = ""
    monitoring_deadline: str = ""
    draft_status: str = DraftStatus.NOT_NEEDED.value
    thread_url: str = ""
    draft_url: str | None = None
    unsubscribe_url: str | None = None
    accounted_reason: str = "included"
    draft_authoring_mode: str = "deterministic"
    draft_context_status: str = "unmatched"
    draft_authoring_error: str | None = None
    matched_project_name: str = ""
    matched_project_priority: str = ""


@dataclass
class CoverageReport:
    expected_message_ids: list[str]
    accounted_message_ids: list[str]
    missing_message_ids: list[str]
    duplicate_thread_keys: list[str]

    @property
    def expected_count(self) -> int:
        return len(self.expected_message_ids)

    @property
    def accounted_count(self) -> int:
        return len(self.accounted_message_ids)

    @property
    def missing_count(self) -> int:
        return len(self.missing_message_ids)

    @property
    def duplicate_count(self) -> int:
        return len(self.duplicate_thread_keys)

    @property
    def passed(self) -> bool:
        return self.missing_count == 0 and self.duplicate_count == 0
