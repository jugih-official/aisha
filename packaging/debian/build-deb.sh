#!/usr/bin/env bash
# build-deb.sh — build dist/aisha_<version>_all.deb from the repo.
#
#   packaging/debian/build-deb.sh
#   sudo apt install ./dist/aisha_*_all.deb
#
# Needs only dpkg-deb (always present on Debian). The package is
# architecture-independent: one Python file plus docs and a man page.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
SRC="$REPO/aisha"
OUT="${OUT:-$REPO/dist}"
MAINTAINER="${DEB_MAINTAINER:-jugih-official <jugih-official@users.noreply.github.com>}"

command -v dpkg-deb >/dev/null || { echo "dpkg-deb not found (this builds on Debian/Ubuntu)" >&2; exit 1; }
VERSION="$(sed -n 's/^VERSION = "\(.*\)"/\1/p' "$SRC")"
[ -n "$VERSION" ] || { echo "cannot read VERSION from $SRC" >&2; exit 1; }

STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT
PKG="$STAGE/aisha_${VERSION}_all"

# The code lives in /usr/lib/aisha as a module so its bytecode is cached
# (compiled in postinst); /usr/bin/aisha is a three-line launcher.
install -Dm0644 "$SRC" "$PKG/usr/lib/aisha/aisha.py"
install -d "$PKG/usr/bin"
cat > "$PKG/usr/bin/aisha" <<'EOF'
#!/usr/bin/python3
import sys
sys.path.insert(0, "/usr/lib/aisha")
import aisha
aisha.cli()
EOF
chmod 0755 "$PKG/usr/bin/aisha"
install -Dm0644 "$HERE/aisha.1" "$PKG/usr/share/man/man1/aisha.1"
gzip -9n "$PKG/usr/share/man/man1/aisha.1"
install -d "$PKG/usr/share/doc/aisha"
# Only the aisha part of the README belongs in this package.
awk '/^## Natural-language shell \(aisha\)/{on=1} on && /^## / && !/aisha/{exit} on' "$REPO/README.md" \
    > "$PKG/usr/share/doc/aisha/README.md"
cat > "$PKG/usr/share/doc/aisha/copyright" <<EOF
Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/
Upstream-Name: aisha
Source: https://github.com/jugih-official/ai-prompt

Files: *
Copyright: jugih-official
License: none-declared
 The upstream repository does not declare a license yet.
EOF
gzip -9cn > "$PKG/usr/share/doc/aisha/changelog.gz" <<EOF
aisha ($VERSION) unstable; urgency=low

  * Release $VERSION.

 -- $MAINTAINER  $(date -R)
EOF

SIZE_KB="$(du -sk "$PKG" | cut -f1)"
install -d "$PKG/DEBIAN"
cat > "$PKG/DEBIAN/control" <<EOF
Package: aisha
Version: $VERSION
Section: utils
Priority: optional
Architecture: all
Installed-Size: $SIZE_KB
Depends: python3 (>= 3.9), bash, coreutils, findutils, grep, debianutils
Recommends: procps, iproute2, sensible-utils, less
Suggests: zip, unzip, xdg-utils
Maintainer: $MAINTAINER
Homepage: https://github.com/jugih-official/ai-prompt
Description: natural-language shell with a local LLM fallback
 aisha runs bash commands as usual and also understands plain requests
 such as "find recursively files older than 2 months from this folder"
 or "edit logs.txt with micro". A deterministic rule engine builds the
 command and shows what it understood; only when it is unsure does it
 ask a small local model through any OpenAI-compatible server (for
 example Ollama). Commands that delete or change data always ask first.
EOF

cat > "$PKG/DEBIAN/postinst" <<'EOF'
#!/bin/sh
set -e
if [ "$1" = configure ]; then
    python3 -m compileall -q /usr/lib/aisha || true
    add-shell /usr/bin/aisha
fi
EOF
cat > "$PKG/DEBIAN/prerm" <<'EOF'
#!/bin/sh
set -e
rm -rf /usr/lib/aisha/__pycache__
EOF
cat > "$PKG/DEBIAN/postrm" <<'EOF'
#!/bin/sh
set -e
if [ "$1" = remove ] || [ "$1" = purge ]; then
    remove-shell /usr/bin/aisha
fi
EOF
chmod 0755 "$PKG/DEBIAN/postinst" "$PKG/DEBIAN/prerm" "$PKG/DEBIAN/postrm"

mkdir -p "$OUT"
dpkg-deb --build --root-owner-group "$PKG" "$OUT/aisha_${VERSION}_all.deb" >/dev/null
echo "built $OUT/aisha_${VERSION}_all.deb"
echo "install with: sudo apt install $OUT/aisha_${VERSION}_all.deb"
