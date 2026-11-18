#!/usr/bin/env bash
# install.sh — install aisha in /usr/local without a Debian package. Asks nothing.
# (With a package instead: packaging/debian/build-deb.sh && sudo apt install ./dist/aisha_*_all.deb)
set -euo pipefail

AISHA_BIN_TARGET=/usr/local/bin/aisha
AISHA_LIB_DIR=/usr/local/lib/aisha
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_AISHA="$SRC_DIR/aisha"

red()   { printf '\033[1;31m%s\033[0m\n' "$*"; }
green() { printf '\033[1;32m%s\033[0m\n' "$*"; }
die()   { red "error: $*"; exit 1; }

FORCE=0
case "${1:-}" in
    -h|--help) sed -n '2,3p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    ""|aisha|--aisha) ;;                      # old spellings still work
    --force) FORCE=1 ;;
    *) die "unknown option: $1 (try --help)" ;;
esac

if [ "$FORCE" -eq 0 ] && dpkg -S /usr/bin/aisha >/dev/null 2>&1; then
    printf '\033[1;33m%s\033[0m\n' "aisha is installed from the Debian package; installing a second copy here would hide it." \
        "Update the package instead:  ./update.sh   (or ./install.sh --force for a /usr/local copy anyway)"
    exit 0
fi

[ -f "$SRC_AISHA" ] || die "cannot find $SRC_AISHA"
command -v python3 >/dev/null 2>&1 || die "python3 is required but not installed"
command -v sudo    >/dev/null 2>&1 || die "sudo is required to install into /usr/local"
python3 -c 'import sys; sys.exit(sys.version_info < (3, 9))' || die "aisha needs python 3.9+"

# The code goes in a lib dir as a module so Python caches its bytecode;
# /usr/local/bin/aisha is a small launcher.
echo "Installing $SRC_AISHA -> $AISHA_LIB_DIR/aisha.py (+ launcher $AISHA_BIN_TARGET)"
sudo install -Dm0644 "$SRC_AISHA" "$AISHA_LIB_DIR/aisha.py"
printf '#!/usr/bin/env python3\nimport sys\nsys.path.insert(0, "%s")\nimport aisha\naisha.cli()\n' \
    "$AISHA_LIB_DIR" | sudo tee "$AISHA_BIN_TARGET" >/dev/null
sudo chmod 0755 "$AISHA_BIN_TARGET"
sudo python3 -m compileall -q "$AISHA_LIB_DIR" || true

green "aisha $(python3 "$SRC_AISHA" --version 2>/dev/null | awk '{print $NF}') is installed. Start it with: aisha"
