"""FastAPI server for running test suites against LiteLLM deployments."""

from fastapi import Depends, FastAPI, HTTPException

from litellm_observatory.auth import verify_api_key
from litellm_observatory.models import RunTestRequest, TestResultResponse, TEST_SUITE_REGISTRY

app = FastAPI(
    title="LiteLLM Observatory",
    description="Testing orchestrator for LiteLLM deployments",
    version="0.1.0",
)


@app.get("/")
async def root(_: str = Depends(verify_api_key)):
    """Root endpoint with API information."""
    return {
        "name": "LiteLLM Observatory",
        "version": "0.1.0",
        "available_test_suites": list(TEST_SUITE_REGISTRY.keys()),
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.post("/run-test", response_model=TestResultResponse)
async def run_test(
    request: RunTestRequest, _: str = Depends(verify_api_key)
) -> TestResultResponse:
    """
    Run a test suite against a LiteLLM deployment.

    This endpoint triggers a test suite to run against the specified deployment.
    The test will run for the specified duration and return results.

    Only test suites registered in TEST_SUITE_REGISTRY can be executed.
    """
    # Validate test suite is in registry - fail early if not
    if request.test_suite not in TEST_SUITE_REGISTRY:
        available_suites = list(TEST_SUITE_REGISTRY.keys())
        raise HTTPException(
            status_code=400,
            detail=(
                f"Test suite '{request.test_suite}' is not available. "
                f"Only the following test suites can be executed: {available_suites}"
            ),
        )

    # Get the test suite class (guaranteed to exist after validation)
    test_suite_class = TEST_SUITE_REGISTRY[request.test_suite]

    # Prepare test parameters
    test_params = {
        "deployment_url": request.deployment_url,
        "api_key": request.api_key,
        "models": request.models,
    }

    # Add optional parameters if provided
    if request.duration_hours is not None:
        test_params["duration_hours"] = request.duration_hours
    if request.max_failure_rate is not None:
        test_params["max_failure_rate"] = request.max_failure_rate
    if request.request_interval_seconds is not None:
        test_params["request_interval_seconds"] = request.request_interval_seconds

    try:
        # Instantiate and run the test suite
        test_suite = test_suite_class(**test_params)
        results = await test_suite.run()

        return TestResultResponse(
            status="completed",
            test_name=results.get("test_name", request.test_suite),
            results=results,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Test execution failed: {str(e)}",
        )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
