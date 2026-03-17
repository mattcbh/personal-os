#!/bin/bash
# System Health Check — coordinator for launchd/runtime drift, sync health,
# state-link integrity, and content hygiene.
#
# Writes:
# - logs/system-health.log
# - core/state/system-health.json
# - Telegram warning alert (only when status is warning)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKING_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
AUDIT_SCRIPT="${AUDIT_SCRIPT:-$WORKING_DIR/scripts/system_health_audit.py}"

detect_role() {
  if [[ -n "${SYSTEM_HEALTH_ROLE:-}" ]]; then
    printf '%s\n' "$SYSTEM_HEALTH_ROLE"
    return 0
  fi

  if [[ "$(basename "$HOME")" == "homeserver" || ! -d "$WORKING_DIR/.git" ]]; then
    printf '%s\n' "brain"
  else
    printf '%s\n' "laptop"
  fi
}

ROLE="$(detect_role)"
export SYSTEM_HEALTH_ROLE="$ROLE"

LOG_DIR="${LOG_DIR:-$WORKING_DIR/logs}"
if [[ "$ROLE" == "brain" ]]; then
  LOG_FILE="${LOG_FILE:-$LOG_DIR/system-health.log}"
  STATE_FILE="${STATE_FILE:-$WORKING_DIR/core/state/system-health.json}"
  ENABLE_TELEGRAM_ALERTS="${ENABLE_TELEGRAM_ALERTS:-1}"
else
  LOG_FILE="${LOG_FILE:-$LOG_DIR/system-health-laptop.log}"
  STATE_FILE="${STATE_FILE:-$WORKING_DIR/core/state/system-health-laptop.json}"
  ENABLE_TELEGRAM_ALERTS="${ENABLE_TELEGRAM_ALERTS:-0}"
fi
TELEGRAM_CONFIG="${TELEGRAM_CONFIG:-$WORKING_DIR/core/state/telegram-brain.json}"

mkdir -p "$LOG_DIR"
mkdir -p "$(dirname "$STATE_FILE")"
cd "$WORKING_DIR"

log() {
  local level="$1"
  shift
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] [$level] $*" | tee -a "$LOG_FILE"
}

send_telegram_warning() {
  local message="$1"

  if [[ ! -f "$TELEGRAM_CONFIG" ]]; then
    log "WARN" "Telegram config missing; cannot send warning alert."
    return 0
  fi

  set +e
  ALERT_TEXT="$message" TELEGRAM_CONFIG="$TELEGRAM_CONFIG" python3 - <<'PY'
import json
import os
import urllib.request

cfg_path = os.environ["TELEGRAM_CONFIG"]
text = os.environ["ALERT_TEXT"]
cfg = json.load(open(cfg_path, encoding="utf-8"))
token = cfg["bot_token"]
chat_id = cfg["chat_id"]
payload = json.dumps(
    {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": True,
    }
).encode("utf-8")
req = urllib.request.Request(
    f"https://api.telegram.org/bot{token}/sendMessage",
    data=payload,
    headers={"Content-Type": "application/json"},
)
with urllib.request.urlopen(req, timeout=15):
    pass
PY
  rc=$?
  set -e

  if (( rc == 0 )); then
    log "WARN" "Warning alert sent to Telegram."
  else
    log "WARN" "Failed to send warning alert to Telegram (exit=${rc})."
  fi
}

log "INFO" "Starting system health check (role=${ROLE})"

set +e
audit_stdout="$(python3 "$AUDIT_SCRIPT" --state-file "$STATE_FILE" 2>&1)"
audit_exit=$?
set -e

printf '%s\n' "$audit_stdout" >> "$LOG_FILE"

if (( audit_exit != 0 )); then
  log "WARN" "system_health_audit.py exited with code ${audit_exit}"
fi

summary_block="$(
  python3 - <<'PY' "$STATE_FILE"
import json
import sys
from pathlib import Path

state_path = Path(sys.argv[1])
if not state_path.exists():
    print("status=warning")
    print("headline=state file missing")
    raise SystemExit(0)

report = json.loads(state_path.read_text(encoding="utf-8"))
summary = report.get("summary", {})

print(f"status={report.get('overall_status', 'unknown')}")
print(f"headline={summary.get('headline', 'no headline')}")
for line in summary.get("lines", [])[:12]:
    print(f"line={line}")
PY
)"

overall_status="warning"
headline="no headline"
summary_lines=()

while IFS= read -r raw_line; do
  case "$raw_line" in
    status=*)
      overall_status="${raw_line#status=}"
      ;;
    headline=*)
      headline="${raw_line#headline=}"
      ;;
    line=*)
      summary_lines+=("${raw_line#line=}")
      ;;
  esac
done <<< "$summary_block"

log "INFO" "System health summary: ${headline}"
summary_text=""
if [[ -n "${summary_lines[*]-}" ]]; then
  for item in "${summary_lines[@]}"; do
    log "WARN" "$item"
  done
  summary_text="$(printf '%s\n' "${summary_lines[@]}")"
fi

if [[ "$overall_status" == "warning" && "$ENABLE_TELEGRAM_ALERTS" == "1" ]]; then
  warning_text="SYSTEM HEALTH WARNING
Host: $(hostname)
Summary: ${headline}
${summary_text}
Log: ${LOG_FILE}
State: ${STATE_FILE}"
  send_telegram_warning "$warning_text"
fi

log "INFO" "Wrote report: ${STATE_FILE}"
log "INFO" "System health status: ${overall_status}"
