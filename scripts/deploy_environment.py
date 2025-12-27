#!/usr/bin/env python3
"""
Environment deployment script for ATS Backend.

Provides one-command deployment automation for dev, staging, and production environments.
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Add src to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from ats_backend.core.environment_manager import EnvironmentManager
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


async def deploy_environment(environment: str, force: bool = False):
    """Deploy a specific environment."""
    env_manager = EnvironmentManager()
    
    try:
        logger.info("Starting environment deployment", environment=environment)
        
        status = await env_manager.deploy_environment(environment, force)
        
        print(f"Deployment Status: {status.status}")
        print(f"Environment: {status.environment}")
        
        if status.services:
            print("Services:")
            for service, service_status in status.services.items():
                print(f"  {service}: {service_status}")
        
        if status.error_message:
            print(f"Error: {status.error_message}")
            return False
        
        if status.status == "healthy":
            print("✅ Environment deployed successfully!")
            return True
        else:
            print("⚠️  Environment deployment completed with issues")
            return False
        
    except Exception as e:
        logger.error("Environment deployment failed", 
                    environment=environment, 
                    error=str(e))
        print(f"❌ Deployment failed: {e}")
        return False


async def stop_environment(environment: str):
    """Stop a specific environment."""
    env_manager = EnvironmentManager()
    
    try:
        logger.info("Stopping environment", environment=environment)
        
        success = await env_manager.stop_environment(environment)
        
        if success:
            print(f"✅ Environment {environment} stopped successfully")
        else:
            print(f"❌ Failed to stop environment {environment}")
        
        return success
        
    except Exception as e:
        logger.error("Failed to stop environment", 
                    environment=environment, 
                    error=str(e))
        print(f"❌ Stop failed: {e}")
        return False


async def get_environment_status(environment: str = None):
    """Get status of environment(s)."""
    env_manager = EnvironmentManager()
    
    try:
        if environment:
            status = await env_manager.get_environment_status(environment)
            statuses = [status]
        else:
            statuses = await env_manager.list_environments()
        
        print(f"{'Environment':<12} {'Status':<12} {'Services':<30}")
        print("-" * 60)
        
        for status in statuses:
            services_str = ", ".join([
                f"{name}:{state}" for name, state in status.services.items()
            ]) if status.services else "None"
            
            # Truncate services string if too long
            if len(services_str) > 28:
                services_str = services_str[:25] + "..."
            
            print(f"{status.environment:<12} {status.status:<12} {services_str:<30}")
            
            if status.error_message:
                print(f"  Error: {status.error_message}")
        
    except Exception as e:
        logger.error("Failed to get environment status", error=str(e))
        print(f"❌ Status check failed: {e}")


async def cleanup_environments():
    """Clean up all environments."""
    env_manager = EnvironmentManager()
    
    try:
        logger.info("Starting environment cleanup")
        
        results = await env_manager.cleanup_environments()
        
        print("Cleanup Results:")
        for env_name, success in results.items():
            status = "✅ Success" if success else "❌ Failed"
            print(f"  {env_name}: {status}")
        
        return all(results.values())
        
    except Exception as e:
        logger.error("Environment cleanup failed", error=str(e))
        print(f"❌ Cleanup failed: {e}")
        return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="ATS Backend Environment Deployment Tool")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Deploy command
    deploy_parser = subparsers.add_parser("deploy", help="Deploy an environment")
    deploy_parser.add_argument("environment", 
                              choices=["dev", "staging", "prod"],
                              help="Environment to deploy")
    deploy_parser.add_argument("--force", action="store_true",
                              help="Force deployment even if already running")
    
    # Stop command
    stop_parser = subparsers.add_parser("stop", help="Stop an environment")
    stop_parser.add_argument("environment",
                            choices=["dev", "staging", "prod"],
                            help="Environment to stop")
    
    # Status command
    status_parser = subparsers.add_parser("status", help="Show environment status")
    status_parser.add_argument("environment", nargs="?",
                              choices=["dev", "staging", "prod"],
                              help="Specific environment (optional)")
    
    # Cleanup command
    subparsers.add_parser("cleanup", help="Clean up all environments")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Run the appropriate command
    if args.command == "deploy":
        success = asyncio.run(deploy_environment(
            environment=args.environment,
            force=args.force
        ))
        sys.exit(0 if success else 1)
        
    elif args.command == "stop":
        success = asyncio.run(stop_environment(args.environment))
        sys.exit(0 if success else 1)
        
    elif args.command == "status":
        asyncio.run(get_environment_status(args.environment))
        
    elif args.command == "cleanup":
        success = asyncio.run(cleanup_environments())
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()