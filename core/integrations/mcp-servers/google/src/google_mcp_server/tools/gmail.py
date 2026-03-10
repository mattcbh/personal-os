"""Gmail MCP tools backed by the gws CLI."""

from __future__ import annotations

import base64
import mimetypes
import os
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Optional

from mcp.server.fastmcp import FastMCP

from google_mcp_server.auth.oauth import GoogleAuthManager


def _headers_map(headers: Any) -> dict[str, str]:
    out: dict[str, str] = {}
    if not isinstance(headers, list):
        return out
    for item in headers:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip().lower()
        value = str(item.get("value") or "").strip()
        if name:
            out[name] = value
    return out


def _decode_b64url(data: str) -> str:
    text = (data or "").strip()
    if not text:
        return ""
    pad = "=" * ((4 - len(text) % 4) % 4)
    decoded = base64.urlsafe_b64decode(text + pad)
    return decoded.decode("utf-8", errors="replace")


def register_tools(mcp: FastMCP, auth: GoogleAuthManager):
    """Register all Gmail tools with the MCP server."""

    @mcp.tool()
    def gmail_search(query: str, max_results: int = 10) -> dict:
        """
        Search for emails using Gmail search syntax.

        Args:
            query: Gmail search query (e.g., 'from:example@gmail.com', 'subject:meeting', 'is:unread')
            max_results: Maximum number of results to return (default: 10, max: 100)

        Returns:
            List of matching email summaries with id, threadId, snippet, and headers
        """
        results = auth.run_gws(
            "gmail",
            "users",
            "messages",
            "list",
            params={
                "userId": "me",
                "q": query,
                "maxResults": min(max_results, 100),
            },
        )

        messages = results.get("messages", [])
        email_summaries = []

        if isinstance(messages, list):
            for msg in messages:
                if not isinstance(msg, dict):
                    continue
                msg_id = str(msg.get("id") or "").strip()
                thread_id = str(msg.get("threadId") or "").strip()
                if not msg_id:
                    continue

                msg_data = auth.run_gws(
                    "gmail",
                    "users",
                    "messages",
                    "get",
                    params={
                        "userId": "me",
                        "id": msg_id,
                        "format": "metadata",
                        "metadataHeaders": ["From", "To", "Subject", "Date"],
                    },
                )

                headers = _headers_map(
                    ((msg_data.get("payload") or {}).get("headers") if isinstance(msg_data.get("payload"), dict) else [])
                )
                email_summaries.append(
                    {
                        "id": msg_id,
                        "threadId": thread_id,
                        "snippet": str(msg_data.get("snippet") or ""),
                        "from": headers.get("from", ""),
                        "to": headers.get("to", ""),
                        "subject": headers.get("subject", ""),
                        "date": headers.get("date", ""),
                    }
                )

        return {"emails": email_summaries, "resultCount": len(email_summaries)}

    @mcp.tool()
    def gmail_read(message_id: str) -> dict:
        """
        Read the full content of an email by its message ID.

        Args:
            message_id: The Gmail message ID to read

        Returns:
            Full email content including headers, body (plain text and HTML), and attachments info
        """
        message = auth.run_gws(
            "gmail",
            "users",
            "messages",
            "get",
            params={
                "userId": "me",
                "id": message_id,
                "format": "full",
            },
        )

        headers = _headers_map(
            ((message.get("payload") or {}).get("headers") if isinstance(message.get("payload"), dict) else [])
        )

        body_plain = ""
        body_html = ""
        attachments: list[dict[str, Any]] = []

        def process_parts(parts: Any) -> None:
            nonlocal body_plain, body_html, attachments
            if not isinstance(parts, list):
                return
            for part in parts:
                if not isinstance(part, dict):
                    continue
                mime_type = str(part.get("mimeType") or "")
                body = part.get("body") if isinstance(part.get("body"), dict) else {}
                data = str(body.get("data") or "")

                if mime_type == "text/plain" and data and not body_plain:
                    body_plain = _decode_b64url(data)
                elif mime_type == "text/html" and data and not body_html:
                    body_html = _decode_b64url(data)
                elif part.get("filename"):
                    attachments.append(
                        {
                            "filename": str(part.get("filename") or ""),
                            "mimeType": mime_type,
                            "size": int(body.get("size") or 0),
                            "attachmentId": str(body.get("attachmentId") or ""),
                        }
                    )

                if "parts" in part:
                    process_parts(part.get("parts"))

        payload = message.get("payload") if isinstance(message.get("payload"), dict) else {}
        if "parts" in payload:
            process_parts(payload.get("parts"))
        else:
            root_body = payload.get("body") if isinstance(payload.get("body"), dict) else {}
            if root_body.get("data"):
                body_plain = _decode_b64url(str(root_body.get("data") or ""))

        return {
            "id": message_id,
            "threadId": message.get("threadId"),
            "from": headers.get("from", ""),
            "to": headers.get("to", ""),
            "cc": headers.get("cc", ""),
            "subject": headers.get("subject", ""),
            "date": headers.get("date", ""),
            "body_plain": body_plain,
            "body_html": body_html,
            "attachments": attachments,
            "labels": message.get("labelIds", []),
        }

    @mcp.tool()
    def gmail_send(
        to: str,
        subject: str,
        body: str,
        cc: Optional[str] = None,
        bcc: Optional[str] = None,
        html_body: Optional[str] = None,
    ) -> dict:
        """
        Send an email.

        Args:
            to: Recipient email address(es), comma-separated for multiple
            subject: Email subject line
            body: Plain text body of the email
            cc: Optional CC recipients, comma-separated
            bcc: Optional BCC recipients, comma-separated
            html_body: Optional HTML version of the body

        Returns:
            Sent message ID and thread ID
        """
        if html_body:
            message = MIMEMultipart("alternative")
            message.attach(MIMEText(body, "plain"))
            message.attach(MIMEText(html_body, "html"))
        else:
            message = MIMEText(body, "plain")

        message["to"] = to
        message["subject"] = subject
        if cc:
            message["cc"] = cc
        if bcc:
            message["bcc"] = bcc

        raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
        sent_message = auth.run_gws(
            "gmail",
            "users",
            "messages",
            "send",
            params={"userId": "me"},
            body={"raw": raw},
        )

        return {
            "id": sent_message.get("id", ""),
            "threadId": sent_message.get("threadId", ""),
            "status": "sent",
        }

    @mcp.tool()
    def gmail_list_labels() -> dict:
        """
        List all Gmail labels for the authenticated user.

        Returns:
            List of labels with id, name, and type (system/user)
        """
        results = auth.run_gws("gmail", "users", "labels", "list", params={"userId": "me"})
        labels = results.get("labels", [])

        out = []
        if isinstance(labels, list):
            for label in labels:
                if not isinstance(label, dict):
                    continue
                out.append(
                    {
                        "id": str(label.get("id") or ""),
                        "name": str(label.get("name") or ""),
                        "type": str(label.get("type") or "user"),
                    }
                )

        return {"labels": out}

    @mcp.tool()
    def gmail_modify_labels(
        message_id: str,
        add_labels: Optional[list[str]] = None,
        remove_labels: Optional[list[str]] = None,
    ) -> dict:
        """
        Add or remove labels from an email.

        Args:
            message_id: The Gmail message ID
            add_labels: List of label IDs to add
            remove_labels: List of label IDs to remove

        Returns:
            Updated label IDs for the message
        """
        body_payload: dict[str, Any] = {}
        if add_labels:
            body_payload["addLabelIds"] = add_labels
        if remove_labels:
            body_payload["removeLabelIds"] = remove_labels

        result = auth.run_gws(
            "gmail",
            "users",
            "messages",
            "modify",
            params={"userId": "me", "id": message_id},
            body=body_payload,
        )

        return {"id": message_id, "labelIds": result.get("labelIds", [])}

    @mcp.tool()
    def gmail_draft_reply(
        message_id: str,
        body: str,
        attachment: Optional[str] = None,
        cc: Optional[str] = None,
        html_body: Optional[str] = None,
    ) -> dict:
        """
        Create a draft reply to an email.

        Args:
            message_id: The Gmail message ID to reply to
            body: Plain text body of the reply
            attachment: Optional file path to attach (e.g., a signed PDF)
            cc: Optional CC recipients, comma-separated
            html_body: Optional HTML version of the body

        Returns:
            Draft ID, message ID, thread ID, threadUrl, and draftUrl
        """
        msg = auth.run_gws(
            "gmail",
            "users",
            "messages",
            "get",
            params={
                "userId": "me",
                "id": message_id,
                "format": "metadata",
                "metadataHeaders": [
                    "From",
                    "To",
                    "Subject",
                    "Message-Id",
                    "References",
                ],
            },
        )

        headers = _headers_map(
            ((msg.get("payload") or {}).get("headers") if isinstance(msg.get("payload"), dict) else [])
        )
        thread_id = str(msg.get("threadId") or "")

        reply_to = headers.get("from", "")
        subject = headers.get("subject", "")
        if subject and not subject.lower().startswith("re:"):
            subject = f"Re: {subject}"
        in_reply_to = headers.get("message-id", "")
        references = headers.get("references", "")
        if in_reply_to:
            references = f"{references} {in_reply_to}".strip()

        if attachment:
            message = MIMEMultipart("mixed")
            if html_body:
                alt = MIMEMultipart("alternative")
                alt.attach(MIMEText(body, "plain"))
                alt.attach(MIMEText(html_body, "html"))
                message.attach(alt)
            else:
                message.attach(MIMEText(body, "plain"))

            filepath = os.path.expanduser(attachment)
            content_type, _ = mimetypes.guess_type(filepath)
            if content_type is None:
                content_type = "application/octet-stream"
            main_type, sub_type = content_type.split("/", 1)
            with open(filepath, "rb") as f:
                att = MIMEBase(main_type, sub_type)
                att.set_payload(f.read())
            encoders.encode_base64(att)
            att.add_header(
                "Content-Disposition",
                "attachment",
                filename=os.path.basename(filepath),
            )
            message.attach(att)
        elif html_body:
            message = MIMEMultipart("alternative")
            message.attach(MIMEText(body, "plain"))
            message.attach(MIMEText(html_body, "html"))
        else:
            message = MIMEText(body, "plain")

        message["to"] = reply_to
        message["subject"] = subject
        if cc:
            message["cc"] = cc
        if in_reply_to:
            message["In-Reply-To"] = in_reply_to
        if references:
            message["References"] = references

        raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")

        draft = auth.run_gws(
            "gmail",
            "users",
            "drafts",
            "create",
            params={"userId": "me"},
            body={"message": {"raw": raw, "threadId": thread_id}},
        )

        draft_message = draft.get("message") if isinstance(draft.get("message"), dict) else {}
        resolved_thread_id = str(draft_message.get("threadId") or thread_id)
        email = auth.get_authenticated_email()
        return {
            "draftId": str(draft.get("id") or ""),
            "messageId": str(draft_message.get("id") or ""),
            "threadId": resolved_thread_id,
            "threadUrl": f"https://mail.google.com/mail/u/0/?authuser={email}#inbox/{resolved_thread_id}",
            "draftUrl": f"https://mail.google.com/mail/u/0/?authuser={email}#drafts/{resolved_thread_id}",
        }

    @mcp.tool()
    def gmail_draft_email(
        to: str,
        subject: str,
        body: str,
        cc: Optional[str] = None,
        bcc: Optional[str] = None,
        html_body: Optional[str] = None,
        attachment: Optional[str] = None,
    ) -> dict:
        """
        Create a new draft email (not a reply).

        Args:
            to: Recipient email address(es), comma-separated for multiple
            subject: Email subject line
            body: Plain text body of the email
            cc: Optional CC recipients, comma-separated
            bcc: Optional BCC recipients, comma-separated
            html_body: Optional HTML version of the body
            attachment: Optional file path to attach

        Returns:
            Draft ID, message ID, and thread ID
        """
        if attachment:
            message = MIMEMultipart("mixed")
            if html_body:
                alt = MIMEMultipart("alternative")
                alt.attach(MIMEText(body, "plain"))
                alt.attach(MIMEText(html_body, "html"))
                message.attach(alt)
            else:
                message.attach(MIMEText(body, "plain"))

            filepath = os.path.expanduser(attachment)
            content_type, _ = mimetypes.guess_type(filepath)
            if content_type is None:
                content_type = "application/octet-stream"
            main_type, sub_type = content_type.split("/", 1)
            with open(filepath, "rb") as f:
                att = MIMEBase(main_type, sub_type)
                att.set_payload(f.read())
            encoders.encode_base64(att)
            att.add_header(
                "Content-Disposition",
                "attachment",
                filename=os.path.basename(filepath),
            )
            message.attach(att)
        elif html_body:
            message = MIMEMultipart("alternative")
            message.attach(MIMEText(body, "plain"))
            message.attach(MIMEText(html_body, "html"))
        else:
            message = MIMEText(body, "plain")

        message["to"] = to
        message["subject"] = subject
        if cc:
            message["cc"] = cc
        if bcc:
            message["bcc"] = bcc

        raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")

        draft = auth.run_gws(
            "gmail",
            "users",
            "drafts",
            "create",
            params={"userId": "me"},
            body={"message": {"raw": raw}},
        )

        draft_message = draft.get("message") if isinstance(draft.get("message"), dict) else {}
        thread_id = str(draft_message.get("threadId") or "")
        message_id = str(draft_message.get("id") or "")
        email = auth.get_authenticated_email()
        return {
            "draftId": str(draft.get("id") or ""),
            "messageId": message_id,
            "threadId": thread_id,
            "threadUrl": f"https://mail.google.com/mail/u/0/?authuser={email}#inbox/{thread_id}" if thread_id else "",
            "draftUrl": f"https://mail.google.com/mail/u/0/?authuser={email}#drafts/{thread_id}" if thread_id else f"https://mail.google.com/mail/u/0/?authuser={email}#drafts/{message_id}",
        }

    @mcp.tool()
    def gmail_download_attachment(
        message_id: str,
        attachment_id: str,
        save_path: str,
    ) -> dict:
        """
        Download an email attachment to disk.

        Args:
            message_id: The Gmail message ID containing the attachment
            attachment_id: The attachment ID (from gmail_read's attachments list)
            save_path: File path to save the attachment to

        Returns:
            File path and size in bytes
        """
        attachment = auth.run_gws(
            "gmail",
            "users",
            "messages",
            "attachments",
            "get",
            params={"userId": "me", "messageId": message_id, "id": attachment_id},
        )

        data = base64.urlsafe_b64decode(str(attachment.get("data") or ""))

        save_path = os.path.expanduser(save_path)
        folder = os.path.dirname(save_path)
        if folder:
            os.makedirs(folder, exist_ok=True)
        with open(save_path, "wb") as f:
            f.write(data)

        return {"path": save_path, "size": len(data)}

    @mcp.tool()
    def gmail_create_label(name: str) -> dict:
        """
        Create a new Gmail label.

        Args:
            name: The name of the label to create

        Returns:
            The new label's ID and name
        """
        label = auth.run_gws(
            "gmail",
            "users",
            "labels",
            "create",
            params={"userId": "me"},
            body={
                "name": name,
                "labelListVisibility": "labelShow",
                "messageListVisibility": "show",
            },
        )

        return {"id": str(label.get("id") or ""), "name": str(label.get("name") or "")}

    @mcp.tool()
    def gmail_delete_email(message_id: str) -> dict:
        """
        Move an email to the Trash.

        Args:
            message_id: The Gmail message ID to trash

        Returns:
            Confirmation with the message ID
        """
        auth.run_gws(
            "gmail",
            "users",
            "messages",
            "trash",
            params={"userId": "me", "id": message_id},
        )

        return {"id": message_id, "status": "trashed"}

    @mcp.tool()
    def gmail_create_filter(
        from_address: Optional[str] = None,
        to_address: Optional[str] = None,
        subject: Optional[str] = None,
        query: Optional[str] = None,
        add_label_ids: Optional[list[str]] = None,
        remove_label_ids: Optional[list[str]] = None,
        forward: Optional[str] = None,
        archive: bool = False,
        mark_read: bool = False,
        star: bool = False,
        never_spam: bool = False,
    ) -> dict:
        """
        Create a Gmail filter to automatically process incoming emails.

        Args:
            from_address: Filter emails from this address
            to_address: Filter emails to this address
            subject: Filter emails with this subject
            query: Gmail search query for matching (advanced)
            add_label_ids: Label IDs to apply to matching messages
            remove_label_ids: Label IDs to remove from matching messages
            forward: Email address to forward matching messages to
            archive: If True, skip the inbox (archive)
            mark_read: If True, mark matching messages as read
            star: If True, star matching messages
            never_spam: If True, never send matching messages to spam

        Returns:
            The created filter's ID and criteria
        """
        criteria: dict[str, Any] = {}
        if from_address:
            criteria["from"] = from_address
        if to_address:
            criteria["to"] = to_address
        if subject:
            criteria["subject"] = subject
        if query:
            criteria["query"] = query

        action: dict[str, Any] = {}
        if add_label_ids:
            action["addLabelIds"] = list(add_label_ids)
        if remove_label_ids:
            action["removeLabelIds"] = list(remove_label_ids)
        if forward:
            action["forward"] = forward
        if archive:
            action.setdefault("removeLabelIds", []).append("INBOX")
        if mark_read:
            action.setdefault("removeLabelIds", []).append("UNREAD")
        if star:
            action.setdefault("addLabelIds", []).append("STARRED")
        if never_spam:
            action.setdefault("removeLabelIds", []).append("SPAM")

        gmail_filter = auth.run_gws(
            "gmail",
            "users",
            "settings",
            "filters",
            "create",
            params={"userId": "me"},
            body={"criteria": criteria, "action": action},
        )

        return {
            "id": str(gmail_filter.get("id") or ""),
            "criteria": gmail_filter.get("criteria", {}),
            "action": gmail_filter.get("action", {}),
        }
