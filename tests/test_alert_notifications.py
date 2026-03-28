from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from ats_backend.core.alerts import EmailNotificationSender, SlackNotificationSender
from ats_backend.core.observability import Alert, AlertSeverity


def build_alert() -> Alert:
    return Alert(
        name="high_queue_depth",
        condition="queue_depth > 100",
        severity=AlertSeverity.WARNING,
        threshold=100.0,
        current_value=250.0,
        triggered_at=datetime.utcnow(),
        message="Queue depth exceeded threshold",
        details={"queue": "email_processing"},
    )


@pytest.mark.asyncio
async def test_email_notification_sender_dispatches_to_all_recipients():
    sender = EmailNotificationSender()
    alert = build_alert()

    with patch("ats_backend.core.alerts.send_email", return_value=True) as mock_send_email:
        result = await sender.send(alert, {"recipients": ["ops@example.com", "lead@example.com"]})

    assert result is True
    assert mock_send_email.call_count == 2


class _FakeResponse:
    def __init__(self, status: int = 200):
        self.status = status

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def text(self):
        return "ok"


class _FakeSession:
    def __init__(self, timeout=None):
        self.timeout = timeout
        self.post = MagicMock(return_value=_FakeResponse(status=200))

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


@pytest.mark.asyncio
async def test_slack_notification_sender_posts_to_webhook():
    sender = SlackNotificationSender()
    alert = build_alert()
    fake_session = _FakeSession()

    with patch("ats_backend.core.alerts.aiohttp.ClientSession", return_value=fake_session):
        result = await sender.send(
            alert,
            {"webhook_url": "https://hooks.slack.test/services/abc", "channel": "#alerts"},
        )

    assert result is True
    fake_session.post.assert_called_once()
