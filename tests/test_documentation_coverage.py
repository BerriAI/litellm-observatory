"""Test to ensure all test suites are documented in TEST_COVERAGE.md."""

import re
from pathlib import Path

import pytest

from litellm_observatory.models import TEST_SUITE_REGISTRY


def test_all_test_suites_documented():
    """Verify that all test suites in the registry are documented in TEST_COVERAGE.md."""
    # Get the path to TEST_COVERAGE.md
    repo_root = Path(__file__).parent.parent
    coverage_doc = repo_root / "docs" / "TEST_COVERAGE.md"

    # Read the documentation file
    content = coverage_doc.read_text()

    # Extract test suite names from the documentation
    # Pattern matches: - **TestSuiteName**: description
    documented_tests = re.findall(r"- \*\*(\w+)\*\*:", content)

    # Get all test suite names from the registry
    registered_tests = set(TEST_SUITE_REGISTRY.keys())

    # Check that all registered tests are documented
    documented_set = set(documented_tests)
    missing_tests = registered_tests - documented_set

    assert (
        not missing_tests
    ), f"The following test suites are registered but not documented in TEST_COVERAGE.md: {missing_tests}"

    # Also check that there are no extra documented tests (not in registry)
    extra_tests = documented_set - registered_tests
    if extra_tests:
        pytest.fail(
            f"The following test suites are documented but not in the registry: {extra_tests}"
        )
