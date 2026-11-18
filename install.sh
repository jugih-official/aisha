#!/usr/bin/env bash
# install.sh — install (or update) aisha. Asks nothing but your sudo password.
#   On Debian/Ubuntu: builds the Debian package and installs it with apt.
#   Elsewhere, or with --local: puts aisha in /usr/local without a package.
#   The first time, it asks whether new terminal windows should open aisha (--no-ask skips it;
#   packaging/terminal-default.sh set|unset changes it later).
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
for arg in "$@"; do
    case "$arg" in
        -h|--help) sed -n '2,6p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        aisha|--aisha) ;;
        --local|--force) MODE=local ;;
        --deb) MODE=deb ;;
        --no-ask) ASK_TERMINAL=0 ;;
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

green "aisha $VERSION is installed. Start it with: aisha"

# Offer once to open aisha in new terminal windows (never asked again; never as root).
if [ "$ASK_TERMINAL" -eq 1 ] && [ "$(id -u)" -ne 0 ] && [ -t 0 ]; then
    "$SRC_DIR/packaging/terminal-default.sh" ask || true
fi
