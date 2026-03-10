#!/usr/bin/env python3
"""One-shot: Email Emma's Torch research report to Matt on Saturday morning."""

import json
import os
import base64
from email.mime.text import MIMEText
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

REPORT_PATH = os.path.expanduser(
    "~/Obsidian/personal-os/Knowledge/WORK/emmas-torch-research.md"
)
TOKEN_PATH = os.path.expanduser("~/.gmail-mcp-personal/token.json")
RECIPIENT = "lieber.matt@gmail.com"


def get_gmail_service():
    with open(TOKEN_PATH) as f:
        token_data = json.load(f)
    creds = Credentials(
        token=token_data.get("token"),
        refresh_token=token_data.get("refresh_token"),
        token_uri=token_data.get("token_uri"),
        client_id=token_data.get("client_id"),
        client_secret=token_data.get("client_secret"),
    )
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(TOKEN_PATH, "w") as f:
            f.write(creds.to_json())
    return build("gmail", "v1", credentials=creds)


def main():
    if not os.path.exists(REPORT_PATH):
        print(f"Report not found at {REPORT_PATH}, skipping.")
        return

    with open(REPORT_PATH) as f:
        report_content = f.read()

    body = (
        "Here's the Emma's Torch research report for your review before "
        "responding to David Tomczak re: Robin Hood board placement.\n\n"
        "---\n\n"
        + report_content
    )

    message = MIMEText(body)
    message["to"] = RECIPIENT
    message["from"] = RECIPIENT
    message["subject"] = "Emma's Torch Research Report"

    service = get_gmail_service()
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    service.users().messages().send(
        userId="me", body={"raw": raw}
    ).execute()
    print("Report emailed successfully.")

    # Clean up: unload the launchd job after sending
    plist = os.path.expanduser(
        "~/Library/LaunchAgents/com.cbh.emmas-torch-report.plist"
    )
    if os.path.exists(plist):
        os.system(f"launchctl bootout gui/$(id -u) {plist} 2>/dev/null")
        os.remove(plist)
        print("One-shot plist removed.")


if __name__ == "__main__":
    main()
