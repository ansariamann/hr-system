"""Alert system for threshold violations and notifications."""

from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import json
import structlog
from pathlib import Path

from .config import settings
from .observability import Alert, AlertSeverity

logger = structlog.get_logger(__name__)


class NotificationChannel(str, Enum):
    """Notification channel types."""
    EMAIL = "email"
    SLACK = "slack"
    WEBHOOK = "webhook"
    LOG = "log"


@dataclass
class NotificationConfig:
    """Configuration for notification channels."""
    channel: NotificationChannel
    enabled: bool = True
    config: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "channel": self.channel.value,
            "enabled": self.enabled,
            "config": self.config
        }


@dataclass
class AlertRule:
    """Alert rule definition."""
    name: str
    condition: str
    threshold: float
    severity: AlertSeverity
    enabled: bool = True
    cooldown_minutes: int = 15
    notification_channels: List[NotificationChannel] = field(default_factory=list)
    last_triggered: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "condition": self.condition,
            "threshold": self.threshold,
            "severity": self.severity.value,
            "enabled": self.enabled,
            "cooldown_minutes": self.cooldown_minutes,
            "notification_channels": [c.value for c in self.notification_channels],
            "last_triggered": self.last_triggered.isoformat() if self.last_triggered else None
        }


class NotificationSender:
    """Base class for notification senders."""
    
    async def send(self, alert: Alert, config: Dict[str, Any]) -> bool:
        """Send notification for alert."""
        raise NotImplementedError


class LogNotificationSender(NotificationSender):
    """Log-based notification sender."""
    
    async def send(self, alert: Alert, config: Dict[str, Any]) -> bool:
        """Send notification via logging."""
        try:
            logger.warning(
                "ALERT NOTIFICATION",
                alert_name=alert.name,
                severity=alert.severity.value,
                message=alert.message,
                threshold=alert.threshold,
                current_value=alert.current_value,
                condition=alert.condition,
                details=alert.details
            )
            return True
        except Exception as e:
            logger.error("Failed to send log notification", error=str(e))
            return False


class EmailNotificationSender(NotificationSender):
    """Email notification sender."""
    
    async def send(self, alert: Alert, config: Dict[str, Any]) -> bool:
        """Send notification via email using SMTP."""
        try:
            import smtplib
            from email.mime.text import MIMEText

            recipients = config.get("recipients") or getattr(settings, 'alerts_email_recipients', [])
            if isinstance(recipients, str):
                recipients = [recipients]

            if not recipients:
                logger.error("Email notification failed: No recipients configured")
                return False

            smtp_host = config.get("smtp_host") or getattr(settings, 'smtp_host', 'localhost')
            if not smtp_host:
                logger.error("Email notification failed: SMTP host not configured")
                return False

            smtp_port = config.get("smtp_port") or getattr(settings, 'smtp_port', 587)
            smtp_username = config.get("smtp_username") or getattr(settings, 'smtp_username', None)
            smtp_password = config.get("smtp_password") or getattr(settings, 'smtp_password', None)

            use_tls = config.get("use_tls", config.get("smtp_use_tls", getattr(settings, 'smtp_use_tls', True)))
            use_ssl = config.get("use_ssl", False)
            
            from_email = (
                config.get("from_email")
                or config.get("sender")
                or smtp_username
                or "noreply@ats.local"
            )

            subject = f"[{alert.severity.value.upper()}] ATS Alert: {alert.name}"
            body = f"""Alert: {alert.name}
Severity: {alert.severity.value}
Condition: {alert.condition}
Threshold: {alert.threshold}
Current Value: {alert.current_value}
Message: {alert.message}
Triggered At: {alert.triggered_at.isoformat()}

Details:
{json.dumps(alert.details, indent=2)}
"""

            def _send_smtp():
                msg = MIMEText(body, "plain", "utf-8")
                msg["Subject"] = subject
                msg["From"] = from_email
                msg["To"] = ", ".join(recipients)

                if use_ssl:
                    server = smtplib.SMTP_SSL(smtp_host, int(smtp_port), timeout=10)
                else:
                    server = smtplib.SMTP(smtp_host, int(smtp_port), timeout=10)

                try:
                    if not use_ssl and use_tls:
                        server.starttls()

                    if smtp_username and smtp_password:
                        server.login(smtp_username, smtp_password)

                    server.sendmail(from_email, recipients, msg.as_string())
                finally:
                    try:
                        server.quit()
                    except Exception:
                        pass

            await asyncio.to_thread(_send_smtp)

            logger.info(
                "Email notification sent successfully",
                to=recipients,
                subject=subject,
                alert_name=alert.name,
                severity=alert.severity.value
            )
            return True
            
        except Exception as e:
            logger.error("Failed to send email notification", error=str(e))
            return False


