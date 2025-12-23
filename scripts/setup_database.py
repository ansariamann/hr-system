#!/usr/bin/env python3
"""Database setup script for ATS Backend."""

import os
import sys
from pathlib import Path

# Add src to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from ats_backend.core.migration import init_database
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


def main():
    """Run database setup."""
    try:
        logger.info("Starting database setup...")
        
        # Initialize database with migrations
        init_database()
        
        logger.info("Database setup completed successfully!")
        
    except Exception as e:
        logger.error("Database setup failed", error=str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()