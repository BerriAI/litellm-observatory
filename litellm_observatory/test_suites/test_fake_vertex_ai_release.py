"""
Fake Vertex AI release test suite - validates Vertex AI provider reliability on new releases.

Uses a fake Vertex AI endpoint (via exampleopenaiendpoint) to test the LiteLLM proxy's
Vertex AI integration path without requiring real GCP credentials. This catches regressions
in the Vertex AI provider's request/response transformation and HTTP client lifecycle.

See test_oai_azure_release.py for detailed background on the HTTP client lifecycle
regression this test family was designed to detect.
"""

from litellm_observatory.test_suites.test_oai_azure_release import TestOAIAzureRelease

# Override constants for Vertex AI
DEFAULT_TEST_MESSAGE = "Hello! This is a fake Vertex AI release test."
TEST_NAME = "Fake Vertex AI Release Test"


class TestFakeVertexAIRelease(TestOAIAzureRelease):
    """
    Fake Vertex AI release reliability test.

    Subclasses TestOAIAzureRelease with Vertex AI-specific naming. The test logic is
    identical — continuous requests through the LiteLLM proxy's /v1/chat/completions
    endpoint, with models routed to a fake Vertex AI backend.
    """

    def _build_chat_completion_payload(self, model):
        """Build the chat completion request payload with Vertex AI test message."""
        return {
            "model": model,
            "messages": [{"role": "user", "content": DEFAULT_TEST_MESSAGE}],
            "max_tokens": 50,
        }

    def _print_test_start_info(self, end_time):
        """Print test configuration at the start of the test."""
        print(
            f"Starting fake Vertex AI release test for {self.duration_hours} hours"
            f" on models: {', '.join(self.models)}"
        )
        print(f"Test will run until: {end_time.isoformat()}")
        print(f"Maximum acceptable failure rate: {self.max_failure_rate * 100}%")

    def _calculate_results(self):
        """Calculate results with Vertex AI test name."""
        results = super()._calculate_results()
        results["test_name"] = TEST_NAME
        return results
