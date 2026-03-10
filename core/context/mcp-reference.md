## MCP Reference

Detailed reference for MCP integrations, lookup workflows, and tool quirks. Loaded on demand when working with these systems.

### Communications Lookup (Contacts + Beeper + Gmail)

**ALWAYS use this workflow when asked about communications with a person:**
- "Do I have chats with [name]?"
- "What did [name] say?"
- "Show me messages/emails from [name]"
- "What's my conversation with [name]?"
- "Have I heard from [name]?"
- Any question involving a person + messages/chats/texts/emails/communication

**Workflow:**
1. FIRST use `mcp__contacts__lookup_name` to get their phone number(s) AND email(s)
2. Search Beeper using BOTH the name AND all phone numbers found
3. Search both Gmail accounts:
   - **Work** (`mcp__google__gmail_users_messages_list`): use `from:[email] OR to:[email]` (or `from:[name] OR to:[name]` if no email)
   - **Personal** (`mcp__google-personal__gmail_users_messages_list`): same query
4. Combine and present results from all platforms (iMessage, WhatsApp, Instagram, Work Gmail, Personal Gmail)

**Why this matters:**
- iMessage/SMS chats are stored by phone number only, not contact name
- Email threads won't appear in Beeper
- Without contacts lookup first, you'll miss communications entirely

**CRITICAL - Beeper phone number search format:**
- iMessage/SMS chats are indexed by phone number, NOT contact name
- When searching Beeper for SMS/iMessage chats, use the phone number WITH SPACES: `718 312 9296`
- Other formats like `+17183129296` or `7183129296` often fail to match
- Always try the spaced format first: `[area code] [first 3] [last 4]`

**CRITICAL - Beeper search_messages 404 bug:**
- `search_messages` with certain keywords (e.g., "pies", "Sarah") triggers `404 Chat not found` due to a corrupted/deleted chat in the search index
- Other keywords ("construction", "singer", "flatbush") work fine
- This is a Beeper-side bug, not fixable from our end
- **Workaround:** Use contacts lookup → phone number → `search_chats` (to get chatIDs) → `list_messages` (by chatID). `list_messages` always works reliably.
- `search_messages` with a `chatIDs` filter avoids the 404 but may still miss results; `list_messages` is preferred

### Supabase (PnT Data Warehouse)

Restaurant analytics for Pies 'n' Thighs. **ALWAYS query this first** when asked about sales, revenue, transactions, order volume, menu performance, weather impact, reviews, labor, food cost, financials, P&L, or any business analytics/data question about PnT.

Use `mcp__supabase__execute_sql` with project ID `zxqtclvljxvdxsnmsqka`. Show the SQL you ran alongside results.

Key tables: `orders`, `order_items`, `menu_items`, `financials`, `reviews`, `weather`, `labor_daily`, `time_punches`, `invoices`, `invoice_items`, `billcom_bills`, `billcom_se_transactions`.

Key views: `v_daily_sales`, `v_weather_sales`, `v_menu_performance`, `v_labor_sales`, `v_food_cost_daily`, `v_financials_best`, `v_transactions_best`, `v_data_freshness`.

For owner-safe financial queries, prefer `v_financials_best` and `v_transactions_best` over the raw dual-source tables unless you explicitly need to compare `systematiq` versus `qbo`.

Note: some item names have variant spellings between CSV and API loads (e.g., "Apple Pie-Whole" vs "Apple Pie, Whole") - always use ILIKE and aggregate across variants.

**Timeout limitation:** `execute_sql` and `apply_migration` have an ~60s HTTP timeout. Operations on large tables (VACUUM, CREATE INDEX on 800MB+ tables) will time out. VACUUM also cannot run via `execute_sql` (it wraps queries in transactions). For long-running maintenance, use the Supabase SQL Editor dashboard or a direct psql connection.

Full schema and ETL docs: `@core/context/data-warehouse.md`

