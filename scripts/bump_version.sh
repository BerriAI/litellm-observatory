#!/usr/bin/env bash
# Usage: ./scripts/bump_version.sh [patch|minor|major]
set -euo pipefail

BUMP=${1:-patch}

if [[ ! "$BUMP" =~ ^(patch|minor|major)$ ]]; then
  echo "Usage: $0 [patch|minor|major]"
  exit 1
fi

# Bump version in pyproject.toml via Poetry
poetry version "$BUMP"

# Read the new version
NEW_VERSION=$(poetry version --short)

# Sync APP_VERSION in server.py
sed -i '' "s/^APP_VERSION = \".*\"/APP_VERSION = \"$NEW_VERSION\"/" litellm_observatory/server.py

echo "Bumped to $NEW_VERSION"

# Commit and push
git add pyproject.toml litellm_observatory/server.py
git commit -m "Release v$NEW_VERSION"
git tag "v$NEW_VERSION"
git push origin main --tags
