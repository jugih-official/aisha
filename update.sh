#!/usr/bin/env bash
# update.sh — pull the latest aisha from GitHub and reinstall it the way it was installed:
#   from the Debian package     -> rebuilds the package and installs it (./install.sh --deb)
#   as a /usr/local copy        -> copies it there again (./install.sh --local)
# ./update.sh deb | local  overrides the guess.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

green()  { printf '\033[1;32m%s\033[0m\n' "$*"; }
yellow() { printf '\033[1;33m%s\033[0m\n' "$*"; }
red()    { printf '\033[1;31m%s\033[0m\n' "$*"; }
dim()    { printf '\033[2m%s\033[0m\n' "$*"; }

if [ ! -d .git ]; then
    red "error: $SCRIPT_DIR is not a git checkout."
    echo "Clone the repo first:  git clone https://github.com/jugih-official/aisha.git"
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
mode="${1:-}"
if [ -z "$mode" ]; then
    if dpkg -S /usr/bin/aisha >/dev/null 2>&1; then
        mode=deb
    elif [ -e /usr/local/bin/aisha ]; then
        mode=local
    else
        mode=auto
    fi
fi
case "$mode" in
    deb)        AISHA_UPDATING=1 ./install.sh --deb ;;
    local)      AISHA_UPDATING=1 ./install.sh --local ;;
    auto|aisha) AISHA_UPDATING=1 ./install.sh ;;
    *) red "unknown mode: $mode (use deb or local)"; exit 2 ;;
esac
if [ -e /usr/local/bin/ai ] || [ -e /usr/local/bin/ai-code ]; then
    dim "The old ai tools are still in /usr/local/bin; ./uninstall.sh offers to remove them."
fi
