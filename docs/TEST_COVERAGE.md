# Test Coverage

This document describes what each test suite validates in LiteLLM deployments.

## Test Suites

- **TestFakeBedrockRelease**: Validates Bedrock provider path reliability using a fake endpoint, catching HTTP client lifecycle regressions
- **TestFakeVertexAIRelease**: Validates Vertex AI provider path reliability using a fake endpoint, catching HTTP client lifecycle regressions
- **TestMockSingleRequest**: Quick connectivity check - makes a single request to verify deployment is reachable and API key works
- **TestOAIAzureRelease**: Validates OpenAI/Azure provider reliability over 3 hours, catching HTTP client lifecycle regressions like PR #19190
- **TestEmbeddingsRelease**: Validates /v1/embeddings reliability over time for the configured models, across whichever providers your LiteLLM deployment routes to
- **TestResponsesRelease**: Validates /v1/responses reliability over time for the configured models, across whichever providers your LiteLLM deployment routes to
- **TestMessagesRelease**: Validates /v1/messages reliability over time for the configured models, across whichever providers your LiteLLM deployment routes to
