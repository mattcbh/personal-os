# Integrations And Skills Registry

Canonical runtime inventory: `core/architecture/runtime-manifest.yaml`.

## Skills

| Skill | Integration | Command | Primary Output |
|---|---|---|---|
| things-sync | Things | `/things-sync` | Sync markdown tasks with Things 3 |
| meeting-sync | Granola | `/meeting-sync` | Sync meetings to `Knowledge/TRANSCRIPTS/` |
| pnt-sync | Notion/Gmail/Beeper/Granola | `/pnt-sync` | Buildout communications + Notion updates |
| cfo-agent | Supabase | `/cfo-agent` | Weekly/monthly financial analysis |
| health-scorecard | Supabase | `/health` | Business health summary |
| chief-of-staff | Gmail | `/cos` | Inbox triage, drafting, scheduling support |
| sign-document | Gmail | (direct) | Signature + reply workflow |
| share-doc | Google Drive | (direct) | Markdown to Google Doc publishing |
| grocery-sort | Apple Notes | (direct) | Structured grocery organization |
| budget-tracker | Frontend Design | (direct) | UI output for budget workflows |
| extract-locations | Notion | (direct) | Candidate location extraction |

Skill file pattern:
- `core/integrations/<service>/skills/<skill-name>/SKILL.md`

## Integration Directories

- `things/`
- `granola/`
- `notion/`
- `supabase/`
- `gmail/`
- `google-drive/`
- `apple-notes/`
- `frontend-design/`
- `digest/`
- `mcp-servers/`

## MCP Server Notes

Custom server docs are in `mcp-servers/`. Machine-specific runtime config is in `~/.mcp.json`.

## Maintenance Rule

When adding/changing an integration:
1. Update this registry.
2. Update any affected skill files.
3. Update `core/architecture/runtime-manifest.yaml` if runtime behavior changed.
