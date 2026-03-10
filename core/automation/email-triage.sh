#!/bin/bash
# Email Triage -- Inbox Scanner + Categorized Report
# Runs at 6am and 4pm via launchd

set -Eeuo pipefail

unset CLAUDECODE

# Runtime args
MODEL="opus"
DRY_RUN=false
FORCE_LABEL=""
while [ $# -gt 0 ]; do
    case "$1" in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --run-label)
            if [ $# -lt 2 ]; then
                echo "--run-label requires 'am' or 'pm'" >&2
                exit 1
            fi
            FORCE_LABEL="$2"
            shift 2
            ;;
        --model)
            if [ $# -lt 2 ]; then
                echo "--model requires a value" >&2
                exit 1
            fi
            MODEL="$2"
            shift 2
            ;;
        --log-json)
            shift
            ;;
        *)
            echo "Unknown argument: $1" >&2
            exit 1
            ;;
    esac
done

CLAUDE_PATH="/Users/homeserver/.local/bin/claude"
WORKING_DIR="/Users/homeserver/Obsidian/personal-os"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="${WORKING_DIR}/logs"
LOG_FILE="${LOG_DIR}/email-triage.log"
STATE_FILE="${WORKING_DIR}/core/state/email-triage-state.json"
PROMPT_TEMPLATE="${SCRIPT_DIR}/email-triage-prompt.md"
TRIAGE_VALIDATOR_SCRIPT="${SCRIPT_DIR}/email-triage-validator.py"
TRIAGE_CONTRACT_FILE="${SCRIPT_DIR}/email-triage-contract.json"
SUPERHUMAN_DRAFT_SCRIPT="${SCRIPT_DIR}/superhuman-draft.sh"
SUPERHUMAN_DRAFT_WATCHER_SCRIPT="${SCRIPT_DIR}/superhuman-draft-watcher.sh"
IDENTITY_RESOLVER_SCRIPT="${SCRIPT_DIR}/email-identity-resolver.py"
TRIAGE_RENDER_SCRIPT="${SCRIPT_DIR}/email-triage-render.py"
DRAFT_RECOVERY_SCRIPT="${SCRIPT_DIR}/email-triage-draft-recovery.py"
DRAFT_STATUS_FILE="${WORKING_DIR}/core/state/superhuman-draft-status.json"
MCP_CONFIG="${WORKING_DIR}/core/automation/mcp-configs/email-triage.json"
LOCK_DIR="${WORKING_DIR}/core/state/.email-triage.lock"
LOCK_PID_FILE="${LOCK_DIR}/pid"

CLAUDE_TIMEOUT_SECONDS="${EMAIL_TRIAGE_CLAUDE_TIMEOUT_SECONDS:-600}"
PRECHECK_TIMEOUT_SECONDS="${EMAIL_TRIAGE_PRECHECK_TIMEOUT_SECONDS:-90}"
SEND_TIMEOUT_SECONDS="${EMAIL_TRIAGE_SEND_TIMEOUT_SECONDS:-180}"
WATCHER_DRAIN_TIMEOUT_SECONDS="${EMAIL_TRIAGE_DRAFT_DRAIN_TIMEOUT_SECONDS:-300}"
RETRY_DELAY_SECONDS="${EMAIL_TRIAGE_RETRY_DELAY_SECONDS:-10}"
SEND_MODEL="${EMAIL_TRIAGE_SEND_MODEL:-haiku}"
SEND_MAX_ATTEMPTS="${EMAIL_TRIAGE_SEND_MAX_ATTEMPTS:-2}"
DRAFT_RECOVERY_TIMEOUT_SECONDS="${EMAIL_TRIAGE_DRAFT_RECOVERY_TIMEOUT_SECONDS:-240}"
REQUIRE_REPLY_DRAFTS="${EMAIL_TRIAGE_REQUIRE_REPLY_DRAFTS:-true}"

SYSTEM_PROMPT="You are an automated email triage assistant running headlessly. Do not use AskUserQuestion. Do not ask for confirmation. Execute all steps exactly as instructed in the prompt."
BUILTIN_TOOLS="Read,Write,Edit,Bash,Glob,Grep"

