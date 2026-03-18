---
name: meeting-sync
description: Sync new Granola meetings to local transcript files and optionally capture follow-up tasks.
---

# Meeting Sync

Canonical policy references:
- `core/policies/paths-and-state.md`
- `core/policies/scheduling.md`

## Required Paths

- Transcript folder: `~/Obsidian/personal-os/Knowledge/TRANSCRIPTS/`
- Sync state file: `~/Obsidian/personal-os/core/state/granola-sync.json`
- Pending tasks file: `~/Obsidian/personal-os/core/state/pending-tasks.md`
- Meeting review state file: `~/Obsidian/personal-os/core/state/meeting-task-review.json`
- Fast helper script: `~/Projects/automation-runtime-personal/core/automation/meeting-sync-fetch.py`

## Workflow

### 1) Determine unsynced meetings (fast local precheck)

Run:

```bash
python3 ~/Projects/automation-runtime-personal/core/automation/meeting-sync-fetch.py --check-new-local
```

This reads Granola's local cache + `granola-sync.json` and returns unsynced meetings from the last 14 days.

If empty, do a freshness fallback before stopping:
1. Call `mcp__granola__list_meetings`
2. Write the raw JSON to `/tmp/granola-meetings-list.json`
3. Run:

```bash
python3 ~/Projects/automation-runtime-personal/core/automation/meeting-sync-fetch.py --check-new < /tmp/granola-meetings-list.json
```

If that is also empty, stop and report "No new meetings found."
If non-empty, present meetings in a numbered list with title + date and ask whether to:
- Sync all
- Select specific
- Skip

### 2) Gather meeting notes/summaries for selected meetings

For each selected meeting:
1. Call `mcp__granola__get_meetings` with the meeting ID.
2. Extract:
   - `id`
   - `title`
   - `date` (ISO)
   - `participants`
   - `summary` (markdown/notes content)
3. Build a JSON array of all selected meetings and write it to `/tmp/meetings-to-sync.json`.

### 3) Sync transcripts and write files (fast path)

Run:

```bash
python3 ~/Projects/automation-runtime-personal/core/automation/meeting-sync-fetch.py --sync < /tmp/meetings-to-sync.json
```

The script handles:
- Transcript fetch via direct Granola API (much faster than MCP transcript calls)
- Markdown file writing in `Knowledge/TRANSCRIPTS/`
- Sync state updates in `core/state/granola-sync.json`

Parse the JSON report and summarize synced/failed meetings.

### 4) Extract task candidates

From selected meetings, extract concrete Matt-owned action items from summary content first (and transcript text if needed).
For the scheduled automation, write candidates into meeting-task review state and send the Telegram digest for explicit approval.
For interactive `/meeting-sync`, show the candidates and require explicit confirmation before creating Things tasks.

The scheduled runtime mirrors pending items into `core/state/pending-tasks.md` under meeting sections so unresolved items can be carried forward:

```markdown
## YYYY-MM-DD — Meeting Title

- [ ] Task description
- [ ] Another task
```

Scheduled review happens through Telegram replies, not morning planning. Valid commands are:

```text
approve 1 3
edit 2: revised task text
reject 4
```

Approved items are appended to `things-sync/inbox.md` with `[things:new]` and then synced into Things.

## Rules

- Do not invent tasks that are not grounded in meeting content.
- Do not call `mcp__granola__get_meeting_transcript` (slow path).
- Do not write transcript files manually when the script can do it.
- Do not read/write `granola-sync.json` manually.
- Use exact path casing: `Knowledge/TRANSCRIPTS/`.

## Troubleshooting

- If local precheck is empty or fails, fall back to `mcp__granola__list_meetings` + `--check-new`.
- If MCP returns authentication errors for `get_meetings`, verify Granola MCP connectivity first.
- If transcript API returns empty/not found, keep summary-only file and mark synced.
- If `--sync` reports failures, report failed meeting IDs and leave those IDs unsynced.
- If unresolved meeting tasks exist with no new meetings, the 5:15 PM digest should still resend the carried-forward items.