### Granola (Meeting Notes)

Uses the official remote MCP at `https://mcp.granola.ai/mcp`, configured in `~/.mcp.json`.

Meeting sync is currently skill-driven (`/meeting-sync`), not an active scheduled launchd job in this repo. **When asked about meetings, search `Knowledge/TRANSCRIPTS/` first** before using MCP tools for historical lookup.

**Granola direct API (for bulk operations only):**
- Endpoint: `POST https://api.granola.ai/v1/get-document-transcript` with `{"document_id": UUID}`
- Auth: WorkOS bearer token from `~/Library/Application Support/Granola/supabase.json` (field: `workos_tokens`, JSON string containing `access_token` + `refresh_token`)
- Headers: `Authorization: Bearer {token}`, `User-Agent: Granola/5.354.0`
- Rate limit: ~300 req/min (safe at 2 req/sec). MCP throttles at ~4 calls; direct API does not.
- Token refresh: `POST https://api.workos.com/user_management/authenticate` with `grant_type: refresh_token`, `client_id: client_01JZJ0XBDAT8PHJWQY09Y0VD61`. Refresh tokens are one-time-use; save new token immediately.
- Response: array of utterances (`source: "microphone"` = Me, `source: "system"` = Them)
- Direct API helper scripts are not currently part of the active in-repo runtime baseline.

### Google Workspace (Gmail, Calendar, Drive via `gws` CLI)

All Google services are accessed via the official Google Workspace CLI (`gws`, `@googleworkspace/cli`), which runs as an MCP server using `gws mcp -s <services>`.

**Two accounts configured:**

| Account | MCP Server Name | Services | Address |
|---------|----------------|----------|---------|
| **Work** | `google` | gmail, calendar, drive | matt@cornerboothholdings.com |
| **Personal** | `google-personal` | gmail, calendar | lieber.matt@gmail.com |

**Key tool name patterns (prefixed by server name):**
- Gmail: `gmail_users_messages_list` (search), `gmail_users_messages_get` (read), `gmail_users_messages_send` (send)
- Calendar: `calendar_events_list`, `calendar_events_insert`, `calendar_events_get`
- Drive: `drive_files_list`, `drive_files_get`, `drive_files_download`
- Full tool list: 79 Gmail + 37 Calendar + 57 Drive per server

When searching emails, default to the last 7 days unless specified otherwise. Always search both accounts for triage, promises, and followup workflows.

**Auth credentials:**
- Work: `~/.gmail-mcp/gws-authorized-user.json`
- Personal: `~/.gmail-mcp-personal/gws-authorized-user.json`
- Both are `authorized_user` type credential files used via `GOOGLE_WORKSPACE_CLI_CREDENTIALS_FILE` env var
- GCP project: `open-ai-470517` (both accounts)

**Re-authenticating an account:**

Since the Mac Mini is headless (SSH only), use this two-step manual flow:

1. **Generate the auth URL** with PKCE from the Mac Mini:
   ```bash
   cd /Users/homeserver/mcp-servers/google && uv run python -c "
   import json, hashlib, base64, secrets
   from urllib.parse import urlencode
   with open('<HOME_DIR>/gcp-oauth.keys.json') as f:
       config = json.load(f)['installed']
   code_verifier = secrets.token_urlsafe(64)
   code_challenge = base64.urlsafe_b64encode(
       hashlib.sha256(code_verifier.encode()).digest()
   ).rstrip(b'=').decode()
   with open('/tmp/oauth_verifier.json', 'w') as f:
       json.dump({'code_verifier': code_verifier, 'client_id': config['client_id'],
                  'client_secret': config['client_secret'], 'token_uri': config['token_uri']}, f)
   SCOPES = ['https://www.googleapis.com/auth/gmail.readonly','https://www.googleapis.com/auth/gmail.send',
     'https://www.googleapis.com/auth/gmail.labels','https://www.googleapis.com/auth/gmail.modify',
     'https://www.googleapis.com/auth/gmail.settings.basic','https://www.googleapis.com/auth/calendar.readonly',
     'https://www.googleapis.com/auth/calendar.events','https://www.googleapis.com/auth/calendar.freebusy',
     'https://www.googleapis.com/auth/drive','https://www.googleapis.com/auth/drive.file']
   params = {'client_id': config['client_id'], 'redirect_uri': 'http://localhost:9876/',
     'response_type': 'code', 'scope': ' '.join(SCOPES), 'access_type': 'offline',
     'prompt': 'consent', 'code_challenge': code_challenge, 'code_challenge_method': 'S256'}
   print(config['auth_uri'] + '?' + urlencode(params))
   "
   ```
   Replace `<HOME_DIR>` with `~/.gmail-mcp` (work) or `~/.gmail-mcp-personal` (personal).

