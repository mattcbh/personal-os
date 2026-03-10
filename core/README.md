# Core System

Shared system components for the Personal OS.

## Canonical Docs

- Runtime inventory: `core/architecture/runtime-manifest.yaml`
- Automation docs: `core/automation/README.md`
- Integrations registry: `core/integrations/README.md`
- Policy pack: `core/policies/README.md`

## Directory Map

- `architecture/` - architecture index + runtime manifest
- `automation/` - scripts and launchd plists
- `context/` - focused context docs loaded by tasks/skills
- `integrations/` - service-specific skills and setup notes
- `mcp/` - local MCP server code (legacy and experimental)
- `policies/` - canonical cross-cutting rules
- `state/` - runtime state files

## Change Discipline

When changing behavior:
1. Update the relevant policy file first (if cross-cutting).
2. Update the runtime manifest for schedule/runtime changes.
3. Update only the skills/prompts that depend on that policy.
