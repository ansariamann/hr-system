"""Email server integration utilities."""

import asyncio
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from typing import List, Optional, Dict, Any
from pathlib import Path
import structlog

from ats_backend.core.config import settings

logger = structlog.get_logger(__name__)


class EmailServerConfig:
    """Configuration for email server integration."""
    
    def __init__(
        self,
        smtp_host: str = "localhost",
        smtp_port: int = 587,
        smtp_username: Optional[str] = None,
        smtp_password: Optional[str] = None,
        use_tls: bool = True,
        use_ssl: bool = False
    ):
        """Initialize email server configuration.
        
        Args:
            smtp_host: SMTP server hostname
            smtp_port: SMTP server port
            smtp_username: SMTP username (optional)
            smtp_password: SMTP password (optional)
            use_tls: Whether to use TLS encryption
            use_ssl: Whether to use SSL encryption
        """
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_username = smtp_username
        self.smtp_password = smtp_password
        self.use_tls = use_tls
        self.use_ssl = use_ssl


class EmailSender:
    """Utility for sending test emails with resume attachments."""
    
    def __init__(self, config: Optional[EmailServerConfig] = None):
        """Initialize email sender.
        
        Args:
            config: Email server configuration
        """
        self.config = config or EmailServerConfig()
    
    def send_test_email(
        self,
        to_address: str,
        from_address: str,
        subject: str,
        body: str,
        attachment_paths: List[str]
    ) -> bool:
        """Send a test email with resume attachments.
        
        Args:
            to_address: Recipient email address
            from_address: Sender email address
            subject: Email subject
            body: Email body text
            attachment_paths: List of file paths to attach
            
        Returns:
            True if email sent successfully, False otherwise
        """
        try:
            # Create message
            msg = MIMEMultipart()
            msg['From'] = from_address
            msg['To'] = to_address
            msg['Subject'] = subject
            
            # Add body
            msg.attach(MIMEText(body, 'plain'))
            
            # Add attachments
            for file_path in attachment_paths:
                if not Path(file_path).exists():
                    logger.warning("Attachment file not found", file_path=file_path)
                    continue
                
                try:
                    with open(file_path, 'rb') as attachment:
                        part = MIMEBase('application', 'octet-stream')
                        part.set_payload(attachment.read())
                    
                    encoders.encode_base64(part)
                    part.add_header(
                        'Content-Disposition',
                        f'attachment; filename= {Path(file_path).name}'
                    )
                    msg.attach(part)
                    
                    logger.debug("Attachment added", file_path=file_path)
                    
                except Exception as e:
                    logger.error("Failed to attach file", file_path=file_path, error=str(e))
                    continue
            
            # Send email
            server = smtplib.SMTP(self.config.smtp_host, self.config.smtp_port)
            
            if self.config.use_tls:
                server.starttls()
            
            if self.config.smtp_username and self.config.smtp_password:
                server.login(self.config.smtp_username, self.config.smtp_password)
            
            text = msg.as_string()
            server.sendmail(from_address, to_address, text)
            server.quit()
            
            logger.info(
                "Test email sent successfully",
                to_address=to_address,
                from_address=from_address,
                subject=subject,
                attachment_count=len(attachment_paths)
            )
            
            return True
            
        except Exception as e:
            logger.error(
                "Failed to send test email",
                to_address=to_address,
                from_address=from_address,
                error=str(e)
            )
            return False
    
    def create_sample_resume_files(self, output_dir: str = "test_resumes") -> List[str]:
        """Create sample resume files for testing.
        
        Args:
            output_dir: Directory to create sample files in
            
        Returns:
            List of created file paths
        """
        try:
            output_path = Path(output_dir)
            output_path.mkdir(exist_ok=True)
            
            created_files = []
            
            # Create a simple text file (will be saved as PDF in real scenario)
            sample_resume_text = """
John Doe
Software Engineer
Email: john.doe@example.com
Phone: (555) 123-4567

EXPERIENCE:
- Senior Software Engineer at Tech Corp (2020-2023)
- Software Engineer at StartupXYZ (2018-2020)

SKILLS:
Python, JavaScript, React, Node.js, PostgreSQL, Docker

EDUCATION:
Bachelor of Science in Computer Science
University of Technology (2014-2018)
            """.strip()
            
            # Create sample text file
            text_file = output_path / "john_doe_resume.txt"
            with open(text_file, 'w') as f:
                f.write(sample_resume_text)
            created_files.append(str(text_file))
            
            logger.info(
                "Sample resume files created",
                output_dir=output_dir,
                file_count=len(created_files)
            )
            
            return created_files
            
        except Exception as e:
            logger.error("Failed to create sample resume files", error=str(e))
            return []


