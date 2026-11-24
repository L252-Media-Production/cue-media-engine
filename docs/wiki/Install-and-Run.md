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

## Install from a .deb (Debian 12 and 13)
For Debian 12 (bookworm) and 13 (trixie), on amd64 (a NUC or PC) and arm64 (a 64-bit Raspberry Pi OS). The package carries
every Python package it needs, so the machine needs **no internet connection** to install it (apt only needs `python3`,
`python3-venv`, `ffmpeg`, `alsa-utils` and `adduser`, which are usually there or on the install medium).

1. From the project's **Releases** page, download the file for your Debian version and architecture, for example
   `cue-media-engine_2.9.1_debian12_amd64.deb`, and `SHA256SUMS`. (`dpkg --print-architecture` and `cat /etc/debian_version`
   tell you which one.)
2. Check the download: `sha256sum -c SHA256SUMS --ignore-missing` must print `OK` for your file.
3. Install: `sudo apt install ./cue-media-engine_2.9.1_debian12_amd64.deb` (the `./` matters).
4. Open `http://<host>:8080`. `systemctl status cue-media-engine` shows the service; `journalctl -u cue-media-engine -f` its log.

What is installed where:
- `/opt/cue-media-engine/`: the program (`player.py`, `cpl/`, `static/`, `VERSION`) and its Python environment `.venv`, made
  at install time from the wheels in `/usr/share/cue-media-engine/wheels/`.
- **Your data lives in the same folder**: `config.json`, `state.json`, `playlists.json`, `durations.json`, `resume.json`,
  `elevenlabs.key` and `media/library/`. The folder belongs to the user `cueme`; the program files belong to root.
- The service `cue-media-engine` runs as the system user `cueme` (member of `audio`), starts at boot and restarts 2 seconds
  after a crash. On a fresh install it is enabled and started.
- `/etc/default/cue-media-engine`: environment for the service, all commented out. For example, uncomment
  `SDL_AUDIODRIVER=alsa` if SDL finds no sound on a headless machine, then `sudo systemctl restart cue-media-engine`.
  Your edits survive updates.

**Updating:** install the new `.deb` the same way. Your data is kept, and **the player is not restarted**, so an update never
cuts the audio. It keeps running the old code until you run `sudo systemctl restart cue-media-engine`. Restart soon (between
shows): helper processes that the player starts (decoding, import, download) already run from the new files.

**Moving from an old `companionplayer` install** (`/opt/media-player`): the package never touches it. If `companionplayer` is
running when you install, the new service is enabled but not started, because both use ports 8080 and 9000. To move over,
between shows:
```
sudo systemctl disable --now companionplayer
cd /opt/media-player
sudo cp -a config.json state.json playlists.json durations.json resume.json elevenlabs.key media /opt/cue-media-engine/
sudo chown -R cueme:cueme /opt/cue-media-engine/config.json /opt/cue-media-engine/state.json \
  /opt/cue-media-engine/playlists.json /opt/cue-media-engine/durations.json /opt/cue-media-engine/resume.json \
  /opt/cue-media-engine/elevenlabs.key /opt/cue-media-engine/media
sudo systemctl start cue-media-engine
```
(`cp` reports any of those files that you do not have; that is fine.) Companion buttons that run `systemctl` as a shell
command must then use the unit name `cue-media-engine` instead of `companionplayer`. Keep `/opt/media-player` until the new
install has proven itself, then delete it by hand.

**Remove:** `sudo apt remove cue-media-engine` stops and disables the service and removes the program; the data and `.venv`
stay. `sudo apt purge cue-media-engine` also removes `.venv`, the compiled `__pycache__` folders, `VERSION` and
`/etc/default/cue-media-engine`. **Neither ever deletes your data** (`config.json`, `state.json`, `playlists.json`,
`durations.json`, `resume.json`, `elevenlabs.key`, `media/`), and the user `cueme` is kept. Delete
`/opt/cue-media-engine` by hand if you no longer need it.

**Building the package yourself** (needs Docker): `packaging/build-deb.sh --debian 12 --arch amd64` in a clone of the
repository writes the `.deb` to `dist/deb/`. See `packaging/README.md`.

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

