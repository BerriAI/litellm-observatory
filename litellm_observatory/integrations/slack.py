"""Slack webhook integration for sending notifications."""

import os
from typing import Any, Dict, Optional

import httpx


class SlackWebhook:
    """Slack webhook client for sending messages."""

    def __init__(self, webhook_url: Optional[str] = None):
        """
        Initialize Slack webhook client.

        Args:
            webhook_url: Slack webhook URL. If not provided, reads from SLACK_WEBHOOK_URL env var.
        """
        self.webhook_url = webhook_url or os.getenv("SLACK_WEBHOOK_URL")

    def send_message(
        self,
        text: str,
        blocks: Optional[list] = None,
        username: Optional[str] = None,
        icon_emoji: Optional[str] = None,
    ) -> bool:
        """
        Send a message to Slack via webhook.

        Args:
            text: Message text (fallback if blocks are provided)
            blocks: Optional Slack block kit blocks for rich formatting
            username: Optional bot username
            icon_emoji: Optional bot icon emoji (e.g., ":robot_face:")

        Returns:
            True if message was sent successfully, False otherwise
        """
        if not self.webhook_url:
            return False

        payload: Dict[str, Any] = {"text": text}

        if blocks:
            payload["blocks"] = blocks
        if username:
            payload["username"] = username
        if icon_emoji:
            payload["icon_emoji"] = icon_emoji

        try:
            response = httpx.post(self.webhook_url, json=payload, timeout=10.0)
            response.raise_for_status()
            return True
        except Exception:
            return False

    def send_test_result_notification(
        self,
        test_name: str,
        deployment_url: str,
        test_passed: bool,
        failure_rate: float,
        total_requests: int,
        duration_hours: float,
        error_message: Optional[str] = None,
    ) -> bool:
        """
        Send a formatted test result notification to Slack.

        Args:
            test_name: Name of the test that was run
            deployment_url: URL of the deployment that was tested
            test_passed: Whether the test passed
            failure_rate: Overall failure rate (0.0 to 1.0)
            total_requests: Total number of requests made
            duration_hours: Test duration in hours
            error_message: Optional error message if test failed

        Returns:
            True if notification was sent successfully, False otherwise
        """
        status_emoji = "✅" if test_passed else "❌"
        status_text = "PASSED" if test_passed else "FAILED"
        failure_rate_percent = failure_rate * 100

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{status_emoji} {test_name} - {status_text}",
                },
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Deployment:*\n{deployment_url}"},
                    {
                        "type": "mrkdwn",
                        "text": f"*Duration:*\n{duration_hours:.2f} hours",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Total Requests:*\n{total_requests:,}",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Failure Rate:*\n{failure_rate_percent:.2f}%",
                    },
                ],
            },
        ]

        if not test_passed and error_message:
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Error:*\n```{error_message}```",
                    },
                }
            )

        text = (
            f"{status_emoji} {test_name} - {status_text}\n"
            f"Deployment: {deployment_url}\n"
            f"Duration: {duration_hours:.2f} hours\n"
            f"Total Requests: {total_requests:,}\n"
            f"Failure Rate: {failure_rate_percent:.2f}%"
        )
        if not test_passed and error_message:
            text += f"\n\nError: {error_message}"

        return self.send_message(
            text=text,
            blocks=blocks,
            username="LiteLLM Observatory",
            icon_emoji=":test_tube:",
        )
