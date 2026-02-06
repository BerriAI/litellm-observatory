"""Base test class for all test suites."""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class BaseTestSuite(ABC):
    """Abstract base class for all test suites."""

    def __init__(self, deployment_url: str, api_key: str):
        """
        Initialize the test suite.

        Args:
            deployment_url: The base URL of the LiteLLM deployment
            api_key: API key for authentication
        """
        self.deployment_url = deployment_url.rstrip("/")
        self.api_key = api_key

    @abstractmethod
    async def run(self, **params: Any) -> Dict[str, Any]:
        """
        Run the test suite.

        Args:
            **params: Test-specific parameters

        Returns:
            Dictionary containing test results
        """
        pass

    def get_endpoint_url(self, endpoint: str) -> str:
        """
        Get the full URL for an endpoint.

        Args:
            endpoint: The endpoint path (e.g., "/v1/chat/completions")

        Returns:
            Full URL
        """
        if not endpoint.startswith("/"):
            endpoint = f"/{endpoint}"
        return f"{self.deployment_url}{endpoint}"

    def get_headers(self) -> Dict[str, str]:
        """
        Get default headers including authorization.

        Returns:
            Dictionary of headers
        """
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
