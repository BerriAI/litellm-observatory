# API Reference

Complete reference for the LiteLLM Observatory API.

## Base URL

- **Local**: `http://localhost:8000`
- **Production**: Your deployment URL

## Authentication

All endpoints require the `X-LiteLLM-Observatory-API-Key` header if `OBSERVATORY_API_KEY` environment variable is set. If not set, endpoints are publicly accessible.

---

## Endpoints

### `GET /`

Get API information and available test suites.

**Response**:
```json
{
  "name": "LiteLLM Observatory",
  "version": "0.1.0",
  "available_test_suites": ["TestOAIAzureRelease", "TestMockSingleRequest"]
}
```

---

### `GET /health`

Health check endpoint.

**Response**:
```json
{
  "status": "healthy"
}
```

---

### `POST /run-test`

Run a test suite against a LiteLLM deployment. Returns immediately; results are sent to Slack when complete.

**Note**: Tests are queued and executed with concurrency control. Duplicate requests (same test_suite, deployment_url, models, and parameters) are rejected with a 409 status code.

**Request Body**:
```json
{
  "deployment_url": "https://your-litellm.com",
  "api_key": "sk-litellm-key",
  "test_suite": "TestOAIAzureRelease",
  "models": ["gpt-4", "gpt-3.5-turbo"],
  "duration_hours": 3.0,
  "max_failure_rate": 0.01,
  "request_interval_seconds": 1.0
}
```

**Required Fields**: `deployment_url`, `api_key`, `test_suite`, `models`  
**Optional Fields**: `duration_hours`, `max_failure_rate`, `request_interval_seconds`

**Response** (200 OK):
```json
{
  "status": "started",
  "test_name": "TestOAIAzureRelease",
  "results": {
    "message": "Test started. Results will be sent via Slack webhook when complete.",
    "deployment_url": "https://your-litellm.com",
    "models": ["gpt-4", "gpt-3.5-turbo"],
    "estimated_duration_hours": 3.0
  }
}
```

**Error Responses**:
- **400**: Invalid test suite name or Slack webhook not configured
- **401**: Missing or invalid API key
- **409**: Duplicate request - a test with identical parameters is already running or queued
- **422**: Invalid request body format

### `GET /queue-status`

Get current queue status and information about running tests.

**Response** (200 OK):
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

---

**Example**:
```bash
curl -X POST http://localhost:8000/run-test \
  -H "X-LiteLLM-Observatory-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "deployment_url": "https://your-litellm.com",
    "api_key": "sk-litellm-key",
    "test_suite": "TestOAIAzureRelease",
    "models": ["gpt-4"]
  }'
```