class SlackNotificationSender(NotificationSender):
    """Slack notification sender."""
    
    async def send(self, alert: Alert, config: Dict[str, Any]) -> bool:
        """Send notification via Slack."""
        try:
            import aiohttp

            webhook_url = config.get("webhook_url")
            if not webhook_url:
                logger.error("Slack webhook URL not configured")
                return False
            
            color = {
                AlertSeverity.INFO: "good",
                AlertSeverity.WARNING: "warning", 
                AlertSeverity.CRITICAL: "danger"
            }.get(alert.severity, "warning")
            
            payload = {
                "text": f"ATS Alert: {alert.name}",
                "channel": config.get("channel", "#alerts"),
                "attachments": [{
                    "color": color,
                    "fields": [
                        {"title": "Severity", "value": alert.severity.value, "short": True},
                        {"title": "Condition", "value": alert.condition, "short": True},
                        {"title": "Threshold", "value": str(alert.threshold), "short": True},
                        {"title": "Current Value", "value": str(alert.current_value), "short": True},
                        {"title": "Message", "value": alert.message, "short": False}
                    ],
                    "ts": int(alert.triggered_at.timestamp())
                }]
            }
            
            timeout = aiohttp.ClientTimeout(total=10)
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(webhook_url, json=payload) as response:
                    if response.status in (200, 201, 204):
                        logger.info(
                            "Slack notification sent successfully",
                            webhook_url=webhook_url,
                            alert_name=alert.name,
                            status_code=response.status
                        )
                        return True
                    else:
                        logger.error(
                            "Slack notification failed",
                            webhook_url=webhook_url,
                            alert_name=alert.name,
                            status_code=response.status,
                            response_text=await response.text()
                        )
                        return False
            
        except Exception as e:
            logger.error("Failed to send Slack notification", error=str(e))
            return False


class WebhookNotificationSender(NotificationSender):
    """Webhook notification sender."""
    
    async def send(self, alert: Alert, config: Dict[str, Any]) -> bool:
        """Send notification via webhook."""
        try:
            import aiohttp
            
            webhook_url = config.get("url")
            if not webhook_url:
                logger.error("Webhook URL not configured")
                return False
            
            payload = {
                "alert": alert.to_dict(),
                "timestamp": datetime.utcnow().isoformat(),
                "source": "ats-backend"
            }
            
            headers = config.get("headers", {})
            headers.setdefault("Content-Type", "application/json")
            
            timeout = aiohttp.ClientTimeout(total=10)
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(webhook_url, json=payload, headers=headers) as response:
                    if response.status == 200:
                        logger.info(
                            "Webhook notification sent successfully",
                            webhook_url=webhook_url,
                            alert_name=alert.name,
                            status_code=response.status
                        )
                        return True
                    else:
                        logger.error(
                            "Webhook notification failed",
                            webhook_url=webhook_url,
                            alert_name=alert.name,
                            status_code=response.status,
                            response_text=await response.text()
                        )
                        return False
            
        except Exception as e:
            logger.error("Failed to send webhook notification", error=str(e))
            return False


