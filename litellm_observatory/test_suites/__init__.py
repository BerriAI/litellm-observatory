"""Test suite implementations."""

from litellm_observatory.test_suites.base import BaseTestSuite
from litellm_observatory.test_suites.test_fake_bedrock_release import TestFakeBedrockRelease
from litellm_observatory.test_suites.test_fake_vertex_ai_release import TestFakeVertexAIRelease
from litellm_observatory.test_suites.test_mock_single_request import TestMockSingleRequest
from litellm_observatory.test_suites.test_oai_azure_release import TestOAIAzureRelease

__all__ = [
    "BaseTestSuite",
    "TestFakeBedrockRelease",
    "TestFakeVertexAIRelease",
    "TestMockSingleRequest",
    "TestOAIAzureRelease",
]
