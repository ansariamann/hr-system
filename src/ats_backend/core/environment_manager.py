"""
Environment Management System for ATS Backend.

Provides environment separation, deployment automation, and configuration management
for dev, staging, and production environments.
"""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Optional
import structlog
import yaml
from pydantic import BaseModel

logger = structlog.get_logger(__name__)


class EnvironmentConfig(BaseModel):
    """Configuration for a specific environment."""
    
    name: str
    database_name: str
    redis_db: int
    api_port: int
    worker_replicas: int
    log_level: str
    debug: bool
    storage_path: str
    backup_path: str
    metrics_enabled: bool
    security_scan_enabled: bool
    rate_limit_enabled: bool


class DeploymentStatus(BaseModel):
    """Status of environment deployment."""
    
    environment: str
    status: str  # "deploying", "healthy", "unhealthy", "stopped"
    services: Dict[str, str]  # service_name -> status
    deployment_time: Optional[str] = None
    last_health_check: Optional[str] = None
    error_message: Optional[str] = None


class EnvironmentManager:
    """Manages environment separation and deployment automation."""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent.parent.parent
        self.environments_dir = self.project_root / "environments"
        self.docker_compose_dir = self.project_root
        
        # Ensure environments directory exists
        self.environments_dir.mkdir(exist_ok=True)
        
        # Environment configurations
        self.env_configs = {
            "dev": EnvironmentConfig(
                name="development",
                database_name="ats_dev",
                redis_db=0,
                api_port=8000,
                worker_replicas=1,
                log_level="DEBUG",
                debug=True,
                storage_path="./storage/dev",
                backup_path="./backups/dev",
                metrics_enabled=True,
                security_scan_enabled=False,
                rate_limit_enabled=True
            ),
            "staging": EnvironmentConfig(
                name="staging",
                database_name="ats_staging",
                redis_db=1,
                api_port=8001,
                worker_replicas=2,
                log_level="INFO",
                debug=False,
                storage_path="/app/storage/staging",
                backup_path="/app/backups/staging",
                metrics_enabled=True,
                security_scan_enabled=True,
                rate_limit_enabled=True
            ),
            "prod": EnvironmentConfig(
                name="production",
                database_name="ats_production",
                redis_db=2,
                api_port=8002,
                worker_replicas=4,
                log_level="WARNING",
                debug=False,
                storage_path="/app/storage/production",
                backup_path="/app/backups/production",
                metrics_enabled=True,
                security_scan_enabled=True,
                rate_limit_enabled=True
            )
        }
    
    async def deploy_environment(self, environment: str, force: bool = False) -> DeploymentStatus:
        """
        Deploy a specific environment with one-command automation.
        
        Args:
            environment: Environment name (dev, staging, prod)
            force: Force deployment even if environment is running
            
        Returns:
            DeploymentStatus: Status of the deployment
        """
        if environment not in self.env_configs:
            raise ValueError(f"Unknown environment: {environment}")
        
        config = self.env_configs[environment]
        
        logger.info("Starting environment deployment", 
                   environment=environment,
                   config=config.name)
        
        try:
            # Check if environment is already running
            if not force:
                status = await self.get_environment_status(environment)
                if status.status == "healthy":
                    logger.info("Environment already running", environment=environment)
                    return status
            
            # Stop existing environment if running
            await self.stop_environment(environment)
            
            # Generate environment configuration
            await self._generate_environment_config(environment)
            
            # Generate docker-compose override for environment
            await self._generate_docker_compose_override(environment)
            
            # Start services
            await self._start_services(environment)
            
            # Wait for services to be ready
            await self._wait_for_services(environment)
            
            # Run database migrations
            await self._run_migrations(environment)
            
            # Perform health checks
            health_status = await self._perform_health_checks(environment)
            
            deployment_status = DeploymentStatus(
                environment=environment,
                status="healthy" if health_status else "unhealthy",
                services=await self._get_service_statuses(environment),
                deployment_time=str(datetime.utcnow()),
                last_health_check=str(datetime.utcnow())
            )
            
            logger.info("Environment deployment completed", 
                       environment=environment,
                       status=deployment_status.status)
            
            return deployment_status
            
        except Exception as e:
            logger.error("Environment deployment failed", 
                        environment=environment, 
                        error=str(e))
            
            return DeploymentStatus(
                environment=environment,
                status="unhealthy",
                services={},
                error_message=str(e)
            )
    
    async def stop_environment(self, environment: str) -> bool:
        """
        Stop a specific environment.
        
        Args:
            environment: Environment name to stop
            
        Returns:
            bool: True if stopped successfully
        """
        if environment not in self.env_configs:
            raise ValueError(f"Unknown environment: {environment}")
        
        logger.info("Stopping environment", environment=environment)
        
        try:
            compose_file = self._get_compose_file_path(environment)
            
            cmd = [
                "docker-compose",
                "-f", "docker-compose.yml",
                "-f", str(compose_file),
                "-p", f"ats-{environment}",
                "down",
                "--volumes",
                "--remove-orphans"
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=self.docker_compose_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                error_msg = stderr.decode() if stderr else "Unknown error"
                logger.error("Failed to stop environment", 
                           environment=environment,
                           error=error_msg)
                return False
            
            logger.info("Environment stopped successfully", environment=environment)
            return True
            
        except Exception as e:
            logger.error("Error stopping environment", 
                        environment=environment, 
                        error=str(e))
            return False
    
    async def get_environment_status(self, environment: str) -> DeploymentStatus:
        """
        Get the current status of an environment.
        
        Args:
            environment: Environment name to check
            
        Returns:
            DeploymentStatus: Current status of the environment
        """
        if environment not in self.env_configs:
            raise ValueError(f"Unknown environment: {environment}")
        
        try:
            services = await self._get_service_statuses(environment)
            
            # Determine overall status
            if not services:
                status = "stopped"
            elif all(s == "healthy" for s in services.values()):
                status = "healthy"
            elif any(s == "unhealthy" for s in services.values()):
                status = "unhealthy"
            else:
                status = "starting"
            
            return DeploymentStatus(
                environment=environment,
                status=status,
                services=services,
                last_health_check=str(datetime.utcnow())
            )
            
        except Exception as e:
            logger.error("Error getting environment status", 
                        environment=environment, 
                        error=str(e))
            
            return DeploymentStatus(
                environment=environment,
                status="unknown",
                services={},
                error_message=str(e)
            )
    
    async def list_environments(self) -> List[DeploymentStatus]:
        """
        List all environments and their statuses.
        
        Returns:
            List[DeploymentStatus]: Status of all environments
        """
        statuses = []
        for env_name in self.env_configs.keys():
            status = await self.get_environment_status(env_name)
            statuses.append(status)
        
        return statuses
    
    async def cleanup_environments(self) -> Dict[str, bool]:
        """
        Clean up all stopped environments and unused resources.
        
        Returns:
            Dict[str, bool]: Cleanup results for each environment
        """
        results = {}
        
        for env_name in self.env_configs.keys():
            try:
                # Stop environment
                stopped = await self.stop_environment(env_name)
                
                # Clean up volumes and networks
                await self._cleanup_environment_resources(env_name)
                
                results[env_name] = stopped
                
            except Exception as e:
                logger.error("Error cleaning up environment", 
                           environment=env_name, 
                           error=str(e))
                results[env_name] = False
        
        # Clean up unused Docker resources
        await self._cleanup_docker_resources()
        
        return results
    
    # Private helper methods
    
    async def _generate_environment_config(self, environment: str):
        """Generate environment-specific configuration file."""
        config = self.env_configs[environment]
        env_file = self.environments_dir / f".env.{environment}"
        
        # Load base environment template
        base_env_file = self.environments_dir / f".env.{environment}"
        if not base_env_file.exists():
            # Create from template
            template_content = self._get_env_template(config)
            with open(env_file, "w") as f:
                f.write(template_content)
        
        logger.info("Generated environment config", 
                   environment=environment,
                   config_file=str(env_file))
    
    async def _generate_docker_compose_override(self, environment: str):
        """Generate docker-compose override file for environment."""
        config = self.env_configs[environment]
        override_file = self.docker_compose_dir / f"docker-compose.{environment}.yml"
        
        override_config = {
            "version": "3.8",
            "services": {
                "postgres": {
                    "container_name": f"ats-postgres-{environment}",
                    "environment": {
                        "POSTGRES_DB": config.database_name,
                        "POSTGRES_USER": f"ats_{environment}_user"
                    },
                    "ports": [f"{5432 + hash(environment) % 1000}:5432"],
                    "volumes": [f"postgres_data_{environment}:/var/lib/postgresql/data"]
                },
                "redis": {
                    "container_name": f"ats-redis-{environment}",
                    "ports": [f"{6379 + hash(environment) % 1000}:6379"],
                    "volumes": [f"redis_data_{environment}:/data"]
                },
                "api": {
                    "container_name": f"ats-api-{environment}",
                    "environment": {
                        "ENVIRONMENT": config.name,
                        "POSTGRES_DB": config.database_name,
                        "REDIS_DB": str(config.redis_db),
                        "LOG_LEVEL": config.log_level,
                        "DEBUG": str(config.debug).lower()
                    },
                    "ports": [f"{config.api_port}:8000"]
                },
                "worker": {
                    "environment": {
                        "ENVIRONMENT": config.name,
                        "POSTGRES_DB": config.database_name,
                        "REDIS_DB": str(config.redis_db),
                        "LOG_LEVEL": config.log_level
                    },
                    "deploy": {
                        "replicas": config.worker_replicas
                    }
                }
            },
            "volumes": {
                f"postgres_data_{environment}": {"driver": "local"},
                f"redis_data_{environment}": {"driver": "local"}
            }
        }
        
        with open(override_file, "w") as f:
            yaml.dump(override_config, f, default_flow_style=False)
        
        logger.info("Generated docker-compose override", 
                   environment=environment,
                   override_file=str(override_file))
    
    async def _start_services(self, environment: str):
        """Start services for environment."""
        compose_file = self._get_compose_file_path(environment)
        
        cmd = [
            "docker-compose",
            "-f", "docker-compose.yml",
            "-f", str(compose_file),
            "-p", f"ats-{environment}",
            "up", "-d",
            "--build"
        ]
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=self.docker_compose_dir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            error_msg = stderr.decode() if stderr else "Unknown error"
            raise RuntimeError(f"Failed to start services: {error_msg}")
    
    async def _wait_for_services(self, environment: str, timeout: int = 300):
        """Wait for services to be ready."""
        import asyncio
        from datetime import datetime, timedelta
        
        start_time = datetime.utcnow()
        timeout_time = start_time + timedelta(seconds=timeout)
        
        while datetime.utcnow() < timeout_time:
            try:
                services = await self._get_service_statuses(environment)
                if all(s in ["healthy", "running"] for s in services.values()):
                    logger.info("All services ready", environment=environment)
                    return
                
                await asyncio.sleep(5)
                
            except Exception as e:
                logger.debug("Waiting for services", 
                           environment=environment, 
                           error=str(e))
                await asyncio.sleep(5)
        
        raise TimeoutError(f"Services did not become ready within {timeout} seconds")
    
    async def _run_migrations(self, environment: str):
        """Run database migrations for environment."""
        config = self.env_configs[environment]
        
        # Run migrations using alembic
        cmd = [
            "docker-compose",
            "-p", f"ats-{environment}",
            "exec", "-T", "api",
            "alembic", "upgrade", "head"
        ]
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=self.docker_compose_dir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            error_msg = stderr.decode() if stderr else "Unknown error"
            logger.warning("Migration may have failed", 
                         environment=environment,
                         error=error_msg)
            # Don't fail deployment for migration issues
    
    async def _perform_health_checks(self, environment: str) -> bool:
        """Perform health checks on all services."""
        try:
            config = self.env_configs[environment]
            
            # Check API health endpoint
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(f"http://localhost:{config.api_port}/health") as response:
                    if response.status != 200:
                        logger.error("API health check failed", 
                                   environment=environment,
                                   status=response.status)
                        return False
            
            logger.info("Health checks passed", environment=environment)
            return True
            
        except Exception as e:
            logger.error("Health check failed", 
                        environment=environment, 
                        error=str(e))
            return False
    
    async def _get_service_statuses(self, environment: str) -> Dict[str, str]:
        """Get status of all services in environment."""
        try:
            cmd = [
                "docker-compose",
                "-p", f"ats-{environment}",
                "ps", "--format", "json"
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=self.docker_compose_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                return {}
            
            # Parse docker-compose ps output
            import json
            services = {}
            
            for line in stdout.decode().strip().split('\n'):
                if line:
                    try:
                        service_info = json.loads(line)
                        name = service_info.get('Service', 'unknown')
                        state = service_info.get('State', 'unknown')
                        
                        # Map docker states to our status
                        if state == 'running':
                            # Check if healthy
                            health = service_info.get('Health', '')
                            if health == 'healthy' or not health:
                                services[name] = 'healthy'
                            else:
                                services[name] = 'unhealthy'
                        else:
                            services[name] = state
                            
                    except json.JSONDecodeError:
                        continue
            
            return services
            
        except Exception as e:
            logger.error("Error getting service statuses", 
                        environment=environment, 
                        error=str(e))
            return {}
    
    def _get_compose_file_path(self, environment: str) -> Path:
        """Get path to docker-compose override file for environment."""
        return self.docker_compose_dir / f"docker-compose.{environment}.yml"
    
    def _get_env_template(self, config: EnvironmentConfig) -> str:
        """Get environment configuration template."""
        return f"""# {config.name.title()} Environment Configuration
ENVIRONMENT={config.name}

# Database Configuration
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB={config.database_name}
POSTGRES_USER=ats_{config.name}_user
POSTGRES_PASSWORD=${{ENV_DB_PASSWORD}}

# Redis Configuration
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB={config.redis_db}

# API Configuration
API_HOST=0.0.0.0
API_PORT={config.api_port}
API_WORKERS={config.worker_replicas}
SECRET_KEY=${{ENV_SECRET_KEY}}
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Celery Configuration
CELERY_BROKER_URL=redis://localhost:6379/{config.redis_db}
CELERY_RESULT_BACKEND=redis://localhost:6379/{config.redis_db}

# Application Configuration
LOG_LEVEL={config.log_level}
DEBUG={str(config.debug).lower()}

# Storage Configuration
STORAGE_PATH={config.storage_path}
BACKUP_PATH={config.backup_path}

# Monitoring Configuration
METRICS_ENABLED={str(config.metrics_enabled).lower()}
METRICS_PORT=9090

# Security Configuration
RATE_LIMIT_ENABLED={str(config.rate_limit_enabled).lower()}
SECURITY_SCAN_ENABLED={str(config.security_scan_enabled).lower()}

# Backup Configuration
BACKUP_SCHEDULE=0 2 * * *  # Daily at 2 AM
BACKUP_RETENTION_DAYS=30
BACKUP_VERIFICATION_ENABLED=true
"""
    
    async def _cleanup_environment_resources(self, environment: str):
        """Clean up Docker resources for environment."""
        try:
            # Remove volumes
            cmd = ["docker", "volume", "ls", "-q", "--filter", f"name=ats-{environment}"]
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0 and stdout:
                volumes = stdout.decode().strip().split('\n')
                for volume in volumes:
                    if volume:
                        await asyncio.create_subprocess_exec(
                            "docker", "volume", "rm", volume,
                            stdout=asyncio.subprocess.DEVNULL,
                            stderr=asyncio.subprocess.DEVNULL
                        )
            
        except Exception as e:
            logger.warning("Error cleaning up environment resources", 
                         environment=environment, 
                         error=str(e))
    
    async def _cleanup_docker_resources(self):
        """Clean up unused Docker resources."""
        try:
            # Clean up unused volumes, networks, and images
            cmd = ["docker", "system", "prune", "-f", "--volumes"]
            await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL
            )
            
        except Exception as e:
            logger.warning("Error cleaning up Docker resources", error=str(e))


# Import datetime for the module
from datetime import datetime
import asyncio