## Deploy from a clone (deploy scripts)
The scripts in `deploy/` copy `player.py`, `requirements.txt`, `cpl/` and `static/` (and `run-player.bat` on Windows) from a
clone of this repository into the folder the player runs from (the *install folder*), and write the deployed tag or commit to
`VERSION` there. Your `config.json`, `state.json`, `playlists.json`, `media/` and `elevenlabs.key` in the install folder are never
touched. The script checks out the tag or branch you name in the clone (a branch is reset to `origin` first), so keep no
uncommitted work in that clone. On Windows, stop the player first.

Before anything else the script prints three lines, so you can see what it is about to do:
```
Source folder:  C:\src\cue-media-engine
Source origin:  https://github.com/L252-Media-Production/cue-media-engine.git
Install folder: C:\Apps\CueME (default)
```
The last line says which rule chose the install folder: `set by -App`, `set by CUEME_APP` or `default`.

- **Source folder:** the clone that holds the script. Set `CUEME_SRC` to deploy from another clone.
- **Install folder:** on Windows the `-App` parameter, else the environment variable `CUEME_APP`, else `C:\Apps\CueME`.
  On macOS and Linux `CUEME_APP`, else `/opt/media-player`.
- A folder named by `-App` or `CUEME_APP` must exist: if it does not (a typo), the script stops and changes nothing. Only the
  Windows default `C:\Apps\CueME` is created by the script, on the first deploy. On macOS and Linux the script never creates
  the install folder.

**Windows** (PowerShell):
```
git clone https://github.com/L252-Media-Production/cue-media-engine.git C:\src\cue-media-engine
powershell -ExecutionPolicy Bypass -File C:\src\cue-media-engine\deploy\deploy.ps1 -Ref v2.9.1
C:\Apps\CueME\run-player.bat
```
Another install folder, once: add `-App D:\Show\CueME`. To make it permanent, set it once and open a new PowerShell window:
```
setx CUEME_APP D:\Show\CueME
```
(and, if you keep the clone somewhere else than where you run the script from, `setx CUEME_SRC <clone folder>`).
`run-player.bat` creates the `.venv` on its first start. To create it yourself instead (the script prints these two commands
when the install folder has no `.venv`):
```
py -3 -m venv "C:\Apps\CueME\.venv"
"C:\Apps\CueME\.venv\Scripts\python.exe" -m pip install -r "C:\Apps\CueME\requirements.txt"
```

**macOS and Linux:**
```
git clone https://github.com/L252-Media-Production/cue-media-engine.git ~/cueme-src
mkdir -p ~/cueme
CUEME_APP=~/cueme bash ~/cueme-src/deploy/deploy.sh v2.9.1
cd ~/cueme && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python player.py
```
Without `CUEME_APP` the install folder is `/opt/media-player` (it must exist). On a Linux service, restart the service after
the deploy; run `pip install -r requirements.txt` again only when `requirements.txt` changed.

## Notes
- **No glitches when a track loads.** A track is decoded into RAM before it plays. Decoding MP3, OGG or FLAC
  inside the player freezes its audio for seconds, so that work is done by a helper process instead and the
  music that is playing is never interrupted. The tracks from the focused one onward in its playlist are decoded
  ahead of time (in the background, at low priority), so normally every cue starts instantly.
- If you trigger a track that isn't ready yet (for example straight after starting the player, or one in a
  playlist you haven't focused), whatever is playing carries on, the page shows "Preparing …" and `mp_loading`
  holds the track name, and the new track cuts or crossfades in as soon as it is ready (a few seconds for a long
  MP3 or FLAC). Pressing Stop or Fade out cancels it, and triggering another track replaces it.
- `cache_mb` (default 768) is the most RAM used for decoded tracks, least recently used first out. Decoded audio is
  about 11 MB per minute (stereo, whatever the file type), so 768 MB holds roughly an hour. Since 2.8.1 the player
  never uses more than a quarter of the machine's RAM, nor the RAM minus 1 GB, whatever `cache_mb` says, so the same
  `config.json` is safe on a 4 GB Raspberry Pi (limit about 1 GB) and a 31 GB NUC (about 7.7 GB). The track that is
  playing, the one after it and the cue are never dropped; a track that is not in RAM is decoded from its file when it
  is played. `tests/tools/ram_breakdown.py <install folder>` prints what a library needs. Plain WAV files load fastest.
- Formats: wav, mp3, ogg, flac.
- Crossfades use equal-power curves so loudness stays steady.
