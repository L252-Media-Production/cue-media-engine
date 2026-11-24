#!/usr/bin/env bash
# Build the cue-media-engine .deb. Normally run inside a debian:<codename> container by packaging/build-deb.sh.
#
#   SRC=/src OUT=/out bash packaging/build-in-container.sh
#
# Environment:
#   SRC              the repository (default: the folder above this script); only read
#   OUT              where the .deb, the frozen requirements and the lintian report go (default: $SRC/dist/deb)
#   DEB_VERSION      overrides APP_VERSION from cpl/config.py; "-rcN" becomes "~rcN"
#   DEB_MAINTAINER   overrides the Maintainer field
#   SOURCE_DATE_EPOCH  file mtimes (default: the HEAD commit time)
#   LINT=1           also install and run lintian (report only: written next to the .deb, never fails the build)
#   STAGE_ONLY=1     assemble the tree into $STAGE_DIR and stop: no apt, no pip, no dpkg-deb (tests/test_deb_packaging.py;
#                    runs on macOS too, so keep this path bash 3.2 and BSD-tool friendly)
#   DEBIAN_RELEASE   12 or 13 (STAGE_ONLY only; a real build reads /etc/debian_version)
#   ARCH             amd64 or arm64 (STAGE_ONLY only; a real build asks dpkg)
#   HOST_UID/HOST_GID  owner given to the output files (set by build-deb.sh)
set -euo pipefail

HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
SRC=${SRC:-$(cd "$HERE/.." && pwd)}
PKG=cue-media-engine
APP_REL=opt/cue-media-engine
SHARE_REL=usr/share/cue-media-engine
DOC_REL=usr/share/doc/cue-media-engine

die() { echo "build-deb: $*" >&2; exit 1; }
say() { echo "build-deb: $*"; }
g() { git -c safe.directory='*' -C "$SRC" "$@"; }

# ---------------------------------------------------------------- version
APP_VERSION=$(sed -nE 's/^APP_VERSION[[:space:]]*=[[:space:]]*"([^"]+)".*/\1/p' "$SRC/cpl/config.py" | head -n 1)
[ -n "$APP_VERSION" ] || die "APP_VERSION not found in cpl/config.py"
UPSTREAM_VERSION=${DEB_VERSION:-$APP_VERSION}
VERSION=$(printf '%s' "$UPSTREAM_VERSION" | sed -E 's/-rc([0-9]+)$/~rc\1/')
printf '%s' "$VERSION" | grep -Eq '^[0-9][A-Za-z0-9.+~-]*$' || die "not a valid package version: '$VERSION'"
MAINTAINER=${DEB_MAINTAINER:-L252 Media Production <support@cuemestage.com>}

# ---------------------------------------------------------------- target
if [ "${STAGE_ONLY:-}" = 1 ]; then
    REL=${DEBIAN_RELEASE:-12}
    if [ -z "${ARCH:-}" ]; then
        case "$(uname -m)" in x86_64|amd64) ARCH=amd64 ;; aarch64|arm64) ARCH=arm64 ;; *) ARCH=$(uname -m) ;; esac
    fi
    [ -n "${STAGE_DIR:-}" ] || die "STAGE_ONLY=1 needs STAGE_DIR"
else
    [ -f /etc/debian_version ] || die "run this inside a debian container (packaging/build-deb.sh), or use STAGE_ONLY=1"
    REL=$(cut -d. -f1 /etc/debian_version)
    case "$REL" in
        12|13) ;;
        bookworm*) REL=12 ;;
        trixie*) REL=13 ;;
        *) die "unsupported Debian release '$(cat /etc/debian_version)' (12 or 13)" ;;
    esac
    export DEBIAN_FRONTEND=noninteractive
    say "installing build tools"
    apt-get update -qq
    # shellcheck disable=SC2046
    apt-get install -y -qq --no-install-recommends python3 python3-pip python3-venv dpkg-dev git ca-certificates \
        $( [ "${LINT:-}" = 1 ] && echo lintian ) >/dev/null
    ARCH=$(dpkg --print-architecture)
fi
case "$REL" in
    12) PY=3.11; UNIT_DIR=lib/systemd/system ;;            # bookworm: the classic location
    13) PY=3.13; UNIT_DIR=usr/lib/systemd/system ;;        # trixie: /lib is an alias of /usr/lib (lintian aliased-location)
    *) die "DEBIAN_RELEASE must be 12 or 13 (got '$REL')" ;;
