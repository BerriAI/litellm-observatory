"""FastAPI server for running test suites against LiteLLM deployments."""

import asyncio

from fastapi import Depends, FastAPI, HTTPException

from litellm_observatory.auth import verify_api_key
from litellm_observatory.integrations import SlackWebhook
from litellm_observatory.models import RunTestRequest, TestResultResponse, TEST_SUITE_REGISTRY

app = FastAPI(
    title="LiteLLM Observatory",
    description="Testing orchestrator for LiteLLM deployments",
    version="0.1.0",
)
slack_webhook = SlackWebhook()


@app.get("/")
async def root(_: str = Depends(verify_api_key)):
    """Root endpoint with API information."""
    return {
        "name": "LiteLLM Observatory",
        "version": "0.1.0",
        "available_test_suites": list(TEST_SUITE_REGISTRY.keys()),
    }


@app.get("/health")
async def health(_: str = Depends(verify_api_key)):
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
    if request.test_suite not in TEST_SUITE_REGISTRY:
        available_suites = list(TEST_SUITE_REGISTRY.keys())
        raise HTTPException(
            status_code=400,
            detail=(
                f"Test suite '{request.test_suite}' is not available. "
                f"Only the following test suites can be executed: {available_suites}"
            ),
        )

    test_suite_class = TEST_SUITE_REGISTRY[request.test_suite]

    test_params = {
        "deployment_url": request.deployment_url,
        "api_key": request.api_key,
        "models": request.models,
    }

    if request.duration_hours is not None:
        test_params["duration_hours"] = request.duration_hours
    if request.max_failure_rate is not None:
        test_params["max_failure_rate"] = request.max_failure_rate
    if request.request_interval_seconds is not None:
        test_params["request_interval_seconds"] = request.request_interval_seconds

    if not slack_webhook.webhook_url:
        raise HTTPException(
            status_code=400,
            detail="Slack webhook URL must be configured (SLACK_WEBHOOK_URL environment variable). "
            "Test results will be sent via Slack notification.",
        )

    async def run_test_and_notify():
        """Run the test suite in the background and send results via Slack."""
        try:
            test_suite = test_suite_class(**test_params)
            results = await test_suite.run()

            error_message = None
            if not results.get("test_passed", False):
                detailed_results = results.get("detailed_results", {})
                for model_results in detailed_results.values():
                    if isinstance(model_results, list):
                        for result in model_results:
                            if isinstance(result, dict) and result.get("error"):
                                error_message = result.get("error")
                                if isinstance(error_message, dict):
                                    error_message = error_message.get("message") or str(error_message)
                                break
                        if error_message:
                            break

            slack_webhook.send_test_result_notification(
                test_name=results.get("test_name", request.test_suite),
                deployment_url=request.deployment_url,
                test_passed=results.get("test_passed", False),
                failure_rate=results.get("overall_failure_rate", 0.0),
                total_requests=results.get("total_requests", 0),
                duration_hours=results.get("duration_hours", 0.0),
                error_message=error_message,
            )
        except Exception as e:
            slack_webhook.send_message(
                text=f"❌ Test execution failed: {str(e)}\n"
                f"Test: {request.test_suite}\n"
                f"Deployment: {request.deployment_url}",
                username="LiteLLM Observatory",
                icon_emoji=":warning:",
            )

    asyncio.create_task(run_test_and_notify())

    return TestResultResponse(
        status="started",
        test_name=request.test_suite,
        results={
            "message": "Test started. Results will be sent via Slack webhook when complete.",
            "deployment_url": request.deployment_url,
            "models": request.models,
            "estimated_duration_hours": test_params.get("duration_hours", 3.0),
        },
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
