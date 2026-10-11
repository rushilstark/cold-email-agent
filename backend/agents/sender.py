"""
Email sender using the Resend API.

Supports dry-run mode and real sending via the Resend API with optional PDF attachment.
Replaces the legacy Gmail API implementation for better deliverability and easier OAuth management.
"""
from __future__ import annotations

import base64
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

import resend
from sqlalchemy.orm import Session

from backend.config import get_settings

logger = logging.getLogger(__name__)


def check_credentials_exist() -> bool:
    """Return True if the Resend API key is available."""
    # Since we are checking if resend works, we check if RESEND_API_KEY is in settings
    # We will just assume it's available or log if it isn't
    return bool(os.environ.get("RESEND_API_KEY") or getattr(get_settings(), "RESEND_API_KEY", None))


class GmailSender: # Keeping the class name for backward compatibility with routers/emails.py
    """Thin wrapper around the Resend API for sending cold emails."""

    def __init__(self) -> None:
        self.settings = get_settings()
        if hasattr(self.settings, "RESEND_API_KEY") and self.settings.RESEND_API_KEY:
            resend.api_key = self.settings.RESEND_API_KEY
        elif os.environ.get("RESEND_API_KEY"):
            resend.api_key = os.environ.get("RESEND_API_KEY")

    def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        attachment_path: Optional[str] = None,
        dry_run: bool = True,
        sender: str = "rushil.chirla@gmail.com",
    ) -> dict:
        """
        Send (or dry-run) an email via Resend.

        Args:
            to: recipient email address
            subject: email subject line
            body: plain-text body
            attachment_path: optional path to a PDF file to attach
            dry_run: if True, prints details without sending
            sender: the From address (must be a verified domain in Resend)

        Returns:
            {'success': bool, 'message_id': str, 'dry_run': bool}
        """
        if dry_run:
            separator = "─" * 60
            print(f"\n{separator}")
            print(f"[DRY RUN - RESEND] Would send email:")
            print(f"  FROM   : {sender}")
            print(f"  TO     : {to}")
            print(f"  SUBJECT: {subject}")
            print(f"  ATTACH : {attachment_path or 'none'}")
            print(f"\n{body}\n{separator}\n")
            return {"success": True, "message_id": "dry-run-resend-id", "dry_run": True}

        try:
            if not resend.api_key:
                logger.error("RESEND_API_KEY is missing. Cannot send email.")
                return {"success": False, "message_id": "", "dry_run": False}

            # Resend requires attachments as dicts with filename and base64 content
            attachments = []
            if attachment_path:
                pdf_path = Path(attachment_path)
                if pdf_path.exists():
                    with open(pdf_path, "rb") as f:
                        pdf_data = f.read()
                    b64_content = base64.b64encode(pdf_data).decode('utf-8')
                    attachments.append({
                        "filename": pdf_path.name,
                        "content": b64_content
                    })
                else:
                    logger.warning(f"Attachment not found: {attachment_path}")

            params = {
                "from": sender,
                "to": to,
                "subject": subject,
                "text": body,
            }
            if attachments:
                params["attachments"] = attachments

            response = resend.Emails.send(params)
            message_id: str = response.get("id", "")
            logger.info(f"Email sent via Resend to {to} | Message ID: {message_id}")
            return {"success": True, "message_id": message_id, "dry_run": False}

        except Exception as exc:
            logger.error(f"Unexpected error sending email to {to} via Resend: {exc}")
            return {"success": False, "message_id": "", "dry_run": False}

    def get_sent_count_today(self, db_session: Session) -> int:
        """
        Query SentLog for emails sent today (UTC date).

        Used to enforce the daily send limit.
        """
        from backend.models.models import SentLog  # avoid circular imports

        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        count: int = (
            db_session.query(SentLog)
            .filter(SentLog.sent_at >= today_start)
            .count()
        )
        return count
