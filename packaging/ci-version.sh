#!/bin/sh
# The package version for a CI build (.github/workflows/deb.yml, packaging/README.md "CI").
#
#   packaging/ci-version.sh <ref type> <ref name> <commit> [cpl/config.py]
#
#   tag    vX.Y.Z-rcN  ->  X.Y.Z-rcN (the build turns "-rcN" into "~rcN")
#   tag    vX.Y.Z      ->  X.Y.Z, only if it equals APP_VERSION in cpl/config.py (no v2.9.1 packages named 2.9.0)
#   other  (a branch push or a manual run)  ->  <APP_VERSION>~ci.<first 7 characters of the commit>, which sorts below the release
#   any other tag fails. Prints the version on stdout, errors on stderr.
set -eu

die() { echo "ci-version: $*" >&2; exit 1; }
[ $# -ge 3 ] || die "usage: ci-version.sh <ref type> <ref name> <commit> [cpl/config.py]"
REF_TYPE=$1
REF_NAME=$2
SHA=$3
CONFIG=${4:-$(dirname "$0")/../cpl/config.py}

# the same expression as build-in-container.sh (the app is never imported)
[ -f "$CONFIG" ] || die "$CONFIG not found"
APP_VERSION=$(sed -nE 's/^APP_VERSION[[:space:]]*=[[:space:]]*"([^"]+)".*/\1/p' "$CONFIG" | head -n 1)
[ -n "$APP_VERSION" ] || die "APP_VERSION not found in $CONFIG"

if [ "$REF_TYPE" = tag ]; then
    printf '%s\n' "$REF_NAME" | grep -Eq '^v[0-9]+\.[0-9]+\.[0-9]+(-rc[0-9]+)?$' \
        || die "tag '$REF_NAME' is not vX.Y.Z or vX.Y.Z-rcN: no packages are built for it"
    VERSION=${REF_NAME#v}
    case "$VERSION" in
        *-rc*) ;;
        *) [ "$VERSION" = "$APP_VERSION" ] \
               || die "tag $REF_NAME but APP_VERSION in cpl/config.py is $APP_VERSION: bump APP_VERSION before the final tag" ;;
    esac
else
    printf '%s\n' "$SHA" | grep -Eq '^[0-9a-f]{7,}$' || die "commit '$SHA' is not a hex commit id"
    VERSION="$APP_VERSION~ci.$(printf '%s' "$SHA" | cut -c1-7)"
fi
printf '%s\n' "$VERSION"
