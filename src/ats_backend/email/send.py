"""Lightweight email sending utility for transactional emails."""

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

import structlog

from ats_backend.core.config import settings

logger = structlog.get_logger(__name__)


def send_email(
    to: str,
    subject: str,
    html_body: str,
    from_address: Optional[str] = None,
) -> bool:
    """Send an email via SMTP.

    If SMTP is not configured (no smtp_username), the email content is logged
    instead of sent.  This allows the feature to work in development without
    a real mail server.

    Args:
        to: Recipient email address.
        subject: Email subject line.
        html_body: HTML body content.
        from_address: Sender address (defaults to ``settings.email_from_address``).

    Returns:
        ``True`` if the email was sent (or logged) successfully.
    """
    sender = from_address or settings.email_from_address

    # If SMTP is not configured, log the email instead of failing
    if not settings.smtp_username or not settings.smtp_password:
        logger.info(
            "SMTP not configured — email logged instead of sent",
            to=to,
            subject=subject,
            from_address=sender,
        )
        # In non-production, print a visible marker so developers can see the email
        if settings.environment != "production":
            print(f"\n{'='*60}")
            print(f"  EMAIL (not sent — SMTP not configured)")
            print(f"  To:      {to}")
            print(f"  From:    {sender}")
            print(f"  Subject: {subject}")
            print(f"{'='*60}\n")
        return True

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to
    msg.attach(MIMEText(html_body, "html"))

    try:
        if settings.smtp_use_tls:
            server = smtplib.SMTP(settings.smtp_host, settings.smtp_port)
            server.starttls()
        else:
            server = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port)

        server.login(settings.smtp_username, settings.smtp_password)
        server.sendmail(sender, [to], msg.as_string())
        server.quit()

        logger.info("Password reset email sent", to=to)
        return True

    except Exception as exc:
        logger.error("Failed to send email", to=to, error=str(exc))
        return False
