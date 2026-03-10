# Automated Cross-Channel Communications Ingest

Use this prompt as the execution contract for scheduled cross-channel ingest.

Canonical policy files (take precedence if duplicated guidance conflicts):
- `core/policies/email-drafting.md`
- `core/policies/paths-and-state.md`

## Parameters

- Now: {{TIMESTAMP}} ({{FULL_DATE}})
- Last ingest: {{LAST_INGEST_TIMESTAMP}}

## Goal

Capture new communications from email and Beeper into a single normalized event log so downstream workflows can consume consistent, up-to-date context.

## Step 1: Read / Initialize State

State file: `core/state/comms-ingest-state.json`

Required keys:
- `last_ingest_timestamp` (ISO8601 or null)
- `seen_event_ids` (array of strings)
- `runs` (integer)
- `last_run_stats` (object)
- `last_warnings` (array of strings)

If missing/corrupt, initialize:

```json
{
  "last_ingest_timestamp": null,
  "seen_event_ids": [],
  "runs": 0,
  "last_run_stats": {},
  "last_warnings": []
}
```

If `last_ingest_timestamp` is null, treat as cold start and ingest only the last 24 hours.

## Step 2: Ingest Email Events (Both Accounts)

Run both searches:
- Work: `mcp__google__gmail_users_messages_list(query='newer_than:2d -label:sent -label:draft', max_results=75)`
- Personal: `mcp__google-personal__gmail_users_messages_list(query='newer_than:2d -label:sent -label:draft', max_results=75)`

Filter to messages:
- newer than `last_ingest_timestamp` (or last 24h on cold start)
- not already present in `seen_event_ids` (`email:<account>:<messageId>`)

Create one normalized event per message:
- `event_id`: `email:<account>:<messageId>`
- `channel`: `email`
- `platform`: `gmail`
- `account`: `work|personal`
- `timestamp`
- `message_id`
- `thread_id`
- `sender`
- `subject`
- `snippet`
- `source_url_superhuman`
- `source_url_gmail`

## Step 3: Ingest Beeper Events

Read optional watchlist file `core/state/beeper-chat-watchlist.json`:
- Schema: `{ "chat_ids": ["..."] }`
- If missing, initialize with `{ "chat_ids": [] }`

Discovery pass (best effort):
- Run `mcp__beeper__search_chats` for these names and collect chat IDs:
  - `Darragh O'Sullivan`
  - `Sarah Sanneh`
  - `Jason Hershfeld`
  - `Marc McQuade`
  - `Abraham Murrell`
  - `Phil Amico`
- Merge discovered IDs into watchlist and write the watchlist back.

Message ingest pass:
- For each watched chat ID, call `mcp__beeper__list_messages` and keep only messages newer than `last_ingest_timestamp` (or last 24h cold start).
- Build stable event IDs:
  - Prefer: `beeper:<chat_id>:<message_id>`
  - Fallback if message ID unavailable: `beeper:<chat_id>:<timestamp>:<author>`
- Skip IDs already in `seen_event_ids`.

Create one normalized event per Beeper message:
- `event_id`
- `channel`: `chat`
- `platform`: `beeper`
- `network` (if available, e.g., `whatsapp|sms|imessage|other`)
- `timestamp`
- `chat_id`
- `author`
- `text`
- `direction` (`incoming|outgoing|unknown`)

If Beeper calls fail, continue the run, record warning(s), and still update state/log with email events.

## Step 4: Append Event Log

Event log file: `core/state/comms-events.jsonl`

Append each new event as one compact JSON line.
Do not rewrite existing lines. Append only new events from this run.

## Step 5: Update State

Update `core/state/comms-ingest-state.json`:
- `last_ingest_timestamp` = now (ISO8601)
- append new event IDs to `seen_event_ids`, keep only latest 3000 IDs
- increment `runs`
- set `last_run_stats`:
  - `new_email_events_work`
  - `new_email_events_personal`
  - `new_beeper_events`
  - `total_new_events`
- set `last_warnings` to warnings from this run (empty array if none)

## Critical Constraints

- Headless run: do not ask user questions
- Do not send any messages or emails
- Do not draft any replies
- Do not modify project briefs in this job
- Be resilient: partial ingest is better than a failed run
