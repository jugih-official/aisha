#!/usr/bin/env bash
# uninstall.sh — remove `ai` and (optionally) its API-key files.
set -euo pipefail

BIN_TARGET=/usr/local/bin/ai
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

echo "Uninstalling ai-bash."
remove_path "$BIN_TARGET" sudo

# API-key files. Ask before deleting — they hold secrets the user may
# want to keep for a future reinstall.
echo
if [ -e "$CFG_DIR_USER" ] || [ -e "$CFG_DIR_SYS" ]; then
    yellow "API-key files exist. They contain your DeepSeek key."
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
