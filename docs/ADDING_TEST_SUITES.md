# Adding a New Test Suite

This guide explains how to create and register a new test suite in the LiteLLM Observatory.

## Overview

A test suite is a class that inherits from `BaseTestSuite` and implements the `run()` method. Test suites are executed against LiteLLM deployments to validate functionality, reliability, or performance.

## Step-by-Step Guide

### 1. Create the Test Suite File

Create a new file in `litellm_observatory/test_suites/` with a descriptive name, e.g., `test_my_feature.py`.

### 2. Implement the Test Suite Class

Your test suite must:

- Inherit from `BaseTestSuite`
- Implement `__init__()` that calls `super().__init__(deployment_url, api_key)`
- Implement `async def run(self, **params: Any) -> Dict[str, Any]`
- Return a dictionary with test results

#### Required Result Dictionary Keys

Your `run()` method should return a dictionary with at least these keys:

- `test_name`: Human-readable name of the test
- `test_passed`: Boolean indicating if the test passed
- `total_requests`: Total number of requests made
- `duration_hours`: Duration of the test in hours

Optional but recommended keys:

- `overall_failure_rate`: Overall failure rate (0.0 to 1.0)
- `detailed_results`: Per-model or per-request detailed results
- `error`: Error message if the test failed

### 3. Example Implementation

```python
"""Example test suite implementation."""

from typing import Any, Dict, List
import httpx
from datetime import datetime, timedelta

from litellm_observatory.test_suites.base import BaseTestSuite

# Define constants at the top
DEFAULT_DURATION_HOURS = 1.0
DEFAULT_MAX_FAILURE_RATE = 0.05
HTTP_REQUEST_TIMEOUT_SECONDS = 60.0


class TestMyFeature(BaseTestSuite):
    """
    Test suite for validating a specific feature.
    
    This test suite validates...
    """

    def __init__(
        self,
        deployment_url: str,
        api_key: str,
        models: List[str],
        duration_hours: float = DEFAULT_DURATION_HOURS,
        max_failure_rate: float = DEFAULT_MAX_FAILURE_RATE,
    ):
        """
        Initialize the test suite.

        Args:
            deployment_url: The base URL of the LiteLLM deployment
            api_key: API key for authentication
            models: List of model names to test
            duration_hours: Test duration in hours
            max_failure_rate: Maximum acceptable failure rate
        """
        super().__init__(deployment_url, api_key)
        self.models = models
        self.duration_hours = duration_hours
        self.max_failure_rate = max_failure_rate

    async def run(self, **params: Any) -> Dict[str, Any]:
        """
        Run the test suite.

        Returns:
            Dictionary containing test results
        """
        start_time = datetime.now()
        end_time = start_time + timedelta(hours=self.duration_hours)
        
        total_requests = 0
        successful_requests = 0
        failed_requests = 0
        detailed_results = {}

        async with httpx.AsyncClient(timeout=HTTP_REQUEST_TIMEOUT_SECONDS) as client:
            # Your test logic here
            while datetime.now() < end_time:
                for model in self.models:
                    try:
                        # Make your test request
                        url = self.get_endpoint_url("/v1/chat/completions")
                        headers = self.get_headers()
                        payload = {
                            "model": model,
                            "messages": [{"role": "user", "content": "Test message"}],
                        }
                        
                        response = await client.post(url, json=payload, headers=headers)
                        total_requests += 1
                        
                        if response.status_code == 200:
                            successful_requests += 1
                        else:
                            failed_requests += 1
                            
                    except Exception as e:
                        total_requests += 1
                        failed_requests += 1
                        # Log error details
                        if model not in detailed_results:
                            detailed_results[model] = []
                        detailed_results[model].append({"error": str(e)})

        # Calculate results
        failure_rate = failed_requests / total_requests if total_requests > 0 else 0.0
        test_passed = failure_rate <= self.max_failure_rate

        return {
            "test_name": "My Feature Test",
            "test_passed": test_passed,
            "total_requests": total_requests,
            "successful_requests": successful_requests,
            "failed_requests": failed_requests,
            "overall_failure_rate": failure_rate,
            "duration_hours": self.duration_hours,
            "detailed_results": detailed_results,
        }
```

### 4. Export the Test Suite

Add your test suite to `litellm_observatory/test_suites/__init__.py`:

```python
from litellm_observatory.test_suites.test_my_feature import TestMyFeature

__all__ = [..., "TestMyFeature"]
```

### 5. Register the Test Suite

Add your test suite to the registry in `litellm_observatory/models.py`:

```python
from litellm_observatory.test_suites import TestMyFeature

TEST_SUITE_REGISTRY = {
    "TestOAIAzureRelease": TestOAIAzureRelease,
    "TestMockSingleRequest": TestMockSingleRequest,
    "TestMyFeature": TestMyFeature,  # Add your test suite here
}
```

### 6. Handle Optional Parameters

If your test suite accepts optional parameters (like `duration_hours`, `max_failure_rate`), the server will pass them from the API request. Make sure your `__init__` method accepts these as optional parameters with defaults.

The server passes these optional parameters from `RunTestRequest`:
- `duration_hours`
- `max_failure_rate`
- `request_interval_seconds`

You can also accept custom parameters by adding them to `RunTestRequest` in `models.py` if needed.

## Helper Methods Available

Your test suite inherits these helper methods from `BaseTestSuite`:

- `get_endpoint_url(endpoint: str) -> str`: Builds full URL from endpoint path
- `get_headers() -> Dict[str, str]`: Returns headers with authentication

## Best Practices

1. **Use constants**: Define configuration values as constants at the top of your file
2. **Document thoroughly**: Add docstrings explaining what your test validates
3. **Handle errors gracefully**: Catch exceptions and include error details in results
4. **Return structured results**: Use consistent dictionary keys for results
5. **Make it configurable**: Accept parameters for duration, failure thresholds, etc.
6. **Use async/await**: All HTTP requests should be async using `httpx.AsyncClient`

## Testing Your Test Suite

You can test your new test suite by:

1. Starting the server: `poetry run python -m litellm_observatory.server`
2. Making a request to `/run-test` with your test suite name
3. Checking Slack for the results notification

## Example API Request

```bash
curl -X POST http://localhost:8000/run-test \
  -H "X-LiteLLM-Observatory-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "deployment_url": "https://your-litellm.com",
    "api_key": "sk-litellm-key",
    "test_suite": "TestMyFeature",
    "models": ["gpt-4"],
    "duration_hours": 1.0,
    "max_failure_rate": 0.05
  }'
```
