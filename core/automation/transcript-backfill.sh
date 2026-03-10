#!/bin/bash
# Transcript Backfill — Fetches Granola raw transcripts and appends to Obsidian meeting notes
# Runs every 2 hours via launchd (com.brain.transcript-backfill.plist)
# Processes 3 meetings per batch to stay within Granola rate limits
# (Granola rate-limits after ~4 transcript fetches; cooldown is several minutes)
#
# State file: core/state/transcript-backfill.json
# Queue: newest meetings first, ~1,049 total with UUIDs
#
# To test manually:
#   ./core/automation/transcript-backfill.sh
#
# To check progress:
#   python3 -c "import json; d=json.load(open('core/state/transcript-backfill.json')); print(f'Done: {len(d.get(\"completed\",{}))} | Skipped: {len(d.get(\"skipped\",{}))} | Failed: {len(d.get(\"failed\",{}))} | Queue: {len(d[\"backfill_queue\"])}')"

set -e

# Allow running from within a Claude Code session (manual testing)
unset CLAUDECODE 2>/dev/null || true

# Configuration
CLAUDE_PATH="/Users/homeserver/.local/bin/claude"
WORKING_DIR="/Users/homeserver/Obsidian/personal-os"
LOG_DIR="${WORKING_DIR}/logs"
LOG_FILE="${LOG_DIR}/transcript-backfill.log"
STATE_FILE="${WORKING_DIR}/core/state/transcript-backfill.json"
TRANSCRIPTS_DIR="${WORKING_DIR}/Knowledge/TRANSCRIPTS"
BATCH_SIZE=3
TIMESTAMP=$(date "+%Y-%m-%d %H:%M:%S")

# Ensure directories exist
mkdir -p "$LOG_DIR"

# Change to working directory
cd "$WORKING_DIR"

echo "[$TIMESTAMP] Starting transcript backfill batch..." >> "$LOG_FILE"

# Check if state file exists
if [ ! -f "$STATE_FILE" ]; then
    echo "[$TIMESTAMP] ERROR: State file not found at $STATE_FILE" >> "$LOG_FILE"
    exit 1
fi

# Pre-compute the next batch using Python (saves Claude tokens)
BATCH_JSON=$(python3 << 'PYEOF'
import json, sys

state_file = "/Users/homeserver/Obsidian/personal-os/core/state/transcript-backfill.json"
transcripts_dir = "/Users/homeserver/Obsidian/personal-os/Knowledge/TRANSCRIPTS"
batch_size = 3

with open(state_file) as f:
    state = json.load(f)

completed = set(state.get("completed", {}).keys())
skipped = set(state.get("skipped", {}).keys())
failed = set(state.get("failed", {}).keys())
done_set = completed | skipped

# Find next batch: skip completed/skipped, include failed (retry them)
batch = []
for item in state["backfill_queue"]:
    fn = item["filename"]
    if fn in done_set:
        continue
    # Check if file already has a transcript section (safety check)
    fpath = f"{transcripts_dir}/{fn}"
    try:
        with open(fpath) as f:
            content = f.read()
        if "## Transcript" in content:
            # Already done (maybe by another process), mark as skipped
            continue
    except FileNotFoundError:
        continue
    batch.append({"filename": fn, "uuid": item["uuid"]})
    if len(batch) >= batch_size:
        break

if not batch:
    print("EMPTY")
else:
    print(json.dumps(batch))
PYEOF
)

# Check if there's work to do
if [ "$BATCH_JSON" = "EMPTY" ]; then
    echo "[$TIMESTAMP] No more files to process. Backfill may be complete." >> "$LOG_FILE"
    echo "---" >> "$LOG_FILE"
    exit 0
fi

echo "[$TIMESTAMP] Batch: $BATCH_JSON" >> "$LOG_FILE"

# Build the Claude prompt with the exact files to process
PROMPT="AUTOMATED TRANSCRIPT BACKFILL

You are processing a batch of meeting files to add raw verbatim transcripts from Granola.

BATCH TO PROCESS (JSON array of {filename, uuid}):
${BATCH_JSON}

For EACH item in the batch, do the following IN SEQUENCE (one at a time, not parallel):

1. Call mcp__granola__get_meeting_transcript with meeting_id set to the uuid
2. If the transcript is non-empty (more than 50 characters):
   a. Read the file at Knowledge/TRANSCRIPTS/<filename>
   b. Append to the END of the file: two newlines, then '## Transcript', two newlines, then the full transcript text
   c. Verify the file now contains '## Transcript' by reading it back (just check the last few lines)
   d. Record as completed
3. If the transcript is empty or null: record as skipped (reason: 'no transcript available')
4. If there's an API error or rate limit: record as failed with the error message, then STOP processing remaining items

After processing all items (or stopping on error), update the state file:
1. Read core/state/transcript-backfill.json
2. For each completed file: add to 'completed' dict with key=filename, value={\"timestamp\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}
3. For each skipped file: add to 'skipped' dict with key=filename, value={\"reason\": \"...\", \"timestamp\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}
4. For each failed file: add to (or update in) 'failed' dict with key=filename, value={\"reason\": \"...\", \"uuid\": \"...\", \"timestamp\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}
5. Update 'last_batch' to current ISO timestamp
6. Increment 'batches_processed' by 1
7. Write the updated state file back

IMPORTANT RULES:
- Fetch transcripts ONE AT A TIME with a 15-second pause between each (to avoid rate limits). Use Bash 'sleep 15' between fetches. Granola rate-limits after ~4 calls; 15s delay keeps us safe at 3 per batch.
- Do NOT use AskUserQuestion - this is headless
- Do NOT send any emails or messages
- Do NOT modify anything except the transcript files and state file
- If a file already has a '## Transcript' section, skip it (record as skipped, reason: 'already has transcript')
- Write the FULL transcript - do not truncate or summarize
- For large transcripts, use the Write tool to write to a temp file first, then use a Python script to append it to the target file. This avoids truncation issues with Bash heredocs."

# Run Claude
SYNC_OUTPUT=$("$CLAUDE_PATH" \
    -p "$PROMPT" \
    --permission-mode bypassPermissions \
    2>&1) || true

EXIT_CODE=$?
END_TIMESTAMP=$(date "+%Y-%m-%d %H:%M:%S")

# Log output (truncated to last 200 lines to keep log manageable)
echo "$SYNC_OUTPUT" | tail -200 >> "$LOG_FILE"

if [ $EXIT_CODE -eq 0 ]; then
    echo "[$END_TIMESTAMP] Transcript backfill batch completed successfully." >> "$LOG_FILE"
else
    echo "[$END_TIMESTAMP] Transcript backfill batch failed with exit code $EXIT_CODE" >> "$LOG_FILE"
fi

# Log current progress
python3 << 'PYEOF' >> "$LOG_FILE"
import json
try:
    with open("/Users/homeserver/Obsidian/personal-os/core/state/transcript-backfill.json") as f:
        d = json.load(f)
    c = len(d.get("completed", {}))
    s = len(d.get("skipped", {}))
    f = len(d.get("failed", {}))
    q = len(d["backfill_queue"])
    remaining = q - c - s
    print(f"  Progress: {c} completed, {s} skipped, {f} failed, ~{remaining} remaining")
except Exception as e:
    print(f"  Could not read state: {e}")
PYEOF

echo "---" >> "$LOG_FILE"