2. **Visit the URL** in a browser, sign in, authorize. The redirect to `localhost:9876` will fail (expected). **Copy the full URL from the address bar** (contains `?code=...`).

3. **Exchange the code for tokens** on the Mac Mini:
   ```bash
   cd /Users/homeserver/mcp-servers/google && uv run python -c "
   import json
   from urllib.parse import urlparse, parse_qs
   from google.oauth2.credentials import Credentials
   import requests as req
   with open('/tmp/oauth_verifier.json') as f:
       v = json.load(f)
   code = parse_qs(urlparse('<PASTE_FULL_REDIRECT_URL>').query)['code'][0]
   r = req.post(v['token_uri'], data={'client_id': v['client_id'], 'client_secret': v['client_secret'],
     'code': code, 'code_verifier': v['code_verifier'], 'grant_type': 'authorization_code',
     'redirect_uri': 'http://localhost:9876/'})
   token_data = r.json()
   creds = Credentials(token=token_data['access_token'], refresh_token=token_data.get('refresh_token'),
     token_uri=v['token_uri'], client_id=v['client_id'], client_secret=v['client_secret'],
     scopes=token_data.get('scope','').split(' '))
   with open('<HOME_DIR>/gws-authorized-user.json', 'w') as f:
       json.dump({'type': 'authorized_user', 'client_id': v['client_id'],
                  'client_secret': v['client_secret'], 'refresh_token': token_data.get('refresh_token')}, f)
   print('Saved!')
   "
   ```
   Replace `<HOME_DIR>` with `~/.gmail-mcp` (work) or `~/.gmail-mcp-personal` (personal). Clean up: `rm /tmp/oauth_verifier.json`

4. **Reconnect** the MCP server: run `/mcp` in Claude Code.

**GCP test users:** The OAuth app is in testing mode. Both `matt@cornerboothholdings.com` and `lieber.matt@gmail.com` must be listed as test users in Google Cloud Console (project `open-ai-470517`).

**Automation note:** Headless automation scripts use per-automation MCP configs in `core/automation/mcp-configs/`. These use `-s gmail` or `-s gmail,calendar` (not drive) to minimize tool count in the prompt. The custom Python MCP server at `/Users/homeserver/mcp-servers/google/` is retired; all Google access now goes through `gws`.

### Excalidraw (Diagramming)

Programmatic diagramming with full element-level control. **Default tool for all workflow diagrams, architecture diagrams, and any visual that needs iterative editing.** When Matt asks for a diagram, flowchart, or visual - use Excalidraw.

23 MCP tools: create/update/delete elements, align, group, export, screenshot.

- **Canvas server:** `http://localhost:3000` (launchd: `com.excalidraw.canvas`, auto-starts on boot)
- **Matt's access from laptop:** `http://192.168.1.77:3000`
- **MCP server:** `~/Projects/mcp_excalidraw/` (community: yctimlin/mcp_excalidraw)
- **Key tools:** `create_element`, `update_element`, `batch_create_elements`, `align_elements`, `distribute_elements`, `group_elements`, `get_canvas_screenshot`, `export_to_image`, `export_scene`, `export_to_excalidraw_url`
- **Supported elements:** rectangle, ellipse, diamond, text, arrow, line

