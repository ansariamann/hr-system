#!/usr/bin/env python3
"""
Automated database backup script for ATS Backend.

Provides automated backup creation with verification and cleanup.
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Add src to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from ats_backend.core.disaster_recovery import DisasterRecoveryManager
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


async def create_backup(backup_id: str = None, verify: bool = True):
    """Create a database backup."""
    dr_manager = DisasterRecoveryManager()
    
    try:
        logger.info("Starting backup creation", backup_id=backup_id)
        
        # Create backup
        metadata = await dr_manager.create_backup(backup_id)
        
        logger.info("Backup created successfully", 
                   backup_id=metadata.backup_id,
                   size_mb=metadata.size_bytes / (1024 * 1024),
                   backup_path=metadata.backup_path)
        
        # Verify backup if requested
        if verify:
            logger.info("Starting backup verification", backup_id=metadata.backup_id)
            verified = await dr_manager.verify_backup(metadata.backup_id)
            
            if verified:
                logger.info("Backup verification successful", backup_id=metadata.backup_id)
            else:
                logger.error("Backup verification failed", backup_id=metadata.backup_id)
                return False
        
        return True
        
    except Exception as e:
        logger.error("Backup creation failed", error=str(e))
        return False


async def restore_backup(backup_id: str, target_database: str = None):
    """Restore from a backup."""
    dr_manager = DisasterRecoveryManager()
    
    try:
        logger.info("Starting backup restore", 
                   backup_id=backup_id,
                   target_database=target_database)
        
        success = await dr_manager.restore_backup(backup_id, target_database)
        
        if success:
            logger.info("Backup restore completed successfully", backup_id=backup_id)
        else:
            logger.error("Backup restore failed", backup_id=backup_id)
        
        return success
        
    except Exception as e:
        logger.error("Backup restore failed", 
                    backup_id=backup_id, 
                    error=str(e))
        return False


async def list_backups(environment: str = None):
    """List available backups."""
    dr_manager = DisasterRecoveryManager()
    
    try:
        backups = await dr_manager.list_backups(environment)
        
        if not backups:
            print("No backups found")
            return
        
        print(f"{'Backup ID':<20} {'Environment':<12} {'Timestamp':<20} {'Size (MB)':<10} {'Verified':<10}")
        print("-" * 80)
        
        for backup in backups:
            size_mb = backup.size_bytes / (1024 * 1024)
            verified = "Yes" if backup.verified else "No"
            
            print(f"{backup.backup_id:<20} {backup.environment:<12} "
                  f"{backup.timestamp.strftime('%Y-%m-%d %H:%M'):<20} "
                  f"{size_mb:<10.1f} {verified:<10}")
        
    except Exception as e:
        logger.error("Failed to list backups", error=str(e))


async def cleanup_backups(retention_days: int = 30):
    """Clean up old backups."""
    dr_manager = DisasterRecoveryManager()
    
    try:
        logger.info("Starting backup cleanup", retention_days=retention_days)
        
        cleaned_count = await dr_manager.cleanup_old_backups(retention_days)
        
        logger.info("Backup cleanup completed", 
                   cleaned_count=cleaned_count,
                   retention_days=retention_days)
        
        return cleaned_count
        
    except Exception as e:
        logger.error("Backup cleanup failed", error=str(e))
        return 0


async def get_recovery_status():
    """Get disaster recovery status."""
    dr_manager = DisasterRecoveryManager()
    
    try:
        status = await dr_manager.get_recovery_status()
        
        print("Disaster Recovery Status:")
        print(f"  Environment: {status['environment']}")
        print(f"  Status: {status['status']}")
        print(f"  Last Backup: {status['last_backup']}")
        print(f"  Time Since Backup: {status['time_since_backup_minutes']:.1f} minutes")
        print(f"  RPO Compliance: {'Yes' if status['rpo_compliance'] else 'No'}")
        print(f"  Total Backups: {status['total_backups']}")
        print(f"  Verified Backups: {status['verified_backups']}")
        
        if status['rto_config']:
            rto = status['rto_config']
            print(f"  RTO Configuration:")
            print(f"    Max Recovery Time: {rto['max_recovery_time_minutes']} minutes")
            print(f"    Max Data Loss: {rto['max_data_loss_minutes']} minutes")
            print(f"    Backup Frequency: {rto['backup_frequency_minutes']} minutes")
        
    except Exception as e:
        logger.error("Failed to get recovery status", error=str(e))


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="ATS Backend Database Backup Tool")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Create backup command
    create_parser = subparsers.add_parser("create", help="Create a new backup")
    create_parser.add_argument("--backup-id", help="Custom backup ID")
    create_parser.add_argument("--no-verify", action="store_true", 
                              help="Skip backup verification")
    
    # Restore backup command
    restore_parser = subparsers.add_parser("restore", help="Restore from backup")
    restore_parser.add_argument("backup_id", help="Backup ID to restore")
    restore_parser.add_argument("--target-database", 
                               help="Target database name (optional)")
    
    # List backups command
    list_parser = subparsers.add_parser("list", help="List available backups")
    list_parser.add_argument("--environment", help="Filter by environment")
    
    # Cleanup command
    cleanup_parser = subparsers.add_parser("cleanup", help="Clean up old backups")
    cleanup_parser.add_argument("--retention-days", type=int, default=30,
                               help="Retention period in days (default: 30)")
    
    # Status command
    subparsers.add_parser("status", help="Show disaster recovery status")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Run the appropriate command
    if args.command == "create":
        success = asyncio.run(create_backup(
            backup_id=args.backup_id,
            verify=not args.no_verify
        ))
        sys.exit(0 if success else 1)
        
    elif args.command == "restore":
        success = asyncio.run(restore_backup(
            backup_id=args.backup_id,
            target_database=args.target_database
        ))
        sys.exit(0 if success else 1)
        
    elif args.command == "list":
        asyncio.run(list_backups(args.environment))
        
    elif args.command == "cleanup":
        cleaned = asyncio.run(cleanup_backups(args.retention_days))
        print(f"Cleaned up {cleaned} old backups")
        
    elif args.command == "status":
        asyncio.run(get_recovery_status())


if __name__ == "__main__":
    main()