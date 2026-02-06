"""
OpenAI/Azure release test suite - validates provider reliability on new releases.

This test is specifically designed to catch the HTTP client lifecycle regression that occurred
in LiteLLM v1.81.3 (PR #19190). The regression caused OpenAI/Azure providers to fail after
approximately 1 hour of operation.

Regression Details:
-------------------
Issue: HTTP client memory leak fix introduced a regression where httpx clients are shared
       between AsyncOpenAI/AsyncAzureOpenAI clients with a 1-hour TTL cache.

Root Cause:
- AsyncHTTPHandler manages httpx clients with a 1-hour TTL in the in-memory cache
- When the handler expires and gets garbage collected, its __del__ method closes the httpx client
- However, the AsyncOpenAI client is still alive and references the now-closed httpx client
- Next request → RuntimeError: "Cannot send a request, as the client has been closed"

Symptoms:
- Periodic failures starting around 1 hour into operation
- Only affects OpenAI-compatible providers (OpenAI, Azure, on-prem)
- Error: APIConnectionError: "Cannot send a request, as the client has been closed"
- Immediate recovery after rollback to versions before PR #19190

Why 3 Hours:
------------
The test runs for 3 hours to ensure we catch the 1-hour TTL expiration cycle. This allows
the test to:
1. Verify the regression occurs after ~1 hour (if present)
2. Confirm the fix works for multiple TTL cycles (if fixed)
3. Ensure long-running deployments remain stable

Expected Behavior:
------------------
- PASS: Failure rate stays under 1% for the entire 3-hour duration
- FAIL: Failure rate spikes after ~1 hour with APIConnectionError exceptions
"""

import asyncio
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import httpx

from litellm_observatory.test_suites.base import BaseTestSuite

# Test configuration constants
DEFAULT_DURATION_HOURS = 3.0
DEFAULT_MAX_FAILURE_RATE = 0.01  # 1%
DEFAULT_REQUEST_INTERVAL_SECONDS = 1.0

# HTTP request constants
HTTP_REQUEST_TIMEOUT_SECONDS = 60.0
HTTP_SUCCESS_STATUS_CODE = 200

# Chat completion request constants
DEFAULT_MAX_TOKENS = 50
DEFAULT_TEST_MESSAGE = "Hello! This is a OpenAI/Azure release test."

# Progress reporting constants
PROGRESS_REPORT_INTERVAL = 10  # Report progress every N requests

# Test metadata constants
TEST_NAME = "OpenAI/Azure Release Test"


