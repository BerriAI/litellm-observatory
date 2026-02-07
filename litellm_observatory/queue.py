"""Queue manager for test execution with concurrency control and duplicate detection."""

import asyncio
import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from litellm_observatory.models import RunTestRequest


class TestStatus(Enum):
    """Status of a test in the queue."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class QueuedTest:
    """Represents a test in the queue."""

    request: RunTestRequest
    request_id: str
    status: TestStatus = TestStatus.QUEUED
    queued_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    task: Optional[asyncio.Task] = None


class TestQueue:
    """Manages test execution queue with concurrency control and duplicate detection."""

    def __init__(self, max_concurrent_tests: int = 5):
        """
        Initialize the test queue.

        Args:
            max_concurrent_tests: Maximum number of tests that can run simultaneously
        """
        self.max_concurrent_tests = max_concurrent_tests
        self.semaphore = asyncio.Semaphore(max_concurrent_tests)
        self.queue: asyncio.Queue[QueuedTest] = asyncio.Queue()
        self.running_tests: Dict[str, QueuedTest] = {}
        self.queued_tests: Dict[str, QueuedTest] = {}
        self.completed_tests: Dict[str, QueuedTest] = {}
        self._queue_processor_task: Optional[asyncio.Task] = None

    async def enqueue(self, request: RunTestRequest, test_runner: callable) -> QueuedTest:
        """
        Add a test request to the queue.

        Args:
            request: The test request
            test_runner: Async function that will run the test (takes QueuedTest as argument)

        Returns:
            QueuedTest instance representing the queued test
        """
        request_id = self._generate_request_id(request)
        queued_test = QueuedTest(request=request, request_id=request_id)

        self.queued_tests[request_id] = queued_test
        await self.queue.put(queued_test)

        if self._queue_processor_task is None or self._queue_processor_task.done():
            self._queue_processor_task = asyncio.create_task(self._process_queue(test_runner))

        return queued_test

    def is_duplicate(self, request: RunTestRequest) -> bool:
        """
        Check if a request is a duplicate of a currently running or queued test.

        Args:
            request: The test request to check

        Returns:
            True if a duplicate request is already running or queued
        """
        request_id = self._generate_request_id(request)
        return request_id in self.running_tests or request_id in self.queued_tests

    def get_duplicate_info(self, request: RunTestRequest) -> Optional[Dict[str, Any]]:
        """
        Get information about a duplicate request if one exists.

        Args:
            request: The test request to check

        Returns:
            Dictionary with duplicate info if found, None otherwise
        """
        request_id = self._generate_request_id(request)

        if request_id in self.running_tests:
            queued_test = self.running_tests[request_id]
            return {
                "request_id": request_id,
                "status": queued_test.status.value,
                "started_at": queued_test.started_at.isoformat() if queued_test.started_at else None,
            }

        if request_id in self.queued_tests:
            queued_test = self.queued_tests[request_id]
            return {
                "request_id": request_id,
                "status": queued_test.status.value,
                "queued_at": queued_test.queued_at.isoformat(),
            }

        return None

    def get_queue_status(self) -> Dict[str, Any]:
        """
        Get current queue status.

        Returns:
            Dictionary with queue statistics
        """
        return {
            "max_concurrent_tests": self.max_concurrent_tests,
            "currently_running": len(self.running_tests),
            "queued": self.queue.qsize(),
            "recently_completed": len(self.completed_tests),
        }

    def get_running_tests(self) -> Dict[str, Dict[str, Any]]:
        """
        Get information about currently running tests.

        Returns:
            Dictionary mapping request_id to test information
        """
        return {
            request_id: {
                "test_suite": test.request.test_suite,
                "deployment_url": test.request.deployment_url,
                "models": test.request.models,
                "status": test.status.value,
                "started_at": test.started_at.isoformat() if test.started_at else None,
            }
            for request_id, test in self.running_tests.items()
        }

    # Helper methods for request ID generation

    def _generate_request_id(self, request: RunTestRequest) -> str:
        """
        Generate a unique ID for a test request based on its parameters.

        This ID is used to detect duplicate requests. Two requests with the same
        test_suite, deployment_url, models, and optional parameters will have the same ID.

        Args:
            request: The test request

        Returns:
            Unique request ID (hash of request parameters)
        """
        params = {
            "test_suite": request.test_suite,
            "deployment_url": request.deployment_url,
            "api_key": request.api_key,
            "models": sorted(request.models),
            "duration_hours": request.duration_hours,
            "max_failure_rate": request.max_failure_rate,
            "request_interval_seconds": request.request_interval_seconds,
        }
        params_json = json.dumps(params, sort_keys=True)
        return hashlib.sha256(params_json.encode()).hexdigest()[:16]

    # Helper methods for queue processing

    async def _process_queue(self, test_runner: callable):
        """Process the queue, running tests up to the concurrency limit."""
        while True:
            queued_test = None
            try:
                queued_test = await self.queue.get()
                await self.semaphore.acquire()

                queued_test.status = TestStatus.RUNNING
                queued_test.started_at = datetime.now()
                self.running_tests[queued_test.request_id] = queued_test
                self.queued_tests.pop(queued_test.request_id, None)

                task = asyncio.create_task(
                    self._run_test_with_cleanup(queued_test, test_runner)
                )
                queued_test.task = task

            except asyncio.CancelledError:
                break
            except Exception as e:
                if queued_test:
                    queued_test.status = TestStatus.FAILED
                    queued_test.completed_at = datetime.now()
                    self.queued_tests.pop(queued_test.request_id, None)
                if self.semaphore.locked():
                    self.semaphore.release()

    async def _run_test_with_cleanup(self, queued_test: QueuedTest, test_runner: callable):
        """Run a test and clean up resources."""
        try:
            await test_runner(queued_test)
            queued_test.status = TestStatus.COMPLETED
        except Exception:
            queued_test.status = TestStatus.FAILED
        finally:
            queued_test.completed_at = datetime.now()
            self.running_tests.pop(queued_test.request_id, None)
            self.completed_tests[queued_test.request_id] = queued_test
            if len(self.completed_tests) > 100:
                oldest_id = min(
                    self.completed_tests.keys(),
                    key=lambda k: self.completed_tests[k].completed_at or datetime.min,
                )
                self.completed_tests.pop(oldest_id, None)
            self.semaphore.release()
            self.queue.task_done()
