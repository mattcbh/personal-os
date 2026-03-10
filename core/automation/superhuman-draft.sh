#!/bin/bash
# superhuman-draft.sh — Create a draft in Superhuman (Chrome) via keyboard automation
#
# Reply mode (existing):
#   superhuman-draft.sh <thread_id> <draft_text> [account_email]
#
# Compose mode (new messages):
#   superhuman-draft.sh --new "<to_addresses>" "<subject>" "<draft_text>" [account_email]
#
# Queue mode (decoupled from Claude's process tree):
#   superhuman-draft.sh --queue <thread_id> <draft_text> [account_email]
#   superhuman-draft.sh --queue --new "<to_addresses>" "<subject>" "<draft_text>" [account_email]
#   Writes a JSON request to /tmp/superhuman-draft-queue/ and exits immediately.
#   The superhuman-draft-watcher.sh process picks up and executes the draft.
#
# Reply mode creates a reply draft by:
#   1. Ensures Chrome is running with the correct Superhuman tab
#   2. Switches to the Superhuman Chrome tab for the account
#   3. Navigates to the thread via Cmd+L address bar (preserves SPA routing)
#   4. Presses Shift+R to open Reply All compose
#   5. Pastes draft text from clipboard
#   6. Escapes compose (auto-saves draft) and navigates back to inbox
#
# Compose mode creates a new message draft by:
#   1. Ensures Chrome is running with the correct Superhuman tab
#   2. Switches to the Superhuman Chrome tab for the account
#   3. Dismisses any open compose window, then presses c to open Compose
#   4. Types the To recipients (comma-separated)
#   5. Tabs to Subject and types/pastes the subject line
#   6. Tabs to Body and pastes the body text
#   7. Escapes compose (auto-saves draft) and navigates back to inbox
#
# Self-healing: If Chrome is not running or the tab is missing, attempts recovery
# before falling back to clipboard-only mode. All steps are logged.
#
# Reliability: Uses Chrome DevTools Protocol (CDP) as primary path for tab discovery
# and health checks. AppleScript (osascript) is used only for keystrokes, with strict
# 5-second timeouts via perl alarm(). Global 120s script timeout prevents infinite hangs.
#
# Arguments (reply mode):
#   thread_id       — Gmail thread ID (hex string, e.g. "18e1a2b3c4d5e6f7")
#   draft_text      — The reply body to paste
#   account_email   — (optional) matt@cornerboothholdings.com (default) or lieber.matt@gmail.com
#
# Arguments (compose mode):
#   --new           — Flag to enable compose mode
#   to_addresses    — Comma-separated recipient emails (e.g. "a@b.com,c@d.com")
#   subject         — Email subject line
#   draft_text      — The message body to paste
#   account_email   — (optional) matt@cornerboothholdings.com (default) or lieber.matt@gmail.com
#
# Exit codes:
#   0 — Draft pasted successfully (or clipboard fallback used)
#   1 — Missing arguments

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
STATUS_SCRIPT="${SCRIPT_DIR}/superhuman-draft-status.py"

# --- Global script timeout (120s) ---
# Prevents the entire script from hanging indefinitely (the 33-minute failure).
( sleep 120; kill -TERM $$ 2>/dev/null ) &
TIMEOUT_PID=$!
trap "kill $TIMEOUT_PID 2>/dev/null" EXIT

# --- Logging ---
LOG_DIR="/Users/homeserver/Obsidian/personal-os/logs"
LOG_FILE="${LOG_DIR}/superhuman-draft.log"
mkdir -p "$LOG_DIR"

log() {
  local level="$1"
  shift
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] [$level] $*" | tee -a "$LOG_FILE"
}

