"""Mock test suite for testing the orchestrator without running actual tests."""

import asyncio
from typing import Any, Dict, List

from litellm_observatory.test_suites.base import BaseTestSuite


class TestMock(BaseTestSuite):
    """
    Mock test suite for testing the orchestrator.

    This test suite simulates test execution without making actual HTTP requests.
    Useful for testing the orchestrator infrastructure without waiting for long-running tests.
    """

    def __init__(
        self,
        deployment_url: str,
        api_key: str,
        models: List[str],
        duration_seconds: float = 1.0,
        should_pass: bool = True,
        failure_rate: float = 0.0,
        total_requests: int = 10,
    ):
        """
        Initialize the mock test suite.

        Args:
            deployment_url: The base URL of the LiteLLM deployment (not used, but required)
            api_key: API key for authentication (not used, but required)
            models: List of model names to test (not used, but required)
            duration_seconds: How long to simulate the test (default: 1.0 seconds)
            should_pass: Whether the test should pass (default: True)
            failure_rate: Simulated failure rate (default: 0.0)
            total_requests: Number of simulated requests (default: 10)
        """
        super().__init__(deployment_url, api_key)
        self.models = models
        self.duration_seconds = duration_seconds
        self.should_pass = should_pass
        self.failure_rate = failure_rate
        self.total_requests = total_requests

    async def run(self, **params: Any) -> Dict[str, Any]:
        """
        Run the mock test suite.

        Returns:
            Dictionary containing simulated test results
        """
        # Simulate test duration
        await asyncio.sleep(self.duration_seconds)

        # Calculate simulated results
        total_failures = int(self.total_requests * self.failure_rate)
        total_successes = self.total_requests - total_failures

        model_stats = {}
        requests_per_model = self.total_requests // len(self.models) if self.models else 0
        remaining_requests = self.total_requests % len(self.models) if self.models else 0

        for i, model in enumerate(self.models):
            model_requests = requests_per_model + (1 if i < remaining_requests else 0)
            model_failures = int(model_requests * self.failure_rate)
            model_successes = model_requests - model_failures

            model_stats[model] = {
                "total_requests": model_requests,
                "successes": model_successes,
                "failures": model_failures,
                "failure_rate": self.failure_rate,
                "failure_rate_percent": self.failure_rate * 100,
                "avg_duration_seconds": 0.1,
            }

        test_passed = self.should_pass and (self.failure_rate < 0.01)

        return {
            "test_name": "Mock Test",
            "start_time": "2024-01-01T00:00:00",
            "end_time": "2024-01-01T00:00:01",
            "duration_seconds": self.duration_seconds,
            "duration_hours": self.duration_seconds / 3600,
            "models_tested": self.models,
            "total_requests": self.total_requests,
            "total_successes": total_successes,
            "total_failures": total_failures,
            "overall_failure_rate": self.failure_rate,
            "overall_failure_rate_percent": self.failure_rate * 100,
            "max_failure_rate": 0.01,
            "max_failure_rate_percent": 1.0,
            "test_passed": test_passed,
            "model_statistics": model_stats,
            "detailed_results": {},
        }
