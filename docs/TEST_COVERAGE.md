# Test Coverage

This document describes what each test suite validates in LiteLLM deployments.

## Test Suites

- **TestFakeBedrockRelease**: Validates Bedrock provider path reliability using a fake endpoint, catching HTTP client lifecycle regressions
- **TestFakeVertexAIRelease**: Validates Vertex AI provider path reliability using a fake endpoint, catching HTTP client lifecycle regressions
- **TestMCPRelease**: MCP smoke test — validates `GET /v1/mcp/tools` is reachable and returns a valid tools list; optionally verifies that specific MCP servers (passed via `models`) have discoverable tools
- **TestMockSingleRequest**: Quick connectivity check - makes a single request to verify deployment is reachable and API key works
- **TestOAIAzureRelease**: Validates OpenAI/Azure provider reliability over 3 hours, catching HTTP client lifecycle regressions like PR #19190
