import pytest
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime
from src.ats_backend.core.alerts import SlackNotificationSender, Alert, AlertSeverity

@pytest.fixture
def slack_sender():
    return SlackNotificationSender()

@pytest.fixture
def sample_alert():
    return Alert(
        name="test_alert",
        condition="cpu > 90%",
        severity=AlertSeverity.CRITICAL,
        threshold=90.0,
        current_value=95.0,
        triggered_at=datetime.utcnow(),
        message="CPU usage is too high"
    )

@pytest.mark.asyncio
async def test_slack_send_success(slack_sender, sample_alert):
    config = {
        "webhook_url": "https://hooks.slack.com/services/test/webhook",
        "channel": "#alerts"
    }

    # Mock aiohttp
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.__aenter__.return_value = mock_response

    mock_session = MagicMock()
    mock_session.post.return_value = mock_response
    mock_session.__aenter__.return_value = mock_session

    with patch("aiohttp.ClientSession", return_value=mock_session):
        result = await slack_sender.send(sample_alert, config)

        assert result is True
        mock_session.post.assert_called_once()
        args, kwargs = mock_session.post.call_args
        assert args[0] == config["webhook_url"]
        assert kwargs["json"]["text"] == f"ATS Alert: {sample_alert.name}"
        assert kwargs["json"]["channel"] == config["channel"]
        assert kwargs["json"]["attachments"][0]["color"] == "danger"

@pytest.mark.asyncio
async def test_slack_send_no_webhook(slack_sender, sample_alert):
    config = {"channel": "#alerts"}
    result = await slack_sender.send(sample_alert, config)
    assert result is False

@pytest.mark.asyncio
async def test_slack_send_failure_status(slack_sender, sample_alert):
    config = {"webhook_url": "https://hooks.slack.com/services/test/webhook"}

    mock_response = AsyncMock()
    mock_response.status = 400
    mock_response.text.return_value = "Bad Request"
    mock_response.__aenter__.return_value = mock_response

    mock_session = MagicMock()
    mock_session.post.return_value = mock_response
    mock_session.__aenter__.return_value = mock_session

    with patch("aiohttp.ClientSession", return_value=mock_session):
        result = await slack_sender.send(sample_alert, config)
        assert result is False

@pytest.mark.asyncio
async def test_slack_send_exception(slack_sender, sample_alert):
    config = {"webhook_url": "https://hooks.slack.com/services/test/webhook"}

    with patch("aiohttp.ClientSession", side_effect=Exception("Connection error")):
        result = await slack_sender.send(sample_alert, config)
        assert result is False
