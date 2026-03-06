"""
MCP release test suite - long-running reliability test for MCP tool discovery.

Continuously polls the MCP tools endpoint for the specified duration and verifies
that configured MCP servers have discoverable tools. Catches regressions in:
- MCP tool listing endpoint (/v1/mcp/tools)
- Authentication flow for MCP endpoints
- MCP server tool availability over time

The `models` parameter is repurposed as a list of MCP server names to verify
(e.g., ["deepwiki", "zapier"]). Each server name is treated as a separate
"model" for statistics purposes.
"""

import asyncio
import math
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import httpx

from litellm_observatory.test_suites.base import BaseTestSuite

# Test configuration constants
DEFAULT_DURATION_HOURS = 3.0
DEFAULT_MAX_FAILURE_RATE = 0.01  # 1%
DEFAULT_REQUEST_INTERVAL_SECONDS = 30.0

# HTTP request constants
HTTP_REQUEST_TIMEOUT_SECONDS = 30.0
HTTP_SUCCESS_STATUS_CODE = 200

# MCP endpoint paths
MCP_TOOLS_LIST_ENDPOINT = "/v1/mcp/tools"

# Progress reporting constants
PROGRESS_REPORT_INTERVAL = 10  # Report progress every N requests

# Test metadata
TEST_NAME = "MCP Release Test"


