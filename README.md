<p align="center"><picture><source media="(prefers-color-scheme: dark)" srcset="assets/branding/cueme-lockup-dark.png"><img src="assets/branding/cueme-lockup-light.png" width="420" alt="Cue Media Engine (CueME)"></picture></p>

# Cue Media Engine (CueME)

A playlist audio player for live AV work, controlled from [Bitfocus Companion](https://bitfocus.io/companion) (OSC and HTTP) and from its own web page. One Python program, no build step.

Cue Media Engine is an independent project and is not affiliated with or endorsed by Bitfocus; Bitfocus Companion is a trademark of Bitfocus AS.

## What it does

- **Library and playlists:** every file is stored once; playlists are lists of references, so a track can sit in several. Folders, favorites, drag and drop, upload.
- **Cue and Go:** cue a track, then cut or crossfade to it. Per-track crossfade times and end actions (once, loop, stop).
- **Trim:** A and B points with fades, and trigger points that start a second track on top of the first.
- **Play on Top:** announcements over music with a sidechain ducker; the same ducker can be driven by a live microphone input.
- **No glitches:** tracks are decoded into RAM ahead of time by helper processes, so a cue starts instantly and the output never freezes.
- **Preview and Solo:** a second output, or the browser, for the engineer's headphones.
- **Level match, loudness and file information** for every track.
- **Stage page:** the time remaining as big text for stage screens.
- **Health panel, watchdog and webhook alerts** for unattended machines.
- **Companion:** variables, feedback and a [Companion module](companion-module/) with actions, feedbacks and presets.

## Security

The web page and the HTTP and OSC control have **no authentication**: anyone who can reach the port can play, stop and change settings. Run the player on a trusted network, behind a firewall, or behind a reverse proxy that adds authentication, and never expose port 8080 (web / HTTP) or 9000 (OSC) to the internet.

## Quick start

Requirements: Python 3, and for the best results ffmpeg (optional; see [Configuration](https://github.com/L252-Media-Production/cue-media-engine/wiki/Configuration)).

First time only:

```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Every time after that, from this folder:

```
.venv/bin/python player.py
```

Open <http://localhost:8080>. At startup the available audio output devices are printed.

- **Linux (Debian), headless, with a USB audio interface** is the production target: run it as a systemd service (see [Install and run](https://github.com/L252-Media-Production/cue-media-engine/wiki/Install-and-Run)). Companion usually runs on the same machine.
- **Raspberry Pi, Windows and macOS** are supported too. On Windows use `run-player.bat`; on macOS `run-player.command`. (The memory readout is not implemented on macOS.)

**Updating:** copy `player.py`, `cpl/` and `static/` together over the old ones (the player refuses to start if `cpl/` or `static/` is missing or incomplete; on Windows also copy `run-player.bat`). Your playlists, library and settings are kept.

## Documentation

The guide is in the [project wiki](https://github.com/L252-Media-Production/cue-media-engine/wiki/Home).

| Topic | Pages |
|---|---|
| Getting going | [Install and run](https://github.com/L252-Media-Production/cue-media-engine/wiki/Install-and-Run), [Configuration](https://github.com/L252-Media-Production/cue-media-engine/wiki/Configuration), [Audio outputs and Dante](https://github.com/L252-Media-Production/cue-media-engine/wiki/Audio-Outputs-and-Dante) |
| Using it | [Library and playlists](https://github.com/L252-Media-Production/cue-media-engine/wiki/Library-and-Playlists), [Play modes and end actions](https://github.com/L252-Media-Production/cue-media-engine/wiki/Play-Modes-and-End-Actions), [Trim](https://github.com/L252-Media-Production/cue-media-engine/wiki/Trim-A-B), [Trigger points](https://github.com/L252-Media-Production/cue-media-engine/wiki/Trigger-Points), [Play on Top](https://github.com/L252-Media-Production/cue-media-engine/wiki/Play-on-Top), [Live input](https://github.com/L252-Media-Production/cue-media-engine/wiki/Live-Input), [Level match](https://github.com/L252-Media-Production/cue-media-engine/wiki/Level-Match), [Preview, Solo and Mirror](https://github.com/L252-Media-Production/cue-media-engine/wiki/Preview-and-Solo), [Live operation](https://github.com/L252-Media-Production/cue-media-engine/wiki/Live-Operation), [Appearance and layout](https://github.com/L252-Media-Production/cue-media-engine/wiki/Appearance-and-Layout), [Stage page](https://github.com/L252-Media-Production/cue-media-engine/wiki/Stage-Page) |
| Companion | [OSC and HTTP commands](https://github.com/L252-Media-Production/cue-media-engine/wiki/OSC-and-HTTP-Commands), [Variables and settings](https://github.com/L252-Media-Production/cue-media-engine/wiki/Companion-Variables) |
| Monitoring | [Health, watchdog and push](https://github.com/L252-Media-Production/cue-media-engine/wiki/Health-and-Monitoring) |
| Developers | [API and data reference](docs/api-reference.md), [Live input design](docs/live-input-design.md), [Changelog](CHANGELOG.md) |

An operator's guide is also built into the player: **⚙ Settings > System > Maintenance > Help guide** (`http://<host>:8080/help`).

## Licence

The source code is MIT licensed (see `LICENSE`). The name "Cue Media Engine", "CueME" and the logo are not covered by that licence (see `TRADEMARKS.md`). Third-party notices (the Lucide icons, ISC and MIT) are in `NOTICE`.
