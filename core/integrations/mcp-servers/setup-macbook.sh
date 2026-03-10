#!/bin/bash
# Run this script on your MacBook to set up MCP servers
# Usage: bash ~/Obsidian/personal-os/core/integrations/mcp-servers/setup-macbook.sh

set -e

echo "Setting up MCP servers on MacBook..."

# 1. Create symlink
ln -sf ~/Obsidian/personal-os/core/integrations/mcp-servers ~/mcp-servers
echo "✓ Created symlink: ~/mcp-servers"

# 2. Create config file
cat > ~/.mcp.json << 'MCPCONFIG'
{
  "mcpServers": {
    "notion": {
      "command": "npx",
      "args": ["-y", "mcp-remote", "https://mcp.notion.com/mcp"]
    },
    "granola": {
      "command": "npx",
      "args": ["-y", "mcp-remote", "https://mcp.granola.ai/mcp"]
    },
    "contacts": {
      "command": "uv",
      "args": [
        "--directory",
        "/Users/matthewlieber/mcp-servers/contacts",
        "run",
        "--python",
        "3.12",
        "contacts-mcp-server"
      ]
    }
  }
}
MCPCONFIG
echo "✓ Created config: ~/.mcp.json"

# 3. Clean up old folders if they exist
rm -rf ~/granola-ai-mcp-server ~/claude-mcp 2>/dev/null || true
echo "✓ Cleaned up old MCP folders"

echo ""
echo "Done! Restart Claude Code to use the new MCP servers."
