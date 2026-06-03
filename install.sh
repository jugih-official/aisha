#!/usr/bin/env bash
# install.sh — install `ai` system-wide so it (and `sudo ai`) work everywhere.
set -euo pipefail

BIN_TARGET=/usr/local/bin/ai
BROWSER_BIN_TARGET=/usr/local/bin/ai-browser
DESKTOP_BIN_TARGET=/usr/local/bin/ai-desktop
CODE_BIN_TARGET=/usr/local/bin/ai-code
CFG_DIR_USER="$HOME/.config/ai-bash"
CFG_KEY_USER="$CFG_DIR_USER/api-key"
# ai-code (local-LLM coding agent) backend config, written after deploy.
CODE_URL_USER="$CFG_DIR_USER/code-url"
CODE_KEY_USER="$CFG_DIR_USER/code-key"

# Browser automation lives in its own venv so we don't fight PEP 668
# (externally-managed-environment) on modern Debian/Ubuntu/Fedora.
BROWSER_PREFIX=/opt/ai-bash
BROWSER_VENV="$BROWSER_PREFIX/venv"
BROWSER_PW_DIR="$BROWSER_PREFIX/browsers"

SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_BIN="$SRC_DIR/ai"
SRC_BROWSER="$SRC_DIR/ai-browser"
SRC_DESKTOP="$SRC_DIR/ai-desktop"
SRC_CODE="$SRC_DIR/ai-code"
SRC_MODAL="$SRC_DIR/modal/llm_modal.py"

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
if [ -f "$SRC_CODE" ]; then
    echo "Installing $SRC_CODE -> $CODE_BIN_TARGET"
    sudo install -m 0755 "$SRC_CODE" "$CODE_BIN_TARGET"
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

# --- optional ai-code Modal GPU backend -------------------------------------
# ai-code is an interactive coding agent (like Claude Code / Codex) that runs a
# local open-weights LLM on your own Modal GPUs. The `ai-code` command is
# already installed above; this step wires up its GPU backend — reusing an
# already-deployed Modal LLM server if one exists, otherwise offering to deploy.

# App name this repo deploys, plus other known LLM-server app names to reuse.
CODE_APP_NAME="$(grep -oE 'modal\.App\("[^"]+"\)' "$SRC_MODAL" 2>/dev/null | sed -E 's/.*"([^"]+)".*/\1/' | head -n1)"
CODE_APP_NAME="${CODE_APP_NAME:-ai-code-llm}"
CODE_APP_CANDIDATES=("$CODE_APP_NAME" "llm-server")

# Write the ai-code endpoint ($1=base url without /v1) and key ($2) locally.
write_code_cfg() {
    mkdir -p "$CFG_DIR_USER"; chmod 700 "$CFG_DIR_USER"
    printf '%s\n' "${1%/}/v1" > "$CODE_URL_USER"; chmod 600 "$CODE_URL_USER"
    printf '%s\n' "$2"        > "$CODE_KEY_USER"; chmod 600 "$CODE_KEY_USER"
    green "  ai-code backend configured: ${1}"
    dim   "  saved to $CODE_URL_USER"
}

echo
echo "ai-code is an interactive coding agent powered by an open-weights LLM"
echo "running on your own Modal GPUs (served via 'modal')."
have_code_cfg=0
[ -s "$CODE_URL_USER" ] && [ -s "$CODE_KEY_USER" ] && have_code_cfg=1
code_done=0   # set once configured (reused or deployed) so we skip later steps

if [ "$have_code_cfg" -eq 1 ]; then
    dim "  ai-code backend already configured ($CODE_URL_USER). Skipping."
    code_done=1
elif [ ! -f "$SRC_MODAL" ]; then
    dim "  modal/llm_modal.py not found in this checkout; skipping ai-code backend."
    code_done=1
fi

# 1) If Modal is already set up, look for an existing deployed LLM server and
#    offer to reuse it instead of deploying a new one.
if [ "$code_done" -eq 0 ] && command -v modal >/dev/null 2>&1 && modal profile current >/dev/null 2>&1; then
    WS="$(modal profile current 2>/dev/null)"
    FOUND_APP="$(modal app list --json 2>/dev/null | python3 -c '
import sys, json
try:
    apps = json.load(sys.stdin)
except Exception:
    apps = []
for cand in sys.argv[1:]:
    for a in apps:
        if a.get("Description") == cand and a.get("State") == "deployed":
            print(cand); sys.exit(0)
