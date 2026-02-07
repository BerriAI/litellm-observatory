"""Tests for server Slack integration."""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from litellm_observatory.server import app


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


def test_run_test_slack_integration(client):
    """Test that /run-test endpoint works with Slack integration."""
    # Setup test suite mock
    mock_results = {
        "test_name": "OpenAI/Azure Release Test",
        "test_passed": True,
        "overall_failure_rate": 0.005,
        "total_requests": 1000,
        "duration_hours": 3.0,
    }
    mock_instance = MagicMock()
    mock_instance.run = AsyncMock(return_value=mock_results)
    mock_test_class = MagicMock(return_value=mock_instance)

    # Setup Slack webhook mock
    with patch("litellm_observatory.server.slack_webhook") as mock_slack:
        mock_slack.webhook_url = "https://hooks.slack.com/services/test"
        send_notification_mock = MagicMock(return_value=True)
        mock_slack.send_test_result_notification = send_notification_mock

        # Patch the test suite registry in the server module where it's used
        with patch("litellm_observatory.server.TEST_SUITE_REGISTRY", {"TestOAIAzureRelease": mock_test_class}):
            # Make request
            request_data = {
                "deployment_url": "https://test-deployment.com",
                "api_key": "sk-test-key",
                "test_suite": "TestOAIAzureRelease",
                "models": ["gpt-4"],
            }

            # Mock authentication - patch get_api_key_from_env to return None (skips auth)
            with patch("litellm_observatory.auth.get_api_key_from_env", return_value=None):
                response = client.post("/run-test", json=request_data)

                # Verify immediate response
                assert response.status_code == 200
                data = response.json()
                # Status can be "queued" or "started" depending on queue state
                assert data["status"] in ["queued", "started"]
                assert "Test" in data["results"]["message"] and "Slack webhook" in data["results"]["message"]
                assert data["results"]["deployment_url"] == "https://test-deployment.com"
                assert data["results"]["models"] == ["gpt-4"]
                assert "request_id" in data["results"]

            # Wait for background task to complete
            # The mocked test suite should return immediately, but we need to give the async task time
            max_wait = 2.0
            waited = 0.0
            while not send_notification_mock.called and waited < max_wait:
                time.sleep(0.1)
                waited += 0.1

            # Verify Slack webhook was called with correct parameters
            assert send_notification_mock.called, "Slack webhook should have been called"
            send_notification_mock.assert_called_once_with(
                test_name="OpenAI/Azure Release Test",
                deployment_url="https://test-deployment.com",
                test_passed=True,
                failure_rate=0.005,
                total_requests=1000,
                duration_hours=3.0,
                error_message=None,
            )
