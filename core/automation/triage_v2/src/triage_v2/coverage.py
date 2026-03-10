from __future__ import annotations

from collections import Counter

from triage_v2.types import CoverageReport, ThreadRecord


def build_coverage_report(expected_message_ids: list[str], threads: list[ThreadRecord]) -> CoverageReport:
    expected = sorted(set(expected_message_ids))
    accounted: list[str] = []
    thread_keys: list[str] = []

    for item in threads:
        thread_keys.append(f"{item.account}:{item.thread_id}")
        accounted.extend(item.message_ids)

    accounted_unique = sorted(set(accounted))
    missing = sorted(set(expected) - set(accounted_unique))
    key_counts = Counter(thread_keys)
    duplicates = sorted([k for k, count in key_counts.items() if count > 1])

    return CoverageReport(
        expected_message_ids=expected,
        accounted_message_ids=accounted_unique,
        missing_message_ids=missing,
        duplicate_thread_keys=duplicates,
    )
