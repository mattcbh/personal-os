#!/bin/bash
# chrome-cdp-helper.sh — Thin wrapper around Chrome DevTools Protocol HTTP endpoints
#
# Chrome must be running with --remote-debugging-port=9222 for these to work.
# All commands use 3-second HTTP timeouts via curl, so they never hang.
#
# Subcommands:
#   health              Exit 0 if CDP responsive, 1 if not
#   find-tab URL_PREFIX Print TAB_ID (wsDebuggerUrl path) if a tab URL starts with prefix
#   activate TAB_ID     Bring tab to foreground via CDP
#   open-tab URL        Open a new tab at URL
#   list                Print all tab URLs and IDs (tsv)
#
# Exit codes:
#   0 — Success
#   1 — CDP not available or tab not found

set -euo pipefail

CDP_PORT="${CDP_PORT:-9222}"
CDP_BASE="http://localhost:${CDP_PORT}"
CURL_TIMEOUT=3

# --- health ---
cmd_health() {
  curl -s --max-time "$CURL_TIMEOUT" "${CDP_BASE}/json/version" >/dev/null 2>&1
}

# --- find-tab URL_PREFIX ---
cmd_find_tab() {
  local url_prefix="$1"
  local json
  json=$(curl -s --max-time "$CURL_TIMEOUT" "${CDP_BASE}/json" 2>/dev/null) || return 1

  python3 -c "
import json, sys
tabs = json.loads(sys.stdin.read())
prefix = sys.argv[1]
for tab in tabs:
    url = tab.get('url', '')
    if url.startswith(prefix) and tab.get('type') == 'page':
        # Extract tab ID from webSocketDebuggerUrl or use 'id' field
        tab_id = tab.get('id', '')
        if tab_id:
            print(tab_id)
            sys.exit(0)
print('', file=sys.stderr)
sys.exit(1)
" "$url_prefix" <<< "$json"
}

# --- activate TAB_ID ---
cmd_activate() {
  local tab_id="$1"
  curl -s --max-time "$CURL_TIMEOUT" "${CDP_BASE}/json/activate/${tab_id}" >/dev/null 2>&1
}

# --- open-tab URL ---
cmd_open_tab() {
  local url="$1"
  curl -s --max-time "$CURL_TIMEOUT" "${CDP_BASE}/json/new?${url}" >/dev/null 2>&1
}

# --- list ---
cmd_list() {
  local json
  json=$(curl -s --max-time "$CURL_TIMEOUT" "${CDP_BASE}/json" 2>/dev/null) || return 1

  python3 -c "
import json, sys
tabs = json.loads(sys.stdin.read())
for tab in tabs:
    if tab.get('type') == 'page':
        tab_id = tab.get('id', '')
        url = tab.get('url', '')
        title = tab.get('title', '')
        print(f'{tab_id}\t{url}\t{title}')
" <<< "$json"
}

# --- Main dispatch ---
cmd="${1:-}"
shift || true

case "$cmd" in
  health)
    cmd_health
    ;;
  find-tab)
    if [[ -z "${1:-}" ]]; then
      echo "Usage: chrome-cdp-helper.sh find-tab URL_PREFIX" >&2
      exit 1
    fi
    cmd_find_tab "$1"
    ;;
  activate)
    if [[ -z "${1:-}" ]]; then
      echo "Usage: chrome-cdp-helper.sh activate TAB_ID" >&2
      exit 1
    fi
    cmd_activate "$1"
    ;;
  open-tab)
    if [[ -z "${1:-}" ]]; then
      echo "Usage: chrome-cdp-helper.sh open-tab URL" >&2
      exit 1
    fi
    cmd_open_tab "$1"
    ;;
  list)
    cmd_list
    ;;
  *)
    echo "Usage: chrome-cdp-helper.sh {health|find-tab|activate|open-tab|list}" >&2
    exit 1
    ;;
esac
