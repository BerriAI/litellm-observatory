"""Test to ensure all environment variables are documented in ENVIRONMENT_VARIABLES.md."""

import re
from pathlib import Path

import pytest


def _find_os_getenv_calls(directory: Path) -> set[str]:
    """Find all os.getenv() calls in Python files and extract environment variable names."""
    env_vars = set()

    # Pattern to match os.getenv("VAR_NAME") or os.getenv("VAR_NAME", "default")
    # This handles both single and double quotes, and accounts for potential whitespace and default values
    pattern = r'os\.getenv\s*\(\s*["\']([^"\']+)["\']'

    for py_file in directory.rglob("*.py"):
        # Skip test files and __pycache__
        if "test" in py_file.name or "__pycache__" in str(py_file):
            continue

        try:
            content = py_file.read_text(encoding="utf-8")
            # Find all matches of os.getenv("VAR_NAME")
            matches = re.findall(pattern, content)
            env_vars.update(matches)
        except (UnicodeDecodeError):
            # Skip files that can't be read
            continue

    return env_vars


def test_all_environment_variables_documented():
    """Verify that all environment variables used in code are documented in ENVIRONMENT_VARIABLES.md."""
    # Get the path to ENVIRONMENT_VARIABLES.md
    repo_root = Path(__file__).parent.parent
    env_vars_doc = repo_root / "docs" / "ENVIRONMENT_VARIABLES.md"

    # Read the documentation file
    content = env_vars_doc.read_text()

    # Extract environment variable names from the documentation
    # Pattern matches: - **VAR_NAME**: description
    documented_vars = re.findall(r"- \*\*(\w+)\*\*:", content)

    # Find all environment variables used in the codebase
    litellm_observatory_dir = repo_root / "litellm_observatory"
    used_vars = _find_os_getenv_calls(litellm_observatory_dir)

    # Check that all used variables are documented
    documented_set = set(documented_vars)
    missing_vars = used_vars - documented_set

    assert (
        not missing_vars
    ), f"The following environment variables are used in code but not documented in ENVIRONMENT_VARIABLES.md: {missing_vars}"

    # Also check that there are no extra documented variables (not used in code)
    extra_vars = documented_set - used_vars
    if extra_vars:
        pytest.fail(
            f"The following environment variables are documented but not used in code: {extra_vars}"
        )
