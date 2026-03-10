#!/bin/bash
#
# Things 3 ↔ Obsidian Sync
#
# Syncs tasks between Things 3 and Obsidian markdown files.
# Uses direct SQLite access (no AppleScript required).
#
# Default behavior: Push new tasks to Things, then pull all tasks to Obsidian
#
# Usage:
#   ./sync_all.sh [--dry-run] [--list LIST] [--pull-only] [--push-only]
#

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VAULT_DIR="$(dirname "$(dirname "$(dirname "$SCRIPT_DIR")")")"

cd "$VAULT_DIR"

# Parse arguments
DRY_RUN=""
LIST_ARG=""
PULL_ONLY=false
PUSH_ONLY=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN="--dry-run"
            shift
            ;;
        --list)
            LIST_ARG="--list $2"
            shift 2
            ;;
        --pull-only)
            PULL_ONLY=true
            shift
            ;;
        --push-only)
            PUSH_ONLY=true
            shift
            ;;
        *)
            shift
            ;;
    esac
done

# Push new tasks and completions from Obsidian to Things (unless pull-only)
if [ "$PULL_ONLY" = false ]; then
    echo "Pushing new tasks and completions to Things..."
    python3 "$SCRIPT_DIR/things_sync.py" --push $DRY_RUN
    echo ""
    # Wait for Things to write changes to database
    sleep 2
fi

# Pull tasks from Things to Obsidian (unless push-only)
if [ "$PUSH_ONLY" = false ]; then
    echo "Pulling tasks from Things..."
    python3 "$SCRIPT_DIR/things_sync.py" $DRY_RUN $LIST_ARG
fi

echo ""
echo "Sync complete."
