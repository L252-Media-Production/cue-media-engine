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
- **Generated announcements (optional):** connect your own [ElevenLabs](https://elevenlabs.io) account, type a line, pick one of your voices, preview it and save it as a normal track ([how](docs/wiki/Generate-Audio-ElevenLabs.md)).
- **Level match, loudness and file information** for every track.
- **Stage page:** the time remaining as big text for stage screens.
- **Health panel, watchdog and webhook alerts** for unattended machines.
- **Companion:** variables, feedback and a [Companion module](companion-module/) with actions, feedbacks and presets.

## Security

The web page and the HTTP and OSC control have **no authentication**: anyone who can reach the port can play, stop and change settings. Run the player on a trusted network, behind a firewall, or behind a reverse proxy that adds authentication, and never expose port 8080 (web / HTTP) or 9000 (OSC) to the internet.

## Quick start

Requirements: Python 3, and for the best results ffmpeg (optional; see [Configuration](docs/wiki/Configuration.md)).

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

- **Linux (Debian), headless, with a USB audio interface** is the production target: run it as a systemd service (see [Install and run](docs/wiki/Install-and-Run.md)). Companion usually runs on the same machine.
- **Raspberry Pi, Windows and macOS** are supported too. On Windows use `run-player.bat`; on macOS `run-player.command`. (The memory readout is not implemented on macOS.)

**Updating:** copy `player.py`, `cpl/` and `static/` together over the old ones (the player refuses to start if `cpl/` or `static/` is missing or incomplete; on Windows also copy `run-player.bat`). Your playlists, library and settings are kept. To deploy from a clone of this repository with `deploy/deploy.ps1` (Windows, default install folder `C:\Apps\CueME`) or `deploy/deploy.sh` (macOS / Linux), see [Install and run: Deploy from a clone](docs/wiki/Install-and-Run.md#deploy-from-a-clone-deploy-scripts).

## Documentation

The guide is in the project wiki (the pages are kept in [`docs/wiki/`](docs/wiki/) until the wiki is live).

| Topic | Pages |
|---|---|
| Getting going | [Install and run](docs/wiki/Install-and-Run.md), [Configuration](docs/wiki/Configuration.md), [Audio outputs and Dante](docs/wiki/Audio-Outputs-and-Dante.md) |
| Using it | [Library and playlists](docs/wiki/Library-and-Playlists.md), [Play modes and end actions](docs/wiki/Play-Modes-and-End-Actions.md), [Trim](docs/wiki/Trim-A-B.md), [Trigger points](docs/wiki/Trigger-Points.md), [Play on Top](docs/wiki/Play-on-Top.md), [Live input](docs/wiki/Live-Input.md), [Level match](docs/wiki/Level-Match.md), [Preview, Solo and Mirror](docs/wiki/Preview-and-Solo.md), [Live operation](docs/wiki/Live-Operation.md), [Appearance and layout](docs/wiki/Appearance-and-Layout.md), [Stage page](docs/wiki/Stage-Page.md) |
| Companion | [OSC and HTTP commands](docs/wiki/OSC-and-HTTP-Commands.md), [Variables and settings](docs/wiki/Companion-Variables.md) |
| Monitoring | [Health, watchdog and push](docs/wiki/Health-and-Monitoring.md) |
| Developers | [API and data reference](docs/api-reference.md), [Live input design](docs/live-input-design.md), [Changelog](CHANGELOG.md) |

An operator's guide is also built into the player: **⚙ Settings > System > Maintenance > Help guide** (`http://<host>:8080/help`).

## Licence

The source code is MIT licensed (see `LICENSE`). The name "Cue Media Engine", "CueME" and the logo are not covered by that licence (see `TRADEMARKS.md`). Third-party notices (the Lucide icons, ISC and MIT) are in `NOTICE`.
