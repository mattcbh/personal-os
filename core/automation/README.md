# Automation

This directory holds Vault-side automation docs, prompt templates, shared helper scripts, and reference material. It is not the canonical inventory for scheduled runtime behavior.

Canonical system narrative: `core/architecture/system-architecture.md`.
Edit and deploy routing: `core/architecture/source-of-truth.md`.
Canonical runtime inventory: `core/architecture/runtime-manifest.yaml`.
Warehouse runtime inventory: `core/architecture/pnt-runtime-inventory.md`.
Warehouse operator runbook: `core/architecture/pnt-operator-runbook.md`.

## Operator Summary

- Production scheduling is Mini-only.
- Vault content syncs through Obsidian Sync. The Laptop is the Git reconciliation authority for Vault history.
- Runtime code lives in `automation-runtime-personal`, `automation-runtime-work`, or the warehouse codebase, not in this directory.
- `system-health` is a Mini production workflow with an optional disabled Laptop audit variant.
- The raw Vault is internal-only by default. Create a sanitized handoff for external engineers instead of sharing the live Vault.

## Files In This Directory

Prompt templates and docs referenced by runtime scripts:
- `comms-ingest-prompt.md` — prompt template for comms ingest
- `email-triage-prompt.md` — prompt template for email triage v1
- `email-triage-runbook.md`, `email-triage-v2-runbook.md` — reference runbooks; execute v2 commands from `automation-runtime-work`
- `email-triage-contract.json` — triage contract schema

Local helper scripts:
- `superhuman-draft.sh` — queue-first draft writer
- `superhuman-draft-watcher.sh` — queue processor for Superhuman UI automation
- `superhuman-draft-status.py` — draft status checker
- `ensure-superhuman.sh` — browser/session prep (archived)
- `chrome-cdp-helper.sh` — CDP helper utilities
- `compare-machine-config.sh` — environment diff utility
- `setup-on-brain.sh`, `setup-email-triage-v2-on-brain.sh` — one-time setup scripts

## Drift Guardrail

If you add or remove a workflow, update the canonical docs in the same change:
1. `core/architecture/system-architecture.md`
2. `core/architecture/runtime-manifest.yaml`
