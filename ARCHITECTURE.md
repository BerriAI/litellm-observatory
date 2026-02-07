# Project Architecture

## Folder Structure

```
litellm-observatory/
├── litellm_observatory/          # Main package
│   ├── __init__.py
│   ├── server.py                 # FastAPI server with endpoints
│   ├── models.py                 # Pydantic models for requests/responses
│   ├── auth.py                   # API key authentication
│   ├── queue.py                  # Test queue with concurrency control and duplicate detection
│   ├── integrations/             # External integrations
│   │   ├── __init__.py
│   │   └── slack.py              # Slack webhook integration
│   └── test_suites/              # Test suite implementations
│       ├── __init__.py
│       ├── base.py                # Base test class/interface
│       ├── test_oai_azure_release.py
│       └── test_mock_single_request.py
├── tests/                        # Unit tests
│   ├── __init__.py
│   ├── test_documentation_coverage.py
│   └── test_server_slack_integration.py
├── docs/                         # Documentation
│   ├── ADDING_TEST_SUITES.md
│   ├── TEST_COVERAGE.md
│   ├── ENVIRONMENT_VARIABLES.md
│   └── API_REFERENCE.md
├── main.py                       # Entry point for Render deployment
├── pyproject.toml
├── README.md
└── .gitignore
```

## Key Components

### `litellm_observatory/server.py`
- FastAPI application with three endpoints
- Handles test execution in background tasks
- Integrates with Slack for result notifications
- Validates test suite names against registry

### `litellm_observatory/models.py`
- `RunTestRequest`: Request model for `/run-test` endpoint
- `TestResultResponse`: Response model for test execution
- `TEST_SUITE_REGISTRY`: Registry mapping test suite names to classes

### `litellm_observatory/auth.py`
- API key authentication using FastAPI Security
- Optional authentication (skips if `OBSERVATORY_API_KEY` not set)
- Validates `X-LiteLLM-Observatory-API-Key` header

### `litellm_observatory/queue.py`
- `TestQueue`: Manages test execution queue with concurrency control
- Prevents duplicate test requests (same parameters)
- Limits concurrent test execution (configurable via `MAX_CONCURRENT_TESTS`)
- Tracks test status: queued, running, completed, failed
- Provides queue status and running test information

### `litellm_observatory/integrations/slack.py`
- `SlackWebhook` class for sending notifications
- Formats test results into Slack messages
- Reads webhook URL from `SLACK_WEBHOOK_URL` environment variable

### `litellm_observatory/test_suites/base.py`
- `BaseTestSuite`: Abstract base class for all test suites
- Provides helper methods: `get_endpoint_url()`, `get_headers()`
- Defines `run()` method interface

### `litellm_observatory/test_suites/test_*.py`
- Individual test suite implementations
- Each inherits from `BaseTestSuite`
- Implements `run()` method returning test results dictionary

## Request Flow

1. **Client sends request** to `/run-test` endpoint with test parameters
2. **Server validates**:
   - API key (if `OBSERVATORY_API_KEY` is set)
   - Test suite exists in registry
   - Slack webhook is configured
3. **Queue checks for duplicates**:
   - Generates request ID from test parameters (test_suite, deployment_url, models, etc.)
   - Returns 409 Conflict if identical test is already running or queued
4. **Test is enqueued**:
   - Added to queue if max concurrent tests reached
   - Starts immediately if under concurrency limit
5. **Server returns immediately** with `{"status": "queued"}` or `{"status": "started"}` response
6. **Queue processor** (background):
   - Manages concurrent test execution (respects `MAX_CONCURRENT_TESTS`)
   - Instantiates test suite class when slot available
   - Runs test suite against deployment
   - Extracts results and error messages
   - Sends formatted notification to Slack
   - Updates test status and cleans up resources
7. **Slack notification** contains test results, failure rates, and error details

## Test Suite Execution

Test suites run asynchronously and make HTTP requests to LiteLLM deployments:
- Use `httpx.AsyncClient` for async HTTP requests
- Test against `/v1/chat/completions` endpoint (or test-specific endpoints)
- Track success/failure rates over time
- Return structured results dictionary

## Queue System

The queue system manages test execution with the following features:

### Concurrency Control
- Maximum concurrent tests configurable via `MAX_CONCURRENT_TESTS` (default: 5)
- Uses `asyncio.Semaphore` to enforce limits
- Tests beyond the limit are queued and processed when slots become available

### Duplicate Detection
- Requests with identical parameters generate the same request ID
- Duplicate detection based on: test_suite, deployment_url, api_key, models, and optional parameters
- Prevents running the same test multiple times simultaneously
- Returns 409 Conflict with information about the existing test

### Queue Status
- `GET /queue-status` endpoint provides real-time queue information
- Shows: max concurrent tests, currently running count, queued count, recently completed
- Lists all running tests with their parameters and start times

### Test Lifecycle
- **QUEUED**: Test is waiting for an available slot
- **RUNNING**: Test is currently executing
- **COMPLETED**: Test finished successfully
- **FAILED**: Test encountered an error

## Background Task Management

Tests run in background to avoid blocking HTTP responses:
- Long-running tests (e.g., 3 hours) don't block the API
- Queue ensures resource limits are respected
- Results are delivered via Slack webhook
- Errors are caught and sent to Slack with details
