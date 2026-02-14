"""
Access Group Performance Test Suite - measures auth overhead from access group resolution.

Access groups introduce additional DB lookups on the critical request path. When a key or
team has `access_group_ids` and native model permissions don't satisfy the request, the
proxy falls back to resolving each access group via `get_access_object()` — one
`find_unique` call per group (cache-first, 10-min TTL).

This test compares latency across scenarios to quantify that overhead:

  A. Baseline: key/team with NO access groups, calling a natively allowed model.
  B. Access groups present but native check passes (should add zero overhead).
  C. Access group fallback success: model only reachable via an access group.
  D. Access group fallback failure: model not in native or any access group (denied).

For failure scenarios, the proxy returns an error without calling any provider, so the
measured latency is pure proxy auth overhead.

Pre-requisites:
  - A running LiteLLM proxy with the access group feature enabled.
  - The keys, teams, and access groups described in access_group_perf_test_plan.md
    must already exist on the proxy.
"""

import asyncio
import statistics
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

from litellm_observatory.test_suites.base import BaseTestSuite

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TEST_NAME = "Access Group Performance Test"

DEFAULT_REQUESTS_PER_SCENARIO = 50
DEFAULT_REQUEST_INTERVAL_SECONDS = 0.2
HTTP_REQUEST_TIMEOUT_SECONDS = 60.0
HTTP_SUCCESS_STATUS_CODE = 200
DEFAULT_MAX_TOKENS = 10
DEFAULT_TEST_MESSAGE = "Say 'hello' and nothing else."

PROGRESS_REPORT_INTERVAL = 10

# A model name that does NOT exist on the proxy or in any access group.
NONEXISTENT_MODEL = "nonexistent-model-for-perf-test"


# ---------------------------------------------------------------------------
# Scenario definition
# ---------------------------------------------------------------------------


@dataclass
class Scenario:
    """A single test scenario to benchmark."""

    name: str
    api_key: str
    model: str
    expect_success: bool
    description: str = ""


@dataclass
class ScenarioResult:
    """Collected results for one scenario."""

    scenario: Scenario
    durations: List[float] = field(default_factory=list)
    successes: int = 0
    failures: int = 0
    errors: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Test suite
# ---------------------------------------------------------------------------