class EmailReceiver:
    """Utility for receiving emails (for testing purposes)."""
    
    def __init__(self):
        """Initialize email receiver."""
        pass
    
    def simulate_email_reception(
        self,
        message_id: str,
        sender: str,
        subject: str,
        attachment_files: List[str]
    ) -> Dict[str, Any]:
        """Simulate receiving an email with attachments.
        
        Args:
            message_id: Email message ID
            sender: Sender email address
            subject: Email subject
            attachment_files: List of file paths to simulate as attachments
            
        Returns:
            Dictionary representing received email data
        """
        try:
            attachments = []
            
            for file_path in attachment_files:
                if not Path(file_path).exists():
                    logger.warning("Simulated attachment file not found", file_path=file_path)
                    continue
                
                try:
                    with open(file_path, 'rb') as f:
                        content = f.read()
                    
                    # Determine content type based on extension
                    extension = Path(file_path).suffix.lower()
                    content_type_map = {
                        '.pdf': 'application/pdf',
                        '.png': 'image/png',
                        '.jpg': 'image/jpeg',
                        '.jpeg': 'image/jpeg',
                        '.tiff': 'image/tiff',
                        '.tif': 'image/tiff'
                    }
                    
                    content_type = content_type_map.get(extension, 'application/octet-stream')
                    
                    attachment_data = {
                        'filename': Path(file_path).name,
                        'content_type': content_type,
                        'content': content,
                        'size': len(content)
                    }
                    
                    attachments.append(attachment_data)
                    
                except Exception as e:
                    logger.error("Failed to read simulated attachment", file_path=file_path, error=str(e))
                    continue
            
            email_data = {
                'message_id': message_id,
                'sender': sender,
                'subject': subject,
                'body': f"Simulated email with {len(attachments)} resume attachments",
                'received_at': None,  # Will be set to current time
                'attachments': attachments,
                'headers': {
                    'From': sender,
                    'Subject': subject,
                    'Message-ID': f'<{message_id}>'
                }
            }
            
            logger.info(
                "Email reception simulated",
                message_id=message_id,
                sender=sender,
                attachment_count=len(attachments)
            )
            
            return email_data
            
        except Exception as e:
            logger.error(
                "Failed to simulate email reception",
                message_id=message_id,
                sender=sender,
                error=str(e)
            )
            return {}


def create_test_email_data(
    message_id: str = "test-email-001@example.com",
    sender: str = "hr@company.com",
    subject: str = "Resume Submission",
    num_attachments: int = 1
) -> Dict[str, Any]:
    """Create test email data for development and testing.
    
    Args:
        message_id: Email message ID
        sender: Sender email address
        subject: Email subject
        num_attachments: Number of test attachments to create
        
    Returns:
        Dictionary with test email data
    """
    attachments = []
    
    for i in range(num_attachments):
        # Create sample resume content
        resume_content = f"""
Test Resume {i+1}
Name: Test Candidate {i+1}
Email: candidate{i+1}@example.com
Phone: (555) 000-000{i+1}

Experience: {3+i} years in software development
Skills: Python, JavaScript, SQL, Docker
        """.strip()
        
        attachment = {
            'filename': f'resume_{i+1}.pdf',
            'content_type': 'application/pdf',
            'content': resume_content.encode('utf-8'),
            'size': len(resume_content.encode('utf-8'))
        }
        attachments.append(attachment)
    
    return {
        'message_id': message_id,
        'sender': sender,
        'subject': subject,
        'body': f"Test email with {num_attachments} resume attachments",
        'attachments': attachments,
        'headers': {
            'From': sender,
            'Subject': subject,
            'Message-ID': f'<{message_id}>'
        }
    }