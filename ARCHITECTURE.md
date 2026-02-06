# Project Architecture

## Folder Structure

```
litellm-observatory/
├── litellm_observatory/          # Main package
│   ├── __init__.py
│   ├── server.py                 # Main API server (FastAPI/Flask)
│   ├── models.py                 # Pydantic models (deployments, results)
│   └── test_suites/              # Test suite implementations
│       ├── __init__.py
│       ├── base.py              # Base test class/interface
│       ├── test_api_connection.py
│       ├── test_performance.py
│       ├── test_reliability.py
│       └── test_provider_coverage.py
├── tests/                        # Unit tests
│   ├── __init__.py
│   └── test_server.py
├── config/                       # Configuration files
│   └── deployments.yaml         # Deployment endpoints
├── pyproject.toml
├── README.md
└── .gitignore
```

## Key Components

### `litellm_observatory/server.py`
- Main API server (FastAPI recommended)
- Endpoints to trigger test runs
- Accepts deployment URLs and test suite names
- Returns test results as JSON

### `litellm_observatory/models.py`
- Deployment model (URL, auth, etc.)
- Test result models
- Request/response schemas

### `litellm_observatory/test_suites/base.py`
- Abstract base class for all test suites
- Defines the interface that tests must implement
- Common utilities for making HTTP requests

### `litellm_observatory/test_suites/test_*.py`
- Individual test suite implementations
- Each test is self-contained with its own logic
- Examples: API connection, performance, reliability, etc.


```

## Flow

1. Server receives request to run a test
2. Server instantiates the requested test suite
3. Test suite runs against the deployment URL
4. Results are returned via API response
