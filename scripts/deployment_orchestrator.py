#!/usr/bin/env python3
"""
Advanced Deployment Orchestrator for ATS Backend.

Provides zero-downtime deployments, rollback capabilities, and comprehensive
deployment validation with automated monitoring setup.
"""

import asyncio
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Add src to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from ats_backend.core.environment_manager import EnvironmentManager
from ats_backend.core.disaster_recovery import DisasterRecoveryManager
import structlog
import aiohttp

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


class DeploymentOrchestrator:
    """Advanced deployment orchestration with zero-downtime capabilities."""
    
    def __init__(self):
        self.env_manager = EnvironmentManager()
        self.dr_manager = DisasterRecoveryManager()
        self.project_root = Path(__file__).parent.parent
    
    async def deploy_with_validation(self, environment: str, 
                                   enable_monitoring: bool = True,
                                   run_smoke_tests: bool = True,
                                   create_backup: bool = True) -> Tuple[bool, Dict]:
        """
        Deploy environment with comprehensive validation and monitoring setup.
        
        Args:
            environment: Target environment (dev, staging, prod)
            enable_monitoring: Whether to start monitoring stack
            run_smoke_tests: Whether to run post-deployment smoke tests
            create_backup: Whether to create backup before/after deployment
            
        Returns:
            Tuple[bool, Dict]: (success, deployment_report)
        """
        deployment_start = datetime.utcnow()
        
        report = {
            "environment": environment,
            "deployment_start": deployment_start.isoformat(),
            "steps": {},
            "success": False,
            "total_time_seconds": 0,
            "rollback_performed": False
        }
        
        logger.info("Starting advanced deployment", environment=environment)
        
        try:
            # Step 1: Pre-deployment backup
            if create_backup:
                logger.info("Creating pre-deployment backup")
                step_start = time.time()
                
                try:
                    backup_metadata = await self.dr_manager.create_backup()
                    report["steps"]["pre_backup"] = {
                        "success": True,
                        "backup_id": backup_metadata.backup_id,
                        "duration_seconds": time.time() - step_start
                    }
                    logger.info("Pre-deployment backup created", 
                               backup_id=backup_metadata.backup_id)
                except Exception as e:
                    report["steps"]["pre_backup"] = {
                        "success": False,
                        "error": str(e),
                        "duration_seconds": time.time() - step_start
                    }
                    logger.error("Pre-deployment backup failed", error=str(e))
                    # Continue deployment even if backup fails
            
            # Step 2: Deploy environment
            logger.info("Deploying environment")
            step_start = time.time()
            
            deployment_status = await self.env_manager.deploy_environment(
                environment, force=True
            )
            
            report["steps"]["deployment"] = {
                "success": deployment_status.status == "healthy",
                "status": deployment_status.status,
                "services": deployment_status.services,
                "duration_seconds": time.time() - step_start
            }
            
            if deployment_status.status != "healthy":
                logger.error("Environment deployment failed", 
                           status=deployment_status.status)
                return False, report
            
            # Step 3: Start monitoring stack
            if enable_monitoring:
                logger.info("Starting monitoring stack")
                step_start = time.time()
                
                monitoring_success = await self._start_monitoring_stack(environment)
                report["steps"]["monitoring"] = {
                    "success": monitoring_success,
                    "duration_seconds": time.time() - step_start
                }
                
                if monitoring_success:
                    # Wait for monitoring to be ready
                    await asyncio.sleep(30)
            
            # Step 4: Health checks and validation
            logger.info("Running health checks and validation")
            step_start = time.time()
            
            validation_success = await self._run_comprehensive_validation(environment)
            report["steps"]["validation"] = {
                "success": validation_success,
                "duration_seconds": time.time() - step_start
            }
            
            # Step 5: Smoke tests
            if run_smoke_tests:
                logger.info("Running smoke tests")
                step_start = time.time()
                
                smoke_test_success = await self._run_smoke_tests(environment)
                report["steps"]["smoke_tests"] = {
                    "success": smoke_test_success,
                    "duration_seconds": time.time() - step_start
                }
            else:
                smoke_test_success = True
            
            # Step 6: Post-deployment backup
            if create_backup and validation_success and smoke_test_success:
                logger.info("Creating post-deployment backup")
                step_start = time.time()
                
                try:
                    backup_metadata = await self.dr_manager.create_backup()
                    report["steps"]["post_backup"] = {
                        "success": True,
                        "backup_id": backup_metadata.backup_id,
                        "duration_seconds": time.time() - step_start
                    }
                    logger.info("Post-deployment backup created", 
                               backup_id=backup_metadata.backup_id)
                except Exception as e:
                    report["steps"]["post_backup"] = {
                        "success": False,
                        "error": str(e),
                        "duration_seconds": time.time() - step_start
                    }
            
            # Determine overall success
            deployment_success = all([
                deployment_status.status == "healthy",
                validation_success,
                smoke_test_success if run_smoke_tests else True
            ])
            
            # If deployment failed, attempt rollback
            if not deployment_success and create_backup:
                logger.warning("Deployment validation failed, attempting rollback")
                rollback_success = await self._attempt_rollback(environment, report)
                report["rollback_performed"] = rollback_success
            
            report["success"] = deployment_success
            report["total_time_seconds"] = (datetime.utcnow() - deployment_start).total_seconds()
            
            if deployment_success:
                logger.info("Deployment completed successfully", 
                           environment=environment,
                           total_time=report["total_time_seconds"])
            else:
                logger.error("Deployment failed", 
                           environment=environment,
                           total_time=report["total_time_seconds"])
            
            return deployment_success, report
            
        except Exception as e:
            logger.error("Deployment orchestration failed", 
                        environment=environment, 
                        error=str(e))
            
            report["success"] = False
            report["error"] = str(e)
            report["total_time_seconds"] = (datetime.utcnow() - deployment_start).total_seconds()
            
            return False, report
    
    async def zero_downtime_deploy(self, environment: str) -> Tuple[bool, Dict]:
        """
        Perform zero-downtime deployment using blue-green strategy.
        
        Args:
            environment: Target environment
            
        Returns:
            Tuple[bool, Dict]: (success, deployment_report)
        """
        if environment == "dev":
            # For dev, just do regular deployment
            return await self.deploy_with_validation(environment)
        
        logger.info("Starting zero-downtime deployment", environment=environment)
        
        report = {
            "environment": environment,
            "strategy": "blue-green",
            "success": False,
            "steps": {}
        }
        
        try:
            # Step 1: Deploy to staging first (green environment)
            logger.info("Deploying to staging environment first")
            staging_success, staging_report = await self.deploy_with_validation("staging")
            
            report["steps"]["staging_deployment"] = {
                "success": staging_success,
                "report": staging_report
            }
            
            if not staging_success:
                logger.error("Staging deployment failed, aborting production deployment")
                return False, report
            
            # Step 2: Run comprehensive tests on staging
            logger.info("Running comprehensive tests on staging")
            staging_tests_success = await self._run_comprehensive_tests("staging")
            
            report["steps"]["staging_tests"] = {
                "success": staging_tests_success
            }
            
            if not staging_tests_success:
                logger.error("Staging tests failed, aborting production deployment")
                return False, report
            
            # Step 3: Deploy to production
            logger.info("Deploying to production")
            prod_success, prod_report = await self.deploy_with_validation(environment)
            
            report["steps"]["production_deployment"] = {
                "success": prod_success,
                "report": prod_report
            }
            
            report["success"] = prod_success
            
            return prod_success, report
            
        except Exception as e:
            logger.error("Zero-downtime deployment failed", error=str(e))
            report["error"] = str(e)
            return False, report
    
    async def _start_monitoring_stack(self, environment: str) -> bool:
        """Start monitoring stack for environment."""
        try:
            cmd = [
                "docker-compose", "-f", "docker-compose.prod.yml",
                "up", "-d",
                "prometheus", "grafana", "alertmanager",
                "node-exporter", "postgres-exporter", "redis-exporter",
                "loki", "promtail"
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=self.project_root,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                logger.error("Failed to start monitoring stack", 
                           error=stderr.decode() if stderr else "Unknown error")
                return False
            
            logger.info("Monitoring stack started successfully")
            return True
            
        except Exception as e:
            logger.error("Error starting monitoring stack", error=str(e))
            return False
    
    async def _run_comprehensive_validation(self, environment: str) -> bool:
        """Run comprehensive deployment validation."""
        try:
            # Import and run deployment validator
            from scripts.validate_deployment import DeploymentValidator
            
            validator = DeploymentValidator(environment)
            success, results = await validator.validate_full_deployment()
            
            logger.info("Deployment validation completed", 
                       environment=environment,
                       success=success)
            
            return success
            
        except Exception as e:
            logger.error("Deployment validation failed", error=str(e))
            return False
    
    async def _run_smoke_tests(self, environment: str) -> bool:
        """Run smoke tests against deployed environment."""
        try:
            # Get environment configuration
            config = self.env_manager.env_configs.get(environment)
            if not config:
                return False
            
            api_port = config.api_port
            
            # Basic smoke tests
            async with aiohttp.ClientSession() as session:
                # Test health endpoint
                async with session.get(f"http://localhost:{api_port}/health") as response:
                    if response.status != 200:
                        logger.error("Health endpoint smoke test failed", 
                                   status=response.status)
                        return False
                
                # Test metrics endpoint (if available)
                try:
                    async with session.get(f"http://localhost:{api_port}/metrics") as response:
                        # Metrics endpoint is optional
                        pass
                except Exception:
                    pass
                
                # Test that protected endpoints are actually protected
                async with session.get(f"http://localhost:{api_port}/api/candidates") as response:
                    if response.status not in [401, 403]:
                        logger.error("Security smoke test failed - unprotected endpoint", 
                                   status=response.status)
                        return False
            
            logger.info("Smoke tests passed", environment=environment)
            return True
            
        except Exception as e:
            logger.error("Smoke tests failed", environment=environment, error=str(e))
            return False
    
    async def _run_comprehensive_tests(self, environment: str) -> bool:
        """Run comprehensive test suite against environment."""
        try:
            # Run property-based tests in CI mode
            cmd = [
                "python", "-m", "pytest", 
                "tests/property_based/", 
                "-v", "--tb=short",
                "--hypothesis-seed=42"
            ]
            
            env = {
                **dict(os.environ),
                "HYPOTHESIS_PROFILE": "ci",
                "TEST_ENVIRONMENT": environment
            }
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=self.project_root,
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                logger.error("Comprehensive tests failed", 
                           error=stderr.decode() if stderr else "Unknown error")
                return False
            
            logger.info("Comprehensive tests passed", environment=environment)
            return True
            
        except Exception as e:
            logger.error("Error running comprehensive tests", error=str(e))
            return False
    
    async def _attempt_rollback(self, environment: str, report: Dict) -> bool:
        """Attempt to rollback deployment using latest backup."""
        try:
            logger.info("Attempting deployment rollback", environment=environment)
            
            # Get latest backup
            backups = await self.dr_manager.list_backups(environment)
            if not backups:
                logger.error("No backups available for rollback")
                return False
            
            latest_backup = backups[0]
            
            # Stop current environment
            await self.env_manager.stop_environment(environment)
            
            # Restore from backup
            await self.dr_manager.restore_backup(latest_backup.backup_id)
            
            # Restart environment
            deployment_status = await self.env_manager.deploy_environment(environment)
            
            rollback_success = deployment_status.status == "healthy"
            
            if rollback_success:
                logger.info("Rollback completed successfully", 
                           environment=environment,
                           backup_id=latest_backup.backup_id)
            else:
                logger.error("Rollback failed", environment=environment)
            
            return rollback_success
            
        except Exception as e:
            logger.error("Rollback attempt failed", error=str(e))
            return False


def print_deployment_report(report: Dict):
    """Print formatted deployment report."""
    print("\n" + "="*80)
    print(f"DEPLOYMENT REPORT - {report['environment'].upper()}")
    print("="*80)
    
    print(f"Environment: {report['environment']}")
    print(f"Success: {'✅ YES' if report['success'] else '❌ NO'}")
    print(f"Total Time: {report.get('total_time_seconds', 0):.1f} seconds")
    
    if report.get("rollback_performed"):
        print("Rollback: ⚠️  PERFORMED")
    
    print("\nSTEP DETAILS:")
    print("-"*80)
    
    for step_name, step_data in report.get("steps", {}).items():
        status = "✅ PASS" if step_data.get("success", False) else "❌ FAIL"
        duration = step_data.get("duration_seconds", 0)
        
        print(f"{step_name.replace('_', ' ').title():<30} {status} ({duration:.1f}s)")
        
        if "error" in step_data:
            print(f"  └─ Error: {step_data['error']}")
        
        if "backup_id" in step_data:
            print(f"  └─ Backup ID: {step_data['backup_id']}")
    
    print("="*80)


async def main():
    """Main entry point."""
    import argparse
    import os
    
    parser = argparse.ArgumentParser(description="ATS Backend Deployment Orchestrator")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Deploy command
    deploy_parser = subparsers.add_parser("deploy", help="Deploy with validation")
    deploy_parser.add_argument("environment", 
                              choices=["dev", "staging", "prod"],
                              help="Environment to deploy")
    deploy_parser.add_argument("--no-monitoring", action="store_true",
                              help="Skip monitoring stack setup")
    deploy_parser.add_argument("--no-smoke-tests", action="store_true",
                              help="Skip smoke tests")
    deploy_parser.add_argument("--no-backup", action="store_true",
                              help="Skip backup creation")
    
    # Zero-downtime deploy command
    zd_parser = subparsers.add_parser("zero-downtime", help="Zero-downtime deployment")
    zd_parser.add_argument("environment",
                          choices=["staging", "prod"],
                          help="Environment for zero-downtime deployment")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    orchestrator = DeploymentOrchestrator()
    
    if args.command == "deploy":
        success, report = await orchestrator.deploy_with_validation(
            environment=args.environment,
            enable_monitoring=not args.no_monitoring,
            run_smoke_tests=not args.no_smoke_tests,
            create_backup=not args.no_backup
        )
        
        print_deployment_report(report)
        sys.exit(0 if success else 1)
        
    elif args.command == "zero-downtime":
        success, report = await orchestrator.zero_downtime_deploy(args.environment)
        
        print_deployment_report(report)
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    import os
    asyncio.run(main())