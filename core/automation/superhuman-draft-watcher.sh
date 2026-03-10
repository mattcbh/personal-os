#!/bin/bash
# superhuman-draft-watcher.sh — Process queued Superhuman draft requests
#
# Watches /tmp/superhuman-draft-queue/ for JSON files written by
# superhuman-draft.sh --queue mode. Processes each file by calling
# superhuman-draft.sh in direct mode, then deletes the queue file.
#
# Designed to run as a LaunchAgent with WatchPaths on the queue directory.
# Since it runs as /bin/bash (a stable system binary), its macOS Automation
# permissions persist across Claude CLI updates.
#
# Can also be run manually: ./superhuman-draft-watcher.sh

set -euo pipefail

QUEUE_DIR="/tmp/superhuman-draft-queue"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DRAFT_SCRIPT="${SCRIPT_DIR}/superhuman-draft.sh"
LOCK_DIR="/tmp/superhuman-draft-watcher.lock"
LOCK_PID_FILE="${LOCK_DIR}/pid"
LOG_DIR="/Users/homeserver/Obsidian/personal-os/logs"
LOG_FILE="${LOG_DIR}/superhuman-draft-watcher.log"
STATUS_SCRIPT="${SCRIPT_DIR}/superhuman-draft-status.py"

mkdir -p "$QUEUE_DIR"
mkdir -p "$LOG_DIR"

log() {
  local level="$1"
  shift
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] [$level] $*" | tee -a "$LOG_FILE"
}

acquire_lock() {
  if mkdir "$LOCK_DIR" 2>/dev/null; then
    echo "$$" > "$LOCK_PID_FILE"
    return 0
  fi

  if [[ -f "$LOCK_PID_FILE" ]]; then
    local old_pid
    old_pid=$(cat "$LOCK_PID_FILE" 2>/dev/null || true)
    if [[ -n "$old_pid" ]] && ! kill -0 "$old_pid" 2>/dev/null; then
      rm -rf "$LOCK_DIR" 2>/dev/null || true
      if mkdir "$LOCK_DIR" 2>/dev/null; then
        echo "$$" > "$LOCK_PID_FILE"
        log "WARN" "Recovered stale watcher lock from PID ${old_pid}"
        return 0
      fi
    fi
  fi

  log "INFO" "Another watcher instance is running; exiting."
  exit 0
}

cleanup_lock() {
  if [[ -d "$LOCK_DIR" && -f "$LOCK_PID_FILE" ]]; then
    local pid
    pid=$(cat "$LOCK_PID_FILE" 2>/dev/null || true)
    if [[ "$pid" == "$$" ]]; then
      rm -rf "$LOCK_DIR" 2>/dev/null || true
    fi
  fi
}

acquire_lock
trap cleanup_lock EXIT INT TERM

