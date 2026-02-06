"""Pydantic models and registry for the LiteLLM Observatory API."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from litellm_observatory.test_suites import TestMockSingleRequest, TestOAIAzureRelease


class RunTestRequest(BaseModel):
    """Request model for running a test suite."""

    deployment_url: str = Field(..., description="Base URL of the LiteLLM deployment")
    api_key: str = Field(..., description="API key for authentication")
    test_suite: str = Field(..., description="Name of the test suite to run (e.g., 'TestOAIAzureRelease')")
    models: List[str] = Field(..., description="List of model names to test")
    duration_hours: Optional[float] = Field(
        None, description="Test duration in hours (uses test default if not provided)"
    )
    max_failure_rate: Optional[float] = Field(
        None, description="Maximum acceptable failure rate (uses test default if not provided)"
    )
    request_interval_seconds: Optional[float] = Field(
        None, description="Time between requests in seconds (uses test default if not provided)"
    )


class TestResultResponse(BaseModel):
    """Response model for test results."""

    status: str = Field(..., description="Test execution status")
    test_name: str = Field(..., description="Name of the test that was run")
    results: Dict[str, Any] = Field(..., description="Detailed test results")


# Registry of available test suites
TEST_SUITE_REGISTRY = {
    "TestOAIAzureRelease": TestOAIAzureRelease,
    "TestMockSingleRequest": TestMockSingleRequest,
}
