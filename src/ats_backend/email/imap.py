"""IMAP mailbox polling for resume ingestion."""

from __future__ import annotations

import imaplib
from dataclasses import dataclass
from typing import Callable, Optional
from uuid import UUID

import structlog
from sqlalchemy.orm import Session

from ats_backend.core.config import settings
from ats_backend.email.parser import EmailParser
from ats_backend.email.processor import EmailProcessor
from ats_backend.models.activity_log import ActivityLog

logger = structlog.get_logger(__name__)


@dataclass
class IMAPPollResult:
    """Summary of one IMAP polling run."""

    messages_seen: int = 0
    messages_ingested: int = 0
    attachments_processed: int = 0
    duplicate_messages: int = 0
    failures: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "messages_seen": self.messages_seen,
            "messages_ingested": self.messages_ingested,
            "attachments_processed": self.attachments_processed,
            "duplicate_messages": self.duplicate_messages,
            "failures": self.failures,
        }


class IMAPPollingService:
    """Poll a configured IMAP mailbox and route messages into EmailProcessor."""

    def __init__(
        self,
        *,
        email_parser: Optional[EmailParser] = None,
        email_processor: Optional[EmailProcessor] = None,
        imap_factory: Optional[Callable[..., imaplib.IMAP4_SSL]] = None,
    ) -> None:
        self.email_parser = email_parser or EmailParser()
        self.email_processor = email_processor or EmailProcessor()
        self.imap_factory = imap_factory or imaplib.IMAP4_SSL

    def poll_inbox(self, db: Session, *, user_id: Optional[UUID] = None) -> IMAPPollResult:
        """Poll unread messages from the configured IMAP inbox."""
        result = IMAPPollResult()

        if not settings.imap_ingestion_enabled:
            logger.info("IMAP ingestion disabled; skipping mailbox poll")
            return result

        if not settings.imap_client_id:
            logger.warning("IMAP ingestion enabled but imap_client_id is missing")
            result.failures += 1
            return result

        if not settings.imap_username or not settings.imap_password:
            logger.warning("IMAP ingestion enabled but mailbox credentials are missing")
            result.failures += 1
            return result

        try:
            client_id = UUID(settings.imap_client_id)
        except ValueError:
            logger.warning("Configured imap_client_id is not a valid UUID", imap_client_id=settings.imap_client_id)
            result.failures += 1
            return result

        mail = None
        try:
            mail = self.imap_factory(settings.imap_host, settings.imap_port)
            mail.login(settings.imap_username, settings.imap_password)
            mail.select(settings.imap_mailbox)

            status, messages = mail.search(None, "UNSEEN")
            if status != "OK":
                raise ValueError(f"IMAP search failed with status {status}")

            message_numbers = [msg_no for msg_no in messages[0].split() if msg_no]
            if settings.imap_max_messages_per_poll > 0:
                # IMAP SEARCH returns message sequence numbers in ascending order.
                # Process the newest unread messages first so a noisy inbox does not
                # starve recently received resumes.
                message_numbers = message_numbers[-settings.imap_max_messages_per_poll :]

            message_numbers = list(reversed(message_numbers))

            for msg_no in message_numbers:
                result.messages_seen += 1
                should_mark_seen = False

                try:
                    fetch_status, data = mail.fetch(msg_no, "(RFC822)")
                    if fetch_status != "OK" or not data or data[0] is None:
                        raise ValueError(f"IMAP fetch failed with status {fetch_status}")

                    raw_email = data[0][1]
                    email_message = self.email_parser.parse_raw_email_bytes(raw_email)
                    processing_result = self.email_processor.process_email(
                        db=db,
                        client_id=client_id,
                        email=email_message,
                        user_id=user_id,
                        ip_address="imap",
                        user_agent="imap-poller",
                    )

                    if processing_result.duplicate_message_id:
                        result.duplicate_messages += 1
                        should_mark_seen = True
                    elif processing_result.success:
                        result.messages_ingested += 1
                        result.attachments_processed += processing_result.processed_attachments
                        should_mark_seen = True
                    elif processing_result.processed_attachments == 0:
                        # Avoid reprocessing non-resume inbox noise forever.
                        should_mark_seen = True

                    logger.info(
                        "IMAP message processed",
                        message_id=email_message.message_id,
                        success=processing_result.success,
                        processed_attachments=processing_result.processed_attachments,
                        duplicate=processing_result.duplicate_message_id is not None,
                    )

                except Exception as exc:
                    result.failures += 1
                    logger.error("IMAP message processing failed", message_number=msg_no, error=str(exc))
                    error_message = str(exc).lower()
                    should_mark_seen = "at least one attachment" in error_message or "resume file" in error_message
                    db.add(
                        ActivityLog(
                            client_id=client_id,
                            user_id=user_id,
                            action_type="IMAP_MESSAGE_FAILED",
                            entity_id=None,
                            details={
                                "message_number": msg_no.decode() if isinstance(msg_no, bytes) else str(msg_no),
                                "error": str(exc),
                            },
                        )
                    )

                if should_mark_seen:
                    mail.store(msg_no, "+FLAGS", "\\Seen")

        except imaplib.IMAP4.error as exc:
            result.failures += 1
            logger.error("IMAP mailbox authentication or command failed", error=str(exc))
        except Exception as exc:
            result.failures += 1
            logger.error("IMAP mailbox polling failed", error=str(exc))
        finally:
            if mail is not None:
                try:
                    mail.logout()
                except Exception:
                    logger.debug("IMAP logout failed", exc_info=True)

        db.add(
            ActivityLog(
                client_id=client_id if settings.imap_client_id else None,
                user_id=user_id,
                action_type="IMAP_POLL_COMPLETED",
                entity_id=None,
                details=result.as_dict(),
            )
        )
        logger.info("IMAP poll completed", **result.as_dict())
        return result
