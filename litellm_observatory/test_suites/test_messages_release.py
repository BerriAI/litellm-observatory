"""Messages release test suite - validates /v1/messages reliability on new releases.

This test is structurally similar to TestOAIAzureRelease but targets the /v1/messages
endpoint (OpenAI- and Vertex-style Messages API). It is provider-agnostic: the LiteLLM
deployment configuration decides which providers are exercised based on the models passed
in.
"""

from typing import Any, Dict, List

from litellm_observatory.test_suites.test_oai_azure_release import TestOAIAzureRelease


DEFAULT_TEST_MESSAGE = "Hello! This is a messages release test."
TEST_NAME = "Messages Release Test"
DEFAULT_MAX_TOKENS = 50


class TestMessagesRelease(TestOAIAzureRelease):
    """
    Messages endpoint reliability test.

    Runs continuous requests against /v1/messages for the configured duration, tracking
    success and failure rates across the provided models.
    """

    async def _make_request(self, model: str) -> Dict[str, Any]:
        """
        Make a single messages request to the deployment.

        Overrides the base implementation to hit /v1/messages and use messages-specific
        payloads while preserving the overall lifecycle and statistics logic.
        """
        import time
        from datetime import datetime

        import httpx

        from litellm_observatory.test_suites.test_oai_azure_release import (
            HTTP_REQUEST_TIMEOUT_SECONDS,
            HTTP_SUCCESS_STATUS_CODE,
        )

        url = self.get_endpoint_url("/v1/messages")
        headers = self.get_headers()
        payload: Dict[str, Any] = {
            "model": model,
            "max_tokens": DEFAULT_MAX_TOKENS,
            "messages": [{"role": "user", "content": DEFAULT_TEST_MESSAGE}],
        }

        request_start = time.time()
        try:
            self._ensure_http_client_exists()
            assert self.client is not None
            response = await self.client.post(url, json=payload, headers=headers)
            request_duration = time.time() - request_start

            if response.status_code == HTTP_SUCCESS_STATUS_CODE:
                result: Dict[str, Any] = {
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
                except Exception as e:  # noqa: BLE001
                    result["error"] = f"Failed to parse response: {str(e)}"
                    result["success"] = False
                return result

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

        except Exception as e:  # noqa: BLE001
            request_duration = time.time() - request_start
            return {
                "timestamp": datetime.now().isoformat(),
                "model": model,
                "status_code": None,
                "success": False,
                "duration_seconds": request_duration,
                "error": str(e),
            }

    def _print_test_start_info(self, end_time):
        from datetime import datetime

        if isinstance(end_time, datetime):
            end_time_iso = end_time.isoformat()
        else:
            end_time_iso = str(end_time)

        print(
            f"Starting messages release test for {self.duration_hours} hours"
            f" on models: {', '.join(self.models)}"
        )
        print(f"Test will run until: {end_time_iso}")
        print(f"Maximum acceptable failure rate: {self.max_failure_rate * 100}%")

    def _calculate_results(self) -> Dict[str, Any]:
        results = super()._calculate_results()
        results["test_name"] = TEST_NAME
        return results

