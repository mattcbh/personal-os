# Architecture Index

## Primary Sources Of Truth

- System-of-record matrix and edit routing: `core/architecture/source-of-truth.md`
- PnT runtime inventory: `core/architecture/pnt-runtime-inventory.md`
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
2. `core/architecture/source-of-truth.md` or `core/architecture/pnt-runtime-inventory.md` when the control plane or PnT runtime changes
3. The corresponding subsystem README (automation/integrations/etc.)
4. Any impacted policy file in `core/policies/`