record_draft_status() {
  local status="$1"
  local note="${2:-}"
  local request_id="${SUPERHUMAN_DRAFT_REQUEST_ID:-}"
  if [[ ! -x "$STATUS_SCRIPT" ]]; then
    return 0
  fi
  if [[ "$MODE" == "reply" ]] && [[ -n "${THREAD_ID:-}" ]]; then
    python3 "$STATUS_SCRIPT" record \
      --mode reply \
      --status "$status" \
      --request-id "$request_id" \
      --account "$ACCOUNT" \
      --thread-id "$THREAD_ID" \
      --note "$note" >/dev/null 2>&1 || true
  else
    python3 "$STATUS_SCRIPT" record \
      --mode compose \
      --status "$status" \
      --request-id "$request_id" \
      --account "$ACCOUNT" \
      --note "$note" >/dev/null 2>&1 || true
  fi
}

# --- Mode detection ---
MODE="reply"
USE_QUEUE=false
if [[ "${1:-}" == "--queue" ]]; then
  USE_QUEUE=true
  shift
fi
if [[ "${1:-}" == "--new" ]]; then
  MODE="compose"
  shift
fi

# --- Arguments ---
if [[ "$MODE" == "compose" ]]; then
  TO_ADDRESSES="${1:-}"
  SUBJECT="${2:-}"
  DRAFT_TEXT="${3:-}"
  ACCOUNT="${4:-matt@cornerboothholdings.com}"

  if [[ -z "$TO_ADDRESSES" || -z "$SUBJECT" || -z "$DRAFT_TEXT" ]]; then
    echo "Usage: superhuman-draft.sh --new \"<to_addresses>\" \"<subject>\" \"<draft_text>\" [account_email]"
    exit 1
  fi

  log "INFO" "Starting COMPOSE draft creation to=${TO_ADDRESSES} subject='${SUBJECT}' account=${ACCOUNT}"
else
  THREAD_ID="${1:-}"
  DRAFT_TEXT="${2:-}"
  ACCOUNT="${3:-matt@cornerboothholdings.com}"

  if [[ -z "$THREAD_ID" || -z "$DRAFT_TEXT" ]]; then
    echo "Usage: superhuman-draft.sh <thread_id> <draft_text> [account_email]"
    exit 1
  fi

  THREAD_URL="https://mail.superhuman.com/${ACCOUNT}/thread/${THREAD_ID}"
  log "INFO" "Starting REPLY draft creation for thread=${THREAD_ID} account=${ACCOUNT}"
fi

ACCOUNT_BASE="https://mail.superhuman.com/${ACCOUNT}"
SUPERHUMAN_BASE="https://mail.superhuman.com/"

# --- Queue mode: write request to file and exit ---
if [[ "$USE_QUEUE" == "true" ]]; then
  QUEUE_DIR="/tmp/superhuman-draft-queue"
  mkdir -p "$QUEUE_DIR"
  REQUEST_ID="$(uuidgen | tr '[:upper:]' '[:lower:]')"
  export SUPERHUMAN_DRAFT_REQUEST_ID="$REQUEST_ID"
  QUEUE_FILE="${QUEUE_DIR}/$(date +%s)-$(uuidgen | tr '[:upper:]' '[:lower:]').json"

  # Escape draft text for JSON (handle newlines, quotes, backslashes)
  DRAFT_TEXT_ESCAPED=$(printf '%s' "$DRAFT_TEXT" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))')

  if [[ "$MODE" == "compose" ]]; then
    SUBJECT_ESCAPED=$(printf '%s' "$SUBJECT" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))')
    cat > "$QUEUE_FILE" <<QEOF
{"mode":"compose","to":"$TO_ADDRESSES","subject":${SUBJECT_ESCAPED},"draft_text":${DRAFT_TEXT_ESCAPED},"account":"$ACCOUNT","request_id":"$REQUEST_ID","timestamp":"$(date -Iseconds)"}
QEOF
  else
    cat > "$QUEUE_FILE" <<QEOF
{"mode":"reply","thread_id":"$THREAD_ID","draft_text":${DRAFT_TEXT_ESCAPED},"account":"$ACCOUNT","request_id":"$REQUEST_ID","timestamp":"$(date -Iseconds)"}
QEOF
  fi

  record_draft_status "queued_pending" "Queued for watcher execution"
  log "INFO" "QUEUE: Draft queued to $QUEUE_FILE (mode=$MODE, account=$ACCOUNT)"
  echo "QUEUED: $QUEUE_FILE"
  echo "Draft queued: $QUEUE_FILE"
  echo "The draft watcher will process it shortly."
  exit 0
