"""
alerts/email_alert.py — Sends free email notifications via SMTP.
"""

import smtplib
import logging
from email.message import EmailMessage
from config import EMAIL_ALERTS_ENABLED, EMAIL_SENDER, EMAIL_PASSWORD, EMAIL_RECIPIENT

logger = logging.getLogger(__name__)

class EmailAlertSystem:
    def __init__(self):
        self.enabled = EMAIL_ALERTS_ENABLED
        self.sender = EMAIL_SENDER
        self.password = EMAIL_PASSWORD
        self.recipient = EMAIL_RECIPIENT

        import time
        self._last_alert_time: float = 0.0
        self._cooldown_seconds: float = 10.0  # 10 seconds

        if self.enabled:
            if not self.sender or not self.password or not self.recipient:
                logger.error("Email alerts enabled but missing credentials in .env! Disabling emails.")
                self.enabled = False
            else:
                logger.info(f"Email alerts initialized. Recipient: {self.recipient}")

    def send_alert(self, risk_level: str, event_type: str, vlm_description: str, recommended_action: str):
        """Send an email alert for a detected anomaly."""
        if not self.enabled:
            return

        import time
        now = time.time()
        if now - self._last_alert_time < self._cooldown_seconds:
            logger.debug(f"Email alert suppressed (cooldown): {event_type}")
            return
        
        self._last_alert_time = now

        try:
            msg = EmailMessage()
            msg['Subject'] = f"[SurveillanceAI] {risk_level.upper()} ALERT: {event_type}"
            msg['From'] = self.sender
            msg['To'] = self.recipient

            body = f"""
SurveillanceAI has detected a {risk_level.upper()} risk event.

Event Type: {event_type}

VLM Scene Analysis:
{vlm_description}

Recommended Action:
{recommended_action}

Please check the Live Monitor immediately.
"""
            msg.set_content(body)

            # Connect to Gmail SMTP server
            with smtplib.SMTP('smtp.gmail.com', 587) as smtp:
                smtp.ehlo()
                smtp.starttls()
                smtp.login(self.sender, self.password)
                smtp.send_message(msg)

            logger.info(f"Sent email alert for {event_type}")

        except Exception as e:
            logger.error(f"Failed to send email alert: {e}")

# Global instance
email_alert = EmailAlertSystem()
