
import unittest
import sys
from unittest.mock import MagicMock, patch
import asyncio
from datetime import datetime

# Mock dependencies
sys.modules["structlog"] = MagicMock()
sys.modules["pydantic"] = MagicMock()
sys.modules["pydantic_settings"] = MagicMock()

# Need to mock settings specifically because it's used at module level
mock_settings = MagicMock()
# Set attribute defaults that are used
mock_settings.alerts_email_enabled = False
mock_settings.alerts_email_recipients = []
mock_settings.alerts_email_from = "alerts@example.com"
mock_settings.smtp_host = "localhost"
mock_settings.smtp_port = 587
mock_settings.smtp_username = None
mock_settings.smtp_password = None
mock_settings.smtp_use_tls = True

# Mock the config module
mock_config_module = MagicMock()
mock_config_module.settings = mock_settings
sys.modules["ats_backend.core.config"] = mock_config_module

# Now import the module under test
# We also need to mock observability as it might be imported
sys.modules["ats_backend.core.observability"] = MagicMock()

# But we need Alert and AlertSeverity classes.
# Since we can't import them if dependencies are missing, we define dummy ones here
# and patch them into the module or use them directly if the module import fails partially.
# Actually, let's try to import the module. If it fails due to other imports, we mock those too.

# Alert and AlertSeverity are simple dataclasses/Enums, maybe we can rely on them if they don't have heavy deps.
# Let's try importing and see what fails.

try:
    from ats_backend.core.alerts import EmailNotificationSender
    # If Alert/AlertSeverity are not available from import due to mocks, we might need to redefine them for the test
    # or mock them.
    from ats_backend.core.observability import Alert, AlertSeverity
except ImportError:
    # If import fails, we might need to mock more things.
    # Let's see the error first.
    pass

# Redefine Alert and AlertSeverity for test purposes if they were mocked out
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, Any, Optional

class AlertSeverity(Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"

@dataclass
class Alert:
    name: str
    condition: str
    threshold: float
    current_value: float
    severity: AlertSeverity
    message: str
    triggered_at: datetime
    details: Dict[str, Any] = field(default_factory=dict)

class TestEmailNotificationSender(unittest.TestCase):
    def setUp(self):
        self.sender = EmailNotificationSender()
        self.alert = Alert(
            name="Test Alert",
            condition="value > 10",
            threshold=10.0,
            current_value=15.0,
            severity=AlertSeverity.WARNING,
            message="Test message",
            triggered_at=datetime.utcnow(),
            details={"key": "value"}
        )
        self.config = {
            "recipients": ["test@example.com"],
            "from_address": "sender@example.com",
            "smtp_host": "smtp.example.com",
            "smtp_port": 587,
            "smtp_username": "user",
            "smtp_password": "password",
            "smtp_use_tls": True
        }

    @patch("ats_backend.core.alerts.smtplib.SMTP")
    def test_send_email_success(self, mock_smtp):
        # Setup mock
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server

        # Run send
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # Spy on run_in_executor to verify async behavior
        with patch.object(loop, 'run_in_executor', wraps=loop.run_in_executor) as mock_run_in_executor:
            result = loop.run_until_complete(self.sender.send(self.alert, self.config))

            # Verify run_in_executor was used to offload work
            mock_run_in_executor.assert_called_once()
            args, _ = mock_run_in_executor.call_args
            self.assertEqual(args[0], None)
            # Verify the function passed is the sync sender method
            self.assertEqual(args[1], self.sender._send_email_sync)

        loop.close()

        # Verify
        self.assertTrue(result)
        mock_smtp.assert_called_with("smtp.example.com", 587)
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with("user", "password")
        mock_server.send_message.assert_called_once()

        # Verify email content
        args, _ = mock_server.send_message.call_args
        msg = args[0]
        self.assertEqual(msg['To'], "test@example.com")
        self.assertEqual(msg['From'], "sender@example.com")
        self.assertIn("[WARNING] ATS Alert: Test Alert", msg['Subject'])

    @patch("ats_backend.core.alerts.smtplib.SMTP")
    def test_send_email_no_recipients(self, mock_smtp):
        config = self.config.copy()
        config["recipients"] = []

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(self.sender.send(self.alert, config))
        loop.close()

        self.assertFalse(result)
        mock_smtp.assert_not_called()

    @patch("ats_backend.core.alerts.smtplib.SMTP")
    def test_send_email_failure(self, mock_smtp):
        # Setup mock to raise exception
        mock_smtp.side_effect = Exception("SMTP Error")

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(self.sender.send(self.alert, self.config))
        loop.close()

        self.assertFalse(result)

if __name__ == '__main__':
    unittest.main()