TIMESTAMP=$(date "+%Y-%m-%d %H:%M:%S")
FULL_DATE=$(date "+%B %d, %Y")
DAY_OF_WEEK=$(date "+%A")
HOUR=$(date "+%H")
DATE_ISO=$(date "+%Y-%m-%d")
TIME_DISPLAY=$(date "+%-I:%M %p")

if [ -n "$FORCE_LABEL" ]; then
    case "$FORCE_LABEL" in
        am|AM)
            TIME_LABEL="AM"
            TRIAGE_SUFFIX="am"
            ;;
        pm|PM)
            TIME_LABEL="PM"
            TRIAGE_SUFFIX="pm"
            ;;
        *)
            echo "--run-label must be 'am' or 'pm'" >&2
            exit 1
            ;;
    esac
else
    if [ "$HOUR" -lt 12 ]; then
        TIME_LABEL="AM"
        TRIAGE_SUFFIX="am"
    else
        TIME_LABEL="PM"
        TRIAGE_SUFFIX="pm"
    fi
fi

RECORDS_FILE="${WORKING_DIR}/logs/email-triage-records-${DATE_ISO}-${TRIAGE_SUFFIX}.json"
if [ "$DRY_RUN" = "true" ]; then
    DIGEST_FILE="/tmp/email-triage/triage-${DATE_ISO}-${TRIAGE_SUFFIX}-dryrun.md"
else
    DIGEST_FILE="${WORKING_DIR}/Knowledge/DIGESTS/triage-${DATE_ISO}-${TRIAGE_SUFFIX}.md"
fi
HTML_FILE="/tmp/email-triage/triage-${DATE_ISO}-${TRIAGE_SUFFIX}.html"

mkdir -p "$LOG_DIR" /tmp/email-triage "$(dirname "$DRAFT_STATUS_FILE")" "$(dirname "$LOCK_DIR")"
cd "$WORKING_DIR"

log_line() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

run_with_timeout_capture() {
    local timeout_seconds="$1"
    shift

    local out_file
    out_file=$(mktemp /tmp/email-triage/cmd.XXXXXX)

    set +e
    "$@" >"$out_file" 2>&1 &
    local cmd_pid=$!
    (
        sleep "$timeout_seconds"
        kill -TERM "$cmd_pid" 2>/dev/null || true
        sleep 5
        kill -KILL "$cmd_pid" 2>/dev/null || true
    ) &
    local watchdog_pid=$!

    wait "$cmd_pid"
    local cmd_code=$?

    kill -TERM "$watchdog_pid" 2>/dev/null || true
    wait "$watchdog_pid" 2>/dev/null || true
    set -e

    CMD_OUTPUT=$(cat "$out_file")
    rm -f "$out_file"
    CMD_EXIT_CODE=$cmd_code
    CMD_TIMED_OUT=0
    if [ "$cmd_code" -eq 143 ] || [ "$cmd_code" -eq 137 ]; then
        CMD_TIMED_OUT=1
    fi
}

cleanup() {
    if [ -d "$LOCK_DIR" ] && [ -f "$LOCK_PID_FILE" ]; then
        local lock_pid
        lock_pid=$(cat "$LOCK_PID_FILE" 2>/dev/null || true)
        if [ "$lock_pid" = "$$" ]; then
            rm -rf "$LOCK_DIR" 2>/dev/null || true
        fi
    fi
}
trap cleanup EXIT INT TERM

send_alert() {
    local subject="$1"
    local body="$2"
    if [ "$DRY_RUN" = "true" ]; then
        log_line "Dry-run alert suppressed: ${subject}"
        return 0
    fi
    run_with_timeout_capture "$SEND_TIMEOUT_SECONDS" \
        "$CLAUDE_PATH" \
        -p "Send an email via mcp__google__gmail_users_messages_send to matt@cornerboothholdings.com with subject '${subject}' and body: ${body}" \
        --model haiku \
        --permission-mode bypassPermissions \
        --system-prompt "Send the specified email immediately. Do not ask questions." \
        --disable-slash-commands \
        --no-session-persistence \
        --strict-mcp-config \
        --mcp-config "$MCP_CONFIG" \
        --tools "Bash"
    local alert_code=$CMD_EXIT_CODE
    echo "$CMD_OUTPUT" >> "$LOG_FILE"
    if [ $alert_code -ne 0 ]; then
        log_line "CRITICAL: alert email failed (${subject})."
    fi
}

