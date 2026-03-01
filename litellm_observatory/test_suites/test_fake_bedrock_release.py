"""
Fake Bedrock release test suite - validates Bedrock provider reliability on new releases.

Uses a fake Bedrock endpoint (via exampleopenaiendpoint) to test the LiteLLM proxy's
Bedrock integration path without requiring real AWS credentials. This catches regressions
in the Bedrock provider's request/response transformation and HTTP client lifecycle.

See test_oai_azure_release.py for detailed background on the HTTP client lifecycle
regression this test family was designed to detect.
"""

from litellm_observatory.test_suites.test_oai_azure_release import TestOAIAzureRelease

# Override constants for Bedrock
DEFAULT_TEST_MESSAGE = "Hello! This is a fake Bedrock release test."
TEST_NAME = "Fake Bedrock Release Test"


class TestFakeBedrockRelease(TestOAIAzureRelease):
    """
    Fake Bedrock release reliability test.

    Subclasses TestOAIAzureRelease with Bedrock-specific naming. The test logic is
    identical — continuous requests through the LiteLLM proxy's /v1/chat/completions
    endpoint, with models routed to a fake Bedrock backend.
    """

    def _build_chat_completion_payload(self, model):
        """Build the chat completion request payload with Bedrock test message."""
        return {
            "model": model,
            "messages": [{"role": "user", "content": DEFAULT_TEST_MESSAGE}],
            "max_tokens": 50,
        }

    def _print_test_start_info(self, end_time):
        """Print test configuration at the start of the test."""
        print(
            f"Starting fake Bedrock release test for {self.duration_hours} hours"
            f" on models: {', '.join(self.models)}"
        )
        print(f"Test will run until: {end_time.isoformat()}")
        print(f"Maximum acceptable failure rate: {self.max_failure_rate * 100}%")

    def _calculate_results(self):
        """Calculate results with Bedrock test name."""
        results = super()._calculate_results()
        results["test_name"] = TEST_NAME
        return results
