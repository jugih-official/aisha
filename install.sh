#!/usr/bin/env bash
# install.sh — install `ai` system-wide so it (and `sudo ai`) work everywhere.
set -euo pipefail

BIN_TARGET=/usr/local/bin/ai
BROWSER_BIN_TARGET=/usr/local/bin/ai-browser
DESKTOP_BIN_TARGET=/usr/local/bin/ai-desktop
CFG_DIR_USER="$HOME/.config/ai-bash"
CFG_KEY_USER="$CFG_DIR_USER/api-key"

# Browser automation lives in its own venv so we don't fight PEP 668
# (externally-managed-environment) on modern Debian/Ubuntu/Fedora.
BROWSER_PREFIX=/opt/ai-bash
BROWSER_VENV="$BROWSER_PREFIX/venv"
BROWSER_PW_DIR="$BROWSER_PREFIX/browsers"

SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_BIN="$SRC_DIR/ai"
SRC_BROWSER="$SRC_DIR/ai-browser"
SRC_DESKTOP="$SRC_DIR/ai-desktop"

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
if [ -f "$SRC_BROWSER" ]; then
    echo "Installing $SRC_BROWSER -> $BROWSER_BIN_TARGET"
    sudo install -m 0755 "$SRC_BROWSER" "$BROWSER_BIN_TARGET"
    green "  installed."
fi
if [ -f "$SRC_DESKTOP" ]; then
    echo "Installing $SRC_DESKTOP -> $DESKTOP_BIN_TARGET"
    sudo install -m 0755 "$SRC_DESKTOP" "$DESKTOP_BIN_TARGET"
    green "  installed."
fi

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

# --- optional browser tools ---------------------------------------------------
echo
read -r -p "Install optional browser automation tools (Playwright + Chromium)? [y/N] " yn
case "${yn,,}" in
    y|yes)
        if ! python3 -c 'import venv' >/dev/null 2>&1; then
            yellow "python3 venv module is missing."
            echo "  On Debian/Ubuntu:  sudo apt install python3-venv python3-full"
            echo "  On Fedora:         sudo dnf install python3-virtualenv"
            yellow "Re-run ./install.sh after installing it."
        else
            echo "Creating browser venv at $BROWSER_VENV"
            sudo install -d -m 0755 "$BROWSER_PREFIX"
            sudo install -d -m 0755 "$BROWSER_PW_DIR"

            install_ok=1
            if ! sudo python3 -m venv "$BROWSER_VENV"; then
                install_ok=0
                yellow "  failed to create venv at $BROWSER_VENV"
            fi

            if [ "$install_ok" -eq 1 ]; then
                echo "Installing Playwright into venv"
                if ! sudo "$BROWSER_VENV/bin/pip" install --upgrade pip >/dev/null; then
                    yellow "  failed to upgrade pip inside venv (continuing)"
                fi
                if ! sudo "$BROWSER_VENV/bin/pip" install --upgrade playwright playwright-stealth; then
                    install_ok=0
                    yellow "  pip failed to install playwright / playwright-stealth"
                fi
            fi

            if [ "$install_ok" -eq 1 ]; then
                echo "Downloading Chromium to $BROWSER_PW_DIR (this may take a while)"
                # --with-deps tries to apt-install the system libs Chromium needs.
                # Fall back to a plain install if the OS isn't supported by the helper.
                if ! sudo PLAYWRIGHT_BROWSERS_PATH="$BROWSER_PW_DIR" \
                        "$BROWSER_VENV/bin/playwright" install --with-deps chromium; then
                    yellow "  '--with-deps' failed; retrying without it (system libs may be missing)"
                    if ! sudo PLAYWRIGHT_BROWSERS_PATH="$BROWSER_PW_DIR" \
                            "$BROWSER_VENV/bin/playwright" install chromium; then
                        install_ok=0
                        yellow "  failed to download Chromium"
                    fi
                fi
            fi

            if [ "$install_ok" -eq 1 ]; then
                # Make Chromium readable/executable by every user (so plain `ai` works,
                # not just `sudo ai`).
                sudo chmod -R a+rX "$BROWSER_PW_DIR"

                # Point the installed ai-browser at the venv's python and at the
                # shared browsers dir.
                if [ -f "$BROWSER_BIN_TARGET" ]; then
                    sudo sed -i "1s|^#!.*|#!$BROWSER_VENV/bin/python3|" "$BROWSER_BIN_TARGET"
                    sudo sed -i "s|^AI_BROWSER_PW_DIR =.*|AI_BROWSER_PW_DIR = \"$BROWSER_PW_DIR\"|" "$BROWSER_BIN_TARGET"
                fi
                green "  browser tools installed."
            else
                yellow "Browser tool install failed. You can retry by re-running ./install.sh"
            fi
        fi
        ;;
    *)
        dim "  skipped browser tools."
        ;;
esac

# --- optional desktop control tools ----------------------------------------
echo
echo "ai-desktop drives the X11 desktop via wmctrl + xdotool (and uses scrot"
echo "for screenshots, tesseract for OCR — both optional)."
missing=()
for cmd in wmctrl xdotool; do
    command -v "$cmd" >/dev/null 2>&1 || missing+=("$cmd")
done
if [ ${#missing[@]} -gt 0 ]; then
    yellow "  missing: ${missing[*]}"
    read -r -p "Install desktop control tools (wmctrl xdotool scrot)? [y/N] " yn
    case "${yn,,}" in
        y|yes)
            if   command -v apt    >/dev/null 2>&1; then sudo apt    install -y wmctrl xdotool scrot
            elif command -v dnf    >/dev/null 2>&1; then sudo dnf    install -y wmctrl xdotool scrot
            elif command -v pacman >/dev/null 2>&1; then sudo pacman -S --needed --noconfirm wmctrl xdotool scrot
            else yellow "  unknown package manager; install wmctrl, xdotool, scrot manually."
            fi
            ;;
        *) dim "  skipped desktop tools." ;;
    esac
else
    dim "  wmctrl + xdotool already present."
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
