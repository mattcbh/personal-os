# System Of Record

This file defines where the system actually lives, how it syncs, and where changes should be made.

## Operating Model

- **Laptop** is the Git authority for `personal-os`.
- **Mac Mini** is the live automation host and uses an Obsidian Sync working copy of `personal-os`.
- **GitHub** is the deployment source of truth for `automation-machine-config`, `automation-runtime-personal`, and `automation-runtime-work`.
- **PnT data warehouse** remains a separate launchd-based cluster on the Mac Mini.
- **Machine-local secrets and app defaults** stay local to each machine and are never committed.

## System-Of-Record Matrix

| Surface | Canonical system | Live copies | Sync / deployment path | Where to edit |
|---|---|---|---|---|
| `personal-os` vault content | Laptop Git repo at `~/Obsidian/personal-os` | Laptop vault, Mini live vault, other synced clients | Obsidian Sync for live copies; Git from laptop only | Edit in the vault, then reconcile and commit from the laptop |
| `automation-runtime-personal` | GitHub repo `automation-runtime-personal` | Laptop clone, Mini clone | Laptop push -> GitHub -> Mini poller (`poll-main.sh`) | Runtime code changes in the repo |
| `automation-runtime-work` | GitHub repo `automation-runtime-work` | Laptop clone, Mini clone | Laptop push -> GitHub -> Mini poller (`poll-main.sh`) | Runtime code changes in the repo |
| Machine config and local MCP server install source | GitHub repo `automation-machine-config` | Laptop clone, Mini clone | Laptop push -> GitHub -> manual pull/install on each machine | Machine config, bootstrap, status scripts |
| Codex core config | `automation-machine-config/bin/install-machine-config.sh` output | `~/.codex/config.toml` on each machine | Install script with role-specific rendering | Machine config repo |
| Claude MCP baseline | `automation-machine-config/bin/install-machine-config.sh` output | `~/.mcp.json` on each machine | Install script with role-specific rendering | Machine config repo |
| Shared vault skills | `personal-os/core/integrations/*/skills/*` | Vault on laptop and Mini | Obsidian Sync | Vault |
| Local MCP server code | `automation-machine-config/mcp-servers/` | Machine-config repo clone on each machine | Git pull / machine bootstrap | Machine config repo |
| Vault MCP docs mirror | `personal-os/core/integrations/mcp-servers/` | Vault copies on laptop and Mini | Obsidian Sync | Reference docs only; do not treat as install source |
| PnT warehouse runtime | Mini repo at `~/Projects/pnt-data-warehouse` | Laptop clone, Mini production repo | Manual Git workflow; launchd on Mini | PnT repo |
| Dropbox screenshots | Dropbox `Screenshots/` folder | Both machines | Dropbox sync | Change machine defaults locally if needed |
| Google Drive agent workspace | `Corner Booth Holdings/8- Agent Workspace/` | Both machines | Google Drive sync | Use the cloud path directly |

## Vault Reconciliation Workflow

`personal-os` edits may originate on the Mac Mini or any synced client, but Git history is still maintained from the laptop.

1. Allow the live Mini vault to receive edits through Obsidian Sync or remote sessions.
2. Let those edits land in the laptop working tree.
3. Review from the laptop repo with `git status` and `git diff`.
4. Commit and push from the laptop when the change belongs in history.
5. Keep the Mini vault out of Git. Do not `git init` or clone `personal-os` into the live Mini vault path.

## Config Contract

### Codex Shared Core

- Model: `gpt-5.4`
- Reasoning effort: `xhigh`
- Shared MCP set: `figma`, `notion`, `playwright`
- Brain-only addition: trusted project entry for `~/Obsidian/personal-os`

### Claude Shared Core

- Shared MCP baseline on both machines: `notion`, `granola`, `contacts`
- Brain-only operational extras: `google`, `google-personal`, `supabase`, `beeper`, `excalidraw`
- Machine-local secrets stay in home-directory paths, not in Git

### Plugin Policy

- Shared core plugins may differ by role, but differences must be documented as intentional.
- Laptop can stay lighter for interactive authoring.
- Mini can keep operational plugins needed for production workflows.

## Edit Routing

Use this table to decide where to make a change:

| If you are changing... | Edit here | Deploy / apply here |
|---|---|---|
| Vault docs, context, prompts, skills | `~/Obsidian/personal-os` | Obsidian Sync for live copies; Git commit from laptop |
| Personal runtime job logic | `~/Projects/automation-runtime-personal` | Push to GitHub, let Mini poller deploy |
| Work runtime job logic | `~/Projects/automation-runtime-work` | Push to GitHub, let Mini poller deploy |
| Machine config or MCP defaults | `~/Projects/automation-machine-config` | Pull on target machine and run `install-machine-config.sh` |
| PnT warehouse code or launchd plists | `~/Projects/pnt-data-warehouse` | Manual Mini workflow |
| macOS defaults, launchctl state, app auth, secret files | target machine home directory | Run directly on the target machine |
