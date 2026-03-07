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

### Run a Single Test

```bash
curl -X POST http://localhost:8000/run-test \
  -H "X-LiteLLM-Observatory-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "deployment_url": "https://your-litellm.com",
    "api_key": "sk-litellm-key",
    "test_suite": "TestOAIAzureRelease",
    "models": ["gpt-4", "gpt-3.5-turbo"],
    "duration_hours": 3.0
  }'
```

### Run Multiple Tests in One Request

Pass an array to enqueue several suites at once. All requests are validated before any are enqueued — if any request is invalid, none will be enqueued.

```bash
curl -X POST http://localhost:8000/run-test \
  -H "X-LiteLLM-Observatory-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '[
    {"test_suite": "TestFakeBedrockRelease", "deployment_url": "https://your-litellm.com", "api_key": "sk-key", "models": ["fake-bedrock-model"], "duration_hours": 3.0},
    {"test_suite": "TestFakeVertexAIRelease", "deployment_url": "https://your-litellm.com", "api_key": "sk-key", "models": ["fake-vertex-model"], "duration_hours": 3.0},
    {"test_suite": "TestMCPRelease", "deployment_url": "https://your-litellm.com", "api_key": "sk-key", "models": ["deepwiki"], "duration_hours": 3.0}
  ]'
```

The endpoint returns immediately. Tests are queued and executed with concurrency control (default: 5 concurrent tests). Duplicate requests are rejected with a 409 status. Test results are sent to Slack when complete.

### Check Run Status

```bash
curl http://localhost:8000/run-status/{request_id} \
  -H "X-LiteLLM-Observatory-API-Key: your-api-key"
```

Returns current status, and `expected_completion_at` (ISO timestamp) for running tests.

## Test Suites

| Suite | Description |
|---|---|
| `TestOAIAzureRelease` | Long-running reliability test for OpenAI/Azure providers. Catches HTTP client lifecycle regressions (e.g. PR #19190). Default: 3h, <1% failure rate. |
| `TestFakeBedrockRelease` | Same as `TestOAIAzureRelease` routed through the Bedrock provider path using a fake endpoint. |
| `TestFakeVertexAIRelease` | Same as `TestOAIAzureRelease` routed through the Vertex AI provider path using a fake endpoint. |
| `TestMCPRelease` | Long-running reliability test for MCP endpoints. Continuously polls `/v1/mcp/tools` and verifies tool availability per MCP server. Pass server names via `models` (e.g. `["deepwiki"]`). Default: 3h, 30s interval. |
| `TestMockSingleRequest` | Quick connectivity check — single request to verify deployment reachability and API key. |

## Endpoints

- `GET /` - API info and available test suites
- `GET /health` - Health check
- `POST /run-test` - Run one or more test suites (accepts single object or array)
- `GET /run-status/{request_id}` - Get status and results for a specific test run
- `GET /queue-status` - Get queue status and running tests

All endpoints require the `X-LiteLLM-Observatory-API-Key` header.

## Versioning

The deployed version is exposed on the `/health` endpoint:

```bash
curl http://localhost:8000/health \
  -H "X-LiteLLM-Observatory-API-Key: your-api-key"
# → {"status": "healthy", "version": "0.2.0"}
```

To release a new version:

```bash
./scripts/bump_version.sh patch   # 0.2.0 → 0.2.1
./scripts/bump_version.sh minor   # 0.2.0 → 0.3.0
./scripts/bump_version.sh major   # 0.2.0 → 1.0.0
```

This bumps `pyproject.toml` via Poetry, syncs `APP_VERSION` in `server.py`, commits, tags (`v0.2.1`), and pushes in one step.

## Documentation

- [Test Coverage](docs/TEST_COVERAGE.md) - What each test suite validates in LiteLLM deployments
- [Adding a New Test Suite](docs/ADDING_TEST_SUITES.md) - Guide for creating custom test suites
- [API Reference](docs/API_REFERENCE.md) - Complete API documentation with request/response examples
- [Queue System](docs/QUEUE_SYSTEM.md) - Test queue, concurrency control, and duplicate detection
- [Environment Variables](docs/ENVIRONMENT_VARIABLES.md) - Configuration variables reference
- [Architecture](ARCHITECTURE.md) - Project structure and component overview