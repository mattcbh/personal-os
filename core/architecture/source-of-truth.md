# System Of Record

This file defines where the current system actually lives, how each surface syncs or deploys, and where changes should be made.

Canonical narrative: `core/architecture/system-architecture.md`

## Operating Model

- **Vault content** is the live content surface distributed through Obsidian Sync.
- **Laptop** is the Git reconciliation authority for the Vault repo at `~/Obsidian/personal-os`.
- **Mini** is the live automation host and uses an Obsidian Sync working copy of the Vault.
- **GitHub** is the remote source of truth for `automation-machine-config`, `automation-runtime-personal`, `automation-runtime-work`, and the warehouse authoring repo.
- **Warehouse runtime** remains a separate launchd-based cluster on the Mini and currently uses both an authoring checkout and a live production checkout.
- **Machine-local secrets and app defaults** stay local to each machine and are never committed.

## System-Of-Record Matrix

| Surface | Canonical system | Live copies | Sync / deployment path | Where to edit |
|---|---|---|---|---|
| Vault content (`~/Obsidian/personal-os`) | Live Vault content distributed by Obsidian Sync; Git reconciled from the Laptop | Laptop Vault, Mini Vault, other synced clients | Obsidian Sync for live copies; Git from the Laptop only | Edit in the Vault, then reconcile and commit from the Laptop |
| `automation-runtime-personal` | GitHub repo `automation-runtime-personal` | Laptop clone, Mini clone | Laptop push -> GitHub -> Mini poller (`poll-main.sh`) | Runtime code changes in the repo |
| `automation-runtime-work` | GitHub repo `automation-runtime-work` | Laptop clone, Mini clone | Laptop push -> GitHub -> Mini poller (`poll-main.sh`) | Runtime code changes in the repo |
| Machine config and local MCP server install source | GitHub repo `automation-machine-config` | Laptop clone, Mini clone | Laptop push -> GitHub -> manual pull/install on each machine | Machine config, bootstrap, status scripts, Codex/Claude baseline, system-health coordinator |
| Codex core config | `automation-machine-config/bin/install-machine-config.sh` output | `~/.codex/config.toml` on each machine | Install script with role-specific rendering | Machine config repo |
| Claude MCP baseline | `automation-machine-config/bin/install-machine-config.sh` output | `~/.mcp.json` on each machine | Install script with role-specific rendering | Machine config repo |
| Shared Vault skills | `~/Obsidian/personal-os/core/integrations/*/skills/*` | Vault on Laptop and Mini | Obsidian Sync | Vault |
| Local MCP server code | `~/Projects/automation-machine-config/mcp-servers/` | Machine-config repo clone on each machine | Git pull / machine bootstrap | Machine config repo |
| Vault MCP docs mirror | `~/Obsidian/personal-os/core/integrations/mcp-servers/` | Vault copies on Laptop and Mini | Obsidian Sync | Reference docs only; do not treat as install source |
| Warehouse authoring repo | GitHub repo `pnt-data-warehouse` at `~/Projects/pnt-data-warehouse` | Laptop clone, Mini clone | Manual Git workflow | Warehouse repo |
| Warehouse production runtime | Live Mini checkout at `~/Production/pnt-data-warehouse-runtime` | Mini only | Manual Git workflow; installed warehouse launchd jobs point here for most scripts | Mini production runtime path |
| Dropbox screenshots | Dropbox `Screenshots/` folder | Both machines | Dropbox sync | Change machine defaults locally if needed |
| Google Drive agent workspace | `Corner Booth Holdings/8- Agent Workspace/` | Both machines | Google Drive sync | Use the cloud path directly |

## Vault Reconciliation Workflow

Vault edits may originate on the Mini or any synced client, but Git history is reconciled from the Laptop.

1. Allow the live Mini Vault to receive edits through Obsidian Sync or remote sessions.
2. Let those edits land in the Laptop working tree.
3. Review from the Laptop repo with `git status` and `git diff`.
4. Commit and push from the Laptop when the change belongs in history.
5. Keep the Mini Vault out of Git. Do not `git init` or clone the Vault repo into the live Mini Vault path.

## External Sharing Boundary

- Treat the raw Vault as internal-only by default.
- For external engineers, prepare a sanitized architecture handoff instead of sharing the live Vault working set.
- Keep people files, sensitive context, and machine-local operational state out of the default external collaboration package.

## Config Contract

### Codex Shared Core

- Model: `gpt-5.4`
- Reasoning effort: `xhigh`
- Shared MCP set: `figma`, `notion`, `playwright`
- Mini-only addition: trusted project entry for `~/Obsidian/personal-os`

### Claude Shared Core

- Shared MCP baseline on both machines: `notion`, `granola`, `contacts`
- Mini-only operational extras: `google`, `google-personal`, `supabase`, `beeper`, `excalidraw`
- Machine-local secrets stay in home-directory paths, not in Git

### Plugin Policy

- Shared core plugins may differ by host role, but differences must be documented as intentional.
- Laptop can stay lighter for interactive authoring.
- Mini can keep operational plugins needed for production workflows.

## Edit Routing

Use this table to decide where to make a change:

| If you are changing... | Edit here | Deploy / apply here |
|---|---|---|
| Vault docs, context, prompts, skills | `~/Obsidian/personal-os` | Obsidian Sync for live copies; Git commit from Laptop |
| Personal runtime job logic | `~/Projects/automation-runtime-personal` | Push to GitHub, let Mini poller deploy |
| Work runtime job logic | `~/Projects/automation-runtime-work` | Push to GitHub, let Mini poller deploy |
| Machine config, Codex/Claude defaults, or system-health coordinator | `~/Projects/automation-machine-config` | Pull on target machine and run `install-machine-config.sh` |
| Warehouse authoring code | `~/Projects/pnt-data-warehouse` | Manual Git workflow |
| Warehouse production runtime pathing or installed Mini warehouse jobs | Mini production runtime and launchd layer | Review manually on the Mini before making runtime changes |
| macOS defaults, launchctl state, app auth, secret files | target machine home directory | Run directly on the target machine |
