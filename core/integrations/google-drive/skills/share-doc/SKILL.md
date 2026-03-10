# /share-doc

Convert a markdown file to a native, properly formatted Google Doc and return a shareable link.

## Usage

```
/share-doc <path-to-markdown-file> [--folder FOLDER_ID] [--name "Doc Name"]
```

**Examples:**
- `/share-doc ~/Obsidian/personal-os/Knowledge/WORK/pnt-email-marketing-strategy.md`
- `/share-doc ./my-report.md --folder 1fKsiGmD1WH8821FVBBJT7QCMuoWST9dK --name "Strategy Doc"`

## Workflow

1. **Validate** the markdown file exists and is readable
2. **Run the conversion script:**
   ```bash
   python3 ~/Obsidian/personal-os/core/integrations/google-drive/scripts/md_to_gdoc.py \
     "<markdown_file>" \
     --folder "<folder_id>" \
     --name "<doc_name>"
   ```
3. **Determine folder ID** if not provided:
   - Default: `8- Agent Workspace/YYYY-MM/` folder ID (use Google Drive MCP `listFolder` to find it)
   - Known folder IDs:
     - `8- Agent Workspace`: `1YCks5-giDhzTvtDvLGkJf8_vILGVI89y`
     - `8- Agent Workspace/2026-02`: `1fKsiGmD1WH8821FVBBJT7QCMuoWST9dK`
     - `3- Pies n Thighs`: `1pF3rhLtszN1nDtXGttU_4Uo7UG7AGcSD`
     - `Corner Booth Holdings` (root): `1y6qeVl-Cgu7bC8hyTvp_tYqMGoHJLz3w`
4. **Return** the Google Doc link to the user

## How It Works

Uses the Google Drive API's native markdown import (available since July 2024). The script uploads the markdown file with MIME type `text/markdown` and target type `application/vnd.google-apps.document`. Google's API converts the markdown to a native Google Doc with proper headings, bold, tables, lists, etc.

## Script Location

```
~/Obsidian/personal-os/core/integrations/google-drive/scripts/md_to_gdoc.py
```

## Auth

- Default OAuth directory: `~/.config/personal-os-secrets/google-drive/`
- OAuth credentials: `~/.config/personal-os-secrets/google-drive/credentials.json`
- Token cache: `~/.config/personal-os-secrets/google-drive/token.json` (auto-created after first auth, refreshes automatically)
- Scope: `drive.file` (can only access files created by the app)
- First run requires browser-based OAuth. After that, runs headlessly.
- Optional env overrides:
  - `GDRIVE_OAUTH_DIR`
  - `GDRIVE_CREDENTIALS_FILE`
  - `GDRIVE_TOKEN_FILE`

## Dependencies

- Python 3 with `google-api-python-client`, `google-auth-httplib2`, `google-auth-oauthlib`
- Google Cloud OAuth credentials (already configured)

## Important

- Do NOT use the Google Drive MCP `createGoogleDoc` tool - it dumps raw markdown as plain text
- Do NOT use pandoc to .docx - it produces ugly Word default formatting
- This script creates a native Google Doc directly from markdown
