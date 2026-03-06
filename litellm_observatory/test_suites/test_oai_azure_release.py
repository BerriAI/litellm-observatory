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
import math
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

        # Track results per model
        self.results: Dict[str, List[Dict[str, Any]]] = {model: [] for model in models}
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
        
        # Reuse HTTP client across all requests to test client lifecycle behavior
        self.client: Optional[httpx.AsyncClient] = None

    # Test execution
    async def run(self, **params: Any) -> Dict[str, Any]:
        """
        Run the reliability test for the specified duration.

        Makes continuous requests to the deployment, cycling through models, until the
        duration is reached. Reuses a single HTTP client to test lifecycle behavior.

        Returns:
            Dictionary containing test results and statistics
        """
        self.start_time = datetime.now()
        end_time = self.start_time + timedelta(hours=self.duration_hours)

        self._print_test_start_info(end_time)

        model_index = 0
        while datetime.now() < end_time:
            model = self._get_next_model_to_test(model_index)
            model_index += 1

            result = await self._make_request(model)
            self.results[model].append(result)

            if self._should_report_progress(model):
                self._print_progress(model)

            await asyncio.sleep(self.request_interval_seconds)

        self.end_time = datetime.now()
        await self._cleanup_resources()

        return self._calculate_results()

    # Helper methods for making requests

    async def _make_request(self, model: str) -> Dict[str, Any]:
        """
        Make a single chat completion request to the deployment.

        Reuses the same HTTP client across all requests to properly test client lifecycle behavior.
        This is critical for catching the regression where clients expire after 1 hour.

        Args:
            model: Model name to test

        Returns:
            Dictionary with request result including success status, duration, and any errors
        """
        url = self.get_endpoint_url("/v1/chat/completions")
        headers = self.get_headers()
        payload = self._build_chat_completion_payload(model)

        request_start = time.time()
        try:
            self._ensure_http_client_exists()
            response = await self.client.post(url, json=payload, headers=headers)
            request_duration = time.time() - request_start

            if response.status_code == HTTP_SUCCESS_STATUS_CODE:
                return self._parse_successful_response(response, request_duration, model)
            else:
                return self._parse_error_response(response, request_duration, model)

        except Exception as e:
            request_duration = time.time() - request_start
            return self._create_error_result(e, request_duration, model)

    def _ensure_http_client_exists(self) -> None:
        """Create HTTP client if it doesn't exist. Reused across all requests."""
        if self.client is None:
            self.client = httpx.AsyncClient(timeout=HTTP_REQUEST_TIMEOUT_SECONDS)

    def _build_chat_completion_payload(self, model: str) -> Dict[str, Any]:
        """Build the chat completion request payload for the given model."""
        return {
            "model": model,
            "messages": [{"role": "user", "content": DEFAULT_TEST_MESSAGE}],
            "max_tokens": DEFAULT_MAX_TOKENS,
        }

    def _parse_successful_response(self, response: httpx.Response, request_duration: float, model: str) -> Dict[str, Any]:
        """Parse a successful HTTP response (status 200)."""
        result = {
            "timestamp": datetime.now().isoformat(),
            "model": model,
            "status_code": response.status_code,
            "success": True,
            "duration_seconds": request_duration,
            "error": None,
        }
        
        try:
            response_data = response.json()
            result["response_data"] = response_data
        except Exception as e:
            result["error"] = f"Failed to parse response: {str(e)}"
            result["success"] = False
        
        return result

    def _parse_error_response(self, response: httpx.Response, request_duration: float, model: str) -> Dict[str, Any]:
        """Parse an error HTTP response (non-200 status)."""
        result = {
            "timestamp": datetime.now().isoformat(),
            "model": model,
            "status_code": response.status_code,
            "success": False,
            "duration_seconds": request_duration,
            "error": None,
        }
        
        try:
            error_data = response.json()
            result["error"] = error_data
        except Exception:
            result["error"] = response.text
        
        return result

    def _create_error_result(self, exception: Exception, request_duration: float, model: str) -> Dict[str, Any]:
        """Create a result dictionary for a request that raised an exception."""
        return {
            "timestamp": datetime.now().isoformat(),
            "model": model,
            "status_code": None,
            "success": False,
            "duration_seconds": request_duration,
            "error": str(exception),
        }

    # Helper methods for test execution

    def _get_next_model_to_test(self, model_index: int) -> str:
        """Cycle through models in round-robin fashion."""
        return self.models[model_index % len(self.models)]

    def _should_report_progress(self, model: str) -> bool:
        """Check if we should print progress for this request."""
        return len(self.results[model]) % PROGRESS_REPORT_INTERVAL == 0

    def _print_progress(self, model: str) -> None:
        """Print progress information including elapsed time and total requests."""
        elapsed_hours = (datetime.now() - self.start_time).total_seconds() / 3600
        total_requests = sum(len(results) for results in self.results.values())
        print(
            f"[{elapsed_hours:.2f}h elapsed] Total requests: {total_requests}, "
            f"Current model: {model}"
        )

    def _print_test_start_info(self, end_time: datetime) -> None:
        """Print test configuration at the start of the test."""
        print(
            f"Starting OpenAI/Azure release test for {self.duration_hours} hours"
            f" on models: {', '.join(self.models)}"
        )
        print(f"Test will run until: {end_time.isoformat()}")
        print(f"Maximum acceptable failure rate: {self.max_failure_rate * 100}%")

    async def _cleanup_resources(self) -> None:
        """Close HTTP client to free resources."""
        if self.client:
            await self.client.aclose()

    # Helper methods for calculating statistics

    def _calculate_model_statistics(self, model: str, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate statistics for a single model."""
        successes = sum(1 for r in results if r["success"])
        failures = len(results) - successes
        total = len(results)

        failure_rate = failures / total if total > 0 else 0.0
        avg_duration = (
            sum(r["duration_seconds"] for r in results) / total if total > 0 else 0.0
        )

        stats = {
            "total_requests": total,
            "successes": successes,
            "failures": failures,
            "failure_rate": failure_rate,
            "failure_rate_percent": failure_rate * 100,
            "avg_duration_seconds": avg_duration,
        }

        durations = [r["duration_seconds"] for r in results if r.get("duration_seconds") is not None]
        if durations:
            stats["latency_percentiles"] = self._calculate_latency_percentiles(durations)

        return stats

    def _calculate_overall_statistics(self) -> tuple[int, int, int, float]:
        """Calculate overall test statistics across all models."""
        total_requests = 0
        total_successes = 0
        total_failures = 0

        for model, results in self.results.items():
            model_stats = self._calculate_model_statistics(model, results)
            total_requests += model_stats["total_requests"]
            total_successes += model_stats["successes"]
            total_failures += model_stats["failures"]

        overall_failure_rate = (
            total_failures / total_requests if total_requests > 0 else 0.0
        )

        return total_requests, total_successes, total_failures, overall_failure_rate

    def _calculate_test_duration(self) -> float:
        """Calculate total test duration in seconds."""
        if self.end_time and self.start_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0.0

    def _calculate_latency_percentiles(self, durations: List[float]) -> Dict[str, float]:
        """
        Compute p50, p95, p99, and max latency from a list of durations.

        Uses sorted-index percentile calculation (no external dependencies).
        """
        if not durations:
            return {"p50": 0.0, "p95": 0.0, "p99": 0.0, "max": 0.0}

        sorted_d = sorted(durations)
        n = len(sorted_d)

        def _percentile(p: float) -> float:
            idx = (p / 100.0) * (n - 1)
            lower = int(math.floor(idx))
            upper = min(lower + 1, n - 1)
            frac = idx - lower
            return sorted_d[lower] + frac * (sorted_d[upper] - sorted_d[lower])

        return {
            "p50": round(_percentile(50), 4),
            "p95": round(_percentile(95), 4),
            "p99": round(_percentile(99), 4),
            "max": round(sorted_d[-1], 4),
        }

    def _calculate_latency_over_time(self) -> List[Dict[str, Any]]:
        """
        Bucket all requests into 10-minute windows and compute per-bucket stats.

        Returns a list of dicts with: window_start, avg_latency, p95_latency,
        request_count, failure_count.
        """
        all_results: List[Dict[str, Any]] = []
        for model_results in self.results.values():
            all_results.extend(model_results)

        if not all_results or not self.start_time:
            return []

        bucket_seconds = 600  # 10 minutes
        buckets: Dict[int, List[Dict[str, Any]]] = {}

        for r in all_results:
            try:
                ts = datetime.fromisoformat(r["timestamp"])
            except (KeyError, ValueError):
                continue
            offset = (ts - self.start_time).total_seconds()
            bucket_idx = int(offset // bucket_seconds)
            buckets.setdefault(bucket_idx, []).append(r)

        result = []
        for idx in sorted(buckets.keys()):
            items = buckets[idx]
            durations = [r["duration_seconds"] for r in items if r.get("duration_seconds") is not None]
            failures = sum(1 for r in items if not r.get("success", True))
            avg_lat = sum(durations) / len(durations) if durations else 0.0
            p95_lat = self._calculate_latency_percentiles(durations).get("p95", 0.0) if durations else 0.0
            window_start = self.start_time + timedelta(seconds=idx * bucket_seconds)

            result.append({
                "window_start": window_start.isoformat(),
                "avg_latency": round(avg_lat, 4),
                "p95_latency": round(p95_lat, 4),
                "request_count": len(items),
                "failure_count": failures,
            })

        return result

    def _categorize_errors(self) -> Dict[str, int]:
        """
        Classify failures into categories based on error string / status code.

        Categories: timeout, connection_refused, client_closed, 4xx, 5xx, other.
        """
        categories: Dict[str, int] = {}

        for model_results in self.results.values():
            for r in model_results:
                if r.get("success", True):
                    continue

                error_str = str(r.get("error", "")).lower()
                status_code = r.get("status_code")

                if "timeout" in error_str or "timed out" in error_str:
                    cat = "timeout"
                elif "connection refused" in error_str or "connect call failed" in error_str:
                    cat = "connection_refused"
                elif "client has been closed" in error_str or "client closed" in error_str:
                    cat = "client_closed"
                elif isinstance(status_code, int) and 400 <= status_code < 500:
                    cat = "4xx"
                elif isinstance(status_code, int) and 500 <= status_code < 600:
                    cat = "5xx"
                else:
                    cat = "other"

                categories[cat] = categories.get(cat, 0) + 1

        return categories

    def _calculate_first_failure_timing(self) -> Optional[Dict[str, Any]]:
        """
        Find the earliest failure across all models.

        Returns dict with timestamp, minutes_after_start, model, error_snippet
        or None if no failures occurred.
        """
        earliest: Optional[Dict[str, Any]] = None
        earliest_ts: Optional[datetime] = None

        for model, model_results in self.results.items():
            for r in model_results:
                if r.get("success", True):
                    continue
                try:
                    ts = datetime.fromisoformat(r["timestamp"])
                except (KeyError, ValueError):
                    continue

                if earliest_ts is None or ts < earliest_ts:
                    earliest_ts = ts
                    error_raw = str(r.get("error", ""))
                    earliest = {
                        "timestamp": r["timestamp"],
                        "minutes_after_start": round(
                            (ts - self.start_time).total_seconds() / 60, 2
                        ) if self.start_time else None,
                        "model": model,
                        "error_snippet": error_raw[:200],
                    }

        return earliest

    def _calculate_results(self) -> Dict[str, Any]:
        """
        Calculate comprehensive test statistics and results.

        Aggregates results across all models and determines if the test passed
        based on the overall failure rate.

        Returns:
            Dictionary with comprehensive test results including per-model and overall statistics
        """
        total_requests, total_successes, total_failures, overall_failure_rate = (
            self._calculate_overall_statistics()
        )

        model_stats = {
            model: self._calculate_model_statistics(model, results)
            for model, results in self.results.items()
        }

        test_passed = overall_failure_rate < self.max_failure_rate
        duration_seconds = self._calculate_test_duration()

        # Compute enhanced metrics
        all_durations = [
            r["duration_seconds"]
            for model_results in self.results.values()
            for r in model_results
            if r.get("duration_seconds") is not None
        ]
        latency_percentiles = self._calculate_latency_percentiles(all_durations)
        latency_over_time = self._calculate_latency_over_time()
        error_categories = self._categorize_errors()
        first_failure = self._calculate_first_failure_timing()

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
            "latency_percentiles": latency_percentiles,
            "latency_over_time": latency_over_time,
            "error_categories": error_categories,
            "first_failure": first_failure,
            "detailed_results": self.results,
        }
