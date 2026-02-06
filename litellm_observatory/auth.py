"""Authentication for the LiteLLM Observatory API."""

import os
from typing import Optional

from fastapi import Header, HTTPException, Security
from fastapi.security import APIKeyHeader

# API key header name
API_KEY_HEADER_NAME = "X-LiteLLM-Observatory-API-Key"

# Create API key header security scheme
api_key_header = APIKeyHeader(name=API_KEY_HEADER_NAME, auto_error=False)


def get_api_key_from_env() -> Optional[str]:
    """
    Get API key from environment variable.

    Returns:
        API key if set, None otherwise
    """
    return os.getenv("OBSERVATORY_API_KEY")


def verify_api_key(api_key: Optional[str] = Security(api_key_header)) -> str:
    """
    Verify the API key from the request header.

    Args:
        api_key: API key from the X-LiteLLM-Observatory-API-Key header

    Returns:
        The verified API key

    Raises:
        HTTPException: If API key is missing or invalid
    """
    expected_api_key = get_api_key_from_env()

    # If no API key is configured in environment, skip authentication
    if expected_api_key is None:
        return "authenticated"

    # If API key is required but not provided
    if api_key is None:
        raise HTTPException(
            status_code=401,
            detail=f"Missing API key. Please provide '{API_KEY_HEADER_NAME}' header.",
        )

    # If API key doesn't match
    if api_key != expected_api_key:
        raise HTTPException(
            status_code=401,
            detail="Invalid API key.",
        )

    return api_key
