#!/usr/bin/env bash
# uninstall.sh — remove `ai` and (optionally) its API-key files.
set -euo pipefail

BIN_TARGET=/usr/local/bin/ai
BROWSER_BIN_TARGET=/usr/local/bin/ai-browser
DESKTOP_BIN_TARGET=/usr/local/bin/ai-desktop
CODE_BIN_TARGET=/usr/local/bin/ai-code
AISHA_BIN_TARGET=/usr/local/bin/aisha
AISHA_LIB_DIR=/usr/local/lib/aisha
AISHA_DATA_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/aisha"
BROWSER_PREFIX=/opt/ai-bash
CFG_DIR_USER="$HOME/.config/ai-bash"
CFG_DIR_SYS=/etc/ai-bash

red()    { printf '\033[1;31m%s\033[0m\n' "$*"; }
green()  { printf '\033[1;32m%s\033[0m\n' "$*"; }
yellow() { printf '\033[1;33m%s\033[0m\n' "$*"; }
dim()    { printf '\033[2m%s\033[0m\n' "$*"; }

remove_path() {
    # $1 = path, $2 = "sudo" or "user"
    local path="$1" how="$2"
    if [ ! -e "$path" ]; then
        dim "  not present: $path"
        return
    fi
    if [ "$how" = "sudo" ]; then
        sudo rm -rf -- "$path"
    else
        rm -rf -- "$path"
    fi
    green "  removed $path"
}

echo "Uninstalling aisha and the ai tools."
remove_path "$BIN_TARGET" sudo
remove_path "$BROWSER_BIN_TARGET" sudo
remove_path "$DESKTOP_BIN_TARGET" sudo
remove_path "$CODE_BIN_TARGET" sudo
remove_path "$AISHA_BIN_TARGET" sudo
remove_path "$AISHA_LIB_DIR" sudo
remove_path "$BROWSER_PREFIX" sudo

# ai-code's Modal GPU backend, if it was deployed. Offer to stop it so it
# stops reserving any resources (it already scales to zero when idle).
if command -v modal >/dev/null 2>&1 && modal profile current >/dev/null 2>&1; then
    if modal app list 2>/dev/null | grep -q "ai-code-llm"; then
        echo
        yellow "ai-code's Modal app 'ai-code-llm' is deployed."
        read -r -p "Stop it on Modal now? [y/N] " yn
        case "${yn,,}" in
            y|yes) modal app stop ai-code-llm && green "  stopped ai-code-llm" || yellow "  could not stop it (do it manually: modal app stop ai-code-llm)" ;;
            *)     dim "  left it running (it scales to zero when idle)." ;;
        esac
    fi
fi

# aisha's downloaded local model (llama.cpp + GGUF), if any.
if [ -e "$AISHA_DATA_DIR" ]; then
    echo
    yellow "aisha's local model files are in $AISHA_DATA_DIR ($(du -sh "$AISHA_DATA_DIR" 2>/dev/null | cut -f1))."
    read -r -p "Delete them? [y/N] " yn
    case "${yn,,}" in
        y|yes) remove_path "$AISHA_DATA_DIR" user ;;
        *)     dim "  kept them." ;;
    esac
fi

# API-key files. Ask before deleting — they hold secrets the user may
# want to keep for a future reinstall.
echo
if [ -e "$CFG_DIR_USER" ] || [ -e "$CFG_DIR_SYS" ]; then
    yellow "Config files exist (Anthropic key, and any ai-code endpoint/key)."
    [ -e "$CFG_DIR_USER" ] && echo "  - $CFG_DIR_USER"
    [ -e "$CFG_DIR_SYS"  ] && echo "  - $CFG_DIR_SYS"
    read -r -p "Delete them too? [y/N] " yn
    case "${yn,,}" in
        y|yes)
            [ -e "$CFG_DIR_USER" ] && remove_path "$CFG_DIR_USER" user
            [ -e "$CFG_DIR_SYS"  ] && remove_path "$CFG_DIR_SYS"  sudo
            ;;
        *)
            dim "  kept key files."
            ;;
    esac
else
    dim "  no key files to remove."
fi

echo
green "Done."
