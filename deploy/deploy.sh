#!/usr/bin/env bash
set -euo pipefail
SRC=/opt/companionplayer-src
APP=/opt/media-player
REF=${1:-main}
cd "$SRC"
git fetch -q --tags --prune origin
git checkout -q "$REF"
[ "$REF" = main ] && git pull -q --ff-only
install -m 644 player.py requirements.txt "$APP/"
rsync -a --delete --exclude __pycache__ static/ "$APP/static/"
[ -d cpl ] && rsync -a --delete --exclude __pycache__ cpl/ "$APP/cpl/"
git describe --tags --always > "$APP/VERSION"
echo "Deployed $(cat "$APP/VERSION"). Restart when ready: sudo systemctl restart companionplayer"