fi

# --- Timeout-wrapped osascript ---
# Replaces the old run_osascript that had no timeout protection.
# Uses perl alarm() to kill osascript if it exceeds timeout_sec (default 5s).
# Falls back to one retry with 2s backoff on failure.
run_osascript_timed() {
  local desc="$1"
  local timeout_sec="${2:-5}"
  shift 2
  local output err_output exit_code

  # First attempt
  err_output=$(mktemp)
  if output=$(perl -e "alarm($timeout_sec); exec @ARGV" -- osascript "$@" 2>"$err_output"); then
    local err_content
    err_content=$(cat "$err_output")
    rm -f "$err_output"
    [[ -n "$err_content" ]] && log "WARN" "${desc}: stderr: ${err_content}"
    echo "$output"
    return 0
  fi
  exit_code=$?
  local err_content
  err_content=$(cat "$err_output")
  rm -f "$err_output"
  log "WARN" "${desc}: failed (exit ${exit_code}, timeout=${timeout_sec}s), stderr: ${err_content}. Retrying in 2s..."

  # Retry after backoff
  sleep 2
  err_output=$(mktemp)
  if output=$(perl -e "alarm($timeout_sec); exec @ARGV" -- osascript "$@" 2>"$err_output"); then
    local err_content2
    err_content2=$(cat "$err_output")
    rm -f "$err_output"
    [[ -n "$err_content2" ]] && log "WARN" "${desc} retry: stderr: ${err_content2}"
    log "INFO" "${desc}: succeeded on retry"
    echo "$output"
    return 0
  fi
  exit_code=$?
  err_content=$(cat "$err_output")
  rm -f "$err_output"
  log "ERROR" "${desc}: failed on retry (exit ${exit_code}), stderr: ${err_content}"
  return $exit_code
}

# --- Clipboard fallback helper ---
clipboard_fallback() {
  printf '%s' "$DRAFT_TEXT" | pbcopy
  record_draft_status "clipboard" "$1"
  log "WARN" "FALLBACK: Draft copied to clipboard only. $1"
  echo "FALLBACK: $1"
  echo "Draft copied to clipboard."
  if [[ "$MODE" == "compose" ]]; then
    echo "Open Superhuman, press c (Compose), fill in To/Subject, then Cmd+V to paste body."
  else
    echo "Open the thread in Superhuman, press r (Reply), then Cmd+V to paste."
  fi
  exit 0
}

# --- Step 1: Check if Chrome is running (pgrep first, CDP, osascript fallback) ---
log "INFO" "Step 1: Checking if Chrome is running..."
chrome_running=false
USE_CDP=false

# Fast check: pgrep needs no macOS Automation permissions
if pgrep -q "Google Chrome"; then
  chrome_running=true
  log "INFO" "Step 1: Chrome is running (pgrep confirmed)"

  # Try CDP for tab operations
  if "$SCRIPT_DIR/chrome-cdp-helper.sh" health 2>/dev/null; then
    USE_CDP=true
    log "INFO" "Step 1: CDP also available"
  fi
else
  log "INFO" "Step 1: Chrome is NOT running (pgrep)"
  # Try CDP as a secondary check (pgrep might miss helper process names)
  if "$SCRIPT_DIR/chrome-cdp-helper.sh" health 2>/dev/null; then
    USE_CDP=true
    chrome_running=true
    log "INFO" "Step 1: Chrome is running (CDP confirmed, pgrep missed it)"
  fi
fi

