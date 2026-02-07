# LiteLLM Observatory

Testing orchestrator for LiteLLM deployments. Run test suites against your LiteLLM instances and receive results via Slack.

![LiteLLM Observatory](https://github.com/AlexsanderHamir/assets/blob/main/Screenshot%202026-01-31%20175355.png)



## Quick Start

> **Note for Developers Using AI Assistants**: If you're using AI coding assistants (like Cursor), make sure they reference `.cursorrules` for project-specific patterns and guidelines.

### Installation

```bash
poetry install
```

### Configuration

```bash
export OBSERVATORY_API_KEY="your-secret-api-key"
export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
```

### Run Server

```bash
poetry run python -m litellm_observatory.server
```

### Run Tests

```bash
# Run all tests
poetry run pytest

# Run with verbose output
poetry run pytest -v

# Run a specific test file
poetry run pytest tests/test_documentation_coverage.py
```

**Note**: Always run tests before pushing changes to ensure everything passes.

## API Usage

### Run a Test

```bash
curl -X POST http://localhost:8000/run-test \
  -H "X-LiteLLM-Observatory-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "deployment_url": "https://your-litellm.com",
    "api_key": "sk-litellm-key",
    "test_suite": "TestOAIAzureRelease",
    "models": ["gpt-4", "gpt-3.5-turbo"]
  }'
```

The endpoint returns immediately. Tests are queued and executed with concurrency control (default: 5 concurrent tests). Duplicate requests are rejected with a 409 status. Test results are sent to Slack when complete.

## Endpoints

- `GET /` - API info
- `GET /health` - Health check
- `POST /run-test` - Run a test suite (queued with concurrency control)
- `GET /queue-status` - Get queue status and running tests

All endpoints require the `X-LiteLLM-Observatory-API-Key` header.

## Documentation

- [Test Coverage](docs/TEST_COVERAGE.md) - What each test suite validates in LiteLLM deployments
- [Adding a New Test Suite](docs/ADDING_TEST_SUITES.md) - Guide for creating custom test suites
- [API Reference](docs/API_REFERENCE.md) - Complete API documentation with request/response examples
- [Queue System](docs/QUEUE_SYSTEM.md) - Test queue, concurrency control, and duplicate detection
- [Environment Variables](docs/ENVIRONMENT_VARIABLES.md) - Configuration variables reference
- [Architecture](ARCHITECTURE.md) - Project structure and component overview