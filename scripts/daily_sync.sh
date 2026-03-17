#!/bin/bash
#
# Daily PnT Data Warehouse Sync
# Runs Toast + Weather ETLs for yesterday's data.
# Designed to be called by launchd daily at 6 AM.
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="$SCRIPT_DIR/../logs"
mkdir -p "$LOG_DIR"

DATE=$(date -v-1d +%Y-%m-%d 2>/dev/null || date -d "yesterday" +%Y-%m-%d)
LOG_FILE="$LOG_DIR/daily_sync_$(date +%Y%m%d).log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

log "=== Daily PnT Sync - $DATE ==="

# Toast ETL
log "Running Toast ETL..."
if python3 "$SCRIPT_DIR/toast_etl.py" --date "$DATE" 2>> "$LOG_FILE"; then
    log "Toast ETL complete."
else
    log "ERROR: Toast ETL failed (exit code $?)."
fi

# Toast Analytics ETL
log "Running Toast Analytics ETL..."
if python3 "$SCRIPT_DIR/toast_analytics_etl.py" --rolling-days 3 2>> "$LOG_FILE"; then
    log "Toast Analytics ETL complete."
else
    log "ERROR: Toast Analytics ETL failed (exit code $?)."
fi

# Weather ETL
log "Running Weather ETL..."
if python3 "$SCRIPT_DIR/weather_etl.py" --date "$DATE" 2>> "$LOG_FILE"; then
    log "Weather ETL complete."
else
    log "ERROR: Weather ETL failed (exit code $?)."
fi

log "=== Daily sync finished ==="
