"""Application configuration management."""

from typing import Optional, List, Dict
from datetime import datetime
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable support."""
    
    model_config = SettingsConfigDict(
        env_file=[".env", ".env.local"],
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # Database Configuration
    postgres_host: str = Field(default="localhost", description="PostgreSQL host")
    postgres_port: int = Field(default=5432, description="PostgreSQL port")
    postgres_db: str = Field(default="ats_db", description="PostgreSQL database name")
    postgres_user: str = Field(default="ats_user", description="PostgreSQL username")
    postgres_password: str = Field(default="", description="PostgreSQL password")
    
    # Redis Configuration
    redis_host: str = Field(default="localhost", description="Redis host")
    redis_port: int = Field(default=6379, description="Redis port")
    redis_db: int = Field(default=0, description="Redis database number")
    
    # API Configuration
    api_host: str = Field(default="0.0.0.0", description="API host")
    api_port: int = Field(default=8000, description="API port")
    api_workers: int = Field(default=4, description="Number of API workers")
    secret_key: str = Field(default="dev-secret-key", description="JWT secret key")
    algorithm: str = Field(default="HS256", description="JWT algorithm")
    access_token_expire_minutes: int = Field(default=30, description="Token expiry minutes")
    password_hash_rounds: int = Field(default=12, description="bcrypt hashing rounds")
    email_webhook_api_key: Optional[str] = Field(default=None, description="Shared secret for email webhook authentication")
    
    # Celery Configuration
    celery_broker_url: Optional[str] = Field(default=None, description="Celery broker URL")
    celery_result_backend: Optional[str] = Field(default=None, description="Celery result backend")
    
    # Application Configuration
    log_level: str = Field(default="INFO", description="Logging level")
    environment: str = Field(default="development", description="Environment name")
    
    # OCR Configuration
    tesseract_cmd: str = Field(default="/usr/bin/tesseract", description="Tesseract command path")
    
    # Email Configuration
    email_storage_path: str = Field(default="uploads/resumes", description="Path for storing email attachments")
    max_attachment_size_mb: int = Field(default=50, description="Maximum attachment size in MB")
    supported_file_extensions: List[str] = Field(
        default=[".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".tif"],
        description="Supported resume file extensions"
    )
    imap_ingestion_enabled: bool = Field(default=False, description="Enable IMAP mailbox polling for resume ingestion")
    imap_host: str = Field(default="imap.gmail.com", description="IMAP server host")
    imap_port: int = Field(default=993, description="IMAP server port")
    imap_username: Optional[str] = Field(default=None, description="IMAP username")
    imap_password: Optional[str] = Field(default=None, description="IMAP password or app password")
    imap_mailbox: str = Field(default="INBOX", description="Mailbox folder to poll")
    imap_poll_interval_seconds: int = Field(default=900, description="Seconds between IMAP polling runs")
    imap_max_messages_per_poll: int = Field(default=25, description="Maximum unread messages to fetch per poll")
    imap_client_id: Optional[str] = Field(default=None, description="Client UUID associated with the IMAP mailbox")
    
    # Storage Configuration
    storage_path: str = Field(default="./storage", description="Path for file storage")
    backup_path: str = Field(default="./backups", description="Path for database backups")
    
    # SMTP Configuration (for testing)
    smtp_host: str = Field(default="localhost", description="SMTP server host")
    smtp_port: int = Field(default=587, description="SMTP server port")
    smtp_username: Optional[str] = Field(default=None, description="SMTP username")
    smtp_password: Optional[str] = Field(default=None, description="SMTP password")
    smtp_use_tls: bool = Field(default=True, description="Use TLS for SMTP")
    
    # Security Configuration
    login_attempts_limit: int = Field(default=5, description="Maximum login attempts before lockout")
    login_window_minutes: int = Field(default=15, description="Time window for login attempts")
    lockout_duration_minutes: int = Field(default=30, description="Account lockout duration")
    token_replay_protection: bool = Field(default=True, description="Enable token replay protection")
    password_reset_token_minutes: int = Field(default=30, description="Password reset token validity in minutes")

    # Frontend URLs (for password reset links)
    frontend_hr_url: str = Field(default="http://localhost:5173", description="HR Dashboard frontend URL")
    frontend_client_url: str = Field(default="http://localhost:8080", description="Client Portal frontend URL")
    email_from_address: str = Field(default="noreply@hr-system.local", description="Email sender address")

    # Alerting Configuration
    alerts_email_enabled: bool = Field(default=False, description="Enable alert delivery via email")
    alerts_email_recipients: List[str] = Field(default_factory=list, description="Email recipients for alerts")
    alerts_slack_enabled: bool = Field(default=False, description="Enable alert delivery via Slack webhook")
    alerts_slack_webhook_url: Optional[str] = Field(default=None, description="Slack incoming webhook URL for alerts")
    alerts_slack_channel: str = Field(default="#alerts", description="Slack channel label for alert messages")
    alerts_webhook_enabled: bool = Field(default=False, description="Enable alert delivery via generic webhook")
    alerts_webhook_url: Optional[str] = Field(default=None, description="Generic webhook URL for alerts")
    alerts_webhook_headers: Dict[str, str] = Field(default_factory=dict, description="Optional HTTP headers for alert webhook delivery")
    
    # Runtime Configuration
    startup_time: Optional[datetime] = Field(default=None, description="System startup time")
    
    # Custom Database URL (overrides postgres config)
    custom_database_url: Optional[str] = Field(default=None, description="Direct database URL override")

    @property
    def database_url(self) -> str:
        """Construct database URL from components or use override."""
        if self.custom_database_url:
            return self.custom_database_url
            
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )
    
    @property
    def redis_url(self) -> str:
        """Construct Redis URL from components."""
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"
    
    @property
    def celery_broker_url_computed(self) -> str:
        """Get Celery broker URL, defaulting to Redis URL."""
        return self.celery_broker_url or self.redis_url
    
    @property
    def celery_result_backend_computed(self) -> str:
        """Get Celery result backend URL, defaulting to Redis URL."""
        return self.celery_result_backend or self.redis_url


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get the global settings instance."""
    return settings
