# Project Architecture

## Folder Structure

```
litellm-observatory/
├── litellm_observatory/          # Main package
│   ├── __init__.py
│   ├── server.py                 # FastAPI server with endpoints
│   ├── models.py                 # Pydantic models for requests/responses
│   ├── auth.py                   # API key authentication
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
3. **Server creates background task** using `asyncio.create_task()`
4. **Server returns immediately** with `{"status": "started"}` response
5. **Background task**:
   - Instantiates test suite class
   - Runs test suite against deployment
   - Extracts results and error messages
   - Sends formatted notification to Slack
6. **Slack notification** contains test results, failure rates, and error details

## Test Suite Execution

Test suites run asynchronously and make HTTP requests to LiteLLM deployments:
- Use `httpx.AsyncClient` for async HTTP requests
- Test against `/v1/chat/completions` endpoint (or test-specific endpoints)
- Track success/failure rates over time
- Return structured results dictionary

## Background Task Management

Tests run in background to avoid blocking HTTP responses:
- Long-running tests (e.g., 3 hours) don't block the API
- Results are delivered via Slack webhook
- Errors are caught and sent to Slack with details
