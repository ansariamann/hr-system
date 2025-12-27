"""
Disaster Recovery System for ATS Backend.

Provides automated backup, restore, and environment management capabilities
with guaranteed recovery time objectives.
"""

import asyncio
import os
import shutil
import subprocess
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import structlog
import asyncpg
from pydantic import BaseModel

from .config import get_settings

logger = structlog.get_logger(__name__)


class BackupMetadata(BaseModel):
    """Metadata for database backups."""
    
    backup_id: str
    environment: str
    timestamp: datetime
    database_name: str
    backup_path: str
    size_bytes: int
    checksum: str
    verified: bool = False
    verification_timestamp: Optional[datetime] = None


class RecoveryTimeObjective(BaseModel):
    """Recovery time objectives for different environments."""
    
    environment: str
    backup_frequency_minutes: int
    max_data_loss_minutes: int  # RPO - Recovery Point Objective
    max_recovery_time_minutes: int  # RTO - Recovery Time Objective
    verification_frequency_hours: int


class DisasterRecoveryManager:
    """Manages automated backup, restore, and disaster recovery operations."""
    
    def __init__(self):
        self.settings = get_settings()
        self.backup_path = Path(self.settings.backup_path)
        self.backup_path.mkdir(parents=True, exist_ok=True)
        
        # Recovery time objectives by environment
        self.rto_config = {
            "development": RecoveryTimeObjective(
                environment="development",
                backup_frequency_minutes=60,  # Hourly backups
                max_data_loss_minutes=60,
                max_recovery_time_minutes=15,
                verification_frequency_hours=24
            ),
            "staging": RecoveryTimeObjective(
                environment="staging",
                backup_frequency_minutes=30,  # Every 30 minutes
                max_data_loss_minutes=30,
                max_recovery_time_minutes=10,
                verification_frequency_hours=12
            ),
            "production": RecoveryTimeObjective(
                environment="production",
                backup_frequency_minutes=15,  # Every 15 minutes
                max_data_loss_minutes=15,
                max_recovery_time_minutes=5,
                verification_frequency_hours=6
            )
        }
    
    async def create_backup(self, backup_id: Optional[str] = None) -> BackupMetadata:
        """
        Create a database backup with metadata.
        
        Args:
            backup_id: Optional custom backup ID, defaults to timestamp
            
        Returns:
            BackupMetadata: Metadata about the created backup
        """
        if backup_id is None:
            backup_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        
        timestamp = datetime.utcnow()
        backup_filename = f"backup_{self.settings.environment}_{backup_id}.sql"
        backup_file_path = self.backup_path / backup_filename
        
        logger.info("Creating database backup", 
                   backup_id=backup_id, 
                   environment=self.settings.environment,
                   backup_path=str(backup_file_path))
        
        try:
            # Create database dump using pg_dump
            cmd = [
                "pg_dump",
                f"--host={self.settings.postgres_host}",
                f"--port={self.settings.postgres_port}",
                f"--username={self.settings.postgres_user}",
                f"--dbname={self.settings.postgres_db}",
                "--verbose",
                "--clean",
                "--if-exists",
                "--create",
                "--format=plain",
                f"--file={backup_file_path}"
            ]
            
            env = os.environ.copy()
            env["PGPASSWORD"] = self.settings.postgres_password
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                error_msg = stderr.decode() if stderr else "Unknown error"
                logger.error("Backup creation failed", 
                           error=error_msg, 
                           return_code=process.returncode)
                raise RuntimeError(f"Backup failed: {error_msg}")
            
            # Calculate file size and checksum
            file_size = backup_file_path.stat().st_size
            checksum = await self._calculate_checksum(backup_file_path)
            
            metadata = BackupMetadata(
                backup_id=backup_id,
                environment=self.settings.environment,
                timestamp=timestamp,
                database_name=self.settings.postgres_db,
                backup_path=str(backup_file_path),
                size_bytes=file_size,
                checksum=checksum
            )
            
            # Save metadata
            await self._save_backup_metadata(metadata)
            
            logger.info("Backup created successfully", 
                       backup_id=backup_id,
                       size_mb=file_size / (1024 * 1024),
                       checksum=checksum)
            
            return metadata
            
        except Exception as e:
            logger.error("Backup creation failed", error=str(e))
            # Clean up partial backup file
            if backup_file_path.exists():
                backup_file_path.unlink()
            raise
    
    async def restore_backup(self, backup_id: str, target_database: Optional[str] = None) -> bool:
        """
        Restore a database from backup.
        
        Args:
            backup_id: ID of the backup to restore
            target_database: Optional target database name, defaults to current
            
        Returns:
            bool: True if restore was successful
        """
        metadata = await self._load_backup_metadata(backup_id)
        if not metadata:
            raise ValueError(f"Backup {backup_id} not found")
        
        backup_file = Path(metadata.backup_path)
        if not backup_file.exists():
            raise FileNotFoundError(f"Backup file not found: {metadata.backup_path}")
        
        # Verify backup integrity
        current_checksum = await self._calculate_checksum(backup_file)
        if current_checksum != metadata.checksum:
            raise ValueError(f"Backup integrity check failed for {backup_id}")
        
        target_db = target_database or self.settings.postgres_db
        
        logger.info("Starting database restore", 
                   backup_id=backup_id,
                   target_database=target_db,
                   backup_file=str(backup_file))
        
        start_time = datetime.utcnow()
        
        try:
            # Restore database using psql
            cmd = [
                "psql",
                f"--host={self.settings.postgres_host}",
                f"--port={self.settings.postgres_port}",
                f"--username={self.settings.postgres_user}",
                f"--dbname={target_db}",
                "--file", str(backup_file),
                "--single-transaction",
                "--set", "ON_ERROR_STOP=on"
            ]
            
            env = os.environ.copy()
            env["PGPASSWORD"] = self.settings.postgres_password
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                error_msg = stderr.decode() if stderr else "Unknown error"
                logger.error("Restore failed", 
                           error=error_msg, 
                           return_code=process.returncode)
                raise RuntimeError(f"Restore failed: {error_msg}")
            
            restore_time = (datetime.utcnow() - start_time).total_seconds()
            
            # Verify RTO compliance
            rto = self.rto_config.get(self.settings.environment)
            if rto and restore_time > (rto.max_recovery_time_minutes * 60):
                logger.warning("RTO violation detected", 
                             restore_time_seconds=restore_time,
                             max_allowed_seconds=rto.max_recovery_time_minutes * 60)
            
            logger.info("Database restore completed successfully", 
                       backup_id=backup_id,
                       restore_time_seconds=restore_time)
            
            return True
            
        except Exception as e:
            logger.error("Database restore failed", error=str(e))
            raise
    
    async def verify_backup(self, backup_id: str) -> bool:
        """
        Verify backup integrity by attempting a test restore.
        
        Args:
            backup_id: ID of the backup to verify
            
        Returns:
            bool: True if backup verification passed
        """
        metadata = await self._load_backup_metadata(backup_id)
        if not metadata:
            raise ValueError(f"Backup {backup_id} not found")
        
        logger.info("Starting backup verification", backup_id=backup_id)
        
        # Create temporary database for verification
        temp_db_name = f"verify_{backup_id}_{int(datetime.utcnow().timestamp())}"
        
        try:
            # Create temporary database
            await self._create_temp_database(temp_db_name)
            
            # Attempt restore to temporary database
            success = await self.restore_backup(backup_id, temp_db_name)
            
            if success:
                # Perform basic integrity checks
                await self._verify_database_integrity(temp_db_name)
                
                # Update metadata
                metadata.verified = True
                metadata.verification_timestamp = datetime.utcnow()
                await self._save_backup_metadata(metadata)
                
                logger.info("Backup verification successful", backup_id=backup_id)
                return True
            
        except Exception as e:
            logger.error("Backup verification failed", 
                        backup_id=backup_id, 
                        error=str(e))
            return False
            
        finally:
            # Clean up temporary database
            try:
                await self._drop_temp_database(temp_db_name)
            except Exception as e:
                logger.warning("Failed to clean up temp database", 
                             temp_db=temp_db_name, 
                             error=str(e))
        
        return False
    
    async def list_backups(self, environment: Optional[str] = None) -> List[BackupMetadata]:
        """
        List available backups.
        
        Args:
            environment: Optional environment filter
            
        Returns:
            List[BackupMetadata]: List of backup metadata
        """
        backups = []
        metadata_pattern = "backup_*.json"
        
        for metadata_file in self.backup_path.glob(metadata_pattern):
            try:
                metadata = await self._load_backup_metadata_from_file(metadata_file)
                if environment is None or metadata.environment == environment:
                    backups.append(metadata)
            except Exception as e:
                logger.warning("Failed to load backup metadata", 
                             file=str(metadata_file), 
                             error=str(e))
        
        # Sort by timestamp, newest first
        backups.sort(key=lambda x: x.timestamp, reverse=True)
        return backups
    
    async def cleanup_old_backups(self, retention_days: int = 30) -> int:
        """
        Clean up old backups based on retention policy.
        
        Args:
            retention_days: Number of days to retain backups
            
        Returns:
            int: Number of backups cleaned up
        """
        cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
        backups = await self.list_backups()
        
        cleaned_count = 0
        for backup in backups:
            if backup.timestamp < cutoff_date:
                try:
                    # Remove backup file
                    backup_file = Path(backup.backup_path)
                    if backup_file.exists():
                        backup_file.unlink()
                    
                    # Remove metadata file
                    metadata_file = self.backup_path / f"backup_{backup.backup_id}.json"
                    if metadata_file.exists():
                        metadata_file.unlink()
                    
                    cleaned_count += 1
                    logger.info("Cleaned up old backup", 
                               backup_id=backup.backup_id,
                               timestamp=backup.timestamp)
                    
                except Exception as e:
                    logger.error("Failed to clean up backup", 
                               backup_id=backup.backup_id, 
                               error=str(e))
        
        logger.info("Backup cleanup completed", 
                   cleaned_count=cleaned_count,
                   retention_days=retention_days)
        
        return cleaned_count
    
    async def get_recovery_status(self) -> Dict:
        """
        Get current disaster recovery status and metrics.
        
        Returns:
            Dict: Recovery status information
        """
        backups = await self.list_backups(self.settings.environment)
        rto = self.rto_config.get(self.settings.environment)
        
        if not backups:
            return {
                "status": "critical",
                "message": "No backups available",
                "last_backup": None,
                "rpo_compliance": False,
                "verified_backups": 0
            }
        
        latest_backup = backups[0]
        time_since_backup = datetime.utcnow() - latest_backup.timestamp
        
        # Check RPO compliance
        rpo_compliant = True
        if rto:
            max_age_minutes = rto.max_data_loss_minutes
            rpo_compliant = time_since_backup.total_seconds() <= (max_age_minutes * 60)
        
        verified_count = sum(1 for b in backups if b.verified)
        
        status = "healthy"
        if not rpo_compliant:
            status = "warning"
        if time_since_backup.total_seconds() > (2 * 60 * 60):  # 2 hours
            status = "critical"
        
        return {
            "status": status,
            "environment": self.settings.environment,
            "last_backup": latest_backup.timestamp,
            "time_since_backup_minutes": time_since_backup.total_seconds() / 60,
            "rpo_compliance": rpo_compliant,
            "total_backups": len(backups),
            "verified_backups": verified_count,
            "rto_config": rto.dict() if rto else None
        }
    
    # Private helper methods
    
    async def _calculate_checksum(self, file_path: Path) -> str:
        """Calculate SHA-256 checksum of a file."""
        import hashlib
        
        hash_sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()
    
    async def _save_backup_metadata(self, metadata: BackupMetadata):
        """Save backup metadata to JSON file."""
        metadata_file = self.backup_path / f"backup_{metadata.backup_id}.json"
        with open(metadata_file, "w") as f:
            f.write(metadata.json(indent=2))
    
    async def _load_backup_metadata(self, backup_id: str) -> Optional[BackupMetadata]:
        """Load backup metadata from JSON file."""
        metadata_file = self.backup_path / f"backup_{backup_id}.json"
        return await self._load_backup_metadata_from_file(metadata_file)
    
    async def _load_backup_metadata_from_file(self, metadata_file: Path) -> Optional[BackupMetadata]:
        """Load backup metadata from specific JSON file."""
        if not metadata_file.exists():
            return None
        
        try:
            with open(metadata_file, "r") as f:
                data = f.read()
            return BackupMetadata.parse_raw(data)
        except Exception as e:
            logger.error("Failed to load backup metadata", 
                        file=str(metadata_file), 
                        error=str(e))
            return None
    
    async def _create_temp_database(self, db_name: str):
        """Create temporary database for verification."""
        conn = await asyncpg.connect(
            host=self.settings.postgres_host,
            port=self.settings.postgres_port,
            user=self.settings.postgres_user,
            password=self.settings.postgres_password,
            database="postgres"  # Connect to default database
        )
        
        try:
            await conn.execute(f'CREATE DATABASE "{db_name}"')
        finally:
            await conn.close()
    
    async def _drop_temp_database(self, db_name: str):
        """Drop temporary database."""
        conn = await asyncpg.connect(
            host=self.settings.postgres_host,
            port=self.settings.postgres_port,
            user=self.settings.postgres_user,
            password=self.settings.postgres_password,
            database="postgres"  # Connect to default database
        )
        
        try:
            # Terminate connections to the database
            await conn.execute(f"""
                SELECT pg_terminate_backend(pid)
                FROM pg_stat_activity
                WHERE datname = '{db_name}' AND pid <> pg_backend_pid()
            """)
            
            await conn.execute(f'DROP DATABASE IF EXISTS "{db_name}"')
        finally:
            await conn.close()
    
    async def _verify_database_integrity(self, db_name: str):
        """Perform basic database integrity checks."""
        conn = await asyncpg.connect(
            host=self.settings.postgres_host,
            port=self.settings.postgres_port,
            user=self.settings.postgres_user,
            password=self.settings.postgres_password,
            database=db_name
        )
        
        try:
            # Check if key tables exist
            tables = await conn.fetch("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
            """)
            
            expected_tables = {'candidates', 'applications', 'clients'}
            actual_tables = {row['table_name'] for row in tables}
            
            missing_tables = expected_tables - actual_tables
            if missing_tables:
                raise ValueError(f"Missing tables in backup: {missing_tables}")
            
            # Check if we can query the tables
            for table in expected_tables:
                count = await conn.fetchval(f"SELECT COUNT(*) FROM {table}")
                logger.debug("Table integrity check", table=table, row_count=count)
                
        finally:
            await conn.close()