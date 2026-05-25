#!/usr/bin/env bash
# update.sh — pull the latest version from GitHub and reinstall.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

green()  { printf '\033[1;32m%s\033[0m\n' "$*"; }
yellow() { printf '\033[1;33m%s\033[0m\n' "$*"; }
red()    { printf '\033[1;31m%s\033[0m\n' "$*"; }
dim()    { printf '\033[2m%s\033[0m\n' "$*"; }

if [ ! -d .git ]; then
    red "error: $SCRIPT_DIR is not a git checkout."
    echo "Clone the repo first:  git clone https://github.com/jugih-official/ai-bash.git"
    exit 1
fi

# Refuse to overwrite uncommitted local edits — they're likely the user's work.
if ! git diff --quiet || ! git diff --cached --quiet; then
    red "error: you have uncommitted local changes in $SCRIPT_DIR."
    git status --short
    echo
    echo "Commit, stash, or discard them before updating."
    exit 1
fi

BEFORE="$(git rev-parse HEAD)"
echo "Fetching latest from origin…"
git pull --ff-only
AFTER="$(git rev-parse HEAD)"

if [ "$BEFORE" = "$AFTER" ]; then
    dim "Already up to date ($AFTER)."
else
    green "Updated $BEFORE → $AFTER"
    echo
    git --no-pager log --oneline "$BEFORE..$AFTER"
fi

echo
./install.sh
