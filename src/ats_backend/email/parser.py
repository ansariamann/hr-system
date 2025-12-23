"""Email parsing utilities for different email formats."""

import email
import base64
from typing import List, Dict, Any, Optional, Tuple
from email.message import EmailMessage as StdEmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from datetime import datetime
import structlog

from ats_backend.email.models import EmailMessage, EmailAttachment

logger = structlog.get_logger(__name__)


class EmailParser:
    """Parser for converting raw email data to EmailMessage objects."""
    
    def __init__(self):
        """Initialize email parser."""
        self.supported_content_types = {
            'application/pdf': '.pdf',
            'image/png': '.png',
            'image/jpeg': '.jpg',
            'image/jpg': '.jpg',
            'image/tiff': '.tiff',
            'image/tif': '.tif'
        }
    
    def parse_raw_email(self, raw_email: str) -> EmailMessage:
        """Parse raw email string into EmailMessage object.
        
        Args:
            raw_email: Raw email string (RFC 2822 format)
            
        Returns:
            EmailMessage object
            
        Raises:
            ValueError: If email parsing fails
        """
        try:
            # Parse raw email
            msg = email.message_from_string(raw_email)
            
            # Extract basic information
            message_id = self._extract_message_id(msg)
            sender = self._extract_sender(msg)
            subject = self._extract_subject(msg)
            body = self._extract_body(msg)
            received_at = self._extract_received_date(msg)
            headers = self._extract_headers(msg)
            
            # Extract attachments
            attachments = self._extract_attachments(msg)
            
            email_message = EmailMessage(
                message_id=message_id,
                sender=sender,
                subject=subject,
                body=body,
                received_at=received_at,
                attachments=attachments,
                headers=headers
            )
            
            logger.info(
                "Email parsed successfully",
                message_id=message_id,
                sender=sender,
                attachment_count=len(attachments)
            )
            
            return email_message
            
        except Exception as e:
            logger.error("Failed to parse raw email", error=str(e))
            raise ValueError(f"Email parsing failed: {str(e)}")
    
    def parse_email_dict(self, email_data: Dict[str, Any]) -> EmailMessage:
        """Parse email dictionary into EmailMessage object.
        
        Args:
            email_data: Dictionary with email data
            
        Returns:
            EmailMessage object
            
        Raises:
            ValueError: If email parsing fails
        """
        try:
            # Convert attachment data if present
            attachments = []
            if 'attachments' in email_data:
                for att_data in email_data['attachments']:
                    # Handle base64 encoded content
                    if isinstance(att_data.get('content'), str):
                        try:
                            content = base64.b64decode(att_data['content'])
                        except Exception:
                            # If not base64, assume it's already bytes
                            content = att_data['content'].encode('utf-8')
                    else:
                        content = att_data['content']
                    
                    attachment = EmailAttachment(
                        filename=att_data['filename'],
                        content_type=att_data['content_type'],
                        content=content,
                        size=att_data.get('size', len(content))
                    )
                    attachments.append(attachment)
            
            # Parse received_at if it's a string
            received_at = email_data.get('received_at')
            if isinstance(received_at, str):
                try:
                    received_at = datetime.fromisoformat(received_at.replace('Z', '+00:00'))
                except Exception:
                    received_at = datetime.utcnow()
            elif not received_at:
                received_at = datetime.utcnow()
            
            email_message = EmailMessage(
                message_id=email_data['message_id'],
                sender=email_data['sender'],
                subject=email_data.get('subject', ''),
                body=email_data.get('body'),
                received_at=received_at,
                attachments=attachments,
                headers=email_data.get('headers', {})
            )
            
            logger.info(
                "Email dictionary parsed successfully",
                message_id=email_message.message_id,
                sender=email_message.sender,
                attachment_count=len(attachments)
            )
            
            return email_message
            
        except Exception as e:
            logger.error("Failed to parse email dictionary", error=str(e))
            raise ValueError(f"Email dictionary parsing failed: {str(e)}")
    
    def _extract_message_id(self, msg: StdEmailMessage) -> str:
        """Extract message ID from email message."""
        message_id = msg.get('Message-ID', '').strip('<>')
        if not message_id:
            # Generate a fallback message ID
            import uuid
            message_id = f"generated-{uuid.uuid4()}@ats-backend"
            logger.warning("No Message-ID found, generated fallback", message_id=message_id)
        return message_id
    
    def _extract_sender(self, msg: StdEmailMessage) -> str:
        """Extract sender email address from email message."""
        sender = msg.get('From', '')
        if not sender:
            raise ValueError("Email must have a sender address")
        
        # Extract email address from "Name <email@domain.com>" format
        if '<' in sender and '>' in sender:
            start = sender.find('<') + 1
            end = sender.find('>')
            sender = sender[start:end]
        
        return sender.strip().lower()
    
    def _extract_subject(self, msg: StdEmailMessage) -> str:
        """Extract subject from email message."""
        return msg.get('Subject', '').strip()
    
    def _extract_body(self, msg: StdEmailMessage) -> Optional[str]:
        """Extract body text from email message."""
        try:
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == 'text/plain':
                        return part.get_payload(decode=True).decode('utf-8', errors='ignore')
            else:
                if msg.get_content_type() == 'text/plain':
                    return msg.get_payload(decode=True).decode('utf-8', errors='ignore')
        except Exception as e:
            logger.warning("Failed to extract email body", error=str(e))
        
        return None
    
    def _extract_received_date(self, msg: StdEmailMessage) -> datetime:
        """Extract received date from email message."""
        try:
            date_str = msg.get('Date')
            if date_str:
                return email.utils.parsedate_to_datetime(date_str)
        except Exception as e:
            logger.warning("Failed to parse email date", error=str(e))
        
        return datetime.utcnow()
    
    def _extract_headers(self, msg: StdEmailMessage) -> Dict[str, str]:
        """Extract headers from email message."""
        headers = {}
        for key, value in msg.items():
            headers[key] = value
        return headers
    
    def _extract_attachments(self, msg: StdEmailMessage) -> List[EmailAttachment]:
        """Extract attachments from email message."""
        attachments = []
        
        try:
            for part in msg.walk():
                # Skip multipart containers
                if part.get_content_maintype() == 'multipart':
                    continue
                
                # Skip text parts (body)
                if part.get_content_type() in ['text/plain', 'text/html']:
                    continue
                
                # Get attachment info
                filename = part.get_filename()
                if not filename:
                    continue
                
                content_type = part.get_content_type()
                
                # Check if it's a supported file type
                if not self._is_supported_attachment(filename, content_type):
                    logger.debug(
                        "Skipping unsupported attachment",
                        filename=filename,
                        content_type=content_type
                    )
                    continue
                
                # Get attachment content
                content = part.get_payload(decode=True)
                if not content:
                    logger.warning("Empty attachment content", filename=filename)
                    continue
                
                attachment = EmailAttachment(
                    filename=filename,
                    content_type=content_type,
                    content=content,
                    size=len(content)
                )
                
                attachments.append(attachment)
                
                logger.debug(
                    "Attachment extracted",
                    filename=filename,
                    content_type=content_type,
                    size=len(content)
                )
                
        except Exception as e:
            logger.error("Failed to extract attachments", error=str(e))
            raise ValueError(f"Attachment extraction failed: {str(e)}")
        
        return attachments
    
    def _is_supported_attachment(self, filename: str, content_type: str) -> bool:
        """Check if attachment is a supported resume file type."""
        # Check by content type
        if content_type in self.supported_content_types:
            return True
        
        # Check by file extension
        filename_lower = filename.lower()
        supported_extensions = ['.pdf', '.png', '.jpg', '.jpeg', '.tiff', '.tif']
        
        return any(filename_lower.endswith(ext) for ext in supported_extensions)
    
    def create_test_email(
        self,
        message_id: str,
        sender: str,
        subject: str,
        attachments: List[Tuple[str, str, bytes]]
    ) -> EmailMessage:
        """Create a test email message for testing purposes.
        
        Args:
            message_id: Email message ID
            sender: Sender email address
            subject: Email subject
            attachments: List of (filename, content_type, content) tuples
            
        Returns:
            EmailMessage object
        """
        email_attachments = []
        
        for filename, content_type, content in attachments:
            attachment = EmailAttachment(
                filename=filename,
                content_type=content_type,
                content=content,
                size=len(content)
            )
            email_attachments.append(attachment)
        
        return EmailMessage(
            message_id=message_id,
            sender=sender,
            subject=subject,
            body="Test email with resume attachments",
            received_at=datetime.utcnow(),
            attachments=email_attachments,
            headers={"From": sender, "Subject": subject}
        )