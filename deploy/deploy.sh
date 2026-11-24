#!/usr/bin/env bash
set -euo pipefail
SRC=${CUEME_SRC:-/opt/companionplayer-src}     # the source checkout and the install folder; CUEME_SRC / CUEME_APP override them (tests/test_deploy_keeps_data.py)
APP=${CUEME_APP:-/opt/media-player}
REF=${1:-main}
cd "$SRC"
git fetch -q --tags --prune origin
git checkout -q "$REF"
[ "$REF" = main ] && git pull -q --ff-only
# Only these files and the two mirrored folders are written: config.json, state.json, playlists.json, media/ and the
# ElevenLabs key (elevenlabs.key) in "$APP" are never touched (tests/test_deploy_keeps_data.py)
install -m 644 player.py requirements.txt "$APP/"
rsync -a --delete --exclude __pycache__ --exclude elevenlabs.key static/ "$APP/static/"
[ -d cpl ] && rsync -a --delete --exclude __pycache__ --exclude elevenlabs.key cpl/ "$APP/cpl/"
git describe --tags --always > "$APP/VERSION"
echo "Deployed $(cat "$APP/VERSION"). Restart when ready: sudo systemctl restart companionplayer"