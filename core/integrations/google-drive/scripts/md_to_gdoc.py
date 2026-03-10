#!/usr/bin/env python3
"""Convert a Markdown file to a native Google Doc with proper formatting.

Uses the Google Drive API's native markdown-to-Google-Doc conversion
(available since July 2024) to create properly formatted documents
with real headings, bold, tables, etc.

Usage:
    python3 md_to_gdoc.py <markdown_file> [--folder FOLDER_ID] [--name DOC_NAME]

First run requires browser-based OAuth authorization.
After that, the token is cached and it runs headlessly.
"""

import argparse
import io
import os
import sys

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

SCOPES = ["https://www.googleapis.com/auth/drive.file"]
SECRETS_DIR = os.path.expanduser(
    os.getenv("GDRIVE_OAUTH_DIR", "~/.config/personal-os-secrets/google-drive")
)
CREDENTIALS_FILE = os.path.expanduser(
    os.getenv("GDRIVE_CREDENTIALS_FILE", os.path.join(SECRETS_DIR, "credentials.json"))
)
TOKEN_FILE = os.path.expanduser(
    os.getenv("GDRIVE_TOKEN_FILE", os.path.join(SECRETS_DIR, "token.json"))
)


def authenticate():
    """Authenticate with Google Drive API, caching the token."""
    creds = None
    if not os.path.exists(CREDENTIALS_FILE):
        print(
            f"Error: OAuth credentials not found at {CREDENTIALS_FILE}",
            file=sys.stderr,
        )
        print(
            "Set GDRIVE_CREDENTIALS_FILE or GDRIVE_OAUTH_DIR, then retry.",
            file=sys.stderr,
        )
        sys.exit(1)
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        os.makedirs(os.path.dirname(TOKEN_FILE), exist_ok=True)
        with open(TOKEN_FILE, "w") as token:
            token.write(creds.to_json())
    return creds


def upload_markdown_as_gdoc(creds, md_content, doc_name, folder_id=None):
    """Upload markdown content as a native Google Doc."""
    service = build("drive", "v3", credentials=creds)

    file_metadata = {
        "name": doc_name,
        "mimeType": "application/vnd.google-apps.document",
    }
    if folder_id:
        file_metadata["parents"] = [folder_id]

    media = MediaIoBaseUpload(
        io.BytesIO(md_content.encode("utf-8")),
        mimetype="text/markdown",
        resumable=True,
    )

    file = service.files().create(
        body=file_metadata,
        media_body=media,
        fields="id, webViewLink",
    ).execute()

    return file


def main():
    parser = argparse.ArgumentParser(description="Convert Markdown to Google Doc")
    parser.add_argument("markdown_file", help="Path to the markdown file")
    parser.add_argument("--folder", help="Google Drive folder ID to place the doc in")
    parser.add_argument("--name", help="Document name (defaults to filename without .md)")
    args = parser.parse_args()

    md_path = os.path.expanduser(args.markdown_file)
    if not os.path.exists(md_path):
        print(f"Error: File not found: {md_path}", file=sys.stderr)
        sys.exit(1)

    with open(md_path, "r") as f:
        md_content = f.read()

    doc_name = args.name or os.path.splitext(os.path.basename(md_path))[0]

    creds = authenticate()
    result = upload_markdown_as_gdoc(creds, md_content, doc_name, args.folder)

    print(f"Created: {doc_name}")
    print(f"ID: {result['id']}")
    print(f"Link: {result['webViewLink']}")


if __name__ == "__main__":
    main()
