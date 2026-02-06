"""Test suite implementations."""

from litellm_observatory.test_suites.base import BaseTestSuite
from litellm_observatory.test_suites.test_oai_azure_release import TestOAIAzureRelease

__all__ = ["BaseTestSuite", "TestOAIAzureRelease"]
