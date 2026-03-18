# System Architecture

Last verified: 2026-03-18

This document is the internal source of truth for how the system is structured today, where it runs, how it deploys, and where the main risks and simplification opportunities are.

## Naming And Glossary

Use these names consistently in documentation:

| Term | Meaning |
|---|---|
| `Laptop` | The MacBook authoring machine and Git reconciliation authority for the Vault repo |
| `Mini` | The live automation host |
| `GitHub` | The remote source of truth for Git-backed runtime and machine-config repos |
| `Vault` | The Obsidian content surface at `~/Obsidian/personal-os` |
| `Personal runtime` | `~/Projects/automation-runtime-personal` |
| `Work runtime` | `~/Projects/automation-runtime-work` |
| `Machine config` | `~/Projects/automation-machine-config` |
| `Warehouse authoring repo` | `~/Projects/pnt-data-warehouse` |
| `Warehouse production runtime` | `~/Production/pnt-data-warehouse-runtime` on the Mini |

### Legacy Identifier Map

| Legacy term | Normalized meaning | Notes |
|---|---|---|
| `brain` | `Mini` | Keep only when quoting literal identifiers such as `com.brain.system-health` or `setup-on-brain.sh`. |
| `personal-os` | Vault repo/path name only | Do not use as the umbrella name for the whole system. |

## Approved Policy Decisions

These decisions are approved unless and until a later architecture review changes them:

1. **Vault content authority**
   Live Vault content is the content source of truth and is distributed through Obsidian Sync. The Laptop is the Git reconciliation authority for Vault history, not the primary content authority.

2. **External sharing boundary**
   The raw Vault is internal-only by default. When working with an external engineer, prepare a sanitized architecture handoff instead of sharing the live Vault.

3. **System-health ownership**
   `system-health` is a Mini production workflow. The Laptop variant is an optional disabled audit helper, not a co-equal production scheduler.

4. **Canonical narrative model**
   This file is the only narrative architecture document. Supporting docs should either be inventories or short operator summaries that point back here.

5. **Execution matrix completeness**
   Every major workflow must appear in both the human-readable execution matrix and the machine-readable manifest, including whether it is deterministic or LLM-backed.

6. **Findings register scope**
   The findings register should contain unresolved gaps and active risks only. Once something is documented, it should move to an operational caution or implementation backlog if risk still remains.

## Current-State Topology

### Laptop

- Holds the Git checkout used for Vault reconciliation at `~/Obsidian/personal-os`.
- Holds Git checkouts for `automation-machine-config`, `automation-runtime-personal`, `automation-runtime-work`, and `pnt-data-warehouse`.
- Runs Codex interactively for engineering and documentation work.
- Can run Claude interactively, but does not own the production scheduler.
- Receives Vault edits from Obsidian Sync and is the only place Vault Git reconciliation commits should be created.

### Mini

- Hosts the live Obsidian Sync working copy of the Vault at `~/Obsidian/personal-os`.
- Hosts the active launchd jobs for personal runtime, work runtime, machine config, and warehouse services.
- Hosts the live `telegram-bridge` process and the machine-config-owned system-health runner.
- Hosts two distinct warehouse code paths:
  - authoring checkout at `~/Projects/pnt-data-warehouse`
  - production runtime at `~/Production/pnt-data-warehouse-runtime`
- Runs Claude CLI for the current headless LLM-backed automations.

### GitHub

- Remote source of truth for:
  - `automation-machine-config`
  - `automation-runtime-personal`
  - `automation-runtime-work`
  - `pnt-data-warehouse`
- Deployment model differs by surface:
  - personal and work runtimes: polled from `origin/main` on the Mini
  - machine config: manually pulled and installed on each machine
  - warehouse: currently manual and split between authoring and production paths

### Surface Inventory

| Surface | Canonical owner | Primary host | Deployment / sync model | Notes |
|---|---|---|---|---|
| Vault content | Live Vault content distributed by Obsidian Sync; Git history reconciled from the Laptop | Laptop + Mini | Obsidian Sync for live copies; Git commits from the Laptop only | The Mini Vault is not a Git checkout. |
| Personal runtime | GitHub repo `automation-runtime-personal` | Mini | Mini poller fast-forwards from `origin/main` | Runtime logic only. |
| Work runtime | GitHub repo `automation-runtime-work` | Mini | Mini poller fast-forwards from `origin/main` | Runtime logic only. |
| Machine config | GitHub repo `automation-machine-config` | Laptop + Mini | Manual pull + install | Owns Codex config, Claude MCP baseline, and system health. |
| Warehouse authoring repo | GitHub repo `pnt-data-warehouse` | Laptop + Mini | Manual Git workflow | Not the path used by most installed warehouse launchd jobs. |
| Warehouse production runtime | Live Mini checkout at `~/Production/pnt-data-warehouse-runtime` | Mini | Manual Git workflow on Mini | Current installed warehouse jobs mostly point here. |

