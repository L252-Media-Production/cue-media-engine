# Install and run

Starting the player, the Linux service, Raspberry Pi, updating and how the folder is laid out.

## Run
First time only:
```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```
Every time after that (from this folder):
```
.venv/bin/python player.py
```
Open http://localhost:8080. At startup the available audio output devices are printed.

## Raspberry Pi
```
sudo apt install python3-venv
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python player.py
```
Pick the output with the web page's Output dropdown (HDMI, 3.5 mm jack or a USB interface). If SDL can't find
sound on a headless Pi, try `SDL_AUDIODRIVER=alsa python player.py`. If Companion runs on the same Pi, leave
`companion_host` at 127.0.0.1. On a Pi with a small SD card, set `storage_limit` so the library can't fill it.

Run at boot: `/etc/systemd/system/cue-media-engine.service`
```
[Unit]
Description=Cue Media Engine
After=network-online.target sound.target

[Service]
User=cueme
WorkingDirectory=/opt/cue-media-engine
ExecStart=/opt/cue-media-engine/.venv/bin/python player.py
Restart=always

[Install]
WantedBy=multi-user.target
```
Then `sudo systemctl enable --now cue-media-engine`. Adjust `User` and paths to match your setup.

## Folder layout
```
cue-media-engine/
├── player.py           the launcher (starts cpl/)
├── cpl/                the program (Python modules); copy it together with player.py
├── static/             the web page files (index.html, style.css, app.js ...) and help/stage/variables pages (deploy together with player.py)
├── run-player.bat      Windows launcher (run-player.command on a Mac)
├── config.json         optional settings
├── playlists.json      playlists and their order (created automatically)
├── state.json          remembered output device
└── media/library/      all audio files
```
**Updating the player:** copy `player.py`, `cpl/` and `static/` together (replace the old ones completely; the player refuses to start if `cpl/` or `static/` is missing or incomplete). On Windows also copy the new `run-player.bat`. Your playlists, library and settings are picked up on the next
start. To move the player to another machine, copy the whole folder.

**Upgrading from the one-folder-per-playlist layout:** the first start moves every file into `media/library/`
(identical files are merged into one), rewrites the playlists to reference the library, and keeps a safety copy of
the old data as `playlists.pre-library.json`.

## Notes
- **No glitches when a track loads.** A track is decoded into RAM before it plays. Decoding MP3, OGG or FLAC
  inside the player freezes its audio for seconds, so that work is done by a helper process instead and the
  music that is playing is never interrupted. The tracks from the focused one onward in its playlist are decoded
  ahead of time (in the background, at low priority), so normally every cue starts instantly.
- If you trigger a track that isn't ready yet (for example straight after starting the player, or one in a
  playlist you haven't focused), whatever is playing carries on, the page shows "Preparing …" and `mp_loading`
  holds the track name, and the new track cuts or crossfades in as soon as it is ready (a few seconds for a long
  MP3 or FLAC). Pressing Stop or Fade out cancels it, and triggering another track replaces it.
- `cache_mb` (default 768) is the RAM used for decoded tracks, least recently used first out. Decoded audio is
  about 11 MB per minute (stereo), so 768 MB holds roughly an hour. Lower it on a Raspberry Pi with little RAM; the
  warm-up then covers fewer tracks. Plain WAV files load fastest.
- Formats: wav, mp3, ogg, flac.
- Crossfades use equal-power curves so loudness stays steady.
