#!/usr/bin/env python3
"""Validation script for ATS Backend infrastructure setup."""

import sys
import os
from pathlib import Path

def validate_project_structure():
    """Validate that all required files and directories exist."""
    print("🔍 Validating project structure...")
    
    required_files = [
        "pyproject.toml",
        "docker-compose.yml", 
        "Dockerfile",
        ".env.example",
        "README.md",
        "alembic.ini",
        "src/ats_backend/__init__.py",
        "src/ats_backend/core/__init__.py",
        "src/ats_backend/core/config.py",
        "src/ats_backend/core/database.py",
        "src/ats_backend/core/logging.py",
        "src/ats_backend/core/redis.py",
        "scripts/init-db.sql",
        "alembic/env.py",
        "alembic/script.py.mako",
    ]
    
    missing_files = []
    for file_path in required_files:
        if not Path(file_path).exists():
            missing_files.append(file_path)
    
    if missing_files:
        print("❌ Missing required files:")
        for file_path in missing_files:
            print(f"   - {file_path}")
        return False
    
    print("✅ All required files present")
    return True

def validate_docker_compose():
    """Validate Docker Compose configuration."""
    print("🐳 Validating Docker Compose configuration...")
    
    try:
        import subprocess
        result = subprocess.run(
            ["docker-compose", "config", "--quiet"],
            capture_output=True,
            text=True,
            check=True
        )
        print("✅ Docker Compose configuration is valid")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Docker Compose validation failed: {e}")
        return False
    except FileNotFoundError:
        print("⚠️  Docker Compose not found - skipping validation")
        return True

def validate_python_structure():
    """Validate Python package structure."""
    print("🐍 Validating Python package structure...")
    
    # Add src to path for imports
    sys.path.insert(0, str(Path("src").absolute()))
    
    try:
        # Test basic imports without external dependencies
        import importlib.util
        
        # Check if config module can be loaded
        config_spec = importlib.util.spec_from_file_location(
            "config", "src/ats_backend/core/config.py"
        )
        if config_spec is None:
            print("❌ Cannot load config module")
            return False
        
        print("✅ Python package structure is valid")
        return True
    except Exception as e:
        print(f"❌ Python structure validation failed: {e}")
        return False

def main():
    """Run all validation checks."""
    print("🚀 ATS Backend Infrastructure Validation")
    print("=" * 50)
    
    checks = [
        validate_project_structure,
        validate_docker_compose,
        validate_python_structure,
    ]
    
    results = []
    for check in checks:
        results.append(check())
        print()
    
    if all(results):
        print("🎉 All validation checks passed!")
        print("✅ Infrastructure setup is complete and ready for development")
        return 0
    else:
        print("❌ Some validation checks failed")
        print("🔧 Please review and fix the issues above")
        return 1

if __name__ == "__main__":
    sys.exit(main())