class AlertManager:
    """Manages alert rules and notifications."""
    
    def __init__(self):
        self.logger = structlog.get_logger("alert_manager")
        
        # Notification senders
        self._senders = {
            NotificationChannel.LOG: LogNotificationSender(),
            NotificationChannel.EMAIL: EmailNotificationSender(),
            NotificationChannel.SLACK: SlackNotificationSender(),
            NotificationChannel.WEBHOOK: WebhookNotificationSender()
        }
        
        # Alert rules
        self._alert_rules: Dict[str, AlertRule] = {}
        
        # Notification configurations
        self._notification_configs: Dict[NotificationChannel, NotificationConfig] = {}
        
        # Initialize default alert rules
        self._initialize_default_rules()
        
        # Initialize default notification configs
        self._initialize_default_notifications()
    
    def _initialize_default_rules(self):
        """Initialize default alert rules."""
        default_rules = [
            AlertRule(
                name="high_resume_parse_time",
                condition="resume_parse_time_p95 > 5000ms",
                threshold=5000.0,
                severity=AlertSeverity.WARNING,
                notification_channels=[NotificationChannel.LOG, NotificationChannel.EMAIL]
            ),
            AlertRule(
                name="high_ocr_fallback_rate",
                condition="ocr_fallback_rate > 30%",
                threshold=0.3,
                severity=AlertSeverity.WARNING,
                notification_channels=[NotificationChannel.LOG, NotificationChannel.SLACK]
            ),
            AlertRule(
                name="high_queue_depth",
                condition="queue_depth > 100",
                threshold=100.0,
                severity=AlertSeverity.WARNING,
                notification_channels=[NotificationChannel.LOG, NotificationChannel.EMAIL]
            ),
            AlertRule(
                name="critical_queue_depth",
                condition="queue_depth > 500",
                threshold=500.0,
                severity=AlertSeverity.CRITICAL,
                notification_channels=[NotificationChannel.LOG, NotificationChannel.EMAIL, NotificationChannel.SLACK]
            ),
            AlertRule(
                name="high_error_rate",
                condition="error_rate > 5%",
                threshold=0.05,
                severity=AlertSeverity.CRITICAL,
                notification_channels=[NotificationChannel.LOG, NotificationChannel.EMAIL, NotificationChannel.SLACK]
            ),
            AlertRule(
                name="no_workers_available",
                condition="worker_count < 1",
                threshold=1.0,
                severity=AlertSeverity.CRITICAL,
                notification_channels=[NotificationChannel.LOG, NotificationChannel.EMAIL, NotificationChannel.SLACK]
            ),
            AlertRule(
                name="high_cpu_usage",
                condition="cpu_usage > 90%",
                threshold=90.0,
                severity=AlertSeverity.WARNING,
                notification_channels=[NotificationChannel.LOG]
            ),
            AlertRule(
                name="high_memory_usage",
                condition="memory_usage > 90%",
                threshold=90.0,
                severity=AlertSeverity.WARNING,
                notification_channels=[NotificationChannel.LOG]
            ),
            AlertRule(
                name="high_cost",
                condition="cost_per_hour > $10",
                threshold=10.0,
                severity=AlertSeverity.WARNING,
                notification_channels=[NotificationChannel.LOG, NotificationChannel.EMAIL]
            )
        ]
        
        for rule in default_rules:
            self._alert_rules[rule.name] = rule
    
    def _initialize_default_notifications(self):
        """Initialize default notification configurations."""
        self._notification_configs = {
            NotificationChannel.LOG: NotificationConfig(
                channel=NotificationChannel.LOG,
                enabled=True
            ),
            NotificationChannel.EMAIL: NotificationConfig(
                channel=NotificationChannel.EMAIL,
                enabled=getattr(settings, 'alerts_email_enabled', False),
                config={
                    "recipients": getattr(settings, 'alerts_email_recipients', []),
                    "smtp_host": getattr(settings, 'smtp_host', ''),
                    "smtp_port": getattr(settings, 'smtp_port', 587)
                }
            ),
            NotificationChannel.SLACK: NotificationConfig(
                channel=NotificationChannel.SLACK,
                enabled=getattr(settings, 'alerts_slack_enabled', False),
                config={
                    "webhook_url": getattr(settings, 'alerts_slack_webhook_url', ''),
                    "channel": getattr(settings, 'alerts_slack_channel', '#alerts')
                }
            ),
            NotificationChannel.WEBHOOK: NotificationConfig(
                channel=NotificationChannel.WEBHOOK,
                enabled=getattr(settings, 'alerts_webhook_enabled', False),
                config={
                    "url": getattr(settings, 'alerts_webhook_url', ''),
                    "headers": getattr(settings, 'alerts_webhook_headers', {})
                }
            )
        }
    
    async def process_alert(self, alert: Alert) -> bool:
        """Process an alert and send notifications."""
        try:
            # Find matching alert rule
            rule = self._alert_rules.get(alert.name)
            if not rule or not rule.enabled:
                self.logger.debug("Alert rule not found or disabled", alert_name=alert.name)
                return False
            
            # Check cooldown period
            if rule.last_triggered:
                cooldown_period = timedelta(minutes=rule.cooldown_minutes)
                if datetime.utcnow() - rule.last_triggered < cooldown_period:
                    self.logger.debug(
                        "Alert in cooldown period",
                        alert_name=alert.name,
                        cooldown_minutes=rule.cooldown_minutes
                    )
                    return False
            
            # Send notifications
            notification_results = []
            for channel in rule.notification_channels:
                config = self._notification_configs.get(channel)
                if not config or not config.enabled:
                    self.logger.debug("Notification channel not configured or disabled", channel=channel.value)
                    continue
                
                sender = self._senders.get(channel)
                if not sender:
                    self.logger.error("No sender available for channel", channel=channel.value)
                    continue
                
                try:
                    result = await sender.send(alert, config.config)
                    notification_results.append(result)
                    
                    self.logger.info(
                        "Notification sent",
                        alert_name=alert.name,
                        channel=channel.value,
                        success=result
                    )
                    
                except Exception as e:
                    self.logger.error(
                        "Failed to send notification",
                        alert_name=alert.name,
                        channel=channel.value,
                        error=str(e)
                    )
                    notification_results.append(False)
            
            # Update rule last triggered time
            rule.last_triggered = datetime.utcnow()
            
            success = any(notification_results) if notification_results else False
            
            self.logger.info(
                "Alert processed",
                alert_name=alert.name,
                severity=alert.severity.value,
                notifications_sent=sum(notification_results),
                total_channels=len(rule.notification_channels),
                success=success
            )
            
            return success
            
        except Exception as e:
            self.logger.error("Failed to process alert", alert_name=alert.name, error=str(e))
            return False
    
    def add_alert_rule(self, rule: AlertRule) -> None:
        """Add or update an alert rule."""
        self._alert_rules[rule.name] = rule
        self.logger.info("Alert rule added/updated", rule_name=rule.name)
    
    def remove_alert_rule(self, rule_name: str) -> bool:
        """Remove an alert rule."""
        if rule_name in self._alert_rules:
            del self._alert_rules[rule_name]
            self.logger.info("Alert rule removed", rule_name=rule_name)
            return True
        return False
    
    def get_alert_rules(self) -> Dict[str, AlertRule]:
        """Get all alert rules."""
        return self._alert_rules.copy()
    
    def update_notification_config(self, channel: NotificationChannel, config: NotificationConfig) -> None:
        """Update notification configuration."""
        self._notification_configs[channel] = config
        self.logger.info("Notification config updated", channel=channel.value)
    
    def get_notification_configs(self) -> Dict[NotificationChannel, NotificationConfig]:
        """Get all notification configurations."""
        return self._notification_configs.copy()
    
    def enable_alert_rule(self, rule_name: str) -> bool:
        """Enable an alert rule."""
        if rule_name in self._alert_rules:
            self._alert_rules[rule_name].enabled = True
            self.logger.info("Alert rule enabled", rule_name=rule_name)
            return True
        return False
    
    def disable_alert_rule(self, rule_name: str) -> bool:
        """Disable an alert rule."""
        if rule_name in self._alert_rules:
            self._alert_rules[rule_name].enabled = False
            self.logger.info("Alert rule disabled", rule_name=rule_name)
            return True
        return False
    
    def test_notification_channel(self, channel: NotificationChannel) -> bool:
        """Test a notification channel."""
        try:
            test_alert = Alert(
                name="test_alert",
                condition="test condition",
                severity=AlertSeverity.INFO,
                threshold=0.0,
                current_value=1.0,
                triggered_at=datetime.utcnow(),
                message="This is a test alert to verify notification configuration"
            )
            
            config = self._notification_configs.get(channel)
            if not config:
                self.logger.error("Notification config not found", channel=channel.value)
                return False
            
            sender = self._senders.get(channel)
            if not sender:
                self.logger.error("Notification sender not found", channel=channel.value)
                return False
            
            # Run async test
            loop = asyncio.get_event_loop()
            result = loop.run_until_complete(sender.send(test_alert, config.config))
            
            self.logger.info(
                "Notification channel test completed",
                channel=channel.value,
                success=result
            )
            
            return result
            
        except Exception as e:
            self.logger.error("Failed to test notification channel", channel=channel.value, error=str(e))
            return False


# Global alert manager instance
alert_manager = AlertManager()