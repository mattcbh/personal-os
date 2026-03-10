# Paths And State Policy

## Canonical directories

- Digests: `Knowledge/DIGESTS/`
- Transcripts: `Knowledge/TRANSCRIPTS/`
- State: `core/state/` (symlinks to canonical copies in GitHub repos)
- Logs: written to the repo that runs each job, not to Obsidian

Use exact casing as listed.

## Canonical state files

Most state files in `core/state/` are symlinks to the work repo (`~/Projects/automation-runtime-work/core/state/`). Interactive skills and automated jobs share the same files through these symlinks.

Symlinked to work repo:
- `core/state/comms-events.jsonl`
- `core/state/beeper-chat-watchlist.json`
- `core/state/comms-ingest-state.json`
- `core/state/beeper-ingest-state.json`
- `core/state/email-monitor-state.json`
- `core/state/pnt-sync-state.json`
- `core/state/project-refresh-state.json`
- `core/state/superhuman-draft-status.json`
- `core/state/telegram-bridge-state.json`
- `core/state/email-triage-v2/` (directory)

Symlinked to personal repo:
- `core/state/daily-digest-context/` (directory)

Local to Obsidian (not symlinked):
- `core/state/granola-sync.json`
- `core/state/cfo-state.json`
- `core/state/pending-tasks.md`
- `core/state/email-triage-state.json`

## Source of truth

Scheduled runtime contracts are defined in:
- `core/architecture/runtime-manifest.yaml`
