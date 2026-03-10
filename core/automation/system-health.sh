#!/bin/bash
# System Health Check — validates launchd runtime and architecture drift daily.
#
# Runs headlessly via launchd and writes a compact report to:
# - logs/system-health.log
# - core/state/system-health.json
# - Telegram warning alert (only when status is warning)
#
# To test manually:
#   ./core/automation/system-health.sh

set -euo pipefail

WORKING_DIR="/Users/homeserver/Obsidian/personal-os"
LOG_DIR="${WORKING_DIR}/logs"
LOG_FILE="${LOG_DIR}/system-health.log"
STATE_FILE="${WORKING_DIR}/core/state/system-health.json"
AUDIT_SCRIPT="${WORKING_DIR}/scripts/audit_personal_os.py"
TELEGRAM_CONFIG="${WORKING_DIR}/core/state/telegram-brain.json"

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

log "INFO" "Starting system health check"

# Pull expected labels from the canonical runtime manifest.
job_lines="$(
  python3 - <<'PY'
from pathlib import Path
import importlib.util

root = Path("/Users/homeserver/Obsidian/personal-os")
spec = importlib.util.spec_from_file_location(
    "audit_personal_os",
    root / "scripts" / "audit_personal_os.py",
)
if spec is None or spec.loader is None:
    raise RuntimeError("Unable to import audit_personal_os.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)  # type: ignore[attr-defined]
manifest = mod.load_manifest()

for item in manifest.get("scheduled_jobs", []) or []:
    if not isinstance(item, dict) or item.get("enabled", True) is False:
        continue
    plist = item.get("launchd_plist")
    if isinstance(plist, str) and plist.strip():
        print(f"S|{Path(plist).stem}")

for item in manifest.get("persistent_jobs", []) or []:
    if not isinstance(item, dict) or item.get("enabled", True) is False:
        continue
    plist = item.get("launchd_plist")
    if isinstance(plist, str) and plist.strip():
        print(f"P|{Path(plist).stem}")
PY
)"

launch_list="$(launchctl list 2>/dev/null || true)"
expected_count=0
loaded_count=0
declare -a missing_labels=()
declare -a persistent_not_running=()

while IFS='|' read -r kind label; do
  [[ -n "${label:-}" ]] || continue
  expected_count=$((expected_count + 1))

  if printf '%s\n' "$launch_list" | awk '{print $3}' | grep -Fqx "$label"; then
    loaded_count=$((loaded_count + 1))
    if [[ "$kind" == "P" ]]; then
      pid="$(printf '%s\n' "$launch_list" | awk -v target="$label" '$3==target {print $1; exit}')"
      if [[ -z "$pid" || "$pid" == "-" || "$pid" == "0" ]]; then
        persistent_not_running+=("$label")
      fi
    fi
  else
    missing_labels+=("$label")
  fi
done <<< "$job_lines"

set +e
telegram_pids="$(pgrep -f '/core/automation/telegram-bridge.py' 2>/dev/null)"
set -e
if [[ -z "$telegram_pids" ]]; then
  telegram_count=0
else
  telegram_count="$(printf '%s\n' "$telegram_pids" | wc -l | tr -d '[:space:]')"
fi

set +e
audit_output="$(python3 "$AUDIT_SCRIPT" 2>&1)"
audit_exit=$?
set -e

audit_counts_json="$(
  printf '%s\n' "$audit_output" | python3 - <<'PY'
import json
import re
import sys

text = sys.stdin.read()
match = re.search(r"\{[\s\S]*?\}", text)
if not match:
    print("{}")
    raise SystemExit(0)
try:
    parsed = json.loads(match.group(0))
except json.JSONDecodeError:
    print("{}")
    raise SystemExit(0)
print(json.dumps(parsed))
PY
)"

audit_total="$(python3 - <<'PY' "$audit_counts_json"
import json
import sys

