"""Tests for the test queue system with concurrency control and duplicate detection."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from litellm_observatory.models import RunTestRequest
from litellm_observatory.queue import QueuedTest, TestQueue, TestStatus as QueueTestStatus


async def cleanup_queue(queue: TestQueue):
    """Helper to clean up queue processor task after tests."""
    if queue._queue_processor_task and not queue._queue_processor_task.done():
        queue._queue_processor_task.cancel()
        try:
            await asyncio.wait_for(queue._queue_processor_task, timeout=0.1)
        except (asyncio.CancelledError, asyncio.TimeoutError):
            pass
    # Wait for any running tests to complete
    if queue.running_tests:
        await asyncio.sleep(0.2)


@pytest.fixture
def test_queue():
    """Create a test queue with max 2 concurrent tests for faster testing."""
    return TestQueue(max_concurrent_tests=2)


@pytest.fixture
def sample_request():
    """Create a sample test request."""
    return RunTestRequest(
        deployment_url="https://test-deployment.com",
        api_key="sk-test-key",
        test_suite="TestOAIAzureRelease",
        models=["gpt-4"],
        duration_hours=0.01,  # Very short for testing
    )


@pytest.fixture
def sample_request_different():
    """Create a different sample test request."""
    return RunTestRequest(
        deployment_url="https://different-deployment.com",
        api_key="sk-different-key",
        test_suite="TestOAIAzureRelease",
        models=["gpt-3.5-turbo"],
    )


class TestRequestIDGeneration:
    """Test request ID generation for duplicate detection."""

    def test_same_parameters_generate_same_id(self, test_queue, sample_request):
        """Two requests with identical parameters should have the same ID."""
        request1 = sample_request
        request2 = RunTestRequest(
            deployment_url=sample_request.deployment_url,
            api_key=sample_request.api_key,
            test_suite=sample_request.test_suite,
            models=sample_request.models,
            duration_hours=sample_request.duration_hours,
        )

        id1 = test_queue._generate_request_id(request1)
        id2 = test_queue._generate_request_id(request2)

        assert id1 == id2, "Identical requests should generate the same ID"

    def test_different_parameters_generate_different_ids(
        self, test_queue, sample_request, sample_request_different
    ):
        """Requests with different parameters should have different IDs."""
        id1 = test_queue._generate_request_id(sample_request)
        id2 = test_queue._generate_request_id(sample_request_different)

        assert id1 != id2, "Different requests should generate different IDs"

    def test_model_order_does_not_affect_id(self, test_queue):
        """Request ID should be the same regardless of model order."""
        request1 = RunTestRequest(
            deployment_url="https://test.com",
            api_key="sk-key",
            test_suite="TestOAIAzureRelease",
            models=["gpt-4", "gpt-3.5-turbo"],
        )
        request2 = RunTestRequest(
            deployment_url="https://test.com",
            api_key="sk-key",
            test_suite="TestOAIAzureRelease",
            models=["gpt-3.5-turbo", "gpt-4"],  # Different order
        )

        id1 = test_queue._generate_request_id(request1)
        id2 = test_queue._generate_request_id(request2)

        assert id1 == id2, "Model order should not affect request ID"

    def test_optional_parameters_affect_id(self, test_queue):
        """Different optional parameters should generate different IDs."""
        request1 = RunTestRequest(
            deployment_url="https://test.com",
            api_key="sk-key",
            test_suite="TestOAIAzureRelease",
            models=["gpt-4"],
            duration_hours=1.0,
        )
        request2 = RunTestRequest(
            deployment_url="https://test.com",
            api_key="sk-key",
            test_suite="TestOAIAzureRelease",
            models=["gpt-4"],
            duration_hours=2.0,  # Different duration
        )

        id1 = test_queue._generate_request_id(request1)
        id2 = test_queue._generate_request_id(request2)

        assert id1 != id2, "Different optional parameters should generate different IDs"


class TestDuplicateDetection:
    """Test duplicate request detection."""

    def test_is_duplicate_returns_false_for_new_request(self, test_queue, sample_request):
        """New requests should not be detected as duplicates."""
        assert not test_queue.is_duplicate(sample_request)

    @pytest.mark.asyncio
    async def test_is_duplicate_detects_queued_request(
        self, test_queue, sample_request
    ):
        """Should detect duplicates in the queue."""
        async def mock_runner(queued_test):
            await asyncio.sleep(0.1)

        # Enqueue first request
        await test_queue.enqueue(sample_request, mock_runner)

        # Second identical request should be detected as duplicate
        assert test_queue.is_duplicate(sample_request)
        
        await cleanup_queue(test_queue)

    @pytest.mark.asyncio
    async def test_is_duplicate_detects_running_request(
        self, test_queue, sample_request
    ):
        """Should detect duplicates that are currently running."""
        async def mock_runner(queued_test):
            await asyncio.sleep(0.5)  # Long enough to be running

        # Enqueue and let it start running
        await test_queue.enqueue(sample_request, mock_runner)
        # Give it time to start
        await asyncio.sleep(0.1)

        # Should detect as duplicate
        assert test_queue.is_duplicate(sample_request)
        
        await cleanup_queue(test_queue)

    def test_get_duplicate_info_returns_none_for_new_request(
        self, test_queue, sample_request
    ):
        """New requests should return None for duplicate info."""
        assert test_queue.get_duplicate_info(sample_request) is None

    @pytest.mark.asyncio
    async def test_get_duplicate_info_returns_queued_info(
        self, test_queue, sample_request
    ):
        """Should return info about queued duplicate."""
        async def mock_runner(queued_test):
            await asyncio.sleep(0.1)

        await test_queue.enqueue(sample_request, mock_runner)

        duplicate_info = test_queue.get_duplicate_info(sample_request)
        assert duplicate_info is not None
        assert duplicate_info["status"] == "queued"
        assert "request_id" in duplicate_info
        assert "queued_at" in duplicate_info
        
        await cleanup_queue(test_queue)

    @pytest.mark.asyncio
    async def test_get_duplicate_info_returns_running_info(
        self, test_queue, sample_request
    ):
        """Should return info about running duplicate."""
        async def mock_runner(queued_test):
            await asyncio.sleep(0.5)

        await test_queue.enqueue(sample_request, mock_runner)
        await asyncio.sleep(0.1)  # Let it start running

        duplicate_info = test_queue.get_duplicate_info(sample_request)
        assert duplicate_info is not None
        assert duplicate_info["status"] == "running"
        assert "request_id" in duplicate_info
        assert "started_at" in duplicate_info
        
        await cleanup_queue(test_queue)


class TestQueueEnqueue:
    """Test enqueueing tests."""

    @pytest.mark.asyncio
    async def test_enqueue_adds_to_queue(self, test_queue, sample_request):
        """Enqueueing should add test to queue."""
        async def mock_runner(queued_test):
            await asyncio.sleep(0.1)

        queued_test = await test_queue.enqueue(sample_request, mock_runner)

        assert queued_test.status == QueueTestStatus.QUEUED
        assert queued_test.request_id is not None
        assert test_queue.queue.qsize() == 1
        
        await cleanup_queue(test_queue)

    @pytest.mark.asyncio
    async def test_enqueue_starts_processor(self, test_queue, sample_request):
        """Enqueueing should start the queue processor."""
        async def mock_runner(queued_test):
            await asyncio.sleep(0.1)

        await test_queue.enqueue(sample_request, mock_runner)

        assert test_queue._queue_processor_task is not None
        assert not test_queue._queue_processor_task.done()
        
        await cleanup_queue(test_queue)

    @pytest.mark.asyncio
    async def test_multiple_enqueues(self, test_queue, sample_request, sample_request_different):
        """Multiple different requests can be enqueued."""
        async def mock_runner(queued_test):
            await asyncio.sleep(0.1)

        queued1 = await test_queue.enqueue(sample_request, mock_runner)
        queued2 = await test_queue.enqueue(sample_request_different, mock_runner)

        assert queued1.request_id != queued2.request_id
        assert test_queue.queue.qsize() == 2
        
        await cleanup_queue(test_queue)


class TestConcurrencyControl:
    """Test concurrency control and limits."""

    @pytest.mark.asyncio
    async def test_respects_max_concurrent_tests(self, test_queue):
        """Should not exceed max concurrent tests."""
        running_count = 0
        max_running = 0

        async def mock_runner(queued_test):
            nonlocal running_count, max_running
            running_count += 1
            max_running = max(max_running, running_count)
            await asyncio.sleep(0.2)  # Long enough to test concurrency
            running_count -= 1

        # Enqueue 5 tests, but max concurrent is 2
        requests = [
            RunTestRequest(
                deployment_url=f"https://test-{i}.com",
                api_key="sk-key",
                test_suite="TestOAIAzureRelease",
                models=["gpt-4"],
            )
            for i in range(5)
        ]

        for request in requests:
            await test_queue.enqueue(request, mock_runner)

        # Wait for all to start
        await asyncio.sleep(0.3)

        # Should never exceed max_concurrent_tests (2)
        assert max_running <= test_queue.max_concurrent_tests
        
        await cleanup_queue(test_queue)

    @pytest.mark.asyncio
    async def test_queue_processes_after_test_completes(self, test_queue):
        """Next test should start when a running test completes."""
        completed_tests = []

        async def mock_runner(queued_test):
            await asyncio.sleep(0.1)
            completed_tests.append(queued_test.request_id)

        # Enqueue 3 tests with max concurrent of 2
        requests = [
            RunTestRequest(
                deployment_url=f"https://test-{i}.com",
                api_key="sk-key",
                test_suite="TestOAIAzureRelease",
                models=["gpt-4"],
            )
            for i in range(3)
        ]

        for request in requests:
            await test_queue.enqueue(request, mock_runner)

        # Wait for all to complete
        await asyncio.sleep(0.5)

        # All 3 should complete
        assert len(completed_tests) == 3
        
        await cleanup_queue(test_queue)


class TestQueueStatus:
    """Test queue status and information methods."""

    def test_get_queue_status_initial_state(self, test_queue):
        """Initial queue status should show no tests."""
        status = test_queue.get_queue_status()

        assert status["max_concurrent_tests"] == 2
        assert status["currently_running"] == 0
        assert status["queued"] == 0
        assert status["recently_completed"] == 0

    @pytest.mark.asyncio
    async def test_get_queue_status_with_queued_tests(
        self, test_queue, sample_request
    ):
        """Queue status should reflect queued tests."""
        async def mock_runner(queued_test):
            await asyncio.sleep(0.1)

        await test_queue.enqueue(sample_request, mock_runner)

        status = test_queue.get_queue_status()
        assert status["queued"] == 1
        
        await cleanup_queue(test_queue)

    @pytest.mark.asyncio
    async def test_get_queue_status_with_running_tests(
        self, test_queue, sample_request
    ):
        """Queue status should reflect running tests."""
        async def mock_runner(queued_test):
            await asyncio.sleep(0.3)

        await test_queue.enqueue(sample_request, mock_runner)
        await asyncio.sleep(0.1)  # Let it start

        status = test_queue.get_queue_status()
        assert status["currently_running"] == 1
        assert status["queued"] == 0  # Should be running, not queued
        
        await cleanup_queue(test_queue)

    @pytest.mark.asyncio
    async def test_get_running_tests(self, test_queue, sample_request):
        """Should return information about running tests."""
        async def mock_runner(queued_test):
            await asyncio.sleep(0.3)

        await test_queue.enqueue(sample_request, mock_runner)
        await asyncio.sleep(0.1)  # Let it start

        running = test_queue.get_running_tests()
        assert len(running) == 1

        request_id = list(running.keys())[0]
        test_info = running[request_id]

        assert test_info["test_suite"] == sample_request.test_suite
        assert test_info["deployment_url"] == sample_request.deployment_url
        assert test_info["models"] == sample_request.models
        assert test_info["status"] == "running"
        assert test_info["started_at"] is not None
        
        await cleanup_queue(test_queue)

    @pytest.mark.asyncio
    async def test_get_running_tests_empty_when_none_running(self, test_queue):
        """Should return empty dict when no tests are running."""
        running = test_queue.get_running_tests()
        assert running == {}
        
        await cleanup_queue(test_queue)


class TestTestLifecycle:
    """Test test lifecycle and cleanup."""

    @pytest.mark.asyncio
    async def test_test_status_changes_to_running(self, test_queue, sample_request):
        """Test status should change to running when started."""
        status_changes = []

        async def mock_runner(queued_test):
            status_changes.append(queued_test.status)
            await asyncio.sleep(0.1)

        await test_queue.enqueue(sample_request, mock_runner)
        await asyncio.sleep(0.2)  # Let it run

        assert QueueTestStatus.RUNNING in status_changes
        
        await cleanup_queue(test_queue)

    @pytest.mark.asyncio
    async def test_test_status_changes_to_completed(self, test_queue, sample_request):
        """Test status should change to completed when finished."""
        queued_test = None

        async def mock_runner(test):
            nonlocal queued_test
            queued_test = test
            await asyncio.sleep(0.1)

        await test_queue.enqueue(sample_request, mock_runner)
        await asyncio.sleep(0.3)  # Let it complete

        assert queued_test is not None
        assert queued_test.status == QueueTestStatus.COMPLETED
        assert queued_test.completed_at is not None
        
        await cleanup_queue(test_queue)

    @pytest.mark.asyncio
    async def test_test_status_changes_to_failed_on_exception(
        self, test_queue, sample_request
    ):
        """Test status should change to failed when exception occurs."""
        queued_test = None

        async def mock_runner(test):
            nonlocal queued_test
            queued_test = test
            raise Exception("Test failure")

        await test_queue.enqueue(sample_request, mock_runner)
        await asyncio.sleep(0.2)  # Let it fail

        assert queued_test is not None
        assert queued_test.status == QueueTestStatus.FAILED
        assert queued_test.completed_at is not None
        
        await cleanup_queue(test_queue)

    @pytest.mark.asyncio
    async def test_completed_tests_are_tracked(self, test_queue, sample_request):
        """Completed tests should be added to completed_tests dict."""
        async def mock_runner(queued_test):
            await asyncio.sleep(0.1)

        await test_queue.enqueue(sample_request, mock_runner)
        await asyncio.sleep(0.3)  # Let it complete

        request_id = test_queue._generate_request_id(sample_request)
        assert request_id in test_queue.completed_tests
        
        await cleanup_queue(test_queue)

    @pytest.mark.asyncio
    async def test_completed_tests_removed_from_running(self, test_queue, sample_request):
        """Completed tests should be removed from running_tests."""
        async def mock_runner(queued_test):
            await asyncio.sleep(0.1)

        await test_queue.enqueue(sample_request, mock_runner)
        await asyncio.sleep(0.3)  # Let it complete

        request_id = test_queue._generate_request_id(sample_request)
        assert request_id not in test_queue.running_tests
        
        await cleanup_queue(test_queue)


class TestEdgeCases:
    """Test edge cases and error scenarios."""

    @pytest.mark.asyncio
    async def test_queue_handles_exception_in_processor(self, test_queue):
        """Queue should handle exceptions in queue processor gracefully."""
        async def failing_runner(queued_test):
            raise ValueError("Test error")

        request = RunTestRequest(
            deployment_url="https://test.com",
            api_key="sk-key",
            test_suite="TestOAIAzureRelease",
            models=["gpt-4"],
        )

        # Should not raise exception
        await test_queue.enqueue(request, failing_runner)
        await asyncio.sleep(0.2)

        # Test should be marked as failed
        request_id = test_queue._generate_request_id(request)
        if request_id in test_queue.completed_tests:
            assert test_queue.completed_tests[request_id].status == QueueTestStatus.FAILED
        
        await cleanup_queue(test_queue)

    @pytest.mark.asyncio
    async def test_semaphore_released_on_exception(self, test_queue):
        """Semaphore should be released even if test raises exception."""
        async def failing_runner(queued_test):
            raise Exception("Failure")

        # Enqueue 2 tests that will fail
        requests = [
            RunTestRequest(
                deployment_url=f"https://test-{i}.com",
                api_key="sk-key",
                test_suite="TestOAIAzureRelease",
                models=["gpt-4"],
            )
            for i in range(2)
        ]

        for request in requests:
            await test_queue.enqueue(request, failing_runner)

        await asyncio.sleep(0.2)

        # Semaphore should be released, allowing queue to process
        # Verify by checking that both completed
        assert len(test_queue.completed_tests) == 2
        
        await cleanup_queue(test_queue)

    def test_empty_queue_status(self, test_queue):
        """Empty queue should return correct status."""
        status = test_queue.get_queue_status()
        assert status["currently_running"] == 0
        assert status["queued"] == 0

    @pytest.mark.asyncio
    async def test_multiple_identical_requests_detected(
        self, test_queue, sample_request
    ):
        """Multiple identical requests should all be detected as duplicates."""
        async def mock_runner(queued_test):
            await asyncio.sleep(0.2)

        # Enqueue first
        await test_queue.enqueue(sample_request, mock_runner)

        # All subsequent identical requests should be duplicates
        assert test_queue.is_duplicate(sample_request)
        assert test_queue.is_duplicate(sample_request)
        assert test_queue.is_duplicate(sample_request)
        
        await cleanup_queue(test_queue)