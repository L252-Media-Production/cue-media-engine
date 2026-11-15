# Configuration and storage

`config.json`, storage limits, ffmpeg and the data files.

## config.json (all optional)
Place it in the same folder as `player.py` and restart the player after editing by hand. (The Companion address
and port can instead be changed from ⚙ Settings on the web page, which updates this file for you.)
```json
{
  "default_transition": "cut",
  "crossfade_ms": 3000,
  "fadeout_ms": 2000,
  "toggle_off_fade_ms": 0,
  "storage_limit": null,
  "storage_reserve": "1GB",
  "play_mode": "stop",
  "preview_device": null,
  "mirror_enabled": false,
  "mirror_device": null,
  "meter_rate_hz": 4,
  "live_volume": 1.0,
  "resume_on_start": true,
  "resume_save_s": 5,
  "resume_max_age_s": 1800,
  "trim_fade_ms": 1500,
  "trim_fadein_ms": 0,
  "audio_device": null,
  "cache_mb": 768,
  "osc_in_port": 9000,
  "http_port": 8080,
  "companion_host": "127.0.0.1",
  "companion_osc_port": 12321,
  "var_prefix": "mp_",
  "ffmpeg_path": "",
  "ffmpeg_cores": 2,
  "ffmpeg_nice": 10,
  "import_convert": true,
  "import_normalise": true
}
```
`audio_device` must match a name from the startup device list exactly. You normally don't need to set it:
pick the output from the dropdown on the web page and the choice is remembered in `state.json`
(it overrides `config.json`). Switching outputs while a track is live carries it over to the new device from the same point (paused stays paused), with only a brief gap while the device opens. If the saved device is
missing at startup (e.g. Dante not connected yet) the player falls back to the system default.

## Storage limits
The Library header on the web page shows one line, for example "Library 1.6 GB of 60.0 GB cap (3%) · 51 file(s)" (without a cap:
"Library 1.6 GB · 51 file(s)"), with a slim usage bar under it. Hover over it to read the free disk space and how much room is left for
uploads ("Disk 348.4 GB free of 468.4 GB · room for uploads: 58.4 GB (library cap)"). The line turns orange at 80% and red at 95%, over the
cap, or when less than 50 MB is left for uploads; a red chip beside it says "Library is over its cap" or "Low room for uploads" so the
problem is visible without hovering. Uploads that would not fit are refused with a message. In `config.json`:
```json
{
  "storage_limit": "10GB",
  "storage_reserve": "1GB"
}
```
- `storage_limit`: cap on the total library size. Use an exact size (`"10GB"`, `"500MB"`) or a percentage of the
  whole disk (`"25%"`). A bare number means GB. `null` (default) means no cap.
- `storage_reserve`: free space that is always kept on the disk (default `"1GB"`). Uploads are refused if they
  would eat into it, even when the cap would allow them. Also accepts a size or a percentage.
- Sizes use 1 GB = 1024 MB. The percentage is of the disk's total capacity.
- Lowering the cap below what the library already uses never deletes anything; it just blocks new uploads
  until you delete files.

## ffmpeg (optional)
Everything works without it. When `ffmpeg` and `ffprobe` are installed (`sudo apt install ffmpeg`; no restart needed, the player looks again every minute) the player also uses it for:
- **More file types on upload:** m4a, aac, aiff, caf, wma, opus, oga, mp2, ac3, wv and the audio of video files (mp4, mov, mkv, webm, avi, 3gp...). They are converted to FLAC (48 kHz, 16-bit, stereo) in the library; the original is not kept. Without ffmpeg these are refused with a message saying so. Turn off with `"import_convert": false`.
- **Normalise at upload:** wav and flac files that are not 48 kHz, are over 16-bit, or have more than two channels are converted to 48 kHz / 16-bit / stereo, so they load fast and play at the right speed. If the conversion fails, the original is kept. Turn off with `"import_normalise": false`.
- **Waveforms:** drawn from a quick 8 kHz decode (also for tracks that are not in memory yet). If ffmpeg is missing or fails, the built-in decoder is used.
- **File checks:** every library file is looked at once in the background (results kept in `formats.json`). A yellow sign on a library row means a warning (more than two channels, very short); a red sign means the file cannot be read or has no audio. Hover for the reason; hover over a name to see its format (codec, rate, channels, bit depth). **Settings > Check all files** decodes every file completely to find damaged ones.
- **Level match:** loudness measured by ffmpeg's `ebur128` filter (see Level match).

ffmpeg is deliberately held back so it can never disturb playback: one job at a time, at low priority (`ffmpeg_nice`, default 10) and, on Linux, restricted to the last `ffmpeg_cores` CPU cores (default 2; ignored when the machine has no more cores than that). `ffmpeg_path` points at a specific ffmpeg if it is not on the PATH. `GET /api/ffmpeg` shows what was found and `GET /api/formats` the check status.

## Track lengths cache

- Track lengths are saved in `durations.json` next to `player.py`, with each file's size and modified time. On start-up
  only new or changed files are measured, so a restart with an unchanged library is ready in a moment. The file is safe
  to delete; lengths are then measured again (MP3/OGG/FLAC in a low-priority helper process, one at a time).