counts = json.loads(sys.argv[1])
print(sum(int(v) for v in counts.values()))
PY
)"

overall_status="ok"
if (( ${#missing_labels[@]} > 0 )); then
  overall_status="warning"
fi
if (( ${#persistent_not_running[@]} > 0 )); then
  overall_status="warning"
fi
if (( telegram_count > 1 )); then
  overall_status="warning"
fi
if (( audit_total > 0 )); then
  overall_status="warning"
fi

log "INFO" "Launchd labels loaded: ${loaded_count}/${expected_count}"
if (( ${#missing_labels[@]} > 0 )); then
  log "WARN" "Missing launchd labels: ${missing_labels[*]}"
fi
if (( ${#persistent_not_running[@]} > 0 )); then
  log "WARN" "Persistent jobs without active PID: ${persistent_not_running[*]}"
fi
if (( telegram_count > 1 )); then
  log "WARN" "telegram-bridge duplicate processes detected: ${telegram_count}"
else
  log "INFO" "telegram-bridge process count: ${telegram_count}"
fi
if (( audit_total > 0 )); then
  log "WARN" "audit_personal_os findings detected: ${audit_counts_json}"
else
  log "INFO" "audit_personal_os clean: ${audit_counts_json}"
fi
if (( audit_exit != 0 )); then
  log "WARN" "audit_personal_os exit code: ${audit_exit}"
fi

if [[ "$overall_status" == "warning" ]]; then
  warning_text="SYSTEM HEALTH WARNING
Host: $(hostname)
Launchd loaded: ${loaded_count}/${expected_count}
Telegram bridge processes: ${telegram_count}
Audit findings total: ${audit_total}
Missing launchd labels: ${missing_labels[*]:-none}
Persistent jobs not running: ${persistent_not_running[*]:-none}
Audit counts: ${audit_counts_json}
Log: ${LOG_FILE}
State: ${STATE_FILE}"
  send_telegram_warning "$warning_text"
fi

export OVERALL_STATUS="$overall_status"
export EXPECTED_COUNT="$expected_count"
export LOADED_COUNT="$loaded_count"
export TELEGRAM_COUNT="$telegram_count"
export AUDIT_EXIT="$audit_exit"
export AUDIT_COUNTS_JSON="$audit_counts_json"
export MISSING_LABELS="$(printf '%s\n' "${missing_labels[@]:-}" | sed '/^$/d')"
export PERSISTENT_NOT_RUNNING="$(printf '%s\n' "${persistent_not_running[@]:-}" | sed '/^$/d')"
export STATE_FILE

python3 - <<'PY'
import json
import os
import platform
from datetime import datetime, timezone
from pathlib import Path

def lines(name: str) -> list[str]:
    raw = os.environ.get(name, "").strip()
    return [line for line in raw.splitlines() if line.strip()]

state_path = Path(os.environ["STATE_FILE"])
report = {
    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    "host": platform.node(),
    "overall_status": os.environ.get("OVERALL_STATUS", "unknown"),
    "launchd": {
        "expected_labels": int(os.environ.get("EXPECTED_COUNT", "0")),
        "loaded_labels": int(os.environ.get("LOADED_COUNT", "0")),
        "missing_labels": lines("MISSING_LABELS"),
        "persistent_not_running": lines("PERSISTENT_NOT_RUNNING"),
    },
    "telegram_bridge": {
        "process_count": int(os.environ.get("TELEGRAM_COUNT", "0")),
        "duplicate_processes": int(os.environ.get("TELEGRAM_COUNT", "0")) > 1,
    },
    "audit_personal_os": {
        "exit_code": int(os.environ.get("AUDIT_EXIT", "0")),
        "counts": json.loads(os.environ.get("AUDIT_COUNTS_JSON", "{}")),
    },
}
state_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
PY

log "INFO" "Wrote report: ${STATE_FILE}"
log "INFO" "System health status: ${overall_status}"