**Workflow:** Build diagrams element-by-element with exact positioning, colors, and connectors. Use `get_canvas_screenshot` to verify layout (requires browser tab open). Refine iteratively with Matt.

**Preferred over:** FigJam (limited Mermaid control), Google Slides (slide-constrained canvas)

**Canvas is ephemeral:** The localhost:3000 canvas lives in memory only. If the server restarts, the canvas clears. Always save externally after building a diagram.

**No share UI on localhost:** The localhost canvas is a custom server, not full excalidraw.com. It does NOT have a native share/export button. To get a shareable link, use `export_to_excalidraw_url` (MCP tool) or save the `.excalidraw` file and open it on excalidraw.com.

**Matt edits in browser:** Matt may edit diagrams directly at `192.168.1.77:3000`. After he edits, use `export_scene` to save his changes before the server restarts.

**Saving diagrams:** Always save to Google Drive `8- Agent Workspace/YYYY-MM/`:
1. `.excalidraw` - editable JSON via `export_scene`. Matt can drag this onto excalidraw.com to reopen.
2. Shareable URL - via `export_to_excalidraw_url`. Permanent link, anyone can view/edit.
3. `.png` - via `export_to_image` (only works with browser tab open)
- Use descriptive filenames like `data-warehouse-architecture.excalidraw`

**Known MCP quirks:**
- **`import_scene` is broken:** Reports success but does NOT persist elements to the server. Always use `batch_create_elements` instead for building diagrams programmatically.
- **`batch_create_elements` is the reliable workaround:** Use this for all bulk diagram creation. Build in batches: shapes first, then text, then arrows.
- **`startArrowhead: null` fails validation:** When creating arrows, omit `startArrowhead` entirely for one-directional arrows. Only include it when you want `"arrow"` on both ends.
- **Text updates:** `update_element` does NOT reliably change displayed text. To change text content, always **delete and recreate** the element.
- **Arrows go diagonal:** Set `width: 0` for vertical arrows and `height: 0` for horizontal arrows. Without this, arrows will render diagonally.
- **`get_canvas_screenshot` requires browser:** Fails with "No frontend client connected" if no browser tab is open at localhost:3000.
- **Large diagrams (100+ elements):** `get_canvas_screenshot` and `export_to_image` may timeout. The `.excalidraw` JSON export still works.
- **Hand-drawn style:** Omit `fontFamily` for Excalidraw's default Virgil hand-drawn font. Use `roughness: 1` and `strokeWidth: 1.5` for hand-drawn arrows.

**Design best practices:**
- Spread elements out generously. Default to 80-100px gaps between layers.
- Keep arrows strictly vertical or horizontal unless there's a specific reason for diagonal.
- Place arrow labels to the RIGHT of vertical arrows, never overlapping.
- Use wider canvases (900-1000px) for diagrams with 3+ columns.

### Screenshots

**When Matt mentions a screenshot** (e.g., "look at this screenshot", "check my screenshot"), always look at the most recent file(s) in his Dropbox Screenshots folder:

**Path:** `/Users/homeserver/Library/CloudStorage/Dropbox/Screenshots/`

```bash
ls -lt "/Users/homeserver/Library/CloudStorage/Dropbox/Screenshots/" | head -5
```

- **No path given?** Check the most recent file(s) in the folder above.
- **MacBook path given** (like `/Users/matthewlieber/...`)? That path won't exist on the brain. Use the Dropbox path instead.
- **Multiple screenshots?** If the context suggests more than one, check the 2-3 most recent files.

### API Guidelines

When researching MCP servers or APIs, check if endpoints are REST/POST-only before attempting to fetch them as webpages. Use appropriate HTTP methods.
