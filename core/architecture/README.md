# Architecture Index

## Primary Sources Of Truth

- System-of-record matrix and edit routing: `core/architecture/source-of-truth.md`
- PnT runtime inventory: `core/architecture/pnt-runtime-inventory.md`
- PnT operator runbook: `core/architecture/pnt-operator-runbook.md`
- Runtime inventory: `core/architecture/runtime-manifest.yaml`
- Automation details: `core/automation/README.md`
- Integration and skills registry: `core/integrations/README.md`
- Policy pack: `core/policies/README.md`

## Related Context Files

- `core/context/data-warehouse.md`
- `core/context/financial-analysis.md`
- `core/context/mcp-reference.md`

## Update Rule

When architecture changes, update these in the same commit:
1. `core/architecture/runtime-manifest.yaml`
2. `core/architecture/source-of-truth.md`, `core/architecture/pnt-runtime-inventory.md`, or `core/architecture/pnt-operator-runbook.md` when the control plane or PnT runtime changes
3. The corresponding subsystem README (automation/integrations/etc.)
4. Any impacted policy file in `core/policies/`
