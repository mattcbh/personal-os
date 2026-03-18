#!/bin/bash
# Setup script for running automations on the Mac Mini ("brain")
#
# Reference-only legacy helper. Active production launchd rendering now lives in
# the runtime repos under ~/Projects/automation-runtime-personal and
# ~/Projects/automation-runtime-work.
#
# Run this on the brain after syncing Obsidian files:
#   cd ~/Obsidian/personal-os
#   ./core/automation/setup-on-brain.sh

set -e

echo "Setting up automation on brain..."

# Configuration
SCRIPT_DIR="$(dirname "$0")"
PLIST_DIR="${SCRIPT_DIR}/launchd-plists"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
LOGS_DIR="${SCRIPT_DIR}/../../logs"
SCRIPTS=(
    "daily-digest.sh"
    "email-triage.sh"
    "email-triage-v2.sh"
    "project-refresh.sh"
    "email-monitor.sh"
    "comms-ingest.sh"
    "pnt-sync.sh"
    "weekly-followup.sh"
    "meeting-sync.sh"
    "transcript-backfill.sh"
    "telegram-bridge.sh"
)

# All jobs to install
PLISTS=(
    "com.matthewlieber.daily-digest"
    "com.brain.comms-ingest"
    "com.brain.pnt-sync"
    "com.brain.meeting-sync"
    "com.brain.email-triage-v2-morning"
    "com.brain.email-triage-v2-evening"
    "com.brain.email-monitor"
    "com.brain.project-refresh-morning"
    "com.brain.project-refresh-evening"
    "com.brain.weekly-followup"
    "com.brain.telegram-bridge"
    "com.brain.transcript-backfill"
)

LEGACY_PLISTS=(
    "com.brain.email-triage-morning"
    "com.brain.email-triage-evening"
)

# 1. Check Claude is installed
echo ""
echo "1. Checking Claude CLI..."
if command -v claude &> /dev/null; then
    CLAUDE_PATH=$(which claude)
    echo "   Found: $CLAUDE_PATH"
else
    echo "   ERROR: Claude CLI not found. Install it first:"
    echo "   https://docs.anthropic.com/claude-code/getting-started"
    exit 1
fi

# 2. Create logs directory
echo ""
echo "2. Creating logs directory..."
mkdir -p "$LOGS_DIR"
echo "   Created: $LOGS_DIR"

# 3. Install all launchd plists
echo ""
echo "3. Installing launchd plists..."
for LABEL in "${PLISTS[@]}"; do
    SOURCE="${PLIST_DIR}/${LABEL}.plist"
    DEST="${LAUNCH_AGENTS_DIR}/${LABEL}.plist"

    if [ -f "$SOURCE" ]; then
        if [ -f "$DEST" ] && cmp -s "$SOURCE" "$DEST"; then
            echo "   Up to date: $LABEL"
        else
            cp "$SOURCE" "$DEST"
            echo "   Installed: $LABEL"
        fi
    else
        echo "   WARNING: Plist not found: $SOURCE"
    fi
done

echo ""
echo "3b. Removing legacy triage v1 plists..."
for LABEL in "${LEGACY_PLISTS[@]}"; do
    DEST="${LAUNCH_AGENTS_DIR}/${LABEL}.plist"
    if [ -f "$DEST" ]; then
        launchctl unload "$DEST" 2>/dev/null || true
        rm -f "$DEST"
        echo "   Removed legacy: $LABEL"
    else
        echo "   Not present: $LABEL"
    fi
done

# 4. Ensure scripts are executable (Obsidian Sync does not preserve mode bits)
echo ""
echo "4. Ensuring script permissions..."
for SCRIPT_NAME in "${SCRIPTS[@]}"; do
    SCRIPT_PATH="${SCRIPT_DIR}/${SCRIPT_NAME}"
    if [ -f "$SCRIPT_PATH" ]; then
        chmod +x "$SCRIPT_PATH"
        echo "   Executable: $SCRIPT_NAME"
    else
        echo "   WARNING: Script not found: $SCRIPT_PATH"
    fi
done

# 5. Load all jobs
echo ""
echo "5. Loading launchd jobs..."
for LABEL in "${PLISTS[@]}"; do
    DEST="${LAUNCH_AGENTS_DIR}/${LABEL}.plist"
    if [ -f "$DEST" ]; then
        launchctl unload "$DEST" 2>/dev/null || true
        launchctl load "$DEST"
        echo "   Loaded: $LABEL"
    fi
done

# 6. Verify
echo ""
echo "6. Verifying..."
for LABEL in "${PLISTS[@]}"; do
    SHORT_NAME=$(echo "$LABEL" | sed 's/com\.\(matthewlieber\|brain\|pnt\)\.//')
    if launchctl list 2>/dev/null | grep -q "$LABEL"; then
        echo "   OK: $LABEL"
    else
        echo "   WARNING: $LABEL may not be loaded correctly"
    fi
done

# 7. Remind about MCP setup
echo ""
echo "========================================"
echo "NEXT STEPS (manual):"
echo "========================================"
echo ""
echo "1. Verify MCP servers are configured:"
echo "   claude mcp list"
echo ""
echo "2. If Gmail/Calendar MCPs are missing, add them:"
echo "   claude mcp add gmail"
echo "   claude mcp add google-calendar"
echo ""
echo "3. Test manually to authenticate OAuth:"
echo "   cd ~/Obsidian/personal-os"
echo "   claude -p 'Show me my daily digest'"
echo ""
echo "4. Schedule overview:"
echo "   5:00 AM  - Daily Digest (industry news + calendar)"
echo "   5:35 AM  - Project Refresh (email + Beeper + Granola context into project briefs)"
echo "   6:00 AM  - Email Triage v2 Morning (queue-backed inbox triage)"
echo "   8AM-6PM - Email Monitor (urgent email alerts via Telegram, every 2hrs)"
echo "   Every 30m - Comms Ingest (email + Beeper event log)"
echo "   Always  - Telegram Bridge (two-way Claude Code via Telegram)"
echo "   4:00 PM  - PnT Buildout Sync (comms + Notion log)"
echo "   3:00 PM  - Email Triage v2 Evening (queue-backed inbox triage)"
echo "   2:35 PM  - Project Refresh (PM context refresh before triage)"
echo "   8:30AM-8:30PM - Transcript Backfill (every 2hrs, 3 transcripts/batch)"
echo "   9:00 PM  - Meeting Sync (Granola transcripts + task extraction)"
echo ""
echo "Setup complete!"