# --- Step 2: Self-healing — launch Chrome if not running ---
if [[ "$chrome_running" == "false" ]]; then
  log "INFO" "Step 2: Attempting to launch Chrome with CDP flag and Superhuman tabs..."
  open -a "Google Chrome" "https://mail.superhuman.com/matt@cornerboothholdings.com" \
                          "https://mail.superhuman.com/lieber.matt@gmail.com"

  # Wait up to 15s for Chrome to start, check via CDP first
  waited=0
  while [[ $waited -lt 15 ]]; do
    sleep 1
    waited=$((waited + 1))
    if "$SCRIPT_DIR/chrome-cdp-helper.sh" health 2>/dev/null; then
      USE_CDP=true
      chrome_running=true
      log "INFO" "Step 2: Chrome launched with CDP after ${waited}s"
      log "INFO" "Step 2: Waiting 10s for Superhuman tabs to load..."
      sleep 10
      break
    fi
  done

  # If CDP still not available, try osascript check
  if [[ "$chrome_running" == "false" ]]; then
    check=$(run_osascript_timed "Chrome launch check" 5 \
      -e 'tell application "System Events" to (name of processes) contains "Google Chrome"' 2>/dev/null) || true
    if echo "$check" | grep -q "true"; then
      chrome_running=true
      log "INFO" "Step 2: Chrome launched (osascript confirmed, CDP not available)"
      sleep 10
    fi
  fi

  if [[ "$chrome_running" == "false" ]]; then
    log "ERROR" "Step 2: Chrome failed to launch after 15s"
    clipboard_fallback "Chrome could not be started."
  fi
fi

# --- Step 3: Find the Superhuman tab for this account ---
tab_found=false

if [[ "$USE_CDP" == "true" ]]; then
  log "INFO" "Step 3: Finding Superhuman tab via CDP (${ACCOUNT_BASE})..."
  TAB_ID=$("$SCRIPT_DIR/chrome-cdp-helper.sh" find-tab "$ACCOUNT_BASE" 2>/dev/null) || true
  if [[ -z "$TAB_ID" ]]; then
    # Superhuman often redirects to generic, non-account-scoped URLs.
    TAB_ID=$("$SCRIPT_DIR/chrome-cdp-helper.sh" find-tab "$SUPERHUMAN_BASE" 2>/dev/null) || true
  fi

  if [[ -n "$TAB_ID" ]]; then
    log "INFO" "Step 3: Found tab via CDP (id=${TAB_ID})"
    "$SCRIPT_DIR/chrome-cdp-helper.sh" activate "$TAB_ID" 2>/dev/null || true
    tab_found=true
    # Also bring Chrome to front via osascript (CDP activate only switches tabs, not app focus)
    run_osascript_timed "Activate Chrome app" 5 \
      -e 'tell application "Google Chrome" to activate' 2>/dev/null || true
  else
    log "WARN" "Step 3: Tab not found via CDP, trying osascript fallback..."
  fi
fi