esac
case "$ARCH" in amd64|arm64) ;; *) die "architecture must be amd64 or arm64 (got '$ARCH')" ;; esac
PY_NEXT="${PY%.*}.$(( ${PY#*.} + 1 ))"
PYTHON_DEP="python3 (>= $PY), python3 (<< $PY_NEXT)"

if [ -z "${SOURCE_DATE_EPOCH:-}" ]; then
    SOURCE_DATE_EPOCH=$(g log -1 --format=%ct)
fi
export SOURCE_DATE_EPOCH

STAGE=${STAGE_DIR:-$(mktemp -d)/root}
[ ! -e "$STAGE" ] || [ -z "$(ls -A "$STAGE" 2>/dev/null)" ] || die "STAGE_DIR $STAGE is not empty"
mkdir -p "$STAGE"
say "version $VERSION (APP_VERSION $APP_VERSION), Debian $REL, $ARCH, python $PY"

# ---------------------------------------------------------------- the tree (tracked files only)
if [ -n "$(g status --porcelain --untracked-files=no -- player.py requirements.txt cpl static 2>/dev/null)" ]; then
    say "WARNING: player.py / requirements.txt / cpl / static have uncommitted changes; the working copy is packaged"
fi
mkdir -p "$STAGE/$APP_REL"
n=0
while IFS= read -r -d '' f; do
    case "$f" in
        *__pycache__*|*.pyc|*.key|.venv*) continue ;;
    esac
    mkdir -p "$STAGE/$APP_REL/$(dirname "$f")"
    cp "$SRC/$f" "$STAGE/$APP_REL/$f"
    n=$((n + 1))
done < <(g ls-files -z -- player.py requirements.txt cpl static)
[ "$n" -gt 0 ] || die "git ls-files found nothing to package"
printf '%s\n' "$UPSTREAM_VERSION" > "$STAGE/$APP_REL/VERSION"

mkdir -p "$STAGE/$DOC_REL"
cp "$SRC/LICENSE" "$STAGE/$DOC_REL/copyright"
cp "$SRC/NOTICE" "$STAGE/$DOC_REL/NOTICE"
cp "$SRC/README.md" "$STAGE/$DOC_REL/README.md"
CHDATE=$(LC_ALL=C date -u -d "@$SOURCE_DATE_EPOCH" '+%a, %d %b %Y %H:%M:%S +0000' 2>/dev/null \
         || LC_ALL=C date -u -r "$SOURCE_DATE_EPOCH" '+%a, %d %b %Y %H:%M:%S +0000')
printf '%s (%s) unstable; urgency=medium\n\n  * Cue Media Engine %s. See CHANGELOG.md in the source repository.\n\n -- %s  %s\n' \
    "$PKG" "$VERSION" "$UPSTREAM_VERSION" "$MAINTAINER" "$CHDATE" | gzip -n -9 > "$STAGE/$DOC_REL/changelog.gz"

mkdir -p "$STAGE/$UNIT_DIR" "$STAGE/etc/default" "$STAGE/usr/share/lintian/overrides"
cp "$HERE/cue-media-engine.service" "$STAGE/$UNIT_DIR/cue-media-engine.service"
cp "$HERE/default" "$STAGE/etc/default/cue-media-engine"
cp "$HERE/lintian-overrides" "$STAGE/usr/share/lintian/overrides/$PKG"

mkdir -p "$STAGE/DEBIAN"
for s in postinst prerm postrm; do cp "$HERE/$s" "$STAGE/DEBIAN/$s"; done
printf '/etc/default/cue-media-engine\n' > "$STAGE/DEBIAN/conffiles"

# ---------------------------------------------------------------- wheelhouse (real build only)
if [ "${STAGE_ONLY:-}" != 1 ]; then
    have=$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')
    [ "$have" = "$PY" ] || die "this container has python $have, expected $PY for Debian $REL"
    say "checking that every packaged .py compiles with python $PY"
    python3 - "$STAGE/$APP_REL" <<'PY' || die "the code does not compile with Debian $REL's python $PY (above); the package would not run there"
import pathlib, sys
bad = 0
for p in sorted(pathlib.Path(sys.argv[1]).rglob("*.py")):
    try:
        compile(p.read_bytes(), str(p), "exec", dont_inherit=True)
    except SyntaxError as e:
        print("  %s:%s: %s" % (p, e.lineno, e.msg), file=sys.stderr)
        bad = 1
