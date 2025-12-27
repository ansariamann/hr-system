#!/usr/bin/env python3
"""
Automated backup scheduler for ATS Backend.

Runs scheduled backups based on environment configuration and RTO requirements.
"""

import asyncio
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add src to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from ats_backend.core.disaster_recovery import DisasterRecoveryManager
from ats_backend.core.config import get_settings
import structlog

# Configure logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)


class BackupScheduler:
    """Automated backup scheduler with RTO compliance."""
    
    def __init__(self):
        self.dr_manager = DisasterRecoveryManager()
        self.settings = get_settings()
        self.running = False
    
    async def start_scheduler(self):
        """Start the backup scheduler."""
        self.running = True
        
        logger.info("Starting backup scheduler", 
                   environment=self.settings.environment)
        
        # Get RTO configuration for current environment
        rto_config = self.dr_manager.rto_config.get(self.settings.environment)
        if not rto_config:
            logger.error("No RTO configuration found for environment", 
                        environment=self.settings.environment)
            return
        
        backup_interval = rto_config.backup_frequency_minutes * 60  # Convert to seconds
        verification_interval = rto_config.verification_frequency_hours * 3600  # Convert to seconds
        
        logger.info("Scheduler configuration", 
                   backup_interval_minutes=rto_config.backup_frequency_minutes,
                   verification_interval_hours=rto_config.verification_frequency_hours)
        
        # Start background tasks
        backup_task = asyncio.create_task(self._backup_loop(backup_interval))
        verification_task = asyncio.create_task(self._verification_loop(verification_interval))
        cleanup_task = asyncio.create_task(self._cleanup_loop(24 * 3600))  # Daily cleanup
        
        try:
            # Wait for all tasks to complete (they run indefinitely)
            await asyncio.gather(backup_task, verification_task, cleanup_task)
        except asyncio.CancelledError:
            logger.info("Backup scheduler stopped")
        except Exception as e:
            logger.error("Backup scheduler error", error=str(e))
            raise
    
    def stop_scheduler(self):
        """Stop the backup scheduler."""
        self.running = False
        logger.info("Stopping backup scheduler")
    
    async def _backup_loop(self, interval: int):
        """Main backup loop."""
        while self.running:
            try:
                logger.info("Starting scheduled backup")
                
                # Create backup
                metadata = await self.dr_manager.create_backup()
                
                logger.info("Scheduled backup completed", 
                           backup_id=metadata.backup_id,
                           size_mb=metadata.size_bytes / (1024 * 1024))
                
                # Check RTO compliance
                await self._check_rto_compliance()
                
            except Exception as e:
                logger.error("Scheduled backup failed", error=str(e))
            
            # Wait for next backup
            await asyncio.sleep(interval)
    
    async def _verification_loop(self, interval: int):
        """Backup verification loop."""
        while self.running:
            try:
                logger.info("Starting scheduled backup verification")
                
                # Get recent unverified backups
                backups = await self.dr_manager.list_backups(self.settings.environment)
                unverified_backups = [b for b in backups if not b.verified]
                
                if unverified_backups:
                    # Verify the most recent unverified backup
                    backup = unverified_backups[0]
                    
                    logger.info("Verifying backup", backup_id=backup.backup_id)
                    
                    verified = await self.dr_manager.verify_backup(backup.backup_id)
                    
                    if verified:
                        logger.info("Backup verification successful", 
                                   backup_id=backup.backup_id)
                    else:
                        logger.error("Backup verification failed", 
                                    backup_id=backup.backup_id)
                        
                        # Alert on verification failure
                        await self._send_verification_alert(backup.backup_id)
                else:
                    logger.info("No unverified backups found")
                
            except Exception as e:
                logger.error("Backup verification failed", error=str(e))
            
            # Wait for next verification
            await asyncio.sleep(interval)
    
    async def _cleanup_loop(self, interval: int):
        """Backup cleanup loop."""
        while self.running:
            try:
                logger.info("Starting scheduled backup cleanup")
                
                # Get retention policy from environment
                retention_days = 30  # Default
                if self.settings.environment == "production":
                    retention_days = 90
                elif self.settings.environment == "staging":
                    retention_days = 60
                
                cleaned_count = await self.dr_manager.cleanup_old_backups(retention_days)
                
                logger.info("Scheduled cleanup completed", 
                           cleaned_count=cleaned_count,
                           retention_days=retention_days)
                
            except Exception as e:
                logger.error("Scheduled cleanup failed", error=str(e))
            
            # Wait for next cleanup (daily)
            await asyncio.sleep(interval)
    
    async def _check_rto_compliance(self):
        """Check RTO compliance and alert if violated."""
        try:
            status = await self.dr_manager.get_recovery_status()
            
            if not status['rpo_compliance']:
                logger.warning("RPO compliance violation detected", 
                             time_since_backup=status['time_since_backup_minutes'],
                             environment=self.settings.environment)
                
                await self._send_rto_alert(status)
            
        except Exception as e:
            logger.error("RTO compliance check failed", error=str(e))
    
    async def _send_verification_alert(self, backup_id: str):
        """Send alert for backup verification failure."""
        # In a real implementation, this would send alerts via email, Slack, etc.
        logger.critical("ALERT: Backup verification failed", 
                       backup_id=backup_id,
                       environment=self.settings.environment,
                       alert_type="backup_verification_failure")
    
    async def _send_rto_alert(self, status: dict):
        """Send alert for RTO compliance violation."""
        # In a real implementation, this would send alerts via email, Slack, etc.
        logger.critical("ALERT: RTO compliance violation", 
                       status=status,
                       environment=self.settings.environment,
                       alert_type="rto_violation")


async def run_once():
    """Run backup once (for cron jobs)."""
    dr_manager = DisasterRecoveryManager()
    
    try:
        logger.info("Running one-time backup")
        
        # Create backup
        metadata = await dr_manager.create_backup()
        
        logger.info("One-time backup completed", 
                   backup_id=metadata.backup_id,
                   size_mb=metadata.size_bytes / (1024 * 1024))
        
        # Check if we need to verify any backups
        backups = await dr_manager.list_backups()
        unverified_backups = [b for b in backups if not b.verified]
        
        if unverified_backups:
            # Verify the oldest unverified backup
            backup = unverified_backups[-1]
            
            logger.info("Verifying backup", backup_id=backup.backup_id)
            
            verified = await dr_manager.verify_backup(backup.backup_id)
            
            if verified:
                logger.info("Backup verification successful", 
                           backup_id=backup.backup_id)
            else:
                logger.error("Backup verification failed", 
                            backup_id=backup.backup_id)
        
        return True
        
    except Exception as e:
        logger.error("One-time backup failed", error=str(e))
        return False


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="ATS Backend Backup Scheduler")
    parser.add_argument("--daemon", action="store_true",
                       help="Run as daemon with continuous scheduling")
    parser.add_argument("--once", action="store_true",
                       help="Run backup once (for cron jobs)")
    
    args = parser.parse_args()
    
    if args.daemon:
        scheduler = BackupScheduler()
        try:
            asyncio.run(scheduler.start_scheduler())
        except KeyboardInterrupt:
            scheduler.stop_scheduler()
            logger.info("Backup scheduler stopped by user")
    elif args.once:
        success = asyncio.run(run_once())
        sys.exit(0 if success else 1)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()