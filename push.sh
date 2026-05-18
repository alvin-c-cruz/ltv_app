#!/bin/sh
# Bumps the patch version, commits it, then pushes to GitHub.
# Use this instead of "git push".

REPO_ROOT="$(git rev-parse --show-toplevel)"
VERSION_FILE="$REPO_ROOT/VERSION"

if [ ! -f "$VERSION_FILE" ]; then
    echo "ERROR: VERSION file not found at $VERSION_FILE"
    exit 1
fi

CURRENT=$(cat "$VERSION_FILE")
MAJOR=$(echo "$CURRENT" | cut -d. -f1)
MINOR=$(echo "$CURRENT" | cut -d. -f2)
PATCH=$(echo "$CURRENT" | cut -d. -f3)
NEW_PATCH=$((PATCH + 1))
NEW_VERSION="$MAJOR.$MINOR.$NEW_PATCH"

echo "$NEW_VERSION" > "$VERSION_FILE"
git add "$VERSION_FILE"
git commit -m "Bump version to $NEW_VERSION"
git push
echo "Pushed version $CURRENT → $NEW_VERSION"
