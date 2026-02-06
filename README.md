# LiteLLM Observatory

Testing orchestrator for LiteLLM deployments. Run test suites against your LiteLLM instances and receive results via Slack.

## Quick Start

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

The endpoint returns immediately. Test results are sent to Slack when complete.

## Available Test Suites

### TestOAIAzureRelease

- **Duration**: 3 hours (default)
- **Purpose**: Validates OpenAI/Azure provider reliability, catches HTTP client lifecycle regressions
- **Failure Threshold**: < 1% (default, configurable)
- **Use Case**: Production release validation, regression detection

### TestMockSingleRequest

- **Duration**: < 1 second
- **Purpose**: Quick connectivity validation - makes a single real HTTP request to verify deployment is reachable
- **Failure Threshold**: N/A (pass/fail based on single request)
- **Use Case**: Quick validation before running longer tests, connectivity checks

## Endpoints

- `GET /` - API info
- `GET /health` - Health check
- `POST /run-test` - Run a test suite

All endpoints require the `X-LiteLLM-Observatory-API-Key` header.

## Documentation

- [Test Coverage](docs/TEST_COVERAGE.md) - What each test suite validates in LiteLLM deployments
- [Adding a New Test Suite](docs/ADDING_TEST_SUITES.md) - Guide for creating custom test suites
