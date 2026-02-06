"""Mock test suite that makes a single real HTTP request to validate deployment connectivity."""

from datetime import datetime
from typing import Any, Dict, List

import httpx

from litellm_observatory.test_suites.base import BaseTestSuite

# HTTP request constants
HTTP_REQUEST_TIMEOUT_SECONDS = 60.0
HTTP_SUCCESS_STATUS_CODE = 200

# Chat completion request constants
DEFAULT_MAX_TOKENS = 50
DEFAULT_TEST_MESSAGE = "Hello! This is a connectivity test."


class TestMockSingleRequest(BaseTestSuite):
    """
    Mock test suite that makes a single real HTTP request to validate deployment.

    This test suite makes one actual request to the deployment to verify:
    - Deployment is reachable
    - API key is valid
    - Endpoint responds correctly
    - Quick validation without long test duration
    """

    def __init__(
        self,
        deployment_url: str,
        api_key: str,
        models: List[str],
    ):
        """
        Initialize the single request mock test suite.

        Args:
            deployment_url: The base URL of the LiteLLM deployment
            api_key: API key for authentication
            models: List of model names to test (uses first model for the single request)
        """
        super().__init__(deployment_url, api_key)
        self.models = models

    async def run(self, **params: Any) -> Dict[str, Any]:
        """
        Run the single request test.

        Returns:
            Dictionary containing test results
        """
        start_time = datetime.now()
        model_to_test = self.models[0] if self.models else "gpt-4"

        url = self.get_endpoint_url("/v1/chat/completions")
        headers = self.get_headers()

        payload = {
            "model": model_to_test,
            "messages": [
                {"role": "user", "content": DEFAULT_TEST_MESSAGE}
            ],
            "max_tokens": DEFAULT_MAX_TOKENS,
        }

        success = False
        status_code = None
        error = None
        request_duration = 0.0

        try:
            request_start = datetime.now()
            async with httpx.AsyncClient(timeout=HTTP_REQUEST_TIMEOUT_SECONDS) as client:
                response = await client.post(url, json=payload, headers=headers)
                request_duration = (datetime.now() - request_start).total_seconds()
                status_code = response.status_code

                if response.status_code == HTTP_SUCCESS_STATUS_CODE:
                    try:
                        response_data = response.json()
                        success = True
                    except Exception as e:
                        error = f"Failed to parse response: {str(e)}"
                        success = False
                else:
                    try:
                        error_data = response.json()
                        error = error_data
                    except Exception:
                        error = response.text
        except Exception as e:
            request_duration = (datetime.now() - request_start).total_seconds() if 'request_start' in locals() else 0.0
            error = str(e)
            success = False

        end_time = datetime.now()
        duration_seconds = (end_time - start_time).total_seconds()

        test_passed = success

        model_stats = {}
        if self.models:
            for model in self.models:
                if model == model_to_test:
                    model_stats[model] = {
                        "total_requests": 1,
                        "successes": 1 if success else 0,
                        "failures": 0 if success else 1,
                        "failure_rate": 0.0 if success else 1.0,
                        "failure_rate_percent": 0.0 if success else 100.0,
                        "avg_duration_seconds": request_duration,
                    }
                else:
                    model_stats[model] = {
                        "total_requests": 0,
                        "successes": 0,
                        "failures": 0,
                        "failure_rate": 0.0,
                        "failure_rate_percent": 0.0,
                        "avg_duration_seconds": 0.0,
                    }

        return {
            "test_name": "Mock Single Request Test",
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_seconds": duration_seconds,
            "duration_hours": duration_seconds / 3600,
            "models_tested": self.models,
            "total_requests": 1,
            "total_successes": 1 if success else 0,
            "total_failures": 0 if success else 1,
            "overall_failure_rate": 0.0 if success else 1.0,
            "overall_failure_rate_percent": 0.0 if success else 100.0,
            "max_failure_rate": 0.01,
            "max_failure_rate_percent": 1.0,
            "test_passed": test_passed,
            "model_statistics": model_stats,
            "detailed_results": {
                model_to_test: [
                    {
                        "timestamp": start_time.isoformat(),
                        "model": model_to_test,
                        "status_code": status_code,
                        "success": success,
                        "duration_seconds": request_duration,
                        "error": error,
                    }
                ]
            },
        }
