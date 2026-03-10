# Matt's Personal AI Operating System

Persistent AI operations environment running from a Mac Mini ("brain") with Obsidian as knowledge/state sync.

## Current Runtime (Canonical)

See `core/architecture/runtime-manifest.yaml` for the source of truth.

Scheduled jobs currently in-repo:
- Daily digest (5:00 AM ET)
- Email triage AM (6:00 AM ET)
- Email triage PM (3:00 PM ET)

## Core Structure

- `AGENTS.md` - top-level behavior/instruction contract
- `core/architecture/` - runtime inventory and architecture index
- `core/automation/` - launch scripts and launchd plists
- `core/context/` - domain context loaded on demand
- `core/policies/` - canonical cross-cutting policies
- `core/integrations/` - skill and integration definitions
- `core/state/` - JSON/markdown state files
- `Knowledge/` - generated outputs, transcripts, learnings
- `projects/` - active project briefs

## Reliability Rules

1. Keep runtime docs aligned with files on disk.
2. Use exact path casing (`Knowledge/DIGESTS`, `Knowledge/TRANSCRIPTS`).
3. Keep secrets out of synced markdown/json files.
4. Update policy files in `core/policies/` before copying rules into skills/prompts.

## Security

If credentials or refresh tokens are ever committed/synced in plain text, rotate immediately and replace with env-based secret loading.
