#!/usr/bin/env python3
"""Shared Toast API helpers for ETL scripts."""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import date, datetime, timedelta, timezone
from typing import Iterable

import requests


DEFAULT_LOCATION_ID = "kent_ave"
DEFAULT_AUTH_TIMEOUT = 30
DEFAULT_REQUEST_TIMEOUT = 90


def build_machine_client_login_payload(client_id: str, client_secret: str) -> dict[str, str]:
    """Return the standard Toast machine-client login payload."""
    return {
        "clientId": client_id,
        "clientSecret": client_secret,
        "userAccessType": "TOAST_MACHINE_CLIENT",
    }


def get_machine_client_token(
    session: requests.Session,
    api_host: str,
    client_id: str,
    client_secret: str,
) -> str:
    """Authenticate against a Toast API host and return an access token."""
    resp = session.post(
        f"{api_host}/authentication/v1/authentication/login",
        json=build_machine_client_login_payload(client_id, client_secret),
        timeout=DEFAULT_AUTH_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()["token"]["accessToken"]


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def orders_headers(token: str, restaurant_guid: str) -> dict[str, str]:
    headers = auth_headers(token)
    headers["Toast-Restaurant-External-ID"] = restaurant_guid
    return headers


def _retry_wait_seconds(resp: requests.Response, attempt: int) -> float:
    retry_after = resp.headers.get("Retry-After")
    if retry_after:
        try:
            return max(float(retry_after), 0.0)
        except ValueError:
            pass

    reset_epoch = resp.headers.get("X-Toast-RateLimit-Reset")
    if reset_epoch:
        try:
            reset_dt = datetime.fromtimestamp(float(reset_epoch), tz=timezone.utc)
            now = datetime.now(timezone.utc)
            return max((reset_dt - now).total_seconds(), 0.0)
        except ValueError:
            pass

    return float(2**attempt)


def request_with_retry(
    session: requests.Session,
    method: str,
    url: str,
    *,
    max_retries: int = 4,
    output_stream=None,
    **kwargs,
) -> requests.Response:
    """Make an HTTP request with retry on timeout, 429, and 5xx responses."""
    kwargs.setdefault("timeout", DEFAULT_REQUEST_TIMEOUT)
    stream = output_stream or sys.stderr

    for attempt in range(max_retries):
        try:
            resp = getattr(session, method)(url, **kwargs)
        except requests.exceptions.Timeout:
            if attempt >= max_retries - 1:
                raise
            wait = float(2**attempt)
            print(
                f"    Timeout calling {url}; retrying in {wait:.1f}s "
                f"(attempt {attempt + 2}/{max_retries})...",
                file=stream,
            )
            time.sleep(wait)
            continue

        if resp.status_code in {429, 500, 502, 503, 504} and attempt < max_retries - 1:
            wait = _retry_wait_seconds(resp, attempt)
            print(
                f"    HTTP {resp.status_code} calling {url}; retrying in {wait:.1f}s "
                f"(attempt {attempt + 2}/{max_retries})...",
                file=stream,
            )
            time.sleep(wait)
            continue

        return resp

    return resp


def load_restaurant_map_from_env(
    environ: dict[str, str] | None = None,
    *,
    mapping_key: str = "TOAST_RESTAURANT_MAP_JSON",
    default_guid_key: str = "TOAST_RESTAURANT_GUID",
    default_location_id: str = DEFAULT_LOCATION_ID,
) -> dict[str, str]:
    """Load Toast restaurant GUID -> warehouse location_id mappings from env."""
    env = environ or os.environ
    raw_mapping = env.get(mapping_key, "").strip()
    mapping: dict[str, str] = {}

    if raw_mapping:
        try:
            parsed = json.loads(raw_mapping)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{mapping_key} must be valid JSON: {exc}") from exc

        if not isinstance(parsed, dict) or not parsed:
            raise ValueError(f"{mapping_key} must be a non-empty JSON object")

        for restaurant_guid, location_id in parsed.items():
            if not isinstance(restaurant_guid, str) or not restaurant_guid.strip():
                raise ValueError(f"{mapping_key} contains a blank restaurant GUID")
            if not isinstance(location_id, str) or not location_id.strip():
                raise ValueError(
                    f"{mapping_key} contains an invalid location_id for {restaurant_guid}"
                )
            mapping[restaurant_guid.strip()] = location_id.strip()

    if not mapping:
        default_guid = env.get(default_guid_key, "").strip()
        if default_guid:
            mapping[default_guid] = default_location_id

    return mapping


def resolve_location_id(
    restaurant_guid: str | None,
    restaurant_map: dict[str, str],
    *,
    default_location_id: str | None = None,
) -> str:
    """Resolve a Toast restaurant GUID to the warehouse location_id."""
    guid = (restaurant_guid or "").strip()
    if guid and guid in restaurant_map:
        return restaurant_map[guid]
    if default_location_id:
        return default_location_id
    if len(restaurant_map) == 1:
        return next(iter(restaurant_map.values()))
    raise KeyError(f"No location_id mapping configured for restaurant GUID: {guid or '<blank>'}")


def parse_iso_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def format_compact_date(value: date) -> str:
    return value.strftime("%Y%m%d")


def iter_date_windows(start_date: date, end_date: date, window_days: int) -> Iterable[tuple[date, date]]:
    """Yield inclusive date windows between start_date and end_date."""
    if window_days <= 0:
        raise ValueError("window_days must be positive")
    if start_date > end_date:
        raise ValueError("start_date must be on or before end_date")

    current = start_date
    while current <= end_date:
        window_end = min(current + timedelta(days=window_days - 1), end_date)
        yield current, window_end
        current = window_end + timedelta(days=1)
