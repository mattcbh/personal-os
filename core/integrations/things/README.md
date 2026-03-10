# Things 3 ↔ Obsidian Sync

Two-way sync between Things 3 and markdown files in your Obsidian vault.

## Quick Start

```bash
# Run a full sync
./sync_all.sh

# Or run from anywhere (recommended in remote/sandbox shells)
cd /path/to/personal-os
./core/integrations/things/sync_all.sh
```

If a shell alias like `things-sync` is unavailable, use the script path directly:

```bash
core/integrations/things/sync_all.sh
```

## What Gets Synced

| Things List | Obsidian File |
|-------------|---------------|
| Today | `things-sync/today.md` |
| Inbox | `things-sync/inbox.md` |
| Anytime | `things-sync/anytime.md` |
| Upcoming | `things-sync/upcoming.md` |
| Someday | `things-sync/someday.md` |
| Logbook | `things-sync/logbook.md` |
| Projects | `things-sync/projects/*.md` |
| Areas | `things-sync/areas/*.md` |

## Task Format

Tasks in markdown look like this:

```markdown
- [ ] Task name `[things:ABC123]`
  - When: 2025-01-20
  - Notes: Any notes here
  - Tags: #tag1 #tag2
```

The `[things:ABC123]` is the unique Things ID that keeps tasks synced.

**Important:** Use `When:` for scheduled dates. This system does NOT use deadlines.

## Creating New Tasks in Obsidian

1. Add a task with `[things:new]` as the ID:
   ```markdown
   - [ ] New task from Obsidian `[things:new]`
     - When: 2025-01-25
     - Notes: Optional notes here
   ```

2. Run `./sync_all.sh`

3. The task will be created in Things and the ID updated:
   ```markdown
   - [ ] New task from Obsidian `[things:XYZ789]`
   ```

## Marking Tasks Complete

**From Obsidian:** Change `[ ]` to `[x]`, then run sync:
```markdown
- [x] Completed task `[things:ABC123]`
```

**From Things:** Just complete it in Things, then run sync. The markdown will be updated.

## Sync Options

```bash
./sync_all.sh              # Full sync (push + pull)
./sync_all.sh --pull-only  # Only update Obsidian from Things
./sync_all.sh --push-only  # Only push new tasks/completions to Things
./sync_all.sh --dry-run    # Preview changes without syncing
```

## Creating Tasks Programmatically (Claude/Scripts)

When creating or updating tasks via code (not through markdown sync), use the **Things URL scheme**:

```bash
# Create a task with a When date
open "things:///add?title=Task%20name&when=2026-03-02&notes=Optional%20notes"

# Create a task with a reminder (use @ to add time)
open "things:///add?title=Task%20name&when=today@7pm&notes=Will%20get%20a%20notification"
open "things:///add?title=Task%20name&when=2026-03-02@14:30&notes=Reminder%20at%202:30pm"

# Other when values with reminders
open "things:///add?title=Task&when=tomorrow@9am"
open "things:///add?title=Task&when=evening@6pm"

# Update an existing task
open "things:///update?id=TASK_ID&when=2026-03-02"
```

### Setting Reminders

To set a reminder that triggers a notification, append `@TIME` to the `when` parameter:
- `when=today@7pm` — Today at 7pm
- `when=tomorrow@9am` — Tomorrow at 9am
- `when=evening@6pm` — This evening at 6pm
- `when=2026-03-02@14:30` — Specific date at 2:30pm

Time formats: `7pm`, `19:00`, `7:00pm`, `14:30`

**Do NOT use AppleScript's `due date` property**—that sets a Deadline, not a When date.

```applescript
# WRONG - sets a deadline
set due date of myTask to date "March 2, 2026"

# CORRECT - use URL scheme instead for When dates
```

This matters because this system uses scheduled dates (When), not deadlines.

## Conflict Resolution

**Things is the source of truth.**

- If a task is deleted in Things → removed from Obsidian
- If a task is edited in both places → Things version wins
- If a task is completed in either → marked complete in both

## Requirements

- macOS
- Things 3 installed (reads directly from SQLite database, app doesn't need to be running for pull)
- Python 3

## File Structure

```text
core/integrations/things/
├── sync_all.sh           # Main entry point (shell wrapper)
├── sync_from_things.py   # Pull Things -> Obsidian
├── sync_to_things.py     # Push Obsidian -> Things
└── README.md             # This file
```

## How It Works

**Pull (Things → Obsidian):** Reads directly from Things SQLite database at:
`~/Library/Group Containers/JLMPQHK86H.com.culturedcode.ThingsMac/ThingsData-*/Things Database.thingsdatabase/main.sqlite`

**Push (Obsidian → Things):** Uses Things URL scheme:
- New tasks: `things:///add?title=...`
- Completions: `things:///update?id=UUID&completed=true`

A 2-second delay is added after push to allow Things to write changes before pull.

## Troubleshooting

**Task not created**
Check that the task line has exactly `[things:new]` (with backticks).

**Completed task still showing**
Run sync again - Things writes asynchronously and may need a moment.

**Database not found**
Ensure Things 3 is installed. The sync reads from the SQLite database directly.
