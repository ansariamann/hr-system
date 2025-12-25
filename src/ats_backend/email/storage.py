"""File storage utilities for email attachments."""

import os
import uuid
from pathlib import Path
from typing import Optional, Tuple
from datetime import datetime
import structlog

from ats_backend.email.models import EmailAttachment, FileStorageInfo
from ats_backend.security.abuse_protection import abuse_protection

logger = structlog.get_logger(__name__)


class FileStorageService:
    """Service for storing email attachments to filesystem."""
    
    def __init__(self, base_storage_path: str = "storage/resumes"):
        """Initialize file storage service.
        
        Args:
            base_storage_path: Base directory for storing files
        """
        self.base_storage_path = Path(base_storage_path)
        self.base_storage_path.mkdir(parents=True, exist_ok=True)
        
        logger.info("File storage service initialized", storage_path=str(self.base_storage_path))
    
    def store_attachment(
        self, 
        attachment: EmailAttachment, 
        client_id: str,
        message_id: str
    ) -> FileStorageInfo:
        """Store an email attachment to filesystem.
        
        Args:
            attachment: Email attachment to store
            client_id: Client UUID for organization
            message_id: Email message ID for organization
            
        Returns:
            FileStorageInfo with storage details
            
        Raises:
            OSError: If file storage fails
            ValueError: If attachment is invalid
        """
        try:
            # Validate attachment using abuse protection
            # Note: This is a synchronous call, but the validation is designed to be fast
            try:
                import asyncio
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # If we're in an async context, we can't use await here
                    # The validation should have been done at the API level
                    pass
                else:
                    # If not in async context, run validation
                    asyncio.run(abuse_protection.validate_attachment(attachment))
            except RuntimeError:
                # Already in async context, validation should have been done at API level
                pass
            
            # Additional synchronous validation
            if not self.validate_file_format(attachment):
                raise ValueError(f"Unsupported file format: {attachment.filename}")
            
            # Create client-specific directory
            client_dir = self.base_storage_path / client_id
            client_dir.mkdir(parents=True, exist_ok=True)
            
            # Generate unique filename while preserving extension
            file_extension = self._get_file_extension(attachment.filename)
            unique_filename = f"{uuid.uuid4()}{file_extension}"
            file_path = client_dir / unique_filename
            
            # Validate file path for security (prevent path traversal)
            if not str(file_path).startswith(str(self.base_storage_path)):
                raise ValueError("Invalid file path detected")
            
            # Write file content
            with open(file_path, 'wb') as f:
                f.write(attachment.content)
            
            # Verify file was written correctly
            if not file_path.exists() or file_path.stat().st_size != len(attachment.content):
                raise OSError(f"File verification failed for {file_path}")
            
            storage_info = FileStorageInfo(
                file_path=str(file_path),
                original_filename=attachment.filename,
                stored_filename=unique_filename,
                content_type=attachment.content_type,
                size_bytes=len(attachment.content),
                storage_timestamp=datetime.utcnow()
            )
            
            logger.info(
                "Attachment stored successfully",
                original_filename=attachment.filename,
                stored_path=str(file_path),
                size_bytes=len(attachment.content),
                client_id=client_id,
                message_id=message_id
            )
            
            return storage_info
            
        except Exception as e:
            logger.error(
                "Failed to store attachment",
                filename=attachment.filename,
                client_id=client_id,
                message_id=message_id,
                error=str(e)
            )
            raise OSError(f"Failed to store attachment {attachment.filename}: {str(e)}")
    
    def _get_file_extension(self, filename: str) -> str:
        """Extract file extension from filename.
        
        Args:
            filename: Original filename
            
        Returns:
            File extension including the dot
        """
        return Path(filename).suffix.lower()
    
    def delete_file(self, file_path: str) -> bool:
        """Delete a stored file.
        
        Args:
            file_path: Path to file to delete
            
        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            path = Path(file_path)
            if path.exists():
                path.unlink()
                logger.info("File deleted successfully", file_path=file_path)
                return True
            else:
                logger.warning("File not found for deletion", file_path=file_path)
                return False
                
        except Exception as e:
            logger.error("Failed to delete file", file_path=file_path, error=str(e))
            return False
    
    def get_file_info(self, file_path: str) -> Optional[dict]:
        """Get information about a stored file.
        
        Args:
            file_path: Path to file
            
        Returns:
            Dictionary with file information or None if not found
        """
        try:
            path = Path(file_path)
            if not path.exists():
                return None
            
            stat = path.stat()
            return {
                "path": str(path),
                "size_bytes": stat.st_size,
                "created_at": datetime.fromtimestamp(stat.st_ctime),
                "modified_at": datetime.fromtimestamp(stat.st_mtime),
                "exists": True
            }
            
        except Exception as e:
            logger.error("Failed to get file info", file_path=file_path, error=str(e))
            return None
    
    def validate_file_format(self, attachment: EmailAttachment) -> bool:
        """Validate that attachment has supported file format.
        
        Args:
            attachment: Email attachment to validate
            
        Returns:
            True if format is supported, False otherwise
        """
        supported_extensions = ['.pdf', '.png', '.jpg', '.jpeg', '.tiff', '.tif']
        file_extension = self._get_file_extension(attachment.filename)
        
        # Check extension
        if file_extension not in supported_extensions:
            logger.warning(
                "Unsupported file format",
                filename=attachment.filename,
                extension=file_extension,
                supported=supported_extensions
            )
            return False
        
        # Basic content type validation
        expected_content_types = {
            '.pdf': ['application/pdf'],
            '.png': ['image/png'],
            '.jpg': ['image/jpeg'],
            '.jpeg': ['image/jpeg'],
            '.tiff': ['image/tiff'],
            '.tif': ['image/tiff']
        }
        
        expected_types = expected_content_types.get(file_extension, [])
        if expected_types and attachment.content_type not in expected_types:
            logger.warning(
                "Content type mismatch",
                filename=attachment.filename,
                content_type=attachment.content_type,
                expected=expected_types
            )
            # Don't fail on content type mismatch, just log warning
        
        return True
    
    def cleanup_old_files(self, days_old: int = 30) -> int:
        """Clean up files older than specified days.
        
        Args:
            days_old: Number of days after which files should be cleaned up
            
        Returns:
            Number of files cleaned up
        """
        try:
            cutoff_time = datetime.utcnow().timestamp() - (days_old * 24 * 60 * 60)
            cleaned_count = 0
            
            for file_path in self.base_storage_path.rglob("*"):
                if file_path.is_file():
                    try:
                        if file_path.stat().st_mtime < cutoff_time:
                            file_path.unlink()
                            cleaned_count += 1
                            logger.debug("Cleaned up old file", file_path=str(file_path))
                    except Exception as e:
                        logger.warning("Failed to clean up file", file_path=str(file_path), error=str(e))
            
            logger.info("File cleanup completed", files_cleaned=cleaned_count, days_old=days_old)
            return cleaned_count
            
        except Exception as e:
            logger.error("File cleanup failed", error=str(e))
            return 0
    
    def get_storage_stats(self) -> dict:
        """Get storage statistics.
        
        Returns:
            Dictionary with storage statistics
        """
        try:
            total_files = 0
            total_size = 0
            
            for file_path in self.base_storage_path.rglob("*"):
                if file_path.is_file():
                    total_files += 1
                    total_size += file_path.stat().st_size
            
            return {
                "total_files": total_files,
                "total_size_bytes": total_size,
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "storage_path": str(self.base_storage_path)
            }
            
        except Exception as e:
            logger.error("Failed to get storage stats", error=str(e))
            return {
                "total_files": 0,
                "total_size_bytes": 0,
                "total_size_mb": 0.0,
                "storage_path": str(self.base_storage_path),
                "error": str(e)
            }