class TestAccessGroupPerf(BaseTestSuite):
    """
    Measures the latency impact of access group resolution on the auth path.

    Runs a configurable number of sequential requests for each scenario and
    produces per-scenario latency statistics (p50 / p95 / p99, mean, min, max)
    plus a cross-scenario comparison.
    """

    def __init__(
        self,
        deployment_url: str,
        api_key: str,  # unused — each scenario carries its own key
        scenarios: List[Scenario],
        requests_per_scenario: int = DEFAULT_REQUESTS_PER_SCENARIO,
        request_interval_seconds: float = DEFAULT_REQUEST_INTERVAL_SECONDS,
    ):
        super().__init__(deployment_url, api_key)
        self.scenarios = scenarios
        self.requests_per_scenario = requests_per_scenario
        self.request_interval_seconds = request_interval_seconds

        self.scenario_results: Dict[str, ScenarioResult] = {}
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def run(self, **params: Any) -> Dict[str, Any]:
        """Run all scenarios sequentially and return aggregated results."""
        self.start_time = datetime.now()
        self._print_test_start_info()

        for scenario in self.scenarios:
            result = await self._run_scenario(scenario)
            self.scenario_results[scenario.name] = result

        self.end_time = datetime.now()
        return self._calculate_results()

    # ------------------------------------------------------------------
    # Scenario runner
    # ------------------------------------------------------------------

    async def _run_scenario(self, scenario: Scenario) -> ScenarioResult:
        """Run *requests_per_scenario* requests for a single scenario."""
        print(f"\n{'='*60}")
        print(f"Scenario: {scenario.name}")
        print(f"  model={scenario.model}  expect_success={scenario.expect_success}")
        print(f"  description: {scenario.description}")
        print(f"  requests: {self.requests_per_scenario}")
        print(f"{'='*60}")

        result = ScenarioResult(scenario=scenario)
        async with httpx.AsyncClient(timeout=HTTP_REQUEST_TIMEOUT_SECONDS) as client:
            for i in range(1, self.requests_per_scenario + 1):
                req_result = await self._make_request(client, scenario)
                result.durations.append(req_result["duration_seconds"])
                if req_result["success"]:
                    result.successes += 1
                else:
                    result.failures += 1
                    if req_result.get("error"):
                        result.errors.append(str(req_result["error"]))

                if i % PROGRESS_REPORT_INTERVAL == 0:
                    self._print_scenario_progress(scenario.name, i, result)

                await asyncio.sleep(self.request_interval_seconds)

        self._print_scenario_summary(scenario.name, result)
        return result

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    async def _make_request(
        self, client: httpx.AsyncClient, scenario: Scenario
    ) -> Dict[str, Any]:
        """Make a single chat completion request for the given scenario."""
        url = self.get_endpoint_url("/v1/chat/completions")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {scenario.api_key}",
        }
        payload = {
            "model": scenario.model,
            "messages": [{"role": "user", "content": DEFAULT_TEST_MESSAGE}],
            "max_tokens": DEFAULT_MAX_TOKENS,
        }

        request_start = time.time()
        try:
            response = await client.post(url, json=payload, headers=headers)
            duration = time.time() - request_start

            success = response.status_code == HTTP_SUCCESS_STATUS_CODE
            error = None
            if not success:
                try:
                    error = response.json()
                except Exception:
                    error = response.text

            return {
                "success": success,
                "status_code": response.status_code,
                "duration_seconds": duration,
                "error": error,
            }
        except Exception as e:
            duration = time.time() - request_start
            return {
                "success": False,
                "status_code": None,
                "duration_seconds": duration,
                "error": str(e),
            }

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    @staticmethod
    def _latency_stats(durations: List[float]) -> Dict[str, float]:
        """Compute latency statistics from a list of durations (seconds)."""
        if not durations:
            return {}
        sorted_d = sorted(durations)
        return {
            "count": len(sorted_d),
            "min_ms": sorted_d[0] * 1000,
            "max_ms": sorted_d[-1] * 1000,
            "mean_ms": statistics.mean(sorted_d) * 1000,
            "median_ms": statistics.median(sorted_d) * 1000,
            "p95_ms": _percentile(sorted_d, 0.95) * 1000,
            "p99_ms": _percentile(sorted_d, 0.99) * 1000,
            "stdev_ms": (statistics.stdev(sorted_d) * 1000) if len(sorted_d) > 1 else 0.0,
        }

    def _calculate_results(self) -> Dict[str, Any]:
        """Aggregate results across all scenarios."""
        scenario_stats: Dict[str, Any] = {}
        for name, result in self.scenario_results.items():
            stats = self._latency_stats(result.durations)
            scenario_stats[name] = {
                "description": result.scenario.description,
                "model": result.scenario.model,
                "expect_success": result.scenario.expect_success,
                "total_requests": result.successes + result.failures,
                "successes": result.successes,
                "failures": result.failures,
                "latency": stats,
                "sample_errors": result.errors[:5],  # first 5 unique-ish errors
            }

        duration_seconds = self._calculate_test_duration()
        return {
            "test_name": TEST_NAME,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_seconds": duration_seconds,
            "requests_per_scenario": self.requests_per_scenario,
            "scenario_count": len(self.scenarios),
            "scenarios": scenario_stats,
        }

    def _calculate_test_duration(self) -> float:
        if self.end_time and self.start_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0.0

    # ------------------------------------------------------------------
    # Printing helpers
    # ------------------------------------------------------------------

    def _print_test_start_info(self) -> None:
        print(f"\nStarting {TEST_NAME}")
        print(f"  Deployment: {self.deployment_url}")
        print(f"  Scenarios:  {len(self.scenarios)}")
        print(f"  Requests per scenario: {self.requests_per_scenario}")
        print(f"  Interval:   {self.request_interval_seconds}s")
        est = len(self.scenarios) * self.requests_per_scenario * self.request_interval_seconds
        print(f"  Estimated minimum runtime: {est:.0f}s (excludes response time)")

    def _print_scenario_progress(
        self, name: str, completed: int, result: ScenarioResult
    ) -> None:
        recent = result.durations[-PROGRESS_REPORT_INTERVAL:]
        avg_ms = statistics.mean(recent) * 1000
        print(
            f"  [{name}] {completed}/{self.requests_per_scenario} done  "
            f"last-{PROGRESS_REPORT_INTERVAL} avg={avg_ms:.1f}ms  "
            f"ok={result.successes} fail={result.failures}"
        )

    def _print_scenario_summary(self, name: str, result: ScenarioResult) -> None:
        stats = self._latency_stats(result.durations)
        print(f"\n  [{name}] DONE — {result.successes} ok, {result.failures} fail")
        if stats:
            print(
                f"  latency: p50={stats['median_ms']:.1f}ms  "
                f"p95={stats['p95_ms']:.1f}ms  p99={stats['p99_ms']:.1f}ms  "
                f"mean={stats['mean_ms']:.1f}ms"
            )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _percentile(sorted_data: List[float], p: float) -> float:
    """Compute the p-th percentile from already-sorted data."""
    if not sorted_data:
        return 0.0
    k = (len(sorted_data) - 1) * p
    f = int(k)
    c = f + 1
    if c >= len(sorted_data):
        return sorted_data[-1]
    return sorted_data[f] + (k - f) * (sorted_data[c] - sorted_data[f])


