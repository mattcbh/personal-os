#!/bin/bash
# Legacy convenience wrapper.
# Canonical install path:
#   ~/Projects/automation-machine-config/bin/install-machine-config.sh --role laptop --force

set -e

echo "Setting up MCP servers on MacBook..."

# 1. Create symlink
ln -sf ~/Obsidian/personal-os/core/integrations/mcp-servers ~/mcp-servers
echo "✓ Created symlink: ~/mcp-servers"

if [ -x "$HOME/Projects/automation-machine-config/bin/install-machine-config.sh" ]; then
  "$HOME/Projects/automation-machine-config/bin/install-machine-config.sh" --role laptop --force
  echo "✓ Installed role-based config from automation-machine-config"
else
  echo "automation-machine-config repo not found; skipping role-based config install."
fi

# 3. Clean up old folders if they exist
rm -rf ~/granola-ai-mcp-server ~/claude-mcp 2>/dev/null || true
echo "✓ Cleaned up old MCP folders"

echo ""
echo "Done! Restart Claude Code to use the new MCP servers."
