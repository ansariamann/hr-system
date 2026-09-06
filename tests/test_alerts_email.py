import pytest
import smtplib
import base64
from unittest.mock import MagicMock, patch
from datetime import datetime
from src.ats_backend.core.alerts import EmailNotificationSender, Alert, AlertSeverity


@pytest.fixture
def email_sender():
    return EmailNotificationSender()


@pytest.fixture
def sample_alert():
    return Alert(
        name="high_error_rate",
        condition="error_rate > 5%",
        severity=AlertSeverity.CRITICAL,
        threshold=0.05,
        current_value=0.12,
        triggered_at=datetime.utcnow(),
        message="High error rate detected on API"
    )


@pytest.mark.asyncio
async def test_email_send_success(email_sender, sample_alert):
    config = {
        "recipients": ["admin@example.com"],
        "smtp_host": "smtp.example.com",
        "smtp_port": 587,
        "smtp_username": "user@example.com",
        "smtp_password": "secretpassword",
        "use_tls": True
    }

    mock_smtp_instance = MagicMock()

    with patch("smtplib.SMTP", return_value=mock_smtp_instance) as mock_smtp_class:
        result = await email_sender.send(sample_alert, config)

        assert result is True
        mock_smtp_class.assert_called_once_with("smtp.example.com", 587, timeout=10)
        mock_smtp_instance.starttls.assert_called_once()
        mock_smtp_instance.login.assert_called_once_with("user@example.com", "secretpassword")
        mock_smtp_instance.sendmail.assert_called_once()
        args, _ = mock_smtp_instance.sendmail.call_args
        assert args[0] == "user@example.com"
        assert args[1] == ["admin@example.com"]

        # Decoding base64 body if base64 encoded
        raw_msg = args[2]
        if "Content-Transfer-Encoding: base64" in raw_msg:
            payload = raw_msg.split("\n\n", 1)[1]
            decoded_body = base64.b64decode(payload).decode("utf-8")
            assert "High error rate detected on API" in decoded_body
        else:
            assert "High error rate detected on API" in raw_msg

        mock_smtp_instance.quit.assert_called_once()


@pytest.mark.asyncio
async def test_email_send_ssl_success(email_sender, sample_alert):
    config = {
        "recipients": ["admin@example.com"],
        "smtp_host": "smtp.example.com",
        "smtp_port": 465,
        "from_email": "alerts@example.com",
        "use_ssl": True
    }

    mock_smtp_ssl_instance = MagicMock()

    with patch("smtplib.SMTP_SSL", return_value=mock_smtp_ssl_instance) as mock_smtp_ssl_class:
        result = await email_sender.send(sample_alert, config)

        assert result is True
        mock_smtp_ssl_class.assert_called_once_with("smtp.example.com", 465, timeout=10)
        mock_smtp_ssl_instance.sendmail.assert_called_once()
        args, _ = mock_smtp_ssl_instance.sendmail.call_args
        assert args[0] == "alerts@example.com"
        assert args[1] == ["admin@example.com"]


@pytest.mark.asyncio
async def test_email_send_no_recipients(email_sender, sample_alert):
    config = {
        "recipients": [],
        "smtp_host": "smtp.example.com"
    }

    with patch("src.ats_backend.core.alerts.settings") as mock_settings:
        mock_settings.alerts_email_recipients = []
        result = await email_sender.send(sample_alert, config)
        assert result is False


@pytest.mark.asyncio
async def test_email_send_no_smtp_host(email_sender, sample_alert):
    config = {
        "recipients": ["admin@example.com"],
        "smtp_host": ""
    }

    with patch("src.ats_backend.core.alerts.settings") as mock_settings:
        mock_settings.smtp_host = ""
        result = await email_sender.send(sample_alert, config)
        assert result is False


@pytest.mark.asyncio
async def test_email_send_smtp_exception(email_sender, sample_alert):
    config = {
        "recipients": ["admin@example.com"],
        "smtp_host": "smtp.example.com"
    }

    with patch("smtplib.SMTP", side_effect=smtplib.SMTPException("Connection error")):
        result = await email_sender.send(sample_alert, config)
        assert result is False
