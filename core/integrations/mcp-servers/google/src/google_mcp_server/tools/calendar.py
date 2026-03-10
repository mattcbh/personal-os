"""Google Calendar MCP tools backed by the gws CLI."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Optional
from zoneinfo import ZoneInfo

from mcp.server.fastmcp import FastMCP

from google_mcp_server.auth.oauth import GoogleAuthManager

LOCAL_TZ = ZoneInfo("America/New_York")


def _compute_local_fields(event: dict[str, Any]) -> dict[str, Optional[str]]:
    """Compute local date, day of week, and formatted time for an event."""
    start_raw = event.get("start", {}) if isinstance(event.get("start"), dict) else {}
    dt_str = start_raw.get("dateTime")

    if isinstance(dt_str, str) and dt_str:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00")).astimezone(LOCAL_TZ)
        return {
            "local_date": dt.strftime("%Y-%m-%d"),
            "day_of_week": dt.strftime("%A"),
            "local_time": dt.strftime("%-I:%M %p"),
        }

    date_str = start_raw.get("date")
    if isinstance(date_str, str) and date_str:
        d = datetime.fromisoformat(f"{date_str}T00:00:00").date()
        return {
            "local_date": date_str,
            "day_of_week": d.strftime("%A"),
            "local_time": "all-day",
        }

    return {"local_date": None, "day_of_week": None, "local_time": None}


def register_tools(mcp: FastMCP, auth: GoogleAuthManager):
    """Register all Calendar tools with the MCP server."""

    @mcp.tool()
    def calendar_list_events(
        calendar_id: str = "primary",
        time_min: Optional[str] = None,
        time_max: Optional[str] = None,
        max_results: int = 10,
        query: Optional[str] = None,
    ) -> dict:
        """
        List calendar events within a time range.

        Args:
            calendar_id: Calendar ID (default: 'primary' for main calendar)
            time_min: Start time in RFC3339 format. Defaults to now.
            time_max: End time in RFC3339 format. Defaults to 7 days from now.
            max_results: Maximum number of events to return (default: 10)
            query: Optional search query to filter events

        Returns:
            List of events with id, summary, start, end, location, and attendees
        """
        if not time_min:
            time_min = datetime.now(LOCAL_TZ).isoformat()
        if not time_max:
            time_max = (datetime.now(LOCAL_TZ) + timedelta(days=7)).isoformat()

        params: dict[str, Any] = {
            "calendarId": calendar_id,
            "timeMin": time_min,
            "timeMax": time_max,
            "maxResults": max_results,
            "singleEvents": True,
            "orderBy": "startTime",
            "timeZone": "America/New_York",
        }
        if query:
            params["q"] = query

        results = auth.run_gws("calendar", "events", "list", params=params)
        events = results.get("items", [])

        enriched_events = []
        if isinstance(events, list):
            for event in events:
                if not isinstance(event, dict):
                    continue
                local_fields = _compute_local_fields(event)
                attendees = event.get("attendees", [])
                enriched_events.append(
                    {
                        "id": event.get("id", ""),
                        "summary": event.get("summary", "(No title)"),
                        "start": (
                            (event.get("start") or {}).get("dateTime")
                            if isinstance(event.get("start"), dict)
                            else None
                        )
                        or (
                            (event.get("start") or {}).get("date")
                            if isinstance(event.get("start"), dict)
                            else None
                        ),
                        "end": (
                            (event.get("end") or {}).get("dateTime")
                            if isinstance(event.get("end"), dict)
                            else None
                        )
                        or (
                            (event.get("end") or {}).get("date")
                            if isinstance(event.get("end"), dict)
                            else None
                        ),
                        "local_date": local_fields["local_date"],
                        "day_of_week": local_fields["day_of_week"],
                        "local_time": local_fields["local_time"],
                        "location": event.get("location", ""),
                        "description": event.get("description", ""),
                        "attendees": [
                            {
                                "email": a.get("email"),
                                "responseStatus": a.get("responseStatus"),
                            }
                            for a in attendees
                            if isinstance(a, dict)
                        ],
                        "htmlLink": event.get("htmlLink", ""),
                    }
                )

        return {"events": enriched_events, "resultCount": len(enriched_events)}

    @mcp.tool()
    def calendar_create_event(
        summary: str,
        start: str,
        end: str,
        calendar_id: str = "primary",
        description: Optional[str] = None,
        location: Optional[str] = None,
        attendees: Optional[list[str]] = None,
        timezone_str: str = "America/New_York",
    ) -> dict:
        """
        Create a new calendar event.

        Args:
            summary: Event title
            start: Start time in RFC3339 format
            end: End time in RFC3339 format
            calendar_id: Calendar ID (default: 'primary')
            description: Optional event description
            location: Optional event location
            attendees: Optional list of attendee email addresses
            timezone_str: Timezone for the event

        Returns:
            Created event details including id and htmlLink
        """
        event_body: dict[str, Any] = {
            "summary": summary,
            "start": {"dateTime": start, "timeZone": timezone_str},
            "end": {"dateTime": end, "timeZone": timezone_str},
        }

        if description:
            event_body["description"] = description
        if location:
            event_body["location"] = location
        if attendees:
            event_body["attendees"] = [{"email": email} for email in attendees]

        event = auth.run_gws(
            "calendar",
            "events",
            "insert",
            params={
                "calendarId": calendar_id,
                "sendUpdates": "all" if attendees else "none",
            },
            body=event_body,
        )

        return {
            "id": event.get("id", ""),
            "summary": event.get("summary"),
            "htmlLink": event.get("htmlLink"),
            "start": event.get("start"),
            "end": event.get("end"),
            "status": "created",
        }

    @mcp.tool()
    def calendar_get_event(event_id: str, calendar_id: str = "primary") -> dict:
        """
        Get details of a specific calendar event.

        Args:
            event_id: The event ID
            calendar_id: Calendar ID (default: 'primary')

        Returns:
            Full event details
        """
        event = auth.run_gws(
            "calendar",
            "events",
            "get",
            params={"calendarId": calendar_id, "eventId": event_id},
        )

        return {
            "id": event.get("id", ""),
            "summary": event.get("summary", "(No title)"),
            "start": event.get("start"),
            "end": event.get("end"),
            "location": event.get("location", ""),
            "description": event.get("description", ""),
            "attendees": event.get("attendees", []),
            "organizer": event.get("organizer", {}),
            "htmlLink": event.get("htmlLink", ""),
            "status": event.get("status", ""),
            "created": event.get("created", ""),
            "updated": event.get("updated", ""),
        }

    @mcp.tool()
    def calendar_freebusy(
        time_min: str,
        time_max: str,
        calendars: Optional[list[str]] = None,
    ) -> dict:
        """
        Query free/busy information for calendars.

        Args:
            time_min: Start time in RFC3339 format
            time_max: End time in RFC3339 format
            calendars: List of calendar IDs to check (default: ['primary'])

        Returns:
            Free/busy information showing busy time blocks for each calendar
        """
        if not calendars:
            calendars = ["primary"]

        body = {
            "timeMin": time_min,
            "timeMax": time_max,
            "items": [{"id": cal_id} for cal_id in calendars],
        }

        result = auth.run_gws("calendar", "freebusy", "query", body=body)
        freebusy_data = {}
        for cal_id, data in (result.get("calendars", {}) or {}).items():
            if not isinstance(data, dict):
                continue
            freebusy_data[str(cal_id)] = {
                "busy": data.get("busy", []),
                "errors": data.get("errors", []),
            }

        return {
            "timeMin": result.get("timeMin"),
            "timeMax": result.get("timeMax"),
            "calendars": freebusy_data,
        }

    @mcp.tool()
    def calendar_list_calendars() -> dict:
        """
        List all calendars accessible to the authenticated user.

        Returns:
            List of calendars with id, summary, and access role
        """
        results = auth.run_gws("calendar", "calendarList", "list")
        calendars = results.get("items", [])

        out = []
        if isinstance(calendars, list):
            for cal in calendars:
                if not isinstance(cal, dict):
                    continue
                out.append(
                    {
                        "id": cal.get("id", ""),
                        "summary": cal.get("summary", ""),
                        "primary": cal.get("primary", False),
                        "accessRole": cal.get("accessRole", ""),
                        "backgroundColor": cal.get("backgroundColor", ""),
                    }
                )

        return {"calendars": out}

    @mcp.tool()
    def calendar_delete_event(
        event_id: str,
        calendar_id: str = "primary",
        send_updates: str = "all",
    ) -> dict:
        """
        Delete a calendar event.

        Args:
            event_id: The event ID to delete
            calendar_id: Calendar ID (default: 'primary')
            send_updates: Whether to send cancellation notifications

        Returns:
            Confirmation of deletion
        """
        auth.run_gws(
            "calendar",
            "events",
            "delete",
            params={
                "calendarId": calendar_id,
                "eventId": event_id,
                "sendUpdates": send_updates,
            },
        )

        return {"id": event_id, "status": "deleted"}

    @mcp.tool()
    def calendar_update_event(
        event_id: str,
        calendar_id: str = "primary",
        summary: Optional[str] = None,
        start: Optional[str] = None,
        end: Optional[str] = None,
        description: Optional[str] = None,
        location: Optional[str] = None,
        timezone_str: str = "America/New_York",
    ) -> dict:
        """
        Update an existing calendar event.

        Args:
            event_id: The event ID to update
            calendar_id: Calendar ID (default: 'primary')
            summary: New event title (optional)
            start: New start time in RFC3339 format (optional)
            end: New end time in RFC3339 format (optional)
            description: New description (optional)
            location: New location (optional)
            timezone_str: Timezone for the event

        Returns:
            Updated event details
        """
        event = auth.run_gws(
            "calendar",
            "events",
            "get",
            params={"calendarId": calendar_id, "eventId": event_id},
        )

        if summary is not None:
            event["summary"] = summary
        if description is not None:
            event["description"] = description
        if location is not None:
            event["location"] = location
        if start is not None:
            event["start"] = {"dateTime": start, "timeZone": timezone_str}
        if end is not None:
            event["end"] = {"dateTime": end, "timeZone": timezone_str}

        updated_event = auth.run_gws(
            "calendar",
            "events",
            "update",
            params={"calendarId": calendar_id, "eventId": event_id},
            body=event,
        )

        return {
            "id": updated_event.get("id", ""),
            "summary": updated_event.get("summary"),
            "htmlLink": updated_event.get("htmlLink"),
            "start": updated_event.get("start"),
            "end": updated_event.get("end"),
            "status": "updated",
        }
