#!/usr/bin/env bash
# Build the cue-media-engine .deb in a clean Debian container (packaging/README.md).
#
#   packaging/build-deb.sh [--debian 12|13] [--arch amd64|arm64] [--out dist/deb]
#
# Defaults: Debian 12, the host's architecture, dist/deb. Passes DEB_VERSION, DEB_MAINTAINER, LINT and
# SOURCE_DATE_EPOCH through to packaging/build-in-container.sh. Needs docker (and QEMU/binfmt for a foreign --arch).
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
REL=12
OUT=dist/deb
case "$(uname -m)" in x86_64|amd64) ARCH=amd64 ;; aarch64|arm64) ARCH=arm64 ;; *) ARCH=$(uname -m) ;; esac

usage() { sed -n '2,8p' "$0" | sed 's/^# \{0,1\}//'; exit "${1:-0}"; }
while [ $# -gt 0 ]; do
    case "$1" in
        --debian) REL=${2:?}; shift 2 ;;
        --arch) ARCH=${2:?}; shift 2 ;;
        --out) OUT=${2:?}; shift 2 ;;
        -h|--help) usage 0 ;;
        *) echo "unknown argument: $1" >&2; usage 2 ;;
    esac
done
case "$REL" in 12) CODENAME=bookworm ;; 13) CODENAME=trixie ;; *) echo "--debian must be 12 or 13" >&2; exit 2 ;; esac
case "$ARCH" in amd64|arm64) ;; *) echo "--arch must be amd64 or arm64" >&2; exit 2 ;; esac
command -v docker >/dev/null || { echo "docker is needed (or run packaging/build-in-container.sh inside debian:$CODENAME)" >&2; exit 1; }

case "$OUT" in /*) ;; *) OUT="$ROOT/$OUT" ;; esac
mkdir -p "$OUT"
OUT=$(cd "$OUT" && pwd)
SOURCE_DATE_EPOCH=${SOURCE_DATE_EPOCH:-$(git -C "$ROOT" log -1 --format=%ct)}

echo "build-deb: debian:$CODENAME linux/$ARCH -> $OUT"
docker run --rm --platform "linux/$ARCH" \
    -v "$ROOT:/src:ro" -v "$OUT:/out" \
    -e SRC=/src -e OUT=/out -e SOURCE_DATE_EPOCH="$SOURCE_DATE_EPOCH" \
    -e HOST_UID="$(id -u)" -e HOST_GID="$(id -g)" \
    -e DEB_VERSION -e DEB_MAINTAINER -e LINT \
    "debian:$CODENAME" bash /src/packaging/build-in-container.sh
