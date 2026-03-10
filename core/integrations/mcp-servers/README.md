# MCP Servers

Model Context Protocol (MCP) servers that extend Claude Code with additional capabilities.

## Structure

```
mcp-servers/
├── credentials/     # OAuth keys and secrets (DO NOT commit to git)
├── google/          # Google MCP server (Calendar, Gmail, Drive)
└── contacts/        # Contacts lookup MCP server
```

## Setup

This folder syncs via Obsidian Sync. On each machine, create a symlink:

```bash
ln -sf ~/Obsidian/personal-os/core/integrations/mcp-servers ~/mcp-servers
```

## Configuration

Each machine needs its own `~/.mcp.json` file because paths include the username. Run the setup script for your machine:

```bash
bash ~/Obsidian/personal-os/core/integrations/mcp-servers/setup-macbook.sh
```

Remote MCP servers (Granola, Notion) use the same config on all machines. Local servers (Contacts) need machine-specific paths.

## Available Servers

### Google (`google/`)
Google Workspace integration (Calendar, Gmail, Drive).

**Requires:** OAuth credentials in home directories (not in vault):
- `~/.gmail-mcp/gcp-oauth.keys.json`
- `~/.gmail-mcp-personal/gcp-oauth.keys.json` (for personal account server)
- `~/.gmail-mcp/token.json`
- `~/.gmail-mcp-personal/token.json`
- `gws` CLI installed: `npm install -g @googleworkspace/cli`

The local `google-mcp-server` keeps the existing MCP tool names (`gmail_search`, `gmail_send`, `calendar_list_events`, etc.) but routes requests through `gws` under the hood.

### Contacts (`contacts/`)
Local contacts lookup for phone numbers and emails.

### Remote MCP Servers (no local code)

These are configured in `~/.mcp.json` but have no local server code:
- **Granola** - Meeting notes via `https://mcp.granola.ai/mcp`
- **Notion** - Notes via `https://mcp.notion.com/mcp`

## Adding New Servers

1. Clone or create the server in this folder
2. Add configuration to `~/.mcp.json` on each machine
3. Restart Claude Code to pick up changes
