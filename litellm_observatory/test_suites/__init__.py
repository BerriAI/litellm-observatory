"""Test suite implementations."""

from litellm_observatory.test_suites.base import BaseTestSuite
from litellm_observatory.test_suites.test_embeddings_release import TestEmbeddingsRelease
from litellm_observatory.test_suites.test_fake_bedrock_release import TestFakeBedrockRelease
from litellm_observatory.test_suites.test_fake_vertex_ai_release import TestFakeVertexAIRelease
from litellm_observatory.test_suites.test_messages_release import TestMessagesRelease
from litellm_observatory.test_suites.test_mcp_release import TestMCPRelease
from litellm_observatory.test_suites.test_mock_single_request import TestMockSingleRequest
from litellm_observatory.test_suites.test_oai_azure_release import TestOAIAzureRelease
from litellm_observatory.test_suites.test_responses_release import TestResponsesRelease

__all__ = [
    "BaseTestSuite",
    "TestEmbeddingsRelease",
    "TestFakeBedrockRelease",
    "TestFakeVertexAIRelease",
    "TestMessagesRelease",
    "TestMCPRelease",
    "TestMockSingleRequest",
    "TestOAIAzureRelease",
    "TestResponsesRelease",
]