' "${CODE_APP_CANDIDATES[@]}" 2>/dev/null)"

    if [ -n "$FOUND_APP" ] && [ -n "$WS" ]; then
        FOUND_URL="https://${WS}--${FOUND_APP}-serve.modal.run"
        green "Found an existing deployed Modal LLM server: '$FOUND_APP'."
        read -r -p "Use it as the ai-code backend (no new deploy)? [Y/n] " yn
        case "${yn,,}" in
        n|no) dim "  not reusing it." ;;
        *)
            echo "  ai-code needs that server's API key (the VLLM_API_KEY in its"
            echo "  Modal secret). Modal can't read secrets back, so paste it here."
            read -r -s -p "  API key (or press Enter to deploy a fresh server instead): " REUSE_KEY; echo
            if [ -n "$REUSE_KEY" ]; then
                write_code_cfg "$FOUND_URL" "$REUSE_KEY"
                code_done=1
            else
                dim "  no key entered; will offer to deploy a fresh server."
            fi
            ;;
        esac
    fi
fi

# 2) Nothing reusable (or user declined) → offer to deploy a fresh backend.
if [ "$code_done" -eq 0 ]; then
    echo "  Deploying a new server runs a vLLM GPU container on Modal and may"
    echo "  incur GPU cost while it serves (it scales to zero ~2 min after the"
    echo "  last request)."
    read -r -p "Deploy the ai-code GPU backend ('$CODE_APP_NAME') on Modal now? [y/N] " yn
    case "${yn,,}" in
    y|yes)
        code_ok=1

        # Ensure the `modal` CLI is available (install via pipx or pip --user).
        if ! command -v modal >/dev/null 2>&1; then
            yellow "  'modal' CLI not found."
            read -r -p "  Install it now? [Y/n] " m
            case "${m,,}" in
            n|no) code_ok=0; dim "  skipped. Install modal, then re-run ./install.sh." ;;
            *)
                if command -v pipx >/dev/null 2>&1; then
                    pipx install modal || code_ok=0
                else
                    python3 -m pip install --user modal || \
                        python3 -m pip install --user --break-system-packages modal || code_ok=0
                fi
                command -v modal >/dev/null 2>&1 || {
                    yellow "  modal still not on PATH (try restarting your shell or 'pipx ensurepath')."
                    code_ok=0
                }
                ;;
            esac
        fi

        # Ensure a Modal token exists (modal token new opens a browser).
        if [ "$code_ok" -eq 1 ] && ! modal profile current >/dev/null 2>&1; then
            yellow "  No Modal token found. Authenticating with Modal…"
            echo "  (this opens a browser; sign up free at https://modal.com if needed)"
            modal token new || { code_ok=0; yellow "  Modal authentication failed."; }
        fi

        # Generate an API key, store it as a Modal secret + locally.
        if [ "$code_ok" -eq 1 ]; then
            CODE_KEY="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
            echo "  Creating Modal secret 'ai-code-llm-key'…"
            modal secret create ai-code-llm-key "VLLM_API_KEY=$CODE_KEY" --force || code_ok=0
        fi

        # Deploy the vLLM server and capture its public URL.
        if [ "$code_ok" -eq 1 ]; then
            echo "  Deploying GPU server (modal deploy $SRC_MODAL)…"
            DEPLOY_LOG="$(mktemp)"
            if modal deploy "$SRC_MODAL" 2>&1 | tee "$DEPLOY_LOG"; then
                CODE_URL="$(grep -oE "https://[a-zA-Z0-9._-]+--${CODE_APP_NAME}-serve\.modal\.run" "$DEPLOY_LOG" | head -n1)"
            else
                code_ok=0; yellow "  modal deploy failed."
            fi
            rm -f "$DEPLOY_LOG"
        fi

        # Persist the endpoint + key so ai-code can reach it.
        if [ "$code_ok" -eq 1 ] && [ -n "${CODE_URL:-}" ]; then
            write_code_cfg "$CODE_URL" "$CODE_KEY"
        elif [ "$code_ok" -eq 1 ]; then
            yellow "  Deployed, but couldn't auto-detect the URL. Find it with"
            yellow "  'modal app list' and write '<url>/v1' to $CODE_URL_USER (key in $CODE_KEY_USER)."
        fi
        ;;
    *)
        dim "  skipped. Set it up later by running ./install.sh again, or by"
        dim "  deploying modal/llm_modal.py yourself (see README)."
        ;;
    esac
fi

# --- post-install message ---------------------------------------------------
echo
green "Done."
echo "Try:"
echo "    ai list files in the current directory"
echo "    ai how much RAM is free"
if [ -s "$CODE_URL_USER" ]; then
    echo "    ai-code              # interactive coding agent (in any project dir)"
fi
echo
dim "Notes:"
dim "  - 'ai ...'      reads the key from \$DEEPSEEK_API_KEY or ~/.config/ai-bash/api-key"
dim "  - 'sudo ai ...' reads the key from /etc/ai-bash/api-key (no need for 'sudo -E')"
dim "  - 'ai-code'     uses the Modal LLM endpoint in ~/.config/ai-bash/code-url"
