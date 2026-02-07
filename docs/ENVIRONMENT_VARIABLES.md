# Environment Variables

This document describes all environment variables used by LiteLLM Observatory.

## Variables

- **SLACK_WEBHOOK_URL**: Slack webhook URL for test result notifications (required for `/run-test` endpoint)
- **OBSERVATORY_API_KEY**: API key for authentication (optional - if not set, authentication is disabled)
- **MAX_CONCURRENT_TESTS**: Maximum number of tests that can run simultaneously (default: 5)