# ---------------------------------------------------------------------------
# Pre-built scenario factory
# ---------------------------------------------------------------------------


def build_default_scenarios() -> List[Scenario]:
    """
    Build the default set of scenarios from the test plan.

    These reference the keys, teams, and access groups that must already
    exist on the proxy.  See access_group_perf_test_plan.md for setup.
    """

    # ---- Keys ----
    KEY_NO_AG = "sk-ctGZv4EFE97raVgHIzeZHg"          # models=["gpt-4o"], no access groups
    KEY_WITH_AG = "sk-e3QqXXZzSU2gmM3lnq-RcQ"        # models=["gpt-4o"], ag1+ag2
    TEAM_KEY_NO_AG = "sk-FvJ0wU_IiFwCwXO50KEPBw"      # team has no access groups
    TEAM_KEY_WITH_AG = "sk-fNCzqA43eJjx9qCFEwWJ5Q"    # team has ag1+ag2

    # ---- Models ----
    NATIVE_MODEL = "gpt-4o"                            # on every key/team natively
    AG_MODEL = "bedrock-claude-sonnet-4"                # only reachable via ag1
    DENIED_MODEL = NONEXISTENT_MODEL                    # not anywhere

    return [
        # --- A: Baseline (no access groups) ---
        Scenario(
            name="A1_key_no_ag_native_model",
            api_key=KEY_NO_AG,
            model=NATIVE_MODEL,
            expect_success=True,
            description="Key without access groups calls natively allowed model. Pure baseline.",
        ),
        Scenario(
            name="A2_team_key_no_ag_native_model",
            api_key=TEAM_KEY_NO_AG,
            model=NATIVE_MODEL,
            expect_success=True,
            description="Key in team without access groups calls natively allowed model. Team baseline.",
        ),
        # --- B: Access groups present, native check passes ---
        Scenario(
            name="B1_key_with_ag_native_model",
            api_key=KEY_WITH_AG,
            model=NATIVE_MODEL,
            expect_success=True,
            description="Key has access groups but calls natively allowed model. AGs should NOT be resolved.",
        ),
        Scenario(
            name="B2_team_key_with_ag_native_model",
            api_key=TEAM_KEY_WITH_AG,
            model=NATIVE_MODEL,
            expect_success=True,
            description="Key in team with access groups calls natively allowed model. AGs should NOT be resolved.",
        ),
        # --- C: Access group fallback (success) ---
        Scenario(
            name="C1_key_with_ag_ag_model",
            api_key=KEY_WITH_AG,
            model=AG_MODEL,
            expect_success=True,
            description="Key calls model only available via access group. Measures AG fallback cost.",
        ),
        Scenario(
            name="C2_team_key_with_ag_ag_model",
            api_key=TEAM_KEY_WITH_AG,
            model=AG_MODEL,
            expect_success=True,
            description="Key in team with AGs calls model only in access group. Team-side AG fallback.",
        ),
        # --- D: Access group fallback (failure / denied) ---
        Scenario(
            name="D1_key_with_ag_denied_model",
            api_key=KEY_WITH_AG,
            model=DENIED_MODEL,
            expect_success=False,
            description="Key with AGs calls model not in native or any AG. Full resolution then deny.",
        ),
        Scenario(
            name="D2_team_key_with_ag_denied_model",
            api_key=TEAM_KEY_WITH_AG,
            model=DENIED_MODEL,
            expect_success=False,
            description="Team key with AGs calls model not anywhere. Full resolution then deny.",
        ),
    ]
