# Test Coverage

This document describes what each test suite validates in LiteLLM deployments.

## Test Suites

- **TestFakeBedrockRelease**: Validates Bedrock provider path reliability using a fake endpoint, catching HTTP client lifecycle regressions
- **TestFakeVertexAIRelease**: Validates Vertex AI provider path reliability using a fake endpoint, catching HTTP client lifecycle regressions
- **TestMCPRelease**: Long-running MCP reliability test — continuously polls `GET /v1/mcp/tools` for the specified duration and verifies that each MCP server name (passed via `models`) has at least one discoverable tool. Reports latency percentiles, error categories, and first-failure timing. Default: 3h duration, 30s polling interval, <1% failure rate.
- **TestMockSingleRequest**: Quick connectivity check - makes a single request to verify deployment is reachable and API key works
- **TestOAIAzureRelease**: Validates OpenAI/Azure provider reliability over 3 hours, catching HTTP client lifecycle regressions like PR #19190
