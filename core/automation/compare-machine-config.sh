#!/bin/bash
# Compare machine config - run on brain, compare output to laptop
# Usage: bash compare-machine-config.sh

echo "=========================================="
echo "MACHINE CONFIG REPORT"
echo "Host: $(hostname)"
echo "Date: $(date)"
echo "=========================================="

echo ""
echo "=== 1. ~/.claude/settings.json (model + plugins) ==="
if [ -f ~/.claude/settings.json ]; then
    cat ~/.claude/settings.json
else
    echo "FILE NOT FOUND"
fi

echo ""
echo "=== 2. ~/.claude/settings.local.json (permissions + MCP) ==="
if [ -f ~/.claude/settings.local.json ]; then
    cat ~/.claude/settings.local.json
else
    echo "FILE NOT FOUND"
fi

echo ""
echo "=== 3. ~/.mcp.json (MCP server definitions) ==="
if [ -f ~/.mcp.json ]; then
    cat ~/.mcp.json
else
    echo "FILE NOT FOUND"
fi

echo ""
echo "=== 4. ~/.claude/CLAUDE.md (global instructions) ==="
if [ -f ~/.claude/CLAUDE.md ]; then
    cat ~/.claude/CLAUDE.md
else
    echo "FILE NOT FOUND"
fi

echo ""
echo "=== 5. ~/.claude/skills/ (skill symlinks) ==="
if [ -d ~/.claude/skills ]; then
    ls -la ~/.claude/skills/
else
    echo "DIRECTORY NOT FOUND"
fi

echo ""
echo "=== 6. ~/mcp-servers symlink ==="
if [ -L ~/mcp-servers ]; then
    echo "Symlink exists, points to: $(readlink ~/mcp-servers)"
elif [ -d ~/mcp-servers ]; then
    echo "Directory exists (not a symlink)"
    ls -la ~/mcp-servers/
else
    echo "NOT FOUND"
fi

echo ""
echo "=== 7. Personal info files ==="
for f in ~/.claude/matt-personal-info.md ~/.claude/sarah-personal-info.md ~/.claude/corner-booth-holdings-context.md; do
    if [ -f "$f" ]; then
        echo "EXISTS: $f"
    else
        echo "MISSING: $f"
    fi
done

echo ""
echo "=== 8. Obsidian vault location ==="
if [ -d ~/Obsidian/personal-os ]; then
    echo "Found: ~/Obsidian/personal-os"
elif [ -d ~/Library/Mobile\ Documents/iCloud~md~obsidian/Documents/personal-os ]; then
    echo "Found: ~/Library/Mobile Documents/iCloud~md~obsidian/Documents/personal-os (iCloud)"
else
    echo "NOT FOUND in expected locations"
    echo "Searching..."
    find ~ -maxdepth 4 -type d -name "personal-os" 2>/dev/null | head -3
fi

echo ""
echo "=== 9. Google Drive mounted? ==="
if [ -d ~/Library/CloudStorage/GoogleDrive-matt@cornerboothholdings.com ]; then
    echo "YES - Google Drive is mounted"
else
    echo "NO - Google Drive not found"
fi

echo ""
echo "=== 10. Claude CLI version ==="
if command -v claude &> /dev/null; then
    claude --version 2>/dev/null || echo "Installed but version unknown"
else
    echo "NOT INSTALLED"
fi

echo ""
echo "=========================================="
echo "END REPORT"
echo "=========================================="
