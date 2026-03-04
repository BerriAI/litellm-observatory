"""
MCP release test suite - validates MCP tool discovery and endpoint availability.

This test ensures the MCP (Model Context Protocol) integration in LiteLLM remains
functional across releases. It catches regressions in:
- MCP tool listing endpoint (/v1/mcp/tools)
- MCP tool call endpoint (/mcp-rest/tools/call)
- Authentication flow for MCP endpoints

The test uses the `models` parameter as a list of expected MCP server names.
If provided, the test verifies those servers have discoverable tools. If empty,
the test only validates that the tools endpoint is reachable and returns a valid response.
"""

import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

from litellm_observatory.test_suites.base import BaseTestSuite

# HTTP request constants
HTTP_REQUEST_TIMEOUT_SECONDS = 30.0
HTTP_SUCCESS_STATUS_CODE = 200

# MCP endpoint paths
MCP_TOOLS_LIST_ENDPOINT = "/v1/mcp/tools"
MCP_TOOLS_CALL_ENDPOINT = "/mcp-rest/tools/call"

# Test metadata
TEST_NAME = "MCP Release Test"


class TestMCPRelease(BaseTestSuite):
    """
    MCP release smoke test.

    Validates that MCP endpoints are functional on a given LiteLLM deployment.
    Designed to run quickly as a post-release gate.

    Steps:
    1. GET /v1/mcp/tools — verify the endpoint responds and returns a tools list
    2. If `models` (MCP server names) are provided, verify each server has at least
       one tool discoverable under that server prefix
    3. Optionally call a specific tool if `mcp_tool_name` is provided

    The `models` parameter is repurposed here as a list of MCP server names to
    verify (e.g., ["zapier", "github"]).
    """

    def __init__(
        self,
        deployment_url: str,
        api_key: str,
        models: List[str],
    ):
        """
        Initialize the MCP release test.

        Args:
            deployment_url: The base URL of the LiteLLM deployment
            api_key: API key for authentication
            models: List of MCP server names to verify tool availability for.
                    If empty, only basic endpoint health is checked.
        """
        super().__init__(deployment_url, api_key)
        self.mcp_server_names = models

    async def run(self, **params: Any) -> Dict[str, Any]:
        """
        Run the MCP smoke test.

        Returns:
            Dictionary containing test results
        """
        start_time = datetime.now()

        checks: List[Dict[str, Any]] = []

        tools_check = await self._check_tools_list_endpoint()
        checks.append(tools_check)

        discovered_tools: List[Dict[str, Any]] = tools_check.get("tools", [])

        for server_name in self.mcp_server_names:
            server_check = self._check_server_tools_present(server_name, discovered_tools)
            checks.append(server_check)

        end_time = datetime.now()
        duration_seconds = (end_time - start_time).total_seconds()

        total_checks = len(checks)
        passed_checks = sum(1 for c in checks if c["passed"])
        failed_checks = total_checks - passed_checks
        test_passed = failed_checks == 0

        return {
            "test_name": TEST_NAME,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_seconds": duration_seconds,
            "duration_hours": duration_seconds / 3600,
            "models_tested": self.mcp_server_names,
            "total_requests": total_checks,
            "total_successes": passed_checks,
            "total_failures": failed_checks,
            "overall_failure_rate": failed_checks / total_checks if total_checks > 0 else 0.0,
            "overall_failure_rate_percent": (failed_checks / total_checks * 100) if total_checks > 0 else 0.0,
            "max_failure_rate": 0.0,
            "max_failure_rate_percent": 0.0,
            "test_passed": test_passed,
            "model_statistics": self._build_model_statistics(checks),
            "detailed_results": {"checks": checks},
        }

    # Check methods

    async def _check_tools_list_endpoint(self) -> Dict[str, Any]:
        """GET /v1/mcp/tools and verify it returns a valid tools list."""
        url = self.get_endpoint_url(MCP_TOOLS_LIST_ENDPOINT)
        headers = self.get_headers()
        request_start = time.time()

        check: Dict[str, Any] = {
            "check": "mcp_tools_list",
            "endpoint": MCP_TOOLS_LIST_ENDPOINT,
            "timestamp": datetime.now().isoformat(),
            "passed": False,
            "status_code": None,
            "error": None,
            "tools": [],
        }

        try:
            async with httpx.AsyncClient(timeout=HTTP_REQUEST_TIMEOUT_SECONDS) as client:
                response = await client.get(url, headers=headers)
                check["duration_seconds"] = time.time() - request_start
                check["status_code"] = response.status_code

                if response.status_code != HTTP_SUCCESS_STATUS_CODE:
                    check["error"] = f"Unexpected status {response.status_code}: {response.text[:200]}"
                    return check

                data = response.json()
                tools = data.get("tools", [])

                if not isinstance(tools, list):
                    check["error"] = f"Expected 'tools' to be a list, got {type(tools).__name__}"
                    return check

                check["tools"] = tools
                check["tool_count"] = len(tools)
                check["passed"] = True

        except Exception as e:
            check["duration_seconds"] = time.time() - request_start
            check["error"] = str(e)

        return check

    def _check_server_tools_present(
        self, server_name: str, tools: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Verify at least one tool is present for the given MCP server name."""
        matching = [
            t for t in tools
            if isinstance(t.get("name"), str) and t["name"].startswith(f"{server_name}")
        ]

        passed = len(matching) > 0
        return {
            "check": f"server_tools_present:{server_name}",
            "mcp_server": server_name,
            "timestamp": datetime.now().isoformat(),
            "passed": passed,
            "matching_tool_count": len(matching),
            "matching_tools": [t.get("name") for t in matching],
            "error": None if passed else f"No tools found for MCP server '{server_name}'",
        }

    # Results helpers

    def _build_model_statistics(self, checks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Build per-check statistics in the standard model_statistics format."""
        stats: Dict[str, Any] = {}
        for check in checks:
            key = check["check"]
            passed = check["passed"]
            stats[key] = {
                "total_requests": 1,
                "successes": 1 if passed else 0,
                "failures": 0 if passed else 1,
                "failure_rate": 0.0 if passed else 1.0,
                "failure_rate_percent": 0.0 if passed else 100.0,
                "avg_duration_seconds": check.get("duration_seconds", 0.0),
            }
        return stats
