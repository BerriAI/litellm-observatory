# Test Coverage

This document describes what each test suite validates in LiteLLM deployments.

## Test Suites

- **TestOAIAzureRelease**: Validates OpenAI/Azure provider reliability over 3 hours, catching HTTP client lifecycle regressions like PR #19190
- **TestMockSingleRequest**: Quick connectivity check - makes a single request to verify deployment is reachable and API key works
