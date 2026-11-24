# Debian package (.deb)

Builds `cue-media-engine_<version>_debian<12|13>_<amd64|arm64>.deb`, which installs Cue Media Engine as the systemd service
`cue-media-engine`. The CI workflow `.github/workflows/deb.yml` builds all four on a `v*` tag and attaches them to a draft Release.
User guide: [Install from a .deb](../docs/wiki/Install-and-Run.md#install-from-a-deb-debian-12-and-13).

## Build

```
packaging/build-deb.sh [--debian 12|13] [--arch amd64|arm64] [--out dist/deb]     # needs docker; defaults: 12, host arch
LINT=1 packaging/build-deb.sh --debian 13                                          # also run lintian (report only)
DEB_VERSION=2.9.1-rc2 packaging/build-deb.sh                                       # version 2.9.1~rc2 instead of APP_VERSION
```

`build-deb.sh` runs `build-in-container.sh` in `debian:<codename>` for the target architecture, with the repository mounted
read-only. Output next to each `.deb`: `<name>.requirements.frozen.txt` and, with `LINT=1`, `<name>.lintian.txt`.
`STAGE_ONLY=1 STAGE_DIR=<empty dir> bash packaging/build-in-container.sh` only assembles the tree (no Docker, no pip; used by
`tests/test_deb_packaging.py`).

## What is in it

- `/opt/cue-media-engine/`: `player.py`, `requirements.txt`, `cpl/`, `static/` (tracked files only, from `git ls-files`) and
  `VERSION`. Root-owned; the folder itself is `cueme:cueme` so the player can write its data there.
- `/usr/share/cue-media-engine/wheels/` and `requirements.frozen.txt`: every Python package as a binary wheel for that Debian
  release and architecture. `postinst` builds `/opt/cue-media-engine/.venv` from them with `--no-index` (no internet needed).
- The unit `cue-media-engine.service` (`/lib/systemd/system` on 12, `/usr/lib/systemd/system` on 13) and the conffile
  `/etc/default/cue-media-engine`.
- `/usr/share/doc/cue-media-engine/`: `copyright` (the LICENSE), `NOTICE`, `README.md`, `changelog.gz`.

## Decisions

1. Install root `/opt/cue-media-engine`, because the player keeps its data next to `player.py` (`cpl/config.py` `BASE`).
2. Python packages from a bundled wheelhouse, binary wheels only; the build fails if one is missing, or if a `.py` file does not
   compile with that release's Python. `postinst` fails loudly if the venv cannot be created.
3. `Depends: python3 (that release's version), python3-venv, ffmpeg, alsa-utils, adduser`. No Bluetooth or PulseAudio/PipeWire tool
   is called by the player; `nice` and `taskset` are Essential.
4. Service user `cueme` (system, member of `audio`, shell `nologin`), created idempotently and never removed.
5. No sandboxing, real-time scheduling or CPU limits in the unit: those need their own audio test first.
6. **Never restarts on upgrade** (a restart cuts the audio): fresh install `enable --now`; upgrade `daemon-reload` and a hint
   `sudo systemctl restart cue-media-engine`. Every `systemctl` call is skipped where systemd is not running.
7. Remove and purge never delete the data (`config.json`, `state.json`, `playlists.json`, `durations.json`, `resume.json`,
   `elevenlabs.key`, `media/`); purge removes only `.venv`, `__pycache__` and `VERSION`. An old `companionplayer` install is
   never touched; if it is running, the new service is enabled but not started (same ports).

Lintian: `dir-or-file-in-opt`, `maintainer-script-calls-systemctl` and `script-not-executable` are overridden on purpose
(`lintian-overrides`); there are no other errors or warnings.
