#!/usr/bin/env bash
# install.sh — install (or update) ai$ha, the ai shell hybrid alpha (command: aisha).
#   On Debian/Ubuntu: builds the Debian package and installs it with apt.
#   Elsewhere, or with --local: puts aisha in /usr/local without a package.
#   The first time, it asks two things: add the optional local language model (--with-llm [0.5b|1.5b|3b]
#   installs it without asking, --no-llm skips it), and open aisha in new terminal windows.
#   --no-ask skips both questions. Later: aisha --setup, packaging/terminal-default.sh set|unset.
set -euo pipefail

SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_AISHA="$SRC_DIR/aisha"
LOCAL_BIN=/usr/local/bin/aisha
LOCAL_LIB=/usr/local/lib/aisha

red()    { printf '\033[1;31m%s\033[0m\n' "$*"; }
green()  { printf '\033[1;32m%s\033[0m\n' "$*"; }
yellow() { printf '\033[1;33m%s\033[0m\n' "$*"; }
die()    { red "error: $*"; exit 1; }

MODE=auto
ASK_TERMINAL=1
LLM=ask              # ask | yes | no
LLM_SIZE=0.5b
for arg in "$@"; do
    case "$arg" in
        --with-llm) LLM=yes ;;
        0.5b|1.5b|3b) LLM=yes; LLM_SIZE="$arg" ;;
        --no-llm) LLM=no ;;
        -h|--help) sed -n '2,7p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        aisha|--aisha) ;;
        --local|--force) MODE=local ;;
        --deb) MODE=deb ;;
        --no-ask) ASK_TERMINAL=0; [ "$LLM" = ask ] && LLM=no ;;
        *) die "unknown option: $arg (try --help)" ;;
    esac
done
if [ "$MODE" = auto ]; then
    if command -v apt >/dev/null 2>&1 && command -v dpkg-deb >/dev/null 2>&1; then MODE=deb; else MODE=local; fi
fi

[ -f "$SRC_AISHA" ] || die "cannot find $SRC_AISHA"
command -v python3 >/dev/null 2>&1 || die "python3 is required but not installed"
python3 -c 'import sys; sys.exit(sys.version_info < (3, 9))' || die "aisha needs python 3.9+"
VERSION="$(sed -n 's/^VERSION = "\(.*\)"/\1/p' "$SRC_AISHA")"
SUDO=""
[ "$(id -u)" -eq 0 ] || { command -v sudo >/dev/null 2>&1 || die "sudo is required to install"; SUDO=sudo; }

if [ "$MODE" = deb ]; then
    echo "Building the aisha $VERSION package…"
    rm -f "$SRC_DIR"/dist/aisha_*_all.deb
    "$SRC_DIR/packaging/debian/build-deb.sh"
    DEB="$SRC_DIR/dist/aisha_${VERSION}_all.deb"
    [ -f "$DEB" ] || die "the build did not produce $DEB"
    echo "Installing it with apt…"
    $SUDO apt install -y --reinstall "$DEB"
    # an earlier /usr/local copy would hide the package (it comes first on PATH)
    if [ -e "$LOCAL_BIN" ] || [ -e "$LOCAL_LIB" ]; then
        $SUDO rm -rf -- "$LOCAL_BIN" "$LOCAL_LIB"
        yellow "removed the older copy in /usr/local so the package is the one that runs"
    fi
    hash -r 2>/dev/null || true
else
    if dpkg -S /usr/bin/aisha >/dev/null 2>&1; then
        yellow "note: the aisha Debian package is installed too; the /usr/local copy will be the one that runs."
    fi
    # The code goes in a lib dir as a module so Python caches its bytecode;
    # /usr/local/bin/aisha is a small launcher.
    echo "Installing $SRC_AISHA -> $LOCAL_LIB/aisha.py (+ launcher $LOCAL_BIN)"
    $SUDO install -Dm0644 "$SRC_AISHA" "$LOCAL_LIB/aisha.py"
    printf '#!/usr/bin/env python3\nimport sys\nsys.path.insert(0, "%s")\nimport aisha\naisha.cli()\n' \
        "$LOCAL_LIB" | $SUDO tee "$LOCAL_BIN" >/dev/null
    $SUDO chmod 0755 "$LOCAL_BIN"
    $SUDO python3 -m compileall -q "$LOCAL_LIB" || true
fi

green 'ai$ha (ai shell hybrid alpha) '"$VERSION"' is installed. Start it with: aisha'

# The optional local language model: asked once, never as root (it belongs to your user).
CFG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}/aisha"
llm_ready() {   # already set up: a model server and model file aisha can start, or another server
    python3 - "$CFG_HOME/config.json" <<'PY' 2>/dev/null
import json, os, sys
try:
    c = json.load(open(sys.argv[1]))
except (OSError, ValueError):
    sys.exit(1)
files = c.get("llm_server") and c.get("llm_model_file")
sys.exit(0 if (files and os.path.isfile(c["llm_server"]) and os.path.isfile(c["llm_model_file"]))
         or (c.get("llm_url") and not files) else 1)
PY
}
AISHA_CMD="$(command -v aisha || echo "python3 $SRC_AISHA")"
if [ "$(id -u)" -ne 0 ] && [ "$LLM" != no ] && ! llm_ready; then
    if [ "$LLM" = ask ] && [ -t 0 ] && [ ! -e "$CFG_HOME/.llm-asked" ]; then
        echo
        echo 'ai$ha works without a language model: its rules and built-in model handle most requests.'
        echo "A small local model (Qwen2.5-Coder 0.5B, run by llamafile; about 550 MB to download, no cloud, no API key)"
        echo "answers the rest. It starts only when needed."
        read -r -p "Add the local language model now? [y/N] " yn
        mkdir -p "$CFG_HOME" && : > "$CFG_HOME/.llm-asked"
        case "${yn,,}" in y|yes) LLM=yes ;; *) echo "  skipped (later: aisha --setup)" ;; esac
    fi
    if [ "$LLM" = yes ]; then
        echo
        $AISHA_CMD --setup "$LLM_SIZE" --yes || yellow "the language model was not set up; try again with: aisha --setup"
    fi
fi

# Offer once to open aisha in new terminal windows (never asked again; never as root).
if [ "$ASK_TERMINAL" -eq 1 ] && [ "$(id -u)" -ne 0 ] && [ -t 0 ]; then
    "$SRC_DIR/packaging/terminal-default.sh" ask || true
fi