if [[ "$tab_found" == "false" ]]; then
  log "INFO" "Step 3: Finding Superhuman tab via osascript (${ACCOUNT_BASE})..."
  tab_result=$(run_osascript_timed "Find Superhuman tab" 10 -e "
tell application \"Google Chrome\"
    activate
    set found to false
    set foundInfo to \"none\"
    repeat with w in windows
        set tabIndex to 0
        repeat with t in tabs of w
            set tabIndex to tabIndex + 1
            if URL of t starts with \"${ACCOUNT_BASE}\" or URL of t starts with \"${SUPERHUMAN_BASE}\" then
                set active tab index of w to tabIndex
                set index of w to 1
                set found to true
                set foundInfo to (URL of t)
                exit repeat
            end if
        end repeat
        if found then exit repeat
    end repeat
    if found then
        return \"FOUND:\" & foundInfo
    else
        return \"NOT_FOUND\"
    end if
end tell") || true

  if echo "$tab_result" | grep -q "^FOUND:"; then
    local_tab_url="${tab_result#FOUND:}"
    log "INFO" "Step 3: Found tab via osascript: ${local_tab_url}"
    tab_found=true
  else
    log "WARN" "Step 3: No tab found for ${ACCOUNT_BASE}"
  fi
fi

# --- Step 4: Self-healing — open missing tab ---
if [[ "$tab_found" == "false" ]]; then
  log "INFO" "Step 4: Opening missing Superhuman tab for ${ACCOUNT}..."

  if [[ "$USE_CDP" == "true" ]]; then
    "$SCRIPT_DIR/chrome-cdp-helper.sh" open-tab "$ACCOUNT_BASE" 2>/dev/null || true
  else
    open -a "Google Chrome" "${ACCOUNT_BASE}"
  fi
  log "INFO" "Step 4: Waiting 8s for tab to load..."
  sleep 8

  # Retry finding the tab (CDP first)
  if [[ "$USE_CDP" == "true" ]]; then
    TAB_ID=$("$SCRIPT_DIR/chrome-cdp-helper.sh" find-tab "$ACCOUNT_BASE" 2>/dev/null) || true
    if [[ -z "$TAB_ID" ]]; then
      TAB_ID=$("$SCRIPT_DIR/chrome-cdp-helper.sh" find-tab "$SUPERHUMAN_BASE" 2>/dev/null) || true
    fi
    if [[ -n "$TAB_ID" ]]; then
      "$SCRIPT_DIR/chrome-cdp-helper.sh" activate "$TAB_ID" 2>/dev/null || true
      run_osascript_timed "Activate Chrome app" 5 \
        -e 'tell application "Google Chrome" to activate' 2>/dev/null || true
      tab_found=true
    fi
  fi

  if [[ "$tab_found" == "false" ]]; then
    # Try osascript as last resort
    tab_result=$(run_osascript_timed "Find Superhuman tab (retry)" 10 -e "
tell application \"Google Chrome\"
    activate
    set found to false
    repeat with w in windows
        set tabIndex to 0
        repeat with t in tabs of w
            set tabIndex to tabIndex + 1
            if URL of t starts with \"${ACCOUNT_BASE}\" or URL of t starts with \"${SUPERHUMAN_BASE}\" then
                set active tab index of w to tabIndex
                set index of w to 1
                set found to true
                exit repeat
            end if
        end repeat
        if found then exit repeat
    end repeat
    return found
end tell") || true

    if echo "$tab_result" | grep -q "true"; then
      tab_found=true
    fi
  fi

  if [[ "$tab_found" == "false" ]]; then
    log "ERROR" "Step 4: Tab still not found after opening URL"
    clipboard_fallback "Superhuman tab not available."
  fi
fi

sleep 1

# =============================================================================
# Branch: Reply mode vs Compose mode
# =============================================================================

if [[ "$MODE" == "reply" ]]; then
  # --- Reply Step 5: Navigate to thread via address bar ---
  log "INFO" "Step 5: Navigating to thread URL..."
  printf '%s' "$THREAD_URL" | pbcopy
  run_osascript_timed "Cmd+L (address bar)" 5 -e 'tell application "System Events" to keystroke "l" using command down'
  sleep 0.5
  run_osascript_timed "Cmd+V (paste URL)" 5 -e 'tell application "System Events" to keystroke "v" using command down'
  sleep 0.5
  run_osascript_timed "Enter (navigate)" 5 -e 'tell application "System Events" to keystroke return'
  log "INFO" "Step 5: Waiting 6s for thread to load..."
  sleep 6

  # --- Reply Step 6: Open Reply compose ---
  log "INFO" "Step 6: Pressing 'R' (Shift+r) to open Reply All..."
  run_osascript_timed "Reply All keystroke" 5 -e 'tell application "System Events" to keystroke "R"'
  sleep 2

  # --- Reply Step 7: Paste draft text ---
  log "INFO" "Step 7: Pasting draft text..."
  printf '%s' "$DRAFT_TEXT" | pbcopy
  sleep 0.3
  run_osascript_timed "Cmd+V (paste draft)" 5 -e 'tell application "System Events" to keystroke "v" using command down'
  sleep 1

  # Brief pause for Superhuman to auto-save
  sleep 1

  # --- Reply Step 8: Escape to close compose (saves draft) ---
  log "INFO" "Step 8: Pressing Escape to save draft..."
  run_osascript_timed "Escape (close compose)" 5 -e 'tell application "System Events" to key code 53'
  sleep 1

  # --- Reply Step 9: Navigate back to inbox ---
  log "INFO" "Step 9: Navigating back to inbox..."
  printf '%s' "$ACCOUNT_BASE" | pbcopy
  run_osascript_timed "Cmd+L (address bar)" 5 -e 'tell application "System Events" to keystroke "l" using command down'
  sleep 0.5
  run_osascript_timed "Cmd+V (paste inbox URL)" 5 -e 'tell application "System Events" to keystroke "v" using command down'
  sleep 0.5
  run_osascript_timed "Enter (navigate)" 5 -e 'tell application "System Events" to keystroke return'
  sleep 1

  log "INFO" "SUCCESS: Reply draft created for thread=${THREAD_ID} account=${ACCOUNT}"
  record_draft_status "queued" "Draft pasted in Superhuman and auto-saved"
  echo "Draft pasted in Superhuman (account: $ACCOUNT)."
  echo "Thread URL: $THREAD_URL"
  echo "Superhuman auto-saves. Draft will sync to all devices."
  echo "Review and send when ready."

else
  # ==========================================================================
  # Compose mode — new message draft
  # ==========================================================================

  # --- Compose Step 5: Dismiss any open compose, then press c ---
  log "INFO" "Compose Step 5: Dismissing any open compose window..."
  run_osascript_timed "Escape (dismiss)" 5 -e 'tell application "System Events" to key code 53'
  sleep 1

  log "INFO" "Compose Step 5: Pressing 'c' to open Compose..."
  run_osascript_timed "Compose keystroke" 5 -e 'tell application "System Events" to keystroke "c"'
  log "INFO" "Compose Step 5: Waiting 2s for compose window to load..."
  sleep 2

  # --- Compose Step 6: Enter To recipients ---
  # Superhuman's To field requires Enter to confirm each recipient as a chip.
  # Tab moves focus to the next field (CC/Subject) WITHOUT confirming, so we
  # press Enter after each paste, then Tab only after the last recipient.
  log "INFO" "Compose Step 6: Entering To recipients: ${TO_ADDRESSES}"
  IFS=',' read -ra RECIPIENTS <<< "$TO_ADDRESSES"
  for i in "${!RECIPIENTS[@]}"; do
    addr=$(echo "${RECIPIENTS[$i]}" | xargs)  # trim whitespace
    log "INFO" "Compose Step 6: Typing recipient: ${addr}"
    printf '%s' "$addr" | pbcopy
    sleep 0.2
    run_osascript_timed "Cmd+V (paste recipient)" 5 -e 'tell application "System Events" to keystroke "v" using command down'
    sleep 0.8
    # Enter confirms the autocomplete/recipient chip
    run_osascript_timed "Enter (confirm recipient)" 5 -e 'tell application "System Events" to keystroke return'
    sleep 0.5
  done
  # Tab from To field to Subject field
  run_osascript_timed "Tab (To -> Subject)" 5 -e 'tell application "System Events" to keystroke tab'
  sleep 0.5

  # --- Compose Step 7: Move to Subject and type it ---
  log "INFO" "Compose Step 7: Entering subject: ${SUBJECT}"
  printf '%s' "$SUBJECT" | pbcopy
  sleep 0.2
  run_osascript_timed "Cmd+V (paste subject)" 5 -e 'tell application "System Events" to keystroke "v" using command down'
  sleep 0.5

  # --- Compose Step 8: Tab to Body and paste draft text ---
  log "INFO" "Compose Step 8: Tabbing to Body and pasting draft text..."
  run_osascript_timed "Tab (move to body)" 5 -e 'tell application "System Events" to keystroke tab'
  sleep 0.5
  printf '%s' "$DRAFT_TEXT" | pbcopy
  sleep 0.2
  run_osascript_timed "Cmd+V (paste body)" 5 -e 'tell application "System Events" to keystroke "v" using command down'
  sleep 1

  # Brief pause for Superhuman to auto-save
  sleep 1

  # --- Compose Step 9: Escape to close compose (saves draft) ---
  log "INFO" "Compose Step 9: Pressing Escape to save draft..."
  run_osascript_timed "Escape (close compose)" 5 -e 'tell application "System Events" to key code 53'
  sleep 2

  # --- Compose Step 10: Navigate to drafts to capture draft URL ---
  DRAFTS_URL="${ACCOUNT_BASE}/drafts"
  log "INFO" "Compose Step 10: Navigating to drafts folder to capture draft URL..."
  printf '%s' "$DRAFTS_URL" | pbcopy
  run_osascript_timed "Cmd+L (address bar)" 5 -e 'tell application "System Events" to keystroke "l" using command down'
  sleep 0.5
  run_osascript_timed "Cmd+V (paste drafts URL)" 5 -e 'tell application "System Events" to keystroke "v" using command down'
  sleep 0.5
  run_osascript_timed "Enter (navigate)" 5 -e 'tell application "System Events" to keystroke return'
  log "INFO" "Compose Step 10: Waiting 3s for drafts folder to load..."
  sleep 3

  # Select and open the first (most recent) draft
  log "INFO" "Compose Step 10: Opening most recent draft to capture URL..."
  run_osascript_timed "Enter (open draft)" 5 -e 'tell application "System Events" to keystroke return'
  sleep 2

  # Read the URL from Chrome's address bar
  DRAFT_URL=""
  draft_url_result=$(run_osascript_timed "Read draft URL from Chrome" 5 -e '
tell application "Google Chrome"
    set tabURL to URL of active tab of front window
    return tabURL
end tell') || true

  if [[ -n "$draft_url_result" ]] && echo "$draft_url_result" | grep -q "mail.superhuman.com"; then
    DRAFT_URL="$draft_url_result"
    log "INFO" "Compose Step 10: Captured draft URL: ${DRAFT_URL}"
  else
    log "WARN" "Compose Step 10: Could not capture draft URL (got: '${draft_url_result}')"
  fi

  # --- Compose Step 11: Navigate back to inbox ---
  log "INFO" "Compose Step 11: Navigating back to inbox..."
  printf '%s' "$ACCOUNT_BASE" | pbcopy
  run_osascript_timed "Cmd+L (address bar)" 5 -e 'tell application "System Events" to keystroke "l" using command down'
  sleep 0.5
  run_osascript_timed "Cmd+V (paste inbox URL)" 5 -e 'tell application "System Events" to keystroke "v" using command down'
  sleep 0.5
  run_osascript_timed "Enter (navigate)" 5 -e 'tell application "System Events" to keystroke return'
  sleep 1

  log "INFO" "SUCCESS: Compose draft created to=${TO_ADDRESSES} subject='${SUBJECT}' account=${ACCOUNT}"
  record_draft_status "queued" "Compose draft created in Superhuman and auto-saved"
  echo "New message draft created in Superhuman (account: $ACCOUNT)."
  echo "To: $TO_ADDRESSES"
  echo "Subject: $SUBJECT"
  if [[ -n "$DRAFT_URL" ]]; then
    echo "Draft URL: $DRAFT_URL"
  fi
  echo "Superhuman auto-saves. Draft will sync to all devices."
  echo "Review and send when ready."
fi