class TestMCPRelease(BaseTestSuite):
    """
    MCP release reliability test.

    Continuously polls /v1/mcp/tools for the specified duration, verifying that
    each configured MCP server has at least one discoverable tool. Failure rate
    must stay below max_failure_rate for the test to pass.

    The `models` parameter is repurposed as a list of MCP server names to verify.
    If empty, only the tools endpoint health is checked on each iteration.
    """

    def __init__(
        self,
        deployment_url: str,
        api_key: str,
        models: List[str],
        duration_hours: float = DEFAULT_DURATION_HOURS,
        max_failure_rate: float = DEFAULT_MAX_FAILURE_RATE,
        request_interval_seconds: float = DEFAULT_REQUEST_INTERVAL_SECONDS,
    ):
        super().__init__(deployment_url, api_key)
        self.mcp_server_names = models
        self.duration_hours = duration_hours
        self.max_failure_rate = max_failure_rate
        self.request_interval_seconds = request_interval_seconds

        # Track results per MCP server name (mirrors per-model tracking in TestOAIAzureRelease)
        check_keys = models if models else ["_tools_endpoint"]
        self.results: Dict[str, List[Dict[str, Any]]] = {key: [] for key in check_keys}
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None

        self.client: Optional[httpx.AsyncClient] = None

    # Test execution

    async def run(self, **params: Any) -> Dict[str, Any]:
        """Run the MCP reliability test for the specified duration."""
        self.start_time = datetime.now()
        end_time = self.start_time + timedelta(hours=self.duration_hours)

        self._print_test_start_info(end_time)

        server_index = 0
        while datetime.now() < end_time:
            tools = await self._fetch_tools()

            if self.mcp_server_names:
                server = self._get_next_server(server_index)
                server_index += 1
                result = self._check_server_tools(server, tools)
                self.results[server].append(result)

                if self._should_report_progress(server):
                    self._print_progress(server)
            else:
                result = {
                    "timestamp": datetime.now().isoformat(),
                    "model": "_tools_endpoint",
                    "success": tools is not None,
                    "duration_seconds": 0.0,
                    "error": None if tools is not None else "Failed to fetch tools",
                }
                self.results["_tools_endpoint"].append(result)

            await asyncio.sleep(self.request_interval_seconds)

        self.end_time = datetime.now()
        await self._cleanup_resources()

        return self._calculate_results()

    # Request methods

    async def _fetch_tools(self) -> Optional[List[Dict[str, Any]]]:
        """GET /v1/mcp/tools and return the tools list, or None on failure."""
        url = self.get_endpoint_url(MCP_TOOLS_LIST_ENDPOINT)
        headers = self.get_headers()
        try:
            self._ensure_http_client_exists()
            response = await self.client.get(url, headers=headers)
            if response.status_code != HTTP_SUCCESS_STATUS_CODE:
                return None
            data = response.json()
            tools = data.get("tools", [])
            return tools if isinstance(tools, list) else None
        except Exception:
            return None

    def _check_server_tools(
        self, server_name: str, tools: Optional[List[Dict[str, Any]]]
    ) -> Dict[str, Any]:
        """Check whether tools are available for the given MCP server name."""
        timestamp = datetime.now().isoformat()

        if tools is None:
            return {
                "timestamp": timestamp,
                "model": server_name,
                "success": False,
                "duration_seconds": 0.0,
                "error": "Failed to fetch tools list",
            }

        matching = [
            t for t in tools
            if isinstance(t.get("name"), str) and t["name"].startswith(server_name)
        ]
        passed = len(matching) > 0
        return {
            "timestamp": timestamp,
            "model": server_name,
            "success": passed,
            "duration_seconds": 0.0,
            "matching_tool_count": len(matching),
            "error": None if passed else f"No tools found for MCP server '{server_name}'",
        }

    def _ensure_http_client_exists(self) -> None:
        if self.client is None:
            self.client = httpx.AsyncClient(timeout=HTTP_REQUEST_TIMEOUT_SECONDS)

    # Helper methods

    def _get_next_server(self, index: int) -> str:
        return self.mcp_server_names[index % len(self.mcp_server_names)]

    def _should_report_progress(self, server_name: str) -> bool:
        return len(self.results[server_name]) % PROGRESS_REPORT_INTERVAL == 0

    def _print_progress(self, server_name: str) -> None:
        elapsed_hours = (datetime.now() - self.start_time).total_seconds() / 3600
        total_requests = sum(len(r) for r in self.results.values())
        print(
            f"[{elapsed_hours:.2f}h elapsed] Total checks: {total_requests}, "
            f"Current server: {server_name}"
        )

    def _print_test_start_info(self, end_time: datetime) -> None:
        print(
            f"Starting MCP release test for {self.duration_hours} hours"
            f" on MCP servers: {', '.join(self.mcp_server_names) or '(endpoint health only)'}"
        )
        print(f"Test will run until: {end_time.isoformat()}")
        print(f"Maximum acceptable failure rate: {self.max_failure_rate * 100}%")

    async def _cleanup_resources(self) -> None:
        if self.client:
            await self.client.aclose()

    # Statistics

    def _calculate_model_statistics(self, key: str, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        successes = sum(1 for r in results if r["success"])
        failures = len(results) - successes
        total = len(results)
        failure_rate = failures / total if total > 0 else 0.0
        avg_duration = sum(r["duration_seconds"] for r in results) / total if total > 0 else 0.0

        stats = {
            "total_requests": total,
            "successes": successes,
            "failures": failures,
            "failure_rate": failure_rate,
            "failure_rate_percent": failure_rate * 100,
            "avg_duration_seconds": avg_duration,
        }

        durations = [r["duration_seconds"] for r in results if r.get("duration_seconds") is not None]
        if durations:
            stats["latency_percentiles"] = self._calculate_latency_percentiles(durations)

        return stats

    def _calculate_overall_statistics(self) -> tuple[int, int, int, float]:
        total_requests = total_successes = total_failures = 0
        for results in self.results.values():
            stats = self._calculate_model_statistics("", results)
            total_requests += stats["total_requests"]
            total_successes += stats["successes"]
            total_failures += stats["failures"]
        overall_failure_rate = total_failures / total_requests if total_requests > 0 else 0.0
        return total_requests, total_successes, total_failures, overall_failure_rate

    def _calculate_test_duration(self) -> float:
        if self.end_time and self.start_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0.0

    def _calculate_latency_percentiles(self, durations: List[float]) -> Dict[str, float]:
        if not durations:
            return {"p50": 0.0, "p95": 0.0, "p99": 0.0, "max": 0.0}
        sorted_d = sorted(durations)
        n = len(sorted_d)

        def _percentile(p: float) -> float:
            idx = (p / 100.0) * (n - 1)
            lower = int(math.floor(idx))
            upper = min(lower + 1, n - 1)
            frac = idx - lower
            return sorted_d[lower] + frac * (sorted_d[upper] - sorted_d[lower])

        return {
            "p50": round(_percentile(50), 4),
            "p95": round(_percentile(95), 4),
            "p99": round(_percentile(99), 4),
            "max": round(sorted_d[-1], 4),
        }

    def _calculate_latency_over_time(self) -> List[Dict[str, Any]]:
        all_results: List[Dict[str, Any]] = []
        for model_results in self.results.values():
            all_results.extend(model_results)

        if not all_results or not self.start_time:
            return []

        bucket_seconds = 600
        buckets: Dict[int, List[Dict[str, Any]]] = {}

        for r in all_results:
            try:
                ts = datetime.fromisoformat(r["timestamp"])
            except (KeyError, ValueError):
                continue
            offset = (ts - self.start_time).total_seconds()
            bucket_idx = int(offset // bucket_seconds)
            buckets.setdefault(bucket_idx, []).append(r)

        result = []
        for idx in sorted(buckets.keys()):
            items = buckets[idx]
            durations = [r["duration_seconds"] for r in items if r.get("duration_seconds") is not None]
            failures = sum(1 for r in items if not r.get("success", True))
            avg_lat = sum(durations) / len(durations) if durations else 0.0
            p95_lat = self._calculate_latency_percentiles(durations).get("p95", 0.0) if durations else 0.0
            window_start = self.start_time + timedelta(seconds=idx * bucket_seconds)
            result.append({
                "window_start": window_start.isoformat(),
                "avg_latency": round(avg_lat, 4),
                "p95_latency": round(p95_lat, 4),
                "request_count": len(items),
                "failure_count": failures,
            })

        return result

    def _categorize_errors(self) -> Dict[str, int]:
        categories: Dict[str, int] = {}
        for model_results in self.results.values():
            for r in model_results:
                if r.get("success", True):
                    continue
                error_str = str(r.get("error", "")).lower()
                status_code = r.get("status_code")
                if "timeout" in error_str or "timed out" in error_str:
                    cat = "timeout"
                elif "connection refused" in error_str or "connect call failed" in error_str:
                    cat = "connection_refused"
                elif "no tools found" in error_str:
                    cat = "no_tools_found"
                elif isinstance(status_code, int) and 400 <= status_code < 500:
                    cat = "4xx"
                elif isinstance(status_code, int) and 500 <= status_code < 600:
                    cat = "5xx"
                else:
                    cat = "other"
                categories[cat] = categories.get(cat, 0) + 1
        return categories

    def _calculate_first_failure_timing(self) -> Optional[Dict[str, Any]]:
        earliest: Optional[Dict[str, Any]] = None
        earliest_ts: Optional[datetime] = None

        for server, server_results in self.results.items():
            for r in server_results:
                if r.get("success", True):
                    continue
                try:
                    ts = datetime.fromisoformat(r["timestamp"])
                except (KeyError, ValueError):
                    continue
                if earliest_ts is None or ts < earliest_ts:
                    earliest_ts = ts
                    earliest = {
                        "timestamp": r["timestamp"],
                        "minutes_after_start": round(
                            (ts - self.start_time).total_seconds() / 60, 2
                        ) if self.start_time else None,
                        "model": server,
                        "error_snippet": str(r.get("error", ""))[:200],
                    }

        return earliest

    def _calculate_results(self) -> Dict[str, Any]:
        total_requests, total_successes, total_failures, overall_failure_rate = (
            self._calculate_overall_statistics()
        )

        model_stats = {
            key: self._calculate_model_statistics(key, results)
            for key, results in self.results.items()
        }

        test_passed = overall_failure_rate < self.max_failure_rate
        duration_seconds = self._calculate_test_duration()

        all_durations = [
            r["duration_seconds"]
            for model_results in self.results.values()
            for r in model_results
            if r.get("duration_seconds") is not None
        ]

        return {
            "test_name": TEST_NAME,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_seconds": duration_seconds,
            "duration_hours": duration_seconds / 3600,
            "models_tested": self.mcp_server_names,
            "total_requests": total_requests,
            "total_successes": total_successes,
            "total_failures": total_failures,
            "overall_failure_rate": overall_failure_rate,
            "overall_failure_rate_percent": overall_failure_rate * 100,
            "max_failure_rate": self.max_failure_rate,
            "max_failure_rate_percent": self.max_failure_rate * 100,
            "test_passed": test_passed,
            "model_statistics": model_stats,
            "latency_percentiles": self._calculate_latency_percentiles(all_durations),
            "latency_over_time": self._calculate_latency_over_time(),
            "error_categories": self._categorize_errors(),
            "first_failure": self._calculate_first_failure_timing(),
            "detailed_results": self.results,
        }