process_draft() {
  local queue_file="$1"

  if [[ ! -f "$queue_file" ]]; then
    return 0
  fi

  log "INFO" "Processing: $queue_file"

  # Parse JSON fields using python3 (available on macOS)
  local mode draft_text account thread_id to_addresses subject request_id run_output run_exit final_status
  mode=$(python3 -c "import json,sys; d=json.load(open('$queue_file')); print(d.get('mode','reply'))" 2>/dev/null) || {
    log "ERROR" "Failed to parse JSON from $queue_file"
    mv "$queue_file" "${queue_file}.failed"
    return 1
  }

  draft_text=$(python3 -c "import json,sys; d=json.load(open('$queue_file')); print(d['draft_text'])" 2>/dev/null)
  account=$(python3 -c "import json,sys; d=json.load(open('$queue_file')); print(d.get('account','matt@cornerboothholdings.com'))" 2>/dev/null)
  request_id=$(python3 -c "import json,sys; d=json.load(open('$queue_file')); print(d.get('request_id',''))" 2>/dev/null)

  if [[ "$mode" == "compose" ]]; then
    to_addresses=$(python3 -c "import json,sys; d=json.load(open('$queue_file')); print(d['to'])" 2>/dev/null)
    subject=$(python3 -c "import json,sys; d=json.load(open('$queue_file')); print(d['subject'])" 2>/dev/null)

    log "INFO" "Executing compose draft: to=$to_addresses subject='$subject' account=$account"
    if [[ -x "$STATUS_SCRIPT" ]]; then
      python3 "$STATUS_SCRIPT" record --mode compose --status executing --request-id "$request_id" --account "$account" --note "Watcher executing compose draft" >/dev/null 2>&1 || true
    fi
    set +e
    run_output=$(SUPERHUMAN_DRAFT_REQUEST_ID="$request_id" "$DRAFT_SCRIPT" --new "$to_addresses" "$subject" "$draft_text" "$account" 2>&1)
    run_exit=$?
    set -e
    echo "$run_output" >> "$LOG_FILE"
    if [[ $run_exit -ne 0 ]]; then
      final_status="failed"
      log "ERROR" "Draft script failed for $queue_file (compose mode)"
      mv "$queue_file" "${queue_file}.failed"
      if [[ -x "$STATUS_SCRIPT" ]]; then
        python3 "$STATUS_SCRIPT" record --mode compose --status failed --request-id "$request_id" --account "$account" --note "Watcher compose execution failed" >/dev/null 2>&1 || true
      fi
      return 1
    elif echo "$run_output" | grep -q "FALLBACK:"; then
      final_status="clipboard"
    else
      final_status="queued"
    fi
    if [[ -x "$STATUS_SCRIPT" ]]; then
      python3 "$STATUS_SCRIPT" record --mode compose --status "$final_status" --request-id "$request_id" --account "$account" --note "Watcher compose execution completed" >/dev/null 2>&1 || true
    fi
  else
    thread_id=$(python3 -c "import json,sys; d=json.load(open('$queue_file')); print(d['thread_id'])" 2>/dev/null)

    log "INFO" "Executing reply draft: thread=$thread_id account=$account"
    if [[ -x "$STATUS_SCRIPT" ]]; then
      python3 "$STATUS_SCRIPT" record --mode reply --status executing --request-id "$request_id" --account "$account" --thread-id "$thread_id" --note "Watcher executing reply draft" >/dev/null 2>&1 || true
    fi
    set +e
    run_output=$(SUPERHUMAN_DRAFT_REQUEST_ID="$request_id" "$DRAFT_SCRIPT" "$thread_id" "$draft_text" "$account" 2>&1)
    run_exit=$?
    set -e
    echo "$run_output" >> "$LOG_FILE"
    if [[ $run_exit -ne 0 ]]; then
      final_status="failed"
      log "ERROR" "Draft script failed for $queue_file (reply mode)"
      mv "$queue_file" "${queue_file}.failed"
      if [[ -x "$STATUS_SCRIPT" ]]; then
        python3 "$STATUS_SCRIPT" record --mode reply --status failed --request-id "$request_id" --account "$account" --thread-id "$thread_id" --note "Watcher reply execution failed" >/dev/null 2>&1 || true
      fi
      return 1
    elif echo "$run_output" | grep -q "FALLBACK:"; then
      final_status="clipboard"
    else
      final_status="queued"
    fi
    if [[ -x "$STATUS_SCRIPT" ]]; then
      python3 "$STATUS_SCRIPT" record --mode reply --status "$final_status" --request-id "$request_id" --account "$account" --thread-id "$thread_id" --note "Watcher reply execution completed" >/dev/null 2>&1 || true
    fi
  fi

  # Success: remove the queue file
  rm -f "$queue_file"
  log "INFO" "Completed and removed: $queue_file"
}

# Process all pending .json files in the queue directory.
# Drain-until-empty avoids races when new files arrive while processing.
file_count=0
while true; do
  had_files=false
  for f in "$QUEUE_DIR"/*.json; do
    [[ -f "$f" ]] || continue
    had_files=true
    process_draft "$f"
    file_count=$((file_count + 1))
    # Brief pause between drafts (they use the clipboard serially)
    sleep 2
  done
  if [[ "$had_files" == "false" ]]; then
    break
  fi
done

if [[ $file_count -eq 0 ]]; then
  log "INFO" "No queue files to process"
else
  log "INFO" "Processed $file_count draft(s)"
fi
