---
title: "MCP Google Services Authentication - Tokens Expired or Missing"
tags:
  - mcp
  - oauth
  - google-calendar
  - gmail
  - authentication
category: integration-issues
symptoms:
  - "Authentication tokens are no longer valid"
  - "No access, refresh token, API key or refresh handler callback is set"
  - "MCP server shows connected but tools return auth errors"
module: mcp-servers
created: 2026-01-22
---

# MCP Google Services Authentication - Tokens Expired or Missing

## Problem

Google Calendar and Gmail MCP servers appear "connected" (processes running) but return authentication errors when tools are called:

**Calendar error:**
```
Authentication tokens are no longer valid. Please restart the server to re-authenticate.
```

**Gmail error:**
```
No access, refresh token, API key or refresh handler callback is set.
```

## Root Cause

MCP servers can be running (process active) but lack valid OAuth tokens. This happens when:
1. OAuth tokens were never generated (first-time setup incomplete)
2. OAuth tokens expired and weren't refreshed
3. Token files are missing or in wrong location

**Key insight:** "Connected" in `/mcp` output means the process is running, NOT that authentication is valid.

## Investigation Steps

1. **Verify processes are running:**
   ```bash
   ps aux | grep -E "(gmail|calendar)" | grep -v grep
   ```

2. **Check token file locations:**
   - Calendar: `~/.config/google-calendar-mcp/tokens.json`
   - Gmail: `~/.gmail-mcp/credentials.json`
   - Google Drive: `~/.config/google-drive-mcp/tokens.json`

3. **Check MCP configuration:**
   ```bash
   cat ~/.claude.json | grep -A 10 '"gmail\|"google-calendar'
   ```
   Look for `GOOGLE_OAUTH_CREDENTIALS` env var pointing to your OAuth keys file.

## Solution

### For Google Calendar MCP (@cocal/google-calendar-mcp)

```bash
# Run auth flow (opens browser)
GOOGLE_OAUTH_CREDENTIALS="/path/to/gcp-oauth.keys.json" npx -y @cocal/google-calendar-mcp auth

# Tokens saved to: ~/.config/google-calendar-mcp/tokens.json
```

### For Gmail MCP (@gongrzhe/server-gmail-autoauth-mcp)

```bash
# 1. Create config directory and copy OAuth keys
mkdir -p ~/.gmail-mcp
cp /path/to/gcp-oauth.keys.json ~/.gmail-mcp/

# 2. Run auth flow (opens browser)
npx @gongrzhe/server-gmail-autoauth-mcp auth

# Credentials saved to: ~/.gmail-mcp/credentials.json
```

### After Re-Authentication

**Restart Claude Code** to reload MCP servers with new credentials:
- Exit current session (`Ctrl+C` or `/exit`)
- Start new session (`claude` or `brain`)

The MCP servers load tokens at startup, so a restart is required after generating new tokens.

## Prevention

1. **Check token expiry:** Google OAuth refresh tokens typically last 6 months if unused
2. **Monitor for errors:** If auth errors appear, re-run the auth commands above
3. **Backup tokens:** Consider backing up `~/.gmail-mcp/` and `~/.config/google-calendar-mcp/` directories

## Token File Locations Summary

| Service | Package | Token Location |
|---------|---------|----------------|
| Calendar | @cocal/google-calendar-mcp | `~/.config/google-calendar-mcp/tokens.json` |
| Gmail | @gongrzhe/server-gmail-autoauth-mcp | `~/.gmail-mcp/credentials.json` |
| Drive | @piotr-agier/google-drive-mcp | `~/.config/google-drive-mcp/tokens.json` |

## Related

- [MCP Authentication Reference](/Users/homeserver/.claude/plugins/marketplaces/claude-plugins-official/plugins/plugin-dev/skills/mcp-integration/references/authentication.md)
- [Daily Digest Integration](/Users/homeserver/Obsidian/personal-os/core/integrations/digest/README.md)
