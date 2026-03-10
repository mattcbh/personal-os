#!/bin/bash
# ensure-superhuman.sh — Pre-flight check: ensure Chrome + Superhuman tabs are ready
#
# Called by email-triage.sh before invoking Claude, so that superhuman-draft.sh
# can assume Chrome is likely ready (it still has its own fallback).
#
# Uses Chrome DevTools Protocol (CDP) as primary path for health checks and tab
# discovery. Falls back to timeout-wrapped osascript if CDP is unavailable.
# Global 30s script timeout prevents infinite hangs.
#
# Steps:
#   1. Check if Chrome is running (CDP first, osascript fallback)
#   2. Launch Chrome with CDP flag if not running
#   3. Check for both Superhuman tabs (work + personal); open any missing
#   4. Wait for new tabs to load
#
# Exit codes:
#   0 — Chrome + Superhuman tabs ready
#   1 — Chrome could not be started

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# --- Global script timeout (30s) ---
( sleep 30; kill -TERM $$ 2>/dev/null ) &
TIMEOUT_PID=$!
trap "kill $TIMEOUT_PID 2>/dev/null" EXIT

LOG_DIR="/Users/homeserver/Obsidian/personal-os/logs"
LOG_FILE="${LOG_DIR}/superhuman-draft.log"
mkdir -p "$LOG_DIR"

log() {
  local level="$1"
  shift
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] [ensure] [$level] $*" | tee -a "$LOG_FILE"
}

# --- Timeout-wrapped osascript ---
run_osascript_timed() {
  local desc="$1"
  local timeout_sec="${2:-5}"
  shift 2
  perl -e "alarm($timeout_sec); exec @ARGV" -- osascript "$@" 2>/dev/null
}

WORK_URL="https://mail.superhuman.com/matt@cornerboothholdings.com"
PERSONAL_URL="https://mail.superhuman.com/lieber.matt@gmail.com"

# --- Step 1: Check if Chrome is running ---
log "INFO" "Checking if Chrome is running..."
chrome_running=false
USE_CDP=false

if "$SCRIPT_DIR/chrome-cdp-helper.sh" health 2>/dev/null; then
  USE_CDP=true
  chrome_running=true
  log "INFO" "Chrome is running (CDP confirmed)"
else
  log "INFO" "CDP not available, trying osascript with 5s timeout..."
  chrome_check=$(run_osascript_timed "Chrome check" 5 \
    -e 'tell application "System Events" to (name of processes) contains "Google Chrome"') || true

  if echo "$chrome_check" | grep -q "true"; then
    chrome_running=true
    log "INFO" "Chrome is running (osascript confirmed, CDP not available)"
  else
    log "WARN" "Chrome is NOT running (result: '${chrome_check}')"
  fi
fi

# --- Step 2: Launch Chrome if needed ---
if [[ "$chrome_running" == "false" ]]; then
  log "INFO" "Launching Chrome with CDP flag..."
  open -a "Google Chrome" "$WORK_URL" "$PERSONAL_URL"

  waited=0
  while [[ $waited -lt 20 ]]; do
    sleep 1
    waited=$((waited + 1))
    if "$SCRIPT_DIR/chrome-cdp-helper.sh" health 2>/dev/null; then
      USE_CDP=true
      chrome_running=true
      log "INFO" "Chrome launched with CDP after ${waited}s"
      break
    fi
  done

  # Fallback to osascript check
  if [[ "$chrome_running" == "false" ]]; then
    check=$(run_osascript_timed "Chrome launch check" 5 \
      -e 'tell application "System Events" to (name of processes) contains "Google Chrome"') || true
    if echo "$check" | grep -q "true"; then
      chrome_running=true
      log "INFO" "Chrome launched (osascript confirmed, CDP not available)"
    fi
  fi

  if [[ "$chrome_running" == "false" ]]; then
    log "ERROR" "Chrome failed to start after 20s"
    exit 1
  fi

  # Both tabs were opened with the launch command, wait for them to load
  log "INFO" "Waiting 10s for Superhuman tabs to load..."
  sleep 10
  log "INFO" "Pre-flight complete (Chrome launched with both tabs)"
  exit 0
fi

# --- Step 3: Check for Superhuman tabs ---
tabs_opened=0

check_and_open_tab() {
  local url_prefix="$1"
  local label="$2"

  log "INFO" "Checking for ${label} Superhuman tab..."

  if [[ "$USE_CDP" == "true" ]]; then
    local tab_id
    tab_id=$("$SCRIPT_DIR/chrome-cdp-helper.sh" find-tab "$url_prefix" 2>/dev/null) || true
    if [[ -n "$tab_id" ]]; then
      log "INFO" "${label} tab present (CDP)"
      return 0
    fi
  else
    local result
    result=$(run_osascript_timed "Check ${label} tab" 10 -e "
tell application \"Google Chrome\"
    repeat with w in windows
        repeat with t in tabs of w
            if URL of t starts with \"${url_prefix}\" then
                return \"found\"
            end if
        end repeat
    end repeat
    return \"not_found\"
end tell") || true

    if echo "$result" | grep -q "found"; then
      log "INFO" "${label} tab present (osascript)"
      return 0
    fi
  fi

  log "WARN" "${label} tab missing, opening..."
  if [[ "$USE_CDP" == "true" ]]; then
    "$SCRIPT_DIR/chrome-cdp-helper.sh" open-tab "$url_prefix" 2>/dev/null || true
  else
    open -a "Google Chrome" "$url_prefix"
  fi
  tabs_opened=$((tabs_opened + 1))
  return 0
}

check_and_open_tab "$WORK_URL" "Work"
check_and_open_tab "$PERSONAL_URL" "Personal"

# --- Step 4: Wait for new tabs to load ---
if [[ $tabs_opened -gt 0 ]]; then
  wait_time=$((tabs_opened * 5))
  log "INFO" "Opened ${tabs_opened} tab(s), waiting ${wait_time}s for load..."
  sleep "$wait_time"
fi

log "INFO" "Pre-flight complete (Chrome ready, ${tabs_opened} tab(s) opened)"
exit 0
