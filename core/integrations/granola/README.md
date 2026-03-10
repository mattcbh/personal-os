# Granola Integration

Sync Granola meetings into local transcript files.

## Canonical Paths

- Transcript folder: `Knowledge/TRANSCRIPTS/`
- Sync state: `core/state/granola-sync.json`
- Skill: `core/integrations/granola/skills/meeting-sync/SKILL.md`

## MCP Setup

Granola MCP endpoint in `~/.mcp.json`:

```json
{
  "mcpServers": {
    "granola": {
      "command": "npx",
      "args": ["-y", "mcp-remote", "https://mcp.granola.ai/mcp"]
    }
  }
}
```

## Workflow

1. List recent meetings from MCP
2. Compare against `core/state/granola-sync.json`
3. Sync selected meetings to `Knowledge/TRANSCRIPTS/`
4. Extract task candidates and optionally push selected tasks to Things
