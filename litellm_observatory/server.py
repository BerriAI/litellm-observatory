"""FastAPI server for running test suites against LiteLLM deployments."""

import os
from importlib.metadata import version as pkg_version
from typing import List, Union

APP_VERSION = pkg_version("litellm-observatory")

from fastapi import Body, Depends, FastAPI, HTTPException

from litellm_observatory.auth import verify_api_key
from litellm_observatory.integrations import SlackWebhook
from litellm_observatory.models import RunTestRequest, TestResultResponse, TEST_SUITE_REGISTRY
from litellm_observatory.queue import TestQueue

app = FastAPI(
    title="LiteLLM Observatory",
    description="Testing orchestrator for LiteLLM deployments",
    version=APP_VERSION,
)
slack_webhook = SlackWebhook()

# Initialize test queue with configurable max concurrent tests
MAX_CONCURRENT_TESTS = int(os.getenv("MAX_CONCURRENT_TESTS", "5"))
test_queue = TestQueue(max_concurrent_tests=MAX_CONCURRENT_TESTS)


@app.get("/")
async def root(_: str = Depends(verify_api_key)):
    """Root endpoint with API information."""
    return {
        "name": "LiteLLM Observatory",
        "version": APP_VERSION,
        "available_test_suites": list(TEST_SUITE_REGISTRY.keys()),
    }


@app.get("/health")
async def health(_: str = Depends(verify_api_key)):
    """Health check endpoint."""
    return {"status": "healthy", "version": APP_VERSION}


def _validate_request(request: RunTestRequest) -> None:
    """Validate a single test request, raising HTTPException on failure."""
    if request.test_suite not in TEST_SUITE_REGISTRY:
        available_suites = list(TEST_SUITE_REGISTRY.keys())
        raise HTTPException(
            status_code=400,
            detail=(
                f"Test suite '{request.test_suite}' is not available. "
                f"Only the following test suites can be executed: {available_suites}"
            ),
        )
    if test_queue.is_duplicate(request):
        duplicate_info = test_queue.get_duplicate_info(request)
        raise HTTPException(
            status_code=409,
            detail={
                "message": "A test with identical parameters is already running or queued.",
                "duplicate_info": duplicate_info,
            },
        )
    if not slack_webhook.webhook_url:
        raise HTTPException(
            status_code=400,
            detail="Slack webhook URL must be configured (SLACK_WEBHOOK_URL environment variable). "
            "Test results will be sent via Slack notification.",
        )


async def _enqueue_request(request: RunTestRequest) -> TestResultResponse:
    """Build a runner closure and enqueue a single validated request."""
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

    async def run_test_and_notify(queued_test):
        """Run the test suite in the background and send results via Slack."""
        try:
            test_suite = test_suite_class(**test_params)
            results = await test_suite.run()

            queued_test.result = {
                "test_passed": results.get("test_passed", False),
                "failure_rate": results.get("overall_failure_rate", 0.0),
                "total_requests": results.get("total_requests", 0),
                "duration_hours": results.get("duration_hours", 0.0),
                "latency_percentiles": results.get("latency_percentiles"),
                "error_categories": results.get("error_categories"),
                "first_failure": results.get("first_failure"),
            }

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

            if error_message:
                queued_test.error = error_message

            slack_webhook.send_test_result_notification(
                test_name=results.get("test_name", queued_test.request.test_suite),
                deployment_url=queued_test.request.deployment_url,
                test_passed=results.get("test_passed", False),
                failure_rate=results.get("overall_failure_rate", 0.0),
                total_requests=results.get("total_requests", 0),
                duration_hours=results.get("duration_hours", 0.0),
                error_message=error_message,
                latency_percentiles=results.get("latency_percentiles"),
                error_categories=results.get("error_categories"),
                first_failure=results.get("first_failure"),
                models=results.get("models_tested"),
                test_suite=queued_test.request.test_suite,
            )
        except Exception as e:
            queued_test.error = str(e)
            slack_webhook.send_message(
                text=f"❌ Test execution failed: {str(e)}\n"
                f"Test: {queued_test.request.test_suite}\n"
                f"Deployment: {queued_test.request.deployment_url}",
                username="LiteLLM Observatory",
                icon_emoji=":warning:",
            )

    queued_test = await test_queue.enqueue(request, run_test_and_notify)
    queue_status = test_queue.get_queue_status()
    status_message = "started" if queued_test.status.value == "running" else "queued"

    return TestResultResponse(
        status=status_message,
        test_name=request.test_suite,
        results={
            "message": f"Test {status_message}. Results will be sent via Slack webhook when complete.",
            "deployment_url": request.deployment_url,
            "models": request.models,
            "estimated_duration_hours": test_params.get("duration_hours", 3.0),
            "request_id": queued_test.request_id,
            "queue_position": queue_status["queued"],
            "currently_running": queue_status["currently_running"],
        },
    )


@app.post("/run-test")
async def run_test(
    request: Union[RunTestRequest, List[RunTestRequest]] = Body(...),
    _: str = Depends(verify_api_key),
) -> Union[TestResultResponse, List[TestResultResponse]]:
    """
    Run one or more test suites against a LiteLLM deployment.

    Accepts either a single request object or an array of request objects.
    When an array is provided, all requests are validated before any are enqueued —
    if any request is invalid, none will be enqueued.
    """
    if isinstance(request, list):
        for req in request:
            _validate_request(req)
        return [await _enqueue_request(req) for req in request]

    _validate_request(request)
    return await _enqueue_request(request)


@app.get("/run-status/{request_id}")
async def run_status(request_id: str, _: str = Depends(verify_api_key)):
    """Get status and results for a specific test run by request_id."""
    status = test_queue.get_test_status(request_id)
    if status is None:
        raise HTTPException(
            status_code=404,
            detail=f"No test found with request_id '{request_id}'",
        )
    return status


@app.get("/queue-status")
async def queue_status(_: str = Depends(verify_api_key)):
    """Get current queue status and running tests."""
    return {
        "queue_status": test_queue.get_queue_status(),
        "running_tests": test_queue.get_running_tests(),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