acquire_lock() {
    if mkdir "$LOCK_DIR" 2>/dev/null; then
        echo "$$" > "$LOCK_PID_FILE"
        return 0
    fi

    if [ -f "$LOCK_PID_FILE" ]; then
        local old_pid
        old_pid=$(cat "$LOCK_PID_FILE" 2>/dev/null || true)
        if [ -n "$old_pid" ] && ! kill -0 "$old_pid" 2>/dev/null; then
            rm -rf "$LOCK_DIR" 2>/dev/null || true
            if mkdir "$LOCK_DIR" 2>/dev/null; then
                echo "$$" > "$LOCK_PID_FILE"
                log_line "Recovered stale email-triage lock from PID ${old_pid}."
                return 0
            fi
        fi
    fi

    log_line "Another email triage run is already in progress; exiting."
    exit 0
}

acquire_lock

log_line "Starting email triage (${TIME_LABEL})..."

if pgrep -q "Google Chrome"; then
    log_line "Chrome is running"
else
    log_line "Chrome is not running (drafts may use clipboard fallback)"
fi

cat > "$DRAFT_STATUS_FILE" <<'JSON'
{
  "threads": {},
  "compose": {},
  "updated_at": null
}
JSON

LAST_TRIAGE_TIMESTAMP="null"
if [ -f "$STATE_FILE" ]; then
    LAST_TRIAGE_TIMESTAMP=$(python3 -c "
import json
try:
  d=json.load(open('$STATE_FILE'))
  ts=d.get('last_triage_timestamp')
  print(ts if ts else 'null')
except Exception:
  print('null')
" 2>/dev/null || echo "null")
fi
log_line "Last triage: $LAST_TRIAGE_TIMESTAMP"

if [ -f "$STATE_FILE" ]; then
    python3 - <<PY
import json
p='$STATE_FILE'
try:
  d=json.load(open(p))
  ids=d.get('processed_message_ids',[])
  if len(ids)>200:
    d['processed_message_ids']=ids[-200:]
    json.dump(d,open(p,'w'),indent=2)
    print(f'Pruned {len(ids)-200} old message IDs')
except Exception:
  pass
PY
fi

if [ ! -f "$PROMPT_TEMPLATE" ]; then
    log_line "FATAL: missing prompt template at $PROMPT_TEMPLATE"
    exit 1
fi

PROMPT_BASE=$(sed \
    -e "s|{{DAY_OF_WEEK}}|${DAY_OF_WEEK}|g" \
    -e "s|{{FULL_DATE}}|${FULL_DATE}|g" \
    -e "s|{{TIME_DISPLAY}}|${TIME_DISPLAY}|g" \
    -e "s|{{TIME_LABEL}}|${TIME_LABEL}|g" \
    -e "s|{{TRIAGE_SUFFIX}}|${TRIAGE_SUFFIX}|g" \
    -e "s|{{LAST_TRIAGE_TIMESTAMP}}|${LAST_TRIAGE_TIMESTAMP}|g" \
    -e "s|{{DATE_ISO}}|${DATE_ISO}|g" \
    -e "s|{{TRIAGE_VALIDATOR_SCRIPT}}|${TRIAGE_VALIDATOR_SCRIPT}|g" \
    -e "s|{{TRIAGE_CONTRACT_FILE}}|${TRIAGE_CONTRACT_FILE}|g" \
    -e "s|{{SUPERHUMAN_DRAFT_SCRIPT}}|${SUPERHUMAN_DRAFT_SCRIPT}|g" \
    -e "s|{{IDENTITY_RESOLVER_SCRIPT}}|${IDENTITY_RESOLVER_SCRIPT}|g" \
    "$PROMPT_TEMPLATE")

PROMPT_BASE="${PROMPT_BASE}

## Runtime Override (Renderer Pipeline)

This run uses a deterministic local renderer pipeline.
- Do NOT send triage report email.
- Do NOT write markdown digest to Knowledge/DIGESTS.
- Skip Step 5.5 and Step 5.7 from the template.
- You MUST write normalized records JSON to: ${RECORDS_FILE}
- Required top-level format: JSON array.
- Required fields per record: bucket, account, threadId, sender_email, subject_latest, summary_latest, draft_status, unsubscribe_url, messageIds.
- For Action Needed records, include suggested_action (single sentence).
- For Monitoring records, include monitoring_owner, monitoring_deliverable, monitoring_deadline when available.
"

if [ "$DRY_RUN" = "true" ]; then
    PROMPT_BASE="${PROMPT_BASE}

## Runtime Override (Dry Run)

- Do NOT queue or create drafts.
- Do NOT create tasks.
- Do NOT update files under core/state/ or projects/.
"
fi

PROMPT_REDUCED="${PROMPT_BASE}

## Runtime Override (Reduced Scope Retry)

This is retry attempt after timeout/hang.
- Process at most the 25 most recent candidate emails after filtering.
- Skip Step 6 project brief updates.
"

run_claude_prompt() {
    local prompt_text="$1"
    run_with_timeout_capture "$CLAUDE_TIMEOUT_SECONDS" \
        "$CLAUDE_PATH" \
        -p "$prompt_text" \
        --model "$MODEL" \
        --permission-mode bypassPermissions \
        --system-prompt "$SYSTEM_PROMPT" \
        --disable-slash-commands \
        --no-session-persistence \
        --strict-mcp-config \
        --mcp-config "$MCP_CONFIG" \
        --tools "$BUILTIN_TOOLS"
    TRIAGE_OUTPUT="$CMD_OUTPUT"
    CLAUDE_EXIT_CODE="$CMD_EXIT_CODE"
}

is_retryable_failure() {
    local code="$1"
    local text="$2"
    if [ "$code" -eq 124 ] || [ "$code" -eq 142 ] || [ "$code" -eq 143 ] || [ "$code" -eq 137 ]; then
        return 0
    fi
    if echo "$text" | grep -Eqi 'prompt is too long|cannot be launched|timed out|timeout|transport|connection error|failed to connect|mcp'; then
        return 0
    fi
    return 1
}

run_preflight() {
    local pre_prompt
    pre_prompt=$(printf '%s\n' \
        "MCP preflight check:" \
        "1) Call mcp__google__gmail_users_messages_list(query='newer_than:1d -label:sent -label:draft', max_results=1)" \
        "2) Call mcp__google-personal__gmail_users_messages_list(query='newer_than:1d -label:sent -label:draft', max_results=1)" \
        "If both succeed, output exactly: PREFLIGHT_OK")

    run_with_timeout_capture "$PRECHECK_TIMEOUT_SECONDS" \
        "$CLAUDE_PATH" \
        -p "$pre_prompt" \
        --model "$MODEL" \
        --permission-mode bypassPermissions \
        --system-prompt "Run the two tool calls exactly and return PREFLIGHT_OK on success." \
        --disable-slash-commands \
        --no-session-persistence \
        --strict-mcp-config \
        --mcp-config "$MCP_CONFIG" \
        --tools "$BUILTIN_TOOLS"
    local pre_output="$CMD_OUTPUT"
    local pre_code="$CMD_EXIT_CODE"
    echo "$pre_output" >> "$LOG_FILE"

    if [ $pre_code -ne 0 ] || ! echo "$pre_output" | grep -q 'PREFLIGHT_OK'; then
        return 1
    fi
    return 0
}

if ! run_preflight; then
    END_TS=$(date "+%Y-%m-%d %H:%M:%S")
    log_line "Email triage (${TIME_LABEL}) FAILED preflight."
    send_alert "ALERT: ${TIME_LABEL} Email Triage Preflight Failed -- ${FULL_DATE}" "The ${TIME_LABEL} email triage preflight failed at ${END_TS}. Check logs/email-triage.log."
    echo "---" >> "$LOG_FILE"
    exit 1
fi

ATTEMPT=1
TRIAGE_OUTPUT=""
CLAUDE_EXIT_CODE=1
while [ $ATTEMPT -le 2 ]; do
    if [ $ATTEMPT -eq 1 ]; then
        run_claude_prompt "$PROMPT_BASE"
    else
        run_claude_prompt "$PROMPT_REDUCED"
    fi

    echo "$TRIAGE_OUTPUT" >> "$LOG_FILE"

    if [ $CLAUDE_EXIT_CODE -eq 0 ]; then
        break
    fi

    if [ $ATTEMPT -eq 1 ] && is_retryable_failure "$CLAUDE_EXIT_CODE" "$TRIAGE_OUTPUT"; then
        log_line "Attempt 1 failed with retryable error (exit ${CLAUDE_EXIT_CODE}); retrying with reduced-scope opus prompt in ${RETRY_DELAY_SECONDS}s..."
        sleep "$RETRY_DELAY_SECONDS"
        ATTEMPT=$((ATTEMPT + 1))
        continue
    fi

    break
done

END_TIMESTAMP=$(date "+%Y-%m-%d %H:%M:%S")

if [ $CLAUDE_EXIT_CODE -ne 0 ]; then
    log_line "Email triage (${TIME_LABEL}) FAILED (exit code ${CLAUDE_EXIT_CODE}, attempt ${ATTEMPT}/2)"
    send_alert "ALERT: ${TIME_LABEL} Email Triage Failed -- ${FULL_DATE}" "The ${TIME_LABEL} email triage failed at ${END_TIMESTAMP}. Exit code: ${CLAUDE_EXIT_CODE}. Check logs/email-triage.log."
    echo "---" >> "$LOG_FILE"
    exit 1
fi

if [ ! -f "$RECORDS_FILE" ]; then
    log_line "Email triage (${TIME_LABEL}) FAILED: records file missing at ${RECORDS_FILE}"
    send_alert "ALERT: ${TIME_LABEL} Email Triage Records Missing -- ${FULL_DATE}" "Records file missing after triage run: ${RECORDS_FILE}."
    echo "---" >> "$LOG_FILE"
    exit 1
fi

if [ -f "$DRAFT_RECOVERY_SCRIPT" ]; then
    run_with_timeout_capture "$DRAFT_RECOVERY_TIMEOUT_SECONDS" \
        python3 "$DRAFT_RECOVERY_SCRIPT" \
        --records "$RECORDS_FILE" \
        --claude "$CLAUDE_PATH" \
        --draft-script "$SUPERHUMAN_DRAFT_SCRIPT" \
        --model "$SEND_MODEL"
    echo "$CMD_OUTPUT" >> "$LOG_FILE"
    if [ $CMD_EXIT_CODE -ne 0 ]; then
        log_line "Draft recovery step failed (exit ${CMD_EXIT_CODE}); continuing with normal reconciliation."
    fi
else
    log_line "Draft recovery script missing at ${DRAFT_RECOVERY_SCRIPT}; skipping."
fi

QUEUED_CANDIDATES=$(python3 - <<PY
import json
count = 0
for rec in json.load(open('$RECORDS_FILE')):
    if isinstance(rec, dict) and str(rec.get('draft_status') or '').lower() == 'queued' and rec.get('threadId'):
        count += 1
print(count)
PY
)

if [ "${QUEUED_CANDIDATES}" -gt 0 ]; then
    log_line "Draft reconciliation: ${QUEUED_CANDIDATES} queued candidate(s); draining watcher queue before render."
    if [ -x "$SUPERHUMAN_DRAFT_WATCHER_SCRIPT" ]; then
        run_with_timeout_capture "$WATCHER_DRAIN_TIMEOUT_SECONDS" "$SUPERHUMAN_DRAFT_WATCHER_SCRIPT"
        echo "$CMD_OUTPUT" >> "$LOG_FILE"
        if [ $CMD_EXIT_CODE -ne 0 ]; then
            log_line "Draft watcher drain returned non-zero (${CMD_EXIT_CODE}); continuing with strict status reconciliation."
        fi
    else
        log_line "Draft watcher script missing/unexecutable at ${SUPERHUMAN_DRAFT_WATCHER_SCRIPT}; continuing with strict status reconciliation."
    fi
fi

python3 - <<PY
import json
from pathlib import Path

records_path = Path("$RECORDS_FILE")
status_path = Path("$DRAFT_STATUS_FILE")
records = json.loads(records_path.read_text(encoding="utf-8"))
status_state = {}
if status_path.exists():
    try:
        status_state = json.loads(status_path.read_text(encoding="utf-8"))
    except Exception:
        status_state = {}
threads = status_state.get("threads", {}) if isinstance(status_state, dict) else {}

def account_email(account: str) -> str:
    if (account or "").strip().lower() == "personal":
        return "lieber.matt@gmail.com"
    return "matt@cornerboothholdings.com"

changed = 0
downgraded = 0
for rec in records:
    if not isinstance(rec, dict):
        continue
    thread_id = str(rec.get("threadId") or "").strip()
    if not thread_id:
        continue
    prev = str(rec.get("draft_status") or "none").strip().lower()
    if prev not in {"queued", "clipboard", "failed", "none"}:
        prev = "none"
    key = f"{account_email(str(rec.get('account') or 'work'))}:{thread_id}"
    rec_state = threads.get(key, {}) if isinstance(threads, dict) else {}
    status = str(rec_state.get("status") or "").strip().lower()

    new = prev
    if prev == "queued":
        if status == "queued":
            new = "queued"
        elif status == "clipboard":
            new = "clipboard"
        else:
            # Any non-final/missing state must not present as draft-ready.
            new = "failed"
    elif prev in {"clipboard", "failed"}:
        if status in {"queued", "clipboard", "failed"}:
            new = status

    if new != prev:
        rec["draft_status"] = new
        changed += 1
        if prev == "queued" and new != "queued":
            downgraded += 1

if changed:
    records_path.write_text(json.dumps(records, indent=2, ensure_ascii=True) + "\\n", encoding="utf-8")

print(f"DRAFT_STATUS_RECONCILED changed={changed} downgraded_from_queued={downgraded}")
PY

python3 - <<PY
import json, sys
p = '$RECORDS_FILE'
obj = json.load(open(p))
if not isinstance(obj, list):
    raise SystemExit('records file is not an array')
print(f'Records count: {len(obj)}')
PY

set +e
SUMMARY_CHECK_OUTPUT=$(python3 - <<PY
import json
import sys

records = json.load(open("$RECORDS_FILE"))
core_buckets = {"action needed", "action_needed", "already addressed", "already_addressed", "monitoring", "fyi"}
summary_fields = ("summary_latest", "summary", "summary_brief", "body_preview", "snippet")

total_core = 0
core_with_summary = 0
action_needed_missing = 0

for rec in records:
    if not isinstance(rec, dict):
        continue
    bucket = str(rec.get("bucket") or "").strip().lower()
    if bucket not in core_buckets:
        continue
    total_core += 1
    has_summary = any(str(rec.get(field) or "").strip() for field in summary_fields)
    if has_summary:
        core_with_summary += 1
    elif bucket in {"action needed", "action_needed"}:
        action_needed_missing += 1

coverage = (core_with_summary / total_core) if total_core else 1.0
print(f"SUMMARY_COVERAGE total_core={total_core} with_summary={core_with_summary} coverage={coverage:.2f} action_needed_missing={action_needed_missing}")

if total_core > 0 and (coverage < 0.85 or action_needed_missing > 0):
    sys.exit(1)
PY
)
SUMMARY_CHECK_EXIT=$?
set -e
echo "$SUMMARY_CHECK_OUTPUT" >> "$LOG_FILE"

if [ $SUMMARY_CHECK_EXIT -ne 0 ]; then
    log_line "Email triage (${TIME_LABEL}) FAILED summary coverage check."
    send_alert "ALERT: ${TIME_LABEL} Email Triage Summary Coverage Failed -- ${FULL_DATE}" "Records lacked required summary text (coverage < 85% or Action Needed missing summary)."
    echo "---" >> "$LOG_FILE"
    exit 1
fi

set +e
DRAFT_ENFORCE_OUTPUT=$(python3 - <<PY
import json
import re
import sys

records = json.load(open("$RECORDS_FILE"))
reply_hint = re.compile(r"\\b(reply|respond|confirmation|confirm|email|send)\\b", re.IGNORECASE)

eligible = []
missing = []
for rec in records:
    if not isinstance(rec, dict):
        continue
    bucket = str(rec.get("bucket") or "").strip().lower().replace("_", " ")
    if bucket != "action needed":
        continue
    suggested = str(rec.get("suggested_action") or "").strip()
    if not suggested or not reply_hint.search(suggested):
        continue
    status = str(rec.get("draft_status") or "").strip().lower()
    row = {
        "threadId": str(rec.get("threadId") or ""),
        "subject": str(rec.get("subject_latest") or ""),
        "status": status,
    }
    eligible.append(row)
    if status != "queued":
        missing.append(row)

print(f"DRAFT_ENFORCE eligible={len(eligible)} queued={len(eligible)-len(missing)} missing={len(missing)}")
for row in missing[:8]:
    print(f"MISSING_DRAFT threadId={row['threadId']} status={row['status']} subject={row['subject']}")

if "$REQUIRE_REPLY_DRAFTS".lower() == "true" and missing:
    sys.exit(1)
PY
)
DRAFT_ENFORCE_EXIT=$?
set -e
echo "$DRAFT_ENFORCE_OUTPUT" >> "$LOG_FILE"

if [ $DRAFT_ENFORCE_EXIT -ne 0 ]; then
    log_line "Email triage (${TIME_LABEL}) FAILED reply-draft enforcement."
    send_alert "ALERT: ${TIME_LABEL} Email Triage Draft Enforcement Failed -- ${FULL_DATE}" "Action Needed reply items did not produce queued drafts. See logs/email-triage.log."
    echo "---" >> "$LOG_FILE"
    exit 1
fi

python3 "$TRIAGE_RENDER_SCRIPT" \
    --records "$RECORDS_FILE" \
    --output "$DIGEST_FILE" \
    --html-output "$HTML_FILE" \
    --date-label "${DAY_OF_WEEK} ${FULL_DATE}" \
    --time-label "${TIME_DISPLAY}" \
    --run-type "${TIME_LABEL}" \
    --last-triage "${LAST_TRIAGE_TIMESTAMP}"

set +e
VALIDATION_OUTPUT=$(python3 "$TRIAGE_VALIDATOR_SCRIPT" report --markdown "$DIGEST_FILE" --contract "$TRIAGE_CONTRACT_FILE" 2>&1)
VALIDATION_EXIT=$?
set -e

echo "$VALIDATION_OUTPUT" >> "$LOG_FILE"

if [ $VALIDATION_EXIT -ne 0 ]; then
    log_line "Email triage (${TIME_LABEL}) FAILED post-render validation."
    python3 - <<PY
import json
p='$STATE_FILE'
try:
  d=json.load(open(p))
  d['emails_processed']=0
  json.dump(d,open(p,'w'),indent=2)
except Exception:
  pass
PY
    send_alert "ALERT: ${TIME_LABEL} Email Triage Validation Failed -- ${FULL_DATE}" "Validation failed for rendered digest at ${DIGEST_FILE}."
    echo "---" >> "$LOG_FILE"
    exit 1
fi

set +e
HTML_SANITY_OUTPUT=$(python3 - <<PY
from pathlib import Path
import sys

p = Path("$HTML_FILE")
if not p.exists():
    print(f"Missing HTML output: {p}")
    sys.exit(1)

text = p.read_text(encoding="utf-8")
low = text.lower()
errors = []

if "<pre" in low:
    errors.append("HTML body contains <pre>; markdown fallback rendering detected")
if "# inbox triage" in low or "\n## " in text:
    errors.append("HTML body contains raw markdown heading tokens")
if "](https://mail.superhuman.com/" in text or "[view](" in low or "[draft ready](" in low:
    errors.append("HTML body contains markdown link syntax")
if "&#35;" in text or "&#91;" in text or "&#93;" in text:
    errors.append("HTML body appears to contain escaped markdown control characters")
if "border-bottom:2px solid #111" not in text:
    errors.append("HTML body missing required section divider styling")
if "<a href=" not in low:
    errors.append("HTML body missing anchor tags")

# Locked compact profile checks (reference-style layout).
required_tokens = [
    "triage-html-profile:compact_ref_v1",
    "padding:22px;background:#ffffff",
    "max-width:760px;margin:0 auto",
    "font-size:18px;font-weight:600;margin:0 0 12px 0",
    "font-size:23px;font-weight:800",
    "border-radius:6px;padding:10px 12px;font-size:15.5px",
]
for token in required_tokens:
    if token not in text:
        errors.append(f"HTML body missing locked style token: {token}")

if errors:
    for err in errors:
        print(err)
    sys.exit(1)

print("HTML_SANITY_OK")
PY
)
HTML_SANITY_EXIT=$?
set -e

echo "$HTML_SANITY_OUTPUT" >> "$LOG_FILE"

if [ $HTML_SANITY_EXIT -ne 0 ]; then
    log_line "Email triage (${TIME_LABEL}) FAILED HTML sanity check."
    send_alert "ALERT: ${TIME_LABEL} Email Triage HTML Render Failed -- ${FULL_DATE}" "HTML render sanity check failed for ${HTML_FILE}. Check logs/email-triage.log."
    echo "---" >> "$LOG_FILE"
    exit 1
fi

if [ "$DRY_RUN" = "true" ]; then
    log_line "Email triage (${TIME_LABEL}) dry-run completed successfully."
    echo "---" >> "$LOG_FILE"
    exit 0
fi

NEW_COUNT=$(python3 - <<PY
import json
print(len(json.load(open('$RECORDS_FILE'))))
PY
)

SEND_SUBJECT="Inbox Triage -- ${DAY_OF_WEEK} ${FULL_DATE}, ${TIME_DISPLAY} (${NEW_COUNT} new)"
SEND_PROMPT=$(cat <<EOF2
Read plain-text email body from: ${DIGEST_FILE}
Read HTML email body from: ${HTML_FILE}
Send an email via mcp__google__gmail_users_messages_send to matt@cornerboothholdings.com with subject '${SEND_SUBJECT}' and BOTH fields:
- body: exact plain-text content from ${DIGEST_FILE}
- html_body: exact HTML content from ${HTML_FILE}
Call mcp__google__gmail_users_messages_send exactly once. Do not escape or transform the HTML.
EOF2
)

SEND_ATTEMPT=1
SEND_EXIT=1
while [ $SEND_ATTEMPT -le $SEND_MAX_ATTEMPTS ]; do
    run_with_timeout_capture "$SEND_TIMEOUT_SECONDS" \
        "$CLAUDE_PATH" \
        -p "$SEND_PROMPT" \
        --model "$SEND_MODEL" \
        --permission-mode bypassPermissions \
        --system-prompt "Send the specified email immediately. Do not ask questions." \
        --disable-slash-commands \
        --no-session-persistence \
        --strict-mcp-config \
        --mcp-config "$MCP_CONFIG" \
        --tools "$BUILTIN_TOOLS"
    SEND_EXIT=$CMD_EXIT_CODE
    echo "$CMD_OUTPUT" >> "$LOG_FILE"

    if [ $SEND_EXIT -eq 0 ]; then
        break
    fi

    if [ $SEND_ATTEMPT -lt $SEND_MAX_ATTEMPTS ] && is_retryable_failure "$SEND_EXIT" "$CMD_OUTPUT"; then
        log_line "Final send attempt ${SEND_ATTEMPT} failed with retryable error (exit ${SEND_EXIT}); retrying in ${RETRY_DELAY_SECONDS}s..."
        sleep "$RETRY_DELAY_SECONDS"
        SEND_ATTEMPT=$((SEND_ATTEMPT + 1))
        continue
    fi

    break
done

if [ $SEND_EXIT -ne 0 ]; then
    SEND_FAIL_TS=$(date "+%Y-%m-%d %H:%M:%S")
    log_line "Email triage (${TIME_LABEL}) FAILED final send step (exit ${SEND_EXIT}, attempt ${SEND_ATTEMPT}/${SEND_MAX_ATTEMPTS})."
    send_alert "ALERT: ${TIME_LABEL} Email Triage Send Failed -- ${FULL_DATE}" "Rendered digest validated but final send failed at ${SEND_FAIL_TS}. Exit code: ${SEND_EXIT}. Attempt: ${SEND_ATTEMPT}/${SEND_MAX_ATTEMPTS}."
    echo "---" >> "$LOG_FILE"
    exit 1
fi

log_line "Email triage (${TIME_LABEL}) completed successfully."
echo "---" >> "$LOG_FILE"