## Scheduler, Deploy, State, Log, And Secret Topology

### Scheduler And Deploy Model

| Area | Host | Scheduler / trigger | Deployment model |
|---|---|---|---|
| Personal runtime jobs | Mini | launchd | Mini poller deploys from `automation-runtime-personal` |
| Work runtime jobs | Mini | launchd | Mini poller deploys from `automation-runtime-work` |
| System health | Mini (production); Laptop (optional disabled audit variant) | launchd | Rendered and installed by machine config |
| Vault content | Laptop + Mini + synced devices | Obsidian Sync | Reconciled to Git on Laptop only |
| Warehouse jobs | Mini | launchd | Manual Git workflow; currently split between authoring and production runtime paths |

### State Topology

| State surface | Laptop reality | Mini reality | Notes |
|---|---|---|---|
| `~/Obsidian/personal-os/core/state` | Plain local files in the Laptop checkout | Mixed local files plus symlinks into runtime repos | This is a real host-to-host difference and should be documented, not assumed away. |
| `automation-runtime-personal/core/state` | Local runtime state | Local runtime state | Source of truth for personal-runtime-only state. |
| `automation-runtime-work/core/state` | Local runtime state | Local runtime state | Source of truth for most shared operational state on the Mini. |
| `~/Production/pnt-data-warehouse-runtime/data` | N/A | Local production runtime data | Warehouse production path. |

### Logs

| Area | Primary log location |
|---|---|
| Personal runtime | `~/Projects/automation-runtime-personal/logs/` |
| Work runtime | `~/Projects/automation-runtime-work/logs/` |
| System health | `~/Obsidian/personal-os/logs/` |
| Warehouse | `~/Library/Logs/pnt-data-warehouse/` |

### Secrets And Credentials

| Area | Current pattern |
|---|---|
| Runtime env files | Local-only `config/runtime.env` in runtime repos |
| Claude auth | Local-only under `~/.claude/` |
| Codex config | Rendered locally to `~/.codex/config.toml` |
| Claude MCP baseline | Rendered locally to `~/.mcp.json` |
| Telegram bot config | Local-only JSON outside Git-backed repos |
| Warehouse secrets | Local-only `.env.toast` and runtime token/session files on the Mini |

## Execution Matrix

| Workflow / Tool | Owner | Host | Deterministic work | LLM-backed work | Engine | Model | Model changeability |
|---|---|---|---|---|---|---|---|
| `Codex` | Machine config | Laptop and Mini | Tool startup, MCP transport, local file and shell execution | Interactive engineering and documentation | Codex | `gpt-5.4` | Centrally configurable via `automation-machine-config/codex/config.toml.template` |
| `Claude CLI / Claude Code` | Machine config + local Claude install | Laptop and Mini | CLI transport, MCP routing, local auth/session handling | Headless and interactive reasoning tasks | Claude CLI / Claude Code | Host-local Claude default unless a job pins `--model` | Job-specific; some code-pinned, some env-configurable, some currently implicit |
| `personal-poll-main` | Personal runtime | Mini | Git fetch, fast-forward check, bootstrap, rollback guard | None | None | None | Not applicable |
| `daily-digest` | Personal runtime | Mini | Runtime preflight, context assembly, markdown write, deterministic email send | Digest synthesis | Claude CLI | `claude-opus-4-6` | Code-pinned |
| `meeting-sync` | Personal runtime | Mini | Direct Granola fetch, transcript markdown writes, sync state update, deterministic meeting review helper | Task extraction and transcript interpretation | Claude CLI | `claude-opus-4-6` | Code-pinned |
| `weekly-followup` | Personal runtime | Mini | Report write, deterministic email send | Weekly scan and summary generation | Claude CLI | `claude-opus-4-6` | Code-pinned |
| `monthly-goals-review` | Personal runtime | Mini | Report write, deterministic email send | Goals review synthesis | Claude CLI | `claude-opus-4-6` | Code-pinned |
| `work-poll-main` | Work runtime | Mini | Git fetch, fast-forward check, bootstrap, rollback guard | None | None | None | Not applicable |
| `project-refresh` | Work runtime | Mini | Input collection, batching, state writes | Project brief refresh and contact extraction | Claude CLI | `claude-opus-4-6` by default | Env-configurable via `TRIAGE_V2_PROJECT_REFRESH_MODEL` |
| `email-triage-v2` | Work runtime | Mini | Gmail fetch, queue orchestration, policy/ranking, draft routing, local outbox/Gmail send | Thread enrichment, draft authoring, project-refresh substep | Claude CLI | `claude-opus-4-6` by default | Env-configurable via `TRIAGE_V2_DRAFT_AUTHORING_MODEL` and `TRIAGE_V2_PROJECT_REFRESH_MODEL` |
| `email-monitor` | Work runtime | Mini | Gmail search, state updates, Telegram delivery | Urgency triage and draft decisioning | Claude CLI | `claude-opus-4-6` for main run; `haiku` for failure alert path | Code-pinned |
| `comms-ingest` | Work runtime | Mini | Communication ingest, event log write, state update | None | None | None | Not applicable |
| `pnt-sync` | Work runtime | Mini | State updates, Notion/Gmail transport | Headless comms synthesis and critical-path analysis | Claude CLI | `claude-opus-4-6` for main run; `haiku` for failure alert path | Code-pinned |
| `telegram-bridge` | Work runtime | Mini | Telegram polling, batching, state/log writes | Freeform assistant execution | Claude CLI | `claude-opus-4-6` by default | Env-configurable via `TELEGRAM_BRIDGE_CLAUDE_MODEL` |
| `system-health` | Machine config | Mini (production); Laptop (disabled audit variant) | Launchd audit, runtime checks, state freshness, Telegram alert transport | None | None | None | Not applicable |
| Warehouse ETLs and services | Warehouse runtime | Mini | API pulls, ETLs, reporting, charts, health checks | None observed in the checked-in warehouse runtime | None | None | Not applicable |