sys.exit(bad)
PY
    WH="$STAGE/$SHARE_REL/wheels"
    mkdir -p "$WH"
    BV=$(mktemp -d)
    python3 -m venv "$BV/dl"
    say "downloading wheels (binary only) for python $PY / $ARCH"
    if ! "$BV/dl/bin/pip" download --disable-pip-version-check --no-cache-dir --only-binary=:all: \
            -r "$SRC/requirements.txt" -d "$WH"; then
        die "a binary wheel is missing for Debian $REL (python $PY) on $ARCH: see the pip output above. No sdist builds are allowed."
    fi
    say "test install from the wheelhouse alone (--no-index)"
    python3 -m venv "$BV/t"
    "$BV/t/bin/pip" install --disable-pip-version-check --no-cache-dir --no-index --find-links "$WH" -r "$SRC/requirements.txt" >/dev/null \
        || die "the wheelhouse does not install offline"
    "$BV/t/bin/pip" freeze --disable-pip-version-check | LC_ALL=C sort > "$STAGE/$SHARE_REL/requirements.frozen.txt"
    "$BV/t/bin/pip" check >/dev/null || die "pip check failed for the installed wheelhouse"
    # the player's own imports, with the dummy SDL driver
    SDL_AUDIODRIVER=dummy PYGAME_HIDE_SUPPORT_PROMPT=1 "$BV/t/bin/python" -c 'import pygame, pythonosc, aiohttp, numpy, scipy, yt_dlp' \
        || die "the installed wheelhouse cannot import the player's packages"
    rm -rf "$BV"
    say "wheelhouse: $(du -sh "$WH" | cut -f1), $(ls "$WH" | wc -l | tr -d ' ') wheels"
fi

# ---------------------------------------------------------------- modes, mtimes, control
find "$STAGE" -type d -exec chmod 0755 {} +
find "$STAGE" -type f -exec chmod 0644 {} +
chmod 0755 "$STAGE/DEBIAN/postinst" "$STAGE/DEBIAN/prerm" "$STAGE/DEBIAN/postrm"

SIZE=$(du -sk --exclude=DEBIAN "$STAGE" 2>/dev/null | cut -f1 || true)
if [ -z "$SIZE" ]; then                                    # BSD du has no --exclude
    SIZE=$(( $(du -sk "$STAGE" | cut -f1) - $(du -sk "$STAGE/DEBIAN" | cut -f1) ))
fi
sed -e "s|@VERSION@|$VERSION|" -e "s|@ARCH@|$ARCH|" -e "s|@MAINTAINER@|$MAINTAINER|" \
    -e "s|@INSTALLED_SIZE@|$SIZE|" -e "s|@PYTHON_DEP@|$PYTHON_DEP|" "$HERE/control.in" > "$STAGE/DEBIAN/control"
chmod 0644 "$STAGE/DEBIAN/control" "$STAGE/DEBIAN/conffiles"
! grep -q '@[A-Z_]*@' "$STAGE/DEBIAN/control" || die "unreplaced placeholder in DEBIAN/control"

if touch -h -d "@$SOURCE_DATE_EPOCH" "$STAGE" 2>/dev/null; then
    find "$STAGE" -exec touch -h -d "@$SOURCE_DATE_EPOCH" {} +
else
    T=$(TZ=UTC date -r "$SOURCE_DATE_EPOCH" '+%Y%m%d%H%M.%S')
    find "$STAGE" -exec env TZ=UTC touch -h -t "$T" {} +
fi

if [ "${STAGE_ONLY:-}" = 1 ]; then
    say "staged into $STAGE (STAGE_ONLY: no wheelhouse, no .deb)"
    exit 0
fi

# ---------------------------------------------------------------- .deb
OUT=${OUT:-$SRC/dist/deb}
mkdir -p "$OUT"
BASE="${PKG}_${VERSION}_debian${REL}_${ARCH}"
DEB="$OUT/$BASE.deb"
dpkg-deb --root-owner-group -Zxz --build "$STAGE" "$DEB" >/dev/null
cp "$STAGE/$SHARE_REL/requirements.frozen.txt" "$OUT/$BASE.requirements.frozen.txt"
say "built $DEB ($(du -h "$DEB" | cut -f1), Installed-Size $SIZE KiB)"

if [ "${LINT:-}" = 1 ]; then
    say "lintian (report only)"
    lintian --tag-display-limit 0 --info "$DEB" > "$OUT/$BASE.lintian.txt" 2>&1 || true
    cat "$OUT/$BASE.lintian.txt"
    grep -c '^E:' "$OUT/$BASE.lintian.txt" | sed 's/^/build-deb: lintian errors: /' || true
fi

if [ -n "${HOST_UID:-}" ]; then
    chown "$HOST_UID:${HOST_GID:-$HOST_UID}" "$OUT" "$OUT/$BASE".* 2>/dev/null || true
fi
