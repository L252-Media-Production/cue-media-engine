#!/usr/bin/env bash
# Usage: deploy/deploy.sh [tag|branch]          (default: main)
#   Source clone:   the repository that holds this script; CUEME_SRC overrides it.
#   Install folder: CUEME_APP, default /opt/media-player. It must exist: nothing is created.
#   (tests/test_deploy_keeps_data.py runs this script in a sandbox)
set -euo pipefail
SRC=${CUEME_SRC:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}
if [ -n "${CUEME_APP:-}" ]; then APP=$CUEME_APP; RULE="set by CUEME_APP"; else APP=/opt/media-player; RULE="default"; fi
REF=${1:-main}
echo "Source folder:  $SRC"
echo "Source origin:  $(git -C "$SRC" remote get-url origin 2>/dev/null || echo '(none)')"
echo "Install folder: $APP ($RULE)"
if [ ! -d "$APP" ]; then
  echo "Stopped: the install folder $APP does not exist ($RULE). Check the path or create the folder first. Nothing was changed." >&2
  exit 1
fi
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
