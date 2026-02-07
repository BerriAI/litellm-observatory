# Queue System

The LiteLLM Observatory uses a queue system to manage test execution with concurrency control and duplicate detection.

## Overview

The queue system ensures:
- **Resource protection**: Limits concurrent test execution to prevent server overload
- **Duplicate prevention**: Prevents running identical tests simultaneously
- **Fair execution**: Tests are processed in order when slots become available

## Concurrency Control

- **Default limit**: 5 concurrent tests (configurable via `MAX_CONCURRENT_TESTS`)
- Tests beyond the limit are queued automatically
- When a test completes, the next queued test starts immediately
- Uses `asyncio.Semaphore` to enforce limits efficiently

## Duplicate Detection

Duplicate requests are detected based on a hash of all test parameters:
- `test_suite` name
- `deployment_url`
- `api_key`
- `models` (sorted, so order doesn't matter)
- `duration_hours` (if specified)
- `max_failure_rate` (if specified)
- `request_interval_seconds` (if specified)

**Behavior**:
- If a duplicate is detected, the endpoint returns `409 Conflict`
- Response includes information about the existing test (status, request_id, start/queue time)
- Prevents accidental duplicate test runs and resource waste

## Queue Status

Use `GET /queue-status` to monitor the queue:

```json
{
  "queue_status": {
    "max_concurrent_tests": 5,
    "currently_running": 2,
    "queued": 3,
    "recently_completed": 10
  },
  "running_tests": {
    "abc123def456": {
      "test_suite": "TestOAIAzureRelease",
      "deployment_url": "https://your-litellm.com",
      "models": ["gpt-4"],
      "status": "running",
      "started_at": "2024-01-15T10:30:00"
    }
  }
}
```

## Test Lifecycle

Tests progress through these states:

1. **QUEUED**: Waiting for an available execution slot
2. **RUNNING**: Currently executing against the deployment
3. **COMPLETED**: Finished successfully
4. **FAILED**: Encountered an error during execution

## Configuration

Set `MAX_CONCURRENT_TESTS` environment variable to adjust the concurrency limit:

```bash
export MAX_CONCURRENT_TESTS=10  # Allow up to 10 concurrent tests
```

## Example Scenarios

### Scenario 1: Under Limit
- 3 tests submitted, max concurrent = 5
- All 3 start immediately
- Status: `"started"`

### Scenario 2: Over Limit
- 8 tests submitted, max concurrent = 5
- First 5 start immediately
- Remaining 3 are queued
- Status: `"queued"` for queued tests, `"started"` for running tests

### Scenario 3: Duplicate Request
- Test A submitted with specific parameters
- Test B submitted with identical parameters
- Test B returns `409 Conflict` with duplicate info
- Test A continues running