class TestOAIAzureRelease(BaseTestSuite):
    """
    OpenAI/Azure release reliability test.

    Designed to be triggered on every new release to validate OpenAI and Azure providers.
    Runs for 3 hours and ensures failure rate stays under 1%.

    This test specifically catches the HTTP client lifecycle regression (PR #19190) where
    httpx clients expire after 1 hour, causing "Cannot send a request, as the client has been
    closed" errors. The 3-hour duration ensures we catch multiple TTL expiration cycles.

    See module docstring for detailed regression information.
    """

    def __init__(
        self,
        deployment_url: str,
        api_key: str,
        models: List[str],
        duration_hours: float = DEFAULT_DURATION_HOURS,
        max_failure_rate: float = DEFAULT_MAX_FAILURE_RATE,
        request_interval_seconds: float = DEFAULT_REQUEST_INTERVAL_SECONDS,
    ):
        """
        Initialize the OpenAI/Azure release test.

        Args:
            deployment_url: The base URL of the LiteLLM deployment
            api_key: API key for authentication
            models: List of OpenAI/Azure model names to test (e.g., ["gpt-4", "gpt-3.5-turbo"])
            duration_hours: How long to run the test (default: 3.0 hours)
            max_failure_rate: Maximum acceptable failure rate (default: 0.01 = 1%)
            request_interval_seconds: Time between requests (in seconds)
        """
        super().__init__(deployment_url, api_key)
        self.models = models
        self.duration_hours = duration_hours
        self.max_failure_rate = max_failure_rate
        self.request_interval_seconds = request_interval_seconds

        self.results: Dict[str, List[Dict[str, Any]]] = {model: [] for model in models}
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None

    async def _make_request(self, model: str) -> Dict[str, Any]:
        """
        Make a single chat completion request.

        Args:
            model: Model name to test

        Returns:
            Dictionary with request result
        """
        url = self.get_endpoint_url("/v1/chat/completions")
        headers = self.get_headers()

        payload = {
            "model": model,
            "messages": [
                {"role": "user", "content": DEFAULT_TEST_MESSAGE}
            ],
            "max_tokens": DEFAULT_MAX_TOKENS,
        }

        request_start = time.time()
        try:
            async with httpx.AsyncClient(timeout=HTTP_REQUEST_TIMEOUT_SECONDS) as client:
                response = await client.post(url, json=payload, headers=headers)
                request_duration = time.time() - request_start

                result = {
                    "timestamp": datetime.now().isoformat(),
                    "model": model,
                    "status_code": response.status_code,
                    "success": response.status_code == HTTP_SUCCESS_STATUS_CODE,
                    "duration_seconds": request_duration,
                    "error": None,
                }

                if response.status_code == HTTP_SUCCESS_STATUS_CODE:
                    try:
                        response_data = response.json()
                        result["response_data"] = response_data
                    except Exception as e:
                        result["error"] = f"Failed to parse response: {str(e)}"
                        result["success"] = False
                else:
                    try:
                        error_data = response.json()
                        result["error"] = error_data
                    except Exception:
                        result["error"] = response.text

                return result

        except Exception as e:
            request_duration = time.time() - request_start
            return {
                "timestamp": datetime.now().isoformat(),
                "model": model,
                "status_code": None,
                "success": False,
                "duration_seconds": request_duration,
                "error": str(e),
            }

    async def run(self, **params: Any) -> Dict[str, Any]:
        """
        Run the reliability test for the specified duration.

        Returns:
            Dictionary containing test results and statistics
        """
        self.start_time = datetime.now()
        end_time = self.start_time + timedelta(hours=self.duration_hours)

        print(
            f"Starting OpenAI/Azure release test for {self.duration_hours} hours"
            f" on models: {', '.join(self.models)}"
        )
        print(f"Test will run until: {end_time.isoformat()}")
        print(f"Maximum acceptable failure rate: {self.max_failure_rate * 100}%")

        model_index = 0
        while datetime.now() < end_time:
            model = self.models[model_index % len(self.models)]
            model_index += 1

            result = await self._make_request(model)
            self.results[model].append(result)

            if len(self.results[model]) % PROGRESS_REPORT_INTERVAL == 0:
                elapsed = (datetime.now() - self.start_time).total_seconds() / 3600
                total_requests = sum(len(results) for results in self.results.values())
                print(
                    f"[{elapsed:.2f}h elapsed] Total requests: {total_requests}, "
                    f"Current model: {model}"
                )

            await asyncio.sleep(self.request_interval_seconds)

        self.end_time = datetime.now()

        return self._calculate_results()

    def _calculate_results(self) -> Dict[str, Any]:
        """
        Calculate test statistics and results.

        Returns:
            Dictionary with comprehensive test results
        """
        total_requests = 0
        total_successes = 0
        total_failures = 0

        model_stats = {}
        for model, results in self.results.items():
            successes = sum(1 for r in results if r["success"])
            failures = len(results) - successes
            total = len(results)

            total_requests += total
            total_successes += successes
            total_failures += failures

            failure_rate = failures / total if total > 0 else 0.0
            avg_duration = (
                sum(r["duration_seconds"] for r in results) / total if total > 0 else 0.0
            )

            model_stats[model] = {
                "total_requests": total,
                "successes": successes,
                "failures": failures,
                "failure_rate": failure_rate,
                "failure_rate_percent": failure_rate * 100,
                "avg_duration_seconds": avg_duration,
            }

        overall_failure_rate = (
            total_failures / total_requests if total_requests > 0 else 0.0
        )
        test_passed = overall_failure_rate < self.max_failure_rate

        duration_seconds = (
            (self.end_time - self.start_time).total_seconds()
            if self.end_time and self.start_time
            else 0
        )

        return {
            "test_name": TEST_NAME,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_seconds": duration_seconds,
            "duration_hours": duration_seconds / 3600,
            "models_tested": self.models,
            "total_requests": total_requests,
            "total_successes": total_successes,
            "total_failures": total_failures,
            "overall_failure_rate": overall_failure_rate,
            "overall_failure_rate_percent": overall_failure_rate * 100,
            "max_failure_rate": self.max_failure_rate,
            "max_failure_rate_percent": self.max_failure_rate * 100,
            "test_passed": test_passed,
            "model_statistics": model_stats,
            "detailed_results": self.results,
        }
