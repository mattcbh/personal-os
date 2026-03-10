#!/bin/bash
# Cut over launchd scheduling from email-triage v1 to email-triage v2.

set -euo pipefail

ROOT="/Users/homeserver/Obsidian/personal-os"
PLIST_DIR="${ROOT}/core/automation/launchd-plists"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"

OLD_LABELS=(
  "com.brain.email-triage-morning"
  "com.brain.email-triage-evening"
)

NEW_LABELS=(
  "com.brain.email-triage-v2-morning"
  "com.brain.email-triage-v2-evening"
  "com.brain.project-refresh-morning"
  "com.brain.project-refresh-evening"
)

echo "Installing triage v2 plists..."
for label in "${NEW_LABELS[@]}"; do
  src="${PLIST_DIR}/${label}.plist"
  dst="${LAUNCH_AGENTS_DIR}/${label}.plist"
  if [ ! -f "$src" ]; then
    echo "Missing plist: $src" >&2
    exit 1
  fi
  cp "$src" "$dst"
  echo "  installed: $label"
done

echo "Unloading triage v1 jobs..."
for label in "${OLD_LABELS[@]}"; do
  dst="${LAUNCH_AGENTS_DIR}/${label}.plist"
  if [ -f "$dst" ]; then
    launchctl unload "$dst" 2>/dev/null || true
    echo "  unloaded: $label"
  else
    echo "  skipped (not installed): $label"
  fi
done

echo "Loading triage v2 jobs..."
for label in "${NEW_LABELS[@]}"; do
  dst="${LAUNCH_AGENTS_DIR}/${label}.plist"
  launchctl unload "$dst" 2>/dev/null || true
  launchctl load "$dst"
  echo "  loaded: $label"
done

echo "Current triage launchd status:"
launchctl list | rg "email-triage(-v2)?" || true

echo "Cutover complete."
