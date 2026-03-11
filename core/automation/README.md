# Automation

Scheduled jobs and automation helpers for the Mac Mini ("brain").

Canonical runtime inventory: `core/architecture/runtime-manifest.yaml`.

## Runtime Architecture

Automation scripts live in two GitHub repos, NOT in this Obsidian vault:

- **`automation-runtime-personal`** (`~/Projects/automation-runtime-personal/`) — daily digest, meeting sync, weekly followup
- **`automation-runtime-work`** (`~/Projects/automation-runtime-work/`) — email triage, comms ingest, email monitor, PnT sync, project refresh, telegram bridge

Both repos reference the Obsidian vault for knowledge (workflows, context docs, transcripts, digests) and MCP configs via `config/runtime.env`. State files in `core/state/` are symlinked to the canonical copies in the work repo.

The live Mac Mini vault is an Obsidian Sync working copy, not a Git checkout. This directory is therefore the Obsidian-side architecture, prompt, and helper layer. Production automation code lives in the runtime repos.

## Where To Edit

- **Vault docs, prompts, context, and skills:** edit in `personal-os`
- **Runtime job logic:** edit in `automation-runtime-personal` or `automation-runtime-work`
- **Machine-local config and MCP defaults:** edit in `automation-machine-config`
- **Git history for `personal-os`:** reconcile and commit from the laptop repo only

## Active Launchd Jobs

| Job | Schedule (ET) | Repo | Script | Plist |
|---|---|---|---|---|
| Daily Digest | 5:00 AM daily | personal | `daily-digest.sh` | `com.matthewlieber.automation-personal.daily-digest.plist` |
| Project Refresh (AM) | 5:35 AM daily | work | `project-refresh.sh` | `com.brain.project-refresh-morning.plist` |
| Email Triage v2 (AM) | 6:00 AM daily | work | `email-triage-v2.sh` | `com.brain.email-triage-v2-morning.plist` |
| Email Triage v2 (PM) | 3:00 PM daily | work | `email-triage-v2.sh` | `com.brain.email-triage-v2-evening.plist` |
| Project Refresh (PM) | 2:35 PM daily | work | `project-refresh.sh` | `com.brain.project-refresh-evening.plist` |
| System Health | 7:10 AM daily | local | `system-health.sh` | `com.brain.system-health.plist` |
| Email Monitor | 8:00,10:00,12:00,14:00,16:00,18:00 | work | `email-monitor.sh` | `com.brain.email-monitor.plist` |
| Comms Ingest | Every 30 minutes | work | `comms-ingest.sh` | `com.brain.comms-ingest.plist` |
| PnT Buildout Sync | 4:00 PM daily | work | `pnt-sync.sh` | `com.brain.pnt-sync.plist` |
| Weekly Follow-Up | Friday 4:00 PM | personal | `weekly-followup.sh` | `com.brain.weekly-followup.plist` |
| Meeting Sync | 9:00 PM daily | personal | `meeting-sync.sh` | `com.brain.meeting-sync.plist` |
| Telegram Bridge | KeepAlive / RunAtLoad | work | `telegram-bridge.sh` | `com.brain.telegram-bridge.plist` |

## Files In This Directory

Prompt templates and docs (referenced by repo scripts via env vars):
- `comms-ingest-prompt.md` — prompt template for comms ingest
- `email-triage-prompt.md` — prompt template for email triage v1
- `email-triage-runbook.md`, `email-triage-v2-runbook.md` — runbook docs
- `email-triage-contract.json` — triage contract schema

Superhuman helpers (run directly from Obsidian):
- `superhuman-draft.sh` — queue-first draft writer
- `superhuman-draft-watcher.sh` — queue processor for Superhuman UI automation
- `superhuman-draft-status.py` — draft status checker
- `ensure-superhuman.sh` — browser/session prep (archived)

Utilities:
- `system-health.sh` — system health checker
- `chrome-cdp-helper.sh` — CDP helper utilities
- `compare-machine-config.sh` — environment diff utility
- `setup-on-brain.sh`, `setup-email-triage-v2-on-brain.sh` — one-time setup scripts

MCP configs:
- `mcp-configs/` — reference copies kept in the vault. Installed production MCP configs are rendered into the runtime repos under `.generated/mcp/`.

Reference-only launchd plists:
- `launchd-plists/` — archival/reference copies from the legacy `personal-os` runtime. Installed plists on the brain are rendered from the runtime repos and loaded into `~/Library/LaunchAgents/`.

Legacy (completed, no longer scheduled):
- `transcript-backfill.sh`, `transcript-backfill-fast.py` — completed Feb 2026
- `email-triage.sh` — v1, replaced by v2
- `email-triage-validator.py`, `email-triage-render.py`, `email-triage-design-preview.py` — v1 helpers
- `email-identity-resolver.py` — identity resolver
- `send-emmas-torch-report.py` — one-off report
- `beeper-auth-health.py` — health check utility

## State Files

All runtime state lives in `core/state/`. Files there are symlinks to the canonical copies in the work repo (`automation-runtime-work/core/state/`). Interactive skills and automated jobs read/write the same files through these symlinks.

## Logs

Logs are written to the repo that runs the job, not to Obsidian:
- Personal repo logs: `~/Projects/automation-runtime-personal/logs/`
- Work repo logs: `~/Projects/automation-runtime-work/logs/`

## Drift Guardrail

If you add/remove jobs, update both in the same change:
1. `core/architecture/runtime-manifest.yaml`
2. `core/automation/README.md`
