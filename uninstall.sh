#!/usr/bin/env bash
# uninstall.sh — remove aisha. Asks before the settings or a downloaded model are deleted.
set -euo pipefail

AISHA_BIN_TARGET=/usr/local/bin/aisha
AISHA_LIB_DIR=/usr/local/lib/aisha
AISHA_DATA_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/aisha"
AISHA_CFG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/aisha"
# Left over from when this repo was ai-prompt and also installed the ai tools.
OLD_BINS=(/usr/local/bin/ai /usr/local/bin/ai-browser /usr/local/bin/ai-desktop /usr/local/bin/ai-code)
OLD_DIRS_SUDO=(/opt/ai-bash /etc/ai-bash)
OLD_DIRS_USER=("$HOME/.config/ai-bash")

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

ask() {  # ask "question" -> 0 on yes
    local yn
    read -r -p "$1 [y/N] " yn
    case "${yn,,}" in y|yes) return 0 ;; *) return 1 ;; esac
}

echo "Uninstalling aisha."
# terminal windows that open aisha revert to the login shell
if [ "$(id -u)" -ne 0 ] && [ -x "$(dirname "$0")/packaging/terminal-default.sh" ]; then
    "$(dirname "$0")/packaging/terminal-default.sh" unset || true
fi
remove_path "$AISHA_BIN_TARGET" sudo
remove_path "$AISHA_LIB_DIR" sudo
if dpkg -S /usr/bin/aisha >/dev/null 2>&1; then
    yellow "The aisha Debian package is installed too."
    ask "Remove it (sudo apt remove aisha)?" && sudo apt remove -y aisha || dim "  kept the package."
fi

# The optional local model (llama.cpp + GGUF), if aisha --setup downloaded one.
if [ -e "$AISHA_DATA_DIR" ]; then
    echo
    yellow "aisha's local model files are in $AISHA_DATA_DIR ($(du -sh "$AISHA_DATA_DIR" 2>/dev/null | cut -f1))."
    ask "Delete them?" && remove_path "$AISHA_DATA_DIR" user || dim "  kept them."
fi

# Settings, learned phrases and history.
if [ -e "$AISHA_CFG_DIR" ]; then
    echo
    yellow "aisha's settings, learned phrases and history are in $AISHA_CFG_DIR."
    ask "Delete them?" && remove_path "$AISHA_CFG_DIR" user || dim "  kept them."
fi

# The old ai tools, if an earlier install.sh put them here.
old=()
for p in "${OLD_BINS[@]}" "${OLD_DIRS_SUDO[@]}" "${OLD_DIRS_USER[@]}"; do
    [ -e "$p" ] && old+=("$p")
done
if [ ${#old[@]} -gt 0 ]; then
    echo
    yellow "Left over from the old ai tools (ai, ai-browser, ai-desktop, ai-code), including any saved API keys:"
    printf '  - %s\n' "${old[@]}"
    if ask "Delete them too?"; then
        for p in "${OLD_BINS[@]}" "${OLD_DIRS_SUDO[@]}"; do [ -e "$p" ] && remove_path "$p" sudo; done
        for p in "${OLD_DIRS_USER[@]}"; do [ -e "$p" ] && remove_path "$p" user; done
    else
        dim "  kept them."
    fi
fi

echo
green "Done."