## Findings Register

### Open Findings

1. **Warehouse production and authoring checkouts have diverged.**
   Observed Mini state shows different commits in:
   - `~/Projects/pnt-data-warehouse`
   - `~/Production/pnt-data-warehouse-runtime`

2. **Mini machine-config checkout has local drift.**
   `~/Projects/automation-machine-config/bin/system-health.sh` is modified on the Mini, so the live system-health logic does not fully match the Git-backed source of truth.

3. **System-health coverage is still incomplete as an enforcement and validation surface.**
   The inventories now document more of the live Mini service set, but the checking layer still does not fully validate every real live service and runtime path end-to-end.

### Security And Integrity Observations

1. **Vault sharing model is internal-only by default.**
   Files like `core/context/people.md` are Git-tracked in the Vault and should not be treated as safe to hand to external engineers without a separate sanitized package.

2. **Vault state topology differs by host.**
   The Mini uses symlinks for much of `core/state`, while the Laptop currently does not. This is an integrity and debugging risk if documentation assumes one model everywhere.

3. **No obvious tracked runtime secrets were found in the checked repos during this pass.**
   Runtime env files, generated MCP material, `.env.toast`, and token/session files are currently ignored in the Git-backed repos we inspected.

### Operational Cautions

1. The warehouse production/runtime split is now documented, but it is still operationally awkward and should be formally simplified later.
2. Legacy identifiers like `brain` remain in launchd labels, filenames, and helper scripts. This is acceptable for now, but they should not spread into new architecture language.

## Target-State Recommendations

### Approved For This Pass

- Normalize documentation vocabulary to `Laptop`, `Mini`, and `GitHub`.
- Make this file the internal source of truth for system architecture.
- Treat the live Vault as the content source of truth and the Laptop as the Git reconciliation authority for Vault history.
- Keep the raw Vault internal-only and derive external handoff material from it when needed.
- Keep inventories and runbooks aligned to observed live state.
- Explicitly distinguish deterministic workflows from LLM-backed workflows.

### Deferred Until Separate Review

- Choose one canonical warehouse production-runtime path.
- Reconcile warehouse branch policy and live deployment path.
- Expand system-health coverage to the full live Mini service set.
- Decide whether legacy identifiers like `brain` should eventually be renamed in code, filenames, and state keys.

## Migration Backlog

1. **Warehouse runtime formalization**
   - Decide whether `~/Production/pnt-data-warehouse-runtime` stays as the formal production path or is collapsed into a single approved checkout.
2. **Model pinning**
   - Decide whether the remaining `haiku` failure-alert paths should stay on the alias or move to a version-specific pin.
3. **Health coverage expansion**
   - Update system-health and warehouse checks to cover the actual installed Mini services and runtime paths.
