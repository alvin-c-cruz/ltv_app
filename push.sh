#!/bin/sh
# Bumps the patch version in the VERSION file only.
# Stage and commit VERSION yourself alongside your other changes.

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
echo "Version bumped $CURRENT → $NEW_VERSION"
