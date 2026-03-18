# Automation

This Vault is the documentation, prompts, shared skills, and helper-script surface for the automation system. It is not the source of truth for scheduled runtime code.

Canonical system narrative: `core/architecture/system-architecture.md`.
Edit and deploy routing: `core/architecture/source-of-truth.md`.
Canonical runtime inventory: `core/architecture/runtime-manifest.yaml`.
Warehouse runtime inventory: `core/architecture/pnt-runtime-inventory.md`.
Warehouse operator runbook: `core/architecture/pnt-operator-runbook.md`.

## Operator Summary

- Production scheduling is Mini-only.
- Vault content syncs through Obsidian Sync. The Laptop is the Git reconciliation authority for Vault history.
- GitHub is the source of truth for `automation-runtime-personal`, `automation-runtime-work`, `automation-machine-config`, and the warehouse authoring repo.
- `system-health` is a Mini production workflow with an optional disabled Laptop audit variant.
- The raw Vault is internal-only by default. Create a sanitized handoff for external engineers instead of sharing the live Vault.

## Where To Edit

- **Vault docs, prompts, context, and skills:** edit in the Vault at `~/Obsidian/personal-os`
- **Runtime job logic:** edit in `automation-runtime-personal` or `automation-runtime-work`
- **Machine-local config and MCP defaults:** edit in `automation-machine-config`
- **Git history for the Vault repo:** reconcile and commit from the Laptop checkout only

## Drift Guardrail

If you add or remove a workflow, update the canonical docs in the same change:
1. `core/architecture/system-architecture.md`
2. `core/architecture/runtime-manifest.yaml`
