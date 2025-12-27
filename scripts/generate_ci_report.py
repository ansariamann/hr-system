#!/usr/bin/env python3
"""
CI Report Generator

Generates a comprehensive HTML report of all CI pipeline results including
security scans, test results, quality gates, and deployment readiness.
"""

import json
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class CIReportGenerator:
    """Generate