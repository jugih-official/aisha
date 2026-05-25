#!/usr/bin/env bash
# install.sh — install `ai` system-wide so it (and `sudo ai`) work everywhere.
set -euo pipefail

BIN_TARGET=/usr/local/bin/ai
CFG_DIR_USER="$HOME/.config/ai-bash"
CFG_KEY_USER="$CFG_DIR_USER/api-key"

SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_BIN="$SRC_DIR/ai"

red()    { printf '\033[1;31m%s\033[0m\n' "$*"; }
green()  { printf '\033[1;32m%s\033[0m\n' "$*"; }
yellow() { printf '\033[1;33m%s\033[0m\n' "$*"; }
dim()    { printf '\033[2m%s\033[0m\n' "$*"; }

die() { red "error: $*"; exit 1; }

# --- preflight --------------------------------------------------------------
[ -f "$SRC_BIN" ] || die "cannot find $SRC_BIN"
command -v python3 >/dev/null 2>&1 || die "python3 is required but not installed"
command -v sudo    >/dev/null 2>&1 || die "sudo is required for system install"

PY_VER="$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
PY_MAJOR="${PY_VER%%.*}"; PY_MINOR="${PY_VER##*.}"
if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 10 ]; }; then
    die "python 3.10+ required (found $PY_VER)"
fi

# --- install binary ---------------------------------------------------------
echo "Installing $SRC_BIN -> $BIN_TARGET"
sudo install -m 0755 "$SRC_BIN" "$BIN_TARGET"
green "  installed."

# --- API key handling -------------------------------------------------------
have_key=0
if [ -n "${DEEPSEEK_API_KEY:-}" ]; then
    have_key=1
    dim "  \$DEEPSEEK_API_KEY is set in your environment."
elif [ -s "$CFG_KEY_USER" ]; then
    have_key=1
    dim "  user key file already exists at $CFG_KEY_USER"
elif [ -s /etc/ai-bash/api-key ]; then
    have_key=1
    dim "  system key file already exists at /etc/ai-bash/api-key"
fi

if [ "$have_key" -eq 0 ]; then
    echo
    yellow "No DeepSeek API key found."
    echo "Get one at https://platform.deepseek.com/  (starts with 'sk-')"
    read -r -p "Paste your DeepSeek API key now (or press Enter to skip): " entered_key
    if [ -n "$entered_key" ]; then
        # user copy — readable by `ai` as your user
        mkdir -p "$CFG_DIR_USER"
        chmod 700 "$CFG_DIR_USER"
        printf '%s\n' "$entered_key" > "$CFG_KEY_USER"
        chmod 600 "$CFG_KEY_USER"
        green "  saved user key to $CFG_KEY_USER (mode 600)"

        # system copy — readable only by root, so `sudo ai` works too
        echo
        read -r -p "Also install key at /etc/ai-bash/api-key so 'sudo ai' works? [Y/n] " yn
        case "${yn,,}" in
            n|no) dim "  skipped system copy. Use 'sudo -E ai ...' to pass your env." ;;
            *)
                sudo install -d -m 0755 /etc/ai-bash
                printf '%s\n' "$entered_key" | sudo tee /etc/ai-bash/api-key >/dev/null
                sudo chmod 600 /etc/ai-bash/api-key
                sudo chown root:root /etc/ai-bash/api-key
                green "  saved system key to /etc/ai-bash/api-key (root:root, mode 600)"
                ;;
        esac
    else
        yellow "  skipped. Set \$DEEPSEEK_API_KEY or write the key to $CFG_KEY_USER later."
    fi
fi

# --- post-install message ---------------------------------------------------
echo
green "Done."
echo "Try:"
echo "    ai list files in the current directory"
echo "    ai how much RAM is free"
echo
dim "Notes:"
dim "  - 'ai ...'      reads the key from \$DEEPSEEK_API_KEY or ~/.config/ai-bash/api-key"
dim "  - 'sudo ai ...' reads the key from /etc/ai-bash/api-key (no need for 'sudo -E')"
