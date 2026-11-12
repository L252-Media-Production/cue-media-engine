# Audio engine audit: what depends on pygame

Scope: `player.py` (6643 lines; CLAUDE.md says ~4,900, so that figure is stale). Read-only audit, no code was changed.
Line numbers refer to the current file. "Verify" marks things that come from knowledge of pygame/SDL_mixer behaviour rather than from this code.

Purpose: plan a swap of the output engine (pygame/SDL on Linux, PortAudio with ASIO on Windows, Core Audio on macOS).

## 0. Findings that differ from the brief

- **`pygame.mixer.music` is not used anywhere.** There is no streamed playback. Every track, including the live one, is a decoded `Sound` in RAM played with `Sound.play()`.
- **`set_endevent` and `pygame.event` are not used.** No `pygame.init()`, `pygame.time`, `pygame.display` either. End of track is found by polling (section 3).
- **`Channel.get_busy()` is used only in the preview worker** (lines 236, 258).
- **`pygame.mixer.stop/pause/fadeout/find_channel` (module level) are not used.** All control is per `Channel`.
- **pygame's own fade (`Sound.fadeout`, `play(fade_ms=)`) is not used.** Fades are done by the Python tick setting channel volume (section 4).
- pygame is also used for **decoding** in three helper entry points (`--probe`, `--decode`, `--preview`). Replacing the output engine does not remove pygame unless decoding is replaced too (section 6).

## 1. pygame calls, what they do, and who owns them

### 1.1 Main process (live output)

| Line | Call | Owner | What it does |
|---|---|---|---|
| 330 | `import pygame` | module top level | Main-process import. The three helper modes import it earlier (lines 24, 37, 147). |
| 1472 | `mixer.pre_init(48000, -16, 2, 1024)` | `init_mixer` (1471) | Fixes 48 kHz, signed 16-bit, stereo, buffer 1024 samples (about 21 ms). |
| 1476, 1478 | `mixer.init(devicename=..., allowedchanges=0)` | `init_mixer` | Opens the device by name, or the system default. `allowedchanges=0` forces SDL to convert to 48k/16/stereo rather than open the device natively. The code relies on this: meters, ducking and loudness read the decoded audio as exactly that format. |
| 1479 | `mixer.set_num_channels(16)` | `init_mixer` | 16 simultaneous voices. |
| 1480 | `mixer.get_init()` | `init_mixer` | Verifies the format; sets `ISSUES["audio_fmt"]` if different. |
| 1490-1491 | `pygame._sdl2.audio.get_audio_device_names(False)` | `list_devices` (1488) | Output device list. This is a private module (`_sdl2`). The device name string is what is stored in `config.json` / `state.json` and matched in `/api/devices`, `/device/<n>`. |
| 1541 | `mixer.quit()` | `set_device` (1530) | Closes the device before reopening on another one. |
| 5118 | `mixer.quit()` | `h_restart` (5107) | Cleanup before `os.execv`. |
| 2819 | `mixer.get_init() is None` | `health` (2816) | Drives the red status light ("audio output is not open"). |
| 1122, 1138, 1150, 1205, 1505, 1517 | `mixer.get_init()` | `cache_put`, `cut_sound`, `trimmed_put`, `decode_in_child`, `_live_snapshot`, `_live_restore` | Reads freq/format/channels to compute byte sizes and frame sizes, and to tell the decode helper what to produce. |
| 1230 | `mixer.Sound(path)` (executor) | `_load` (1224) | Loads a WAV directly in the player process (no decoder involved). |
| 1236 | `mixer.Sound(buffer=raw)` | `_load` | Wraps PCM from the decode helper. |
| 1230-1231, 1140, 1505 | `Sound.get_raw()` | `_load`, `cut_sound`, `_live_snapshot` | Gets the PCM bytes back (for envelopes, ducking key, trimming, device change). |
| 1123, 1151, 1586, 1745, 1762, 2270 | `Sound.get_length()` | `cache_put`, `trimmed_put`, `Deck.__init__`, `seek_live`, `_start` | Duration in seconds. Used for cache accounting, deck duration, trim range, seek bounds. |
| 1140 | `mixer.Sound(buffer=memoryview slice)` | `cut_sound` (1136) | Makes a trimmed copy (In..Out, or from a seek/resume position). |
| 1518 | `mixer.Sound(buffer=s["raw"])` | `_live_restore` (1508) | Rebuilds the sound on the new device after a device change. |
| 2300 | `Sound.play(loops=-1 / 1 / 0)` | `_start` (2267) | Starts a voice; pygame picks a free channel. Returns `None` if none is free ("no free mixer channel"). Returns the `Channel`. |
| 1754 | `Sound.play(loops=0)` | `seek_live` (1737) | Starts the cut sound for a seek. |
| 1643, 1732 | `Channel.set_volume(v)` | `Deck.apply` (1642), `set_live_volume` (1722) | The only volume control: `vol * gain * duck * live_volume`. Used for fades, crossfade, ducking, level match, master volume, mute. |
| 1655-1656 | `Channel.pause()` | `Deck.pause` (1653) | Pause. |
| 1664 | `Channel.unpause()` | `Deck.resume` (1658) | Resume. |
| 1668-1669 | `Channel.get_sound()`, `Channel.stop()` | `Deck.stop` (1667) | Stops only if the channel still holds this deck's sound (so a reused channel is not killed). |
| 1707 | `Channel.get_sound() is not self.sound` | `Deck.update` (1671) | Detects that the channel finished playing. This is the one hardware-driven end signal (section 3). |
| 1759 | `Channel.stop()` | `seek_live` | Stops the old voice after the new one is started. |
| 1765 | `Channel.pause()` | `seek_live` | Re-applies pause on the new voice. |
| 3123 / 1530 | `set_device` | `command` `/device`, `h_set_device` (5920) | Device switch entry points. |

`allowedchanges=0`, `pre_init` and `set_num_channels` are the whole configuration surface. There is no use of panning, `Channel.set_volume(left, right)`, queues (`Channel.queue`), or `Channel.set_endevent`.

### 1.2 Preview / Mirror worker (`player.py --preview <device>`, lines 144-327)

A separate process with its own mixer.

| Line | Call | What it does |
|---|---|---|
| 149 | `mixer.pre_init(48000, -16, 2, 1024)` | Same nominal format. |
| 151 | `mixer.init(devicename=_dev)` or `mixer.init()` | Opens the preview/mirror device. **No `allowedchanges=0` here** (default lets SDL change frequency/channels). See risk R8. |
| 155 | `mixer.set_num_channels(4)` | Channel 0 = preview, channels 1-3 = live monitor (Solo / Mirror). |
| 173-176, 247-249 | `Sound(buffer=raw[off:])`, `Channel(n).play(snd)`, `set_volume` | Start from an offset by slicing the raw bytes (this copies). |
| 184, 207 | `Sound(path).get_raw()` | The worker decodes files itself, in-process, for the preview (`_load_and_play`) and for the monitor (`_mon_load`, `MRAW`, up to 4 files). |
| 236, 258 | `Channel.get_busy()` | Detects that the preview (258) or a monitor voice (236) finished, or restarts a monitor voice that stopped. |
| 176, 249, 317, 321 | `Channel.set_volume` | Preview volume, Solo mute, monitor volume. |
| 300, 304 | `Channel.pause()` / `unpause()` | Preview pause and resume. |
| 171, 252, 262 | `Channel.stop()` | Stops. |

### 1.3 Helper processes that need pygame only for decoding

| Line | Mode | Use |
|---|---|---|
| 17-27 | `--probe <file>` | `SDL_AUDIODRIVER=dummy`, `mixer.init()`, prints `Sound(path).get_length()`. Used by `_probe_dur` (5196) for the duration of non-WAV files. |
| 30-46 | `--decode <file> <freq> <fmt> <chans>` | `SDL_AUDIODRIVER=dummy`, `pre_init` + `init`, checks `get_init()` matches, writes `Sound(path).get_raw()` to stdout. Used by `decode_in_child` (1204) for MP3/OGG/FLAC, and by `_loud_worker` as the loudness fallback. |

These use SDL_mixer's decoders and its resampler/channel converter (section 6).

## 2. How playback works

### 2.1 Sound objects, not streaming

- **Decode first, play from RAM.** A track must be decoded before it can start. WAV: `Sound(path)` in an executor (1230). MP3/OGG/FLAC: decoded in a `--decode` child process and wrapped with `Sound(buffer=raw)` (1236). `get_raw()` of the WAV is also taken for the envelope and ducking key.
- **Cache.** `_cache` is an LRU of `path -> (Sound, nbytes)` (1121 `cache_put`, 1090 `cached`), budget `cache_mb`. `_tcache` holds trimmed copies keyed `(path, lo, hi)`, counted in the same budget. `cache_drop` (1111) forgets all derived data. Memory per minute of audio at 48k/16/stereo is about 11.5 MB.
- **Warm-up.** `request_warm` (1273) / `_warm_loop` (1285) decode two tracks at a time ahead of the cue. `_warm_trims` (1316) pre-cuts trimmed tracks via `cut_sound` in an executor so that cueing does not copy audio on the event loop.
- **Starting.** `play()` (1792) and `play_on_top()` (1965) either start at once from cache, or set `pending` and `spawn(_start_when_ready)` (2000). `_start` (2267) does the real work.
- **Device change** (`set_device`, 1530) clears both caches because a `Sound` belongs to the mixer instance that made it. The live track is carried over through `_live_snapshot` / `_live_restore` (1496, 1508) by re-wrapping its raw bytes.

### 2.2 Trim start/end (A/B)

- Trim data: `trim_of` / `trim_range` (606) / `set_trim`. `trim_range` returns `(lo, hi, trim)` in file seconds.
- Start at In, stop at Out: `_start` (2267-2282) calls `cut_sound(snd, start, hi)` (a new `Sound` holding only the window, with `trimmed_cached` for the pre-cut one) whenever `start > 0.05` or `hi < full - 0.01`. Nothing is trimmed inside the audio callback or by SDL; the engine just plays a shorter buffer.
- The Deck keeps `base` (file position where the played sound begins), `lo`, `hi` (2305-2306). `fpos() = base + elapsed` (1605).
- **Fade at B**: `deck.end_fade_ms = trim_fade_ms` when the trim has an Out with `end == "fade"` (2307-2308). `Deck.update` (1694-1700) starts a volume fade that ends exactly when the cut sound ends. **Cut at B** simply lets the shorter sound end.

### 2.3 Seeking

- `seek_live` (1737) builds a new cut `Sound` from `pos` to `hi`, calls `new.play(loops=0)` first, then stops the old channel (1754-1759). The deck's `sound`, `channel`, `base`, `duration` and `started` are replaced; loop state is reset (`d.loop=False`, `passes=1`). Pause state is re-applied by pausing the new channel.
- Consequence: seeking within a looping track turns the loop off for that pass; the old and new voices overlap for a moment with no fade. Both are existing behaviours a new engine must reproduce or consciously change.
- Resume after restart / device change uses the same cut mechanism through `_start(..., offset=...)` (2268-2278), `try_resume` (2489), `_live_restore` (1508).

### 2.4 Loops and end-of-track modes

- **Per-track end action** (`END_ACTIONS`, 543; `end_of` 546; `is_loop` 555): `default`, `once` (two passes), `loop` (forever), `stop`.
- **Loop forever:** `play(loops=-1)` (2300). The loop is inside SDL_mixer, so the boundary is sample-exact (verify for MP3-derived buffers: no encoder padding is trimmed because the buffer was decoded whole). It is applied only when the pass starts at the In point (`fresh`, 2294-2295). A resumed or seeked pass plays once and then the app restarts the track through `auto_advance` (a small gap).
- **Loop once:** `play(loops=1)` = two passes; `Deck.passes = 2` (2306). The deck tracks pass number from wall-clock time (`pass_no`, 1619).
- **Mode change while looping:** `Deck.update` (1672-1708) computes `end_at` = end of the pass that is running and removes the deck then, calling `Channel.stop()`. The audio of the next pass can leak by up to one 50 ms tick.
- **Play modes** (`stop`, `loop_playlist`, `next_playlist`, `shuffle`) are not engine-related: `next_in_order` (2392) and `auto_advance` (2429) choose the next track and call `play()` after the previous deck is reported as naturally ended.
- **Play on Top:** `_start(..., top=True)` plays the new track at its own level without fading the others, and `duck_arm` (1858) starts the ducking loop (section 4).

## 3. Position, time remaining and end detection

### 3.1 How they are produced

- **Everything is wall-clock based.** `Deck.started = time.monotonic()` is set in `Deck.__init__` right after `play()` returns (1591, constructed at 2304). `elapsed()` = `(paused_at or now) - started` (1602). `fpos()` (1605) = `base + min(elapsed, duration)`, modulo `duration` while looping. `remaining()` (1612) = `duration - elapsed` (modulo for loops). `pass_no()` (1619).
- Pause: `paused_at` stored; `resume()` shifts `started` by the paused gap (1658-1665). Seek and resume-from-offset restart the clock (`started = now`, 1763).
- **Consumers:** `snapshot()` "remaining" (2851); `h_state` `live_pos`, `live_rem` (5150-5153; the stage page counts down from `live_rem`); ducking look-up `top.fpos()` (1911); `monitor_decks` (2777); `save_resume` / `_live_snapshot` (2481, 1503); meters (`Deck.level`, 1625).
- No value is read back from the output device (no frames-played counter, no stream time). pygame does not offer one.

### 3.2 End-of-track detection

- `ticker` (6496) calls `tick()` (2570) every 50 ms from the asyncio loop. `tick` calls `Deck.update` (1671) for each deck. A deck is finished when either
  1. `elapsed >= duration * passes` (1696-1709), or
  2. `channel.get_sound() is not self.sound` (1707), i.e. pygame cleared the channel because the voice ended.
- `natural` is set when it ended by itself (not by a fade-out kill) (1706). `tick` then calls `auto_advance` (2429) for the live deck, handles the "track on top finished, bring background back" case, and a background track that ended under a top track.
- The preview worker has its own copy of this logic, using `get_busy()` (258) and a wall-clock position (`_pos`, line 156-163).

### 3.3 Accuracy (what the code implies, not measured)

- Granularity of end detection is the 50 ms tick, plus asyncio scheduling jitter if the event loop is busy (CLAUDE.md warns about CPU-heavy tasks on the tick for this reason).
- The clock starts when `play()` returns, but sound leaves the device one buffer later (1024 samples = 21.3 ms at 48 kHz, plus whatever SDL/ALSA/WASAPI adds; verify on the production machine). So `fpos()` runs a little **ahead** of what is audible. This is not compensated.
- The wall clock and the audio device clock drift apart slowly (Dante USB adapter with its own clock). Over a 10-minute track this can be tens of milliseconds. Not corrected.
- Gaps between tracks: `auto_advance` is only called after the first tick that sees the end, then `play()` starts the next cached sound immediately. There is no pre-queued next voice, so the gap is detection delay (0-50 ms) plus start latency. Gapless is not guaranteed.
- Pause/resume does not account for the buffered audio still in the device.

## 4. Meters, level match, fades, crossfade

### 4.1 Meters

- **Meters are not measured from the output.** They are computed from the decoded PCM ahead of time.
  - `compute_env` (125): per-50 ms peak (L, R) of 48k/16/stereo int16, stored in `_env[path]`.
  - `Deck.level` (1625): reads the envelope between the previous read and the current `fpos()`, takes the max, and multiplies by `vol * gain * duck * live_volume` **at the moment of reading** (not the gain that was in effect when that audio was played).
  - `update_meters` (2538) sums the decks in power (`sqrt(sum l^2)`), converts to dB, applies a 30 dB/s decay (`METER_DECAY`), and publishes to the page (`meters_json` 2562; SSE `/api/live` at about 14 Hz, 5819) and to Companion variables.
- The envelope is computed in the background after the track starts (`_env_job`, 1241); until then the meter is flat (1630).
- The preview/mirror worker builds its own envelope the same way (`compute_env`, line 196) and reports `l`, `r` each 100 ms (250-270); `update_meters` reads them from `preview.status`.
- Consequences: meters ignore clipping, SDL's rounding, and anything the device does; they are tied to the wall clock position; the mirror and monitor outputs are not metered.

### 4.2 Level match

- Per playlist: `norm_gain` (2105) turns a measured LUFS (ffmpeg ebur128 via `ff_loudness` 2172, or `lufs_from_pcm` 2042 on decoded PCM) into a linear gain **never above 1.0** (`norm_gain_db` 2088, `min(0.0, target - mine)` at 2102).
- Applied as `Deck.gain` (set in `_start`, 2309) and multiplied into channel volume (1642-1643). `apply_gain_live` (2110) re-applies it to running decks when a measurement arrives.

### 4.3 Fades and crossfade

- Fade state lives in `Deck.fade` (`start_fade`, 1645). `Deck.update` (1671-1690) advances it on the 50 ms tick and sets `vol` with **equal-power curves** (sin for fade in, cos for fade out) through `set_vol` -> `Channel.set_volume`.
- **Crossfade:** `_start` (2291-2295) starts a `kill_on_fade_end` fade-out on every current deck and a fade-in on the new one (`set_vol(0.0)` then `start_fade(1.0, ms)`). It is two independent equal-power ramps, one per deck.
- **Fade-out / stop:** `fade_out` (2336) uses the same kill fade. `toggle` (2349) uses `toggle_off_fade_ms`.
- **Ducking:** `_duck_loop` (1896) runs every 10 ms on the asyncio loop, reads the pre-analysed curve (`duck_key` 1822, `duck_curve` 1841) at `top.fpos()` plus 20 ms look-ahead, smooths with attack/release, and writes `Deck.duck` for each background deck, then `apply()` (only when the multiplier changed by more than 0.0005).
- **Master volume:** `set_live_volume` (1722) loops over decks and sets each channel volume.
- **Quantisation (verify):** SDL_mixer channel volume is an integer 0-128, so every one of these gains is quantised to 1/128 steps; a slow fade-out is audibly stepped near the bottom, and the 50 ms tick adds zipper steps on top. A float-gain callback engine removes both.
- The preview/mirror worker applies `W["vol"]` and per-deck `vol` through `set_volume` as well; monitor updates are throttled to 10 Hz (`monitor_sync`, 2782: `now - _mon["t"] < 0.1`; resend on a changed `(id, vol)` signature or every 0.5 s). Fades and ducking on the mirror are therefore much coarser than on the main output.

## 5. Preview worker and Mirror

- **Process model.** `Preview` (2607) starts `python player.py --preview <device>` with `asyncio.create_subprocess_exec` (`_spawn`, 2636). Commands are JSON lines on stdin (`play`, `stop`, `pause`, `resume`, `seek`, `vol`, `solo`, `mon`, `quit`); status is JSON lines on stdout every 100 ms (`state`, `pos`, `dur`, `error`, `l`, `r`, `solo`, `mon`).
- **Device opening.** The worker opens `pygame.mixer.init(devicename=<name>)` itself (151). On failure it prints `{"state":"error", ...}` and exits with code 2 (153). `Preview.set_device` (2712) quits the old worker and starts a new one on the new name. The device name comes from the same `list_devices()` list as the main output (validated in `h_pv_device` 5885-5892 and `h_mirror_device` 5896).
- **Relationship to the main output.** None at the audio level. Each process opens its own SDL audio device; there is no shared clock, no shared buffer, no sample sync. Two outputs on the same hardware device would need the OS/driver to allow it (ASIO normally does not).
- **Solo live:** `monitor_set` (2761) sends `solo`; `monitor_sync` (2782) sends `mon` with up to 3 audible decks `{id, path, pos, vol}` (`monitor_decks` 2768). The worker loads the file itself (up to 4 in `MRAW`) and plays `raw[off:]` from `pos`. A voice is restarted when the path changes, when it is no longer busy, or when it is more than 0.3 s away from the expected position (236). The monitor does not know about loops or trim: it plays the full file from the reported position, and is re-synced when the main deck wraps.
- **Mirror.** `Mirror(Preview)` (2730) uses the same worker with `solo` always on, keyed to `CFG["mirror_device"]` and `mirror_enabled`; `apply()` restarts or stops the worker. It is a copy of the live decks driven by position messages, not an audio-level tap.
- **Latency/quality.** The mirror starts late if the worker has not decoded the file yet (`_mon_load` runs on first sight), and its start is offset by the stdin message delay. Alignment with the main output is therefore within hundreds of milliseconds, not samples (the 0.3 s drift threshold shows the intent).
- **Restart handling.** `h_restart` (5107) kills `preview.proc` (5117) but not `mirror.proc`; the worker exits when its stdin closes at `os.execv`, so this is harmless but inconsistent.

## 6. What pygame does implicitly that a callback engine would have to do

| Duty | Where it happens today | Notes |
|---|---|---|
| **Decoding MP3/OGG/FLAC (and WAV)** | `Sound(path)` in `--decode`, `--probe`, `--preview`, and in-process for WAV (1230) | SDL_mixer's loaders. Replacing the output engine alone does not remove this. A new engine either keeps a pygame decode helper (pygame stays a dependency, at least on Linux) or moves decoding to ffmpeg/soundfile/miniaudio. ffmpeg is already optional, with fallbacks, so it cannot be assumed present. |
| **Resampling to 48 kHz** | SDL_mixer converts at load time (`Sound(path)` after `pre_init(48000)`), and again at device level if the device cannot do 48k (`allowedchanges=0`) | The whole app assumes decoded audio is exactly 48k. Hard-coded in `compute_env` (125), `duck_key` (1822), `lufs_from_pcm` (2042), `_BPS` in the worker (156), `needs_normalising` (6241: files that "the mixer would have to resample" are converted on import). A PortAudio device on ASIO may be fixed at 44.1 or 96 kHz, so a device-rate resampler becomes necessary. |
| **Channel conversion** | Mono to stereo and 5.1/etc. downmix at load (`--decode` check at line 41 expects stereo) | Level behaviour of the mono upmix must be preserved (verify against SDL: CLAUDE.md notes ffmpeg's `-ac 2` upmix differs by 3 dB for waveforms). The app only supports a stereo output. ASIO multichannel routing would be new work. |
| **Bit depth** | Everything is int16 (`dtype=np.int16` in 130, 1826, `<i2` in 2047) | A float32 callback engine would convert at the edge or switch the analysers to float. |
| **Mixing several voices** | 16 SDL channels summed in the SDL audio callback | A new engine needs its own mixer: sum of active voices with per-voice gain, sample-accurate start/stop, pause. |
| **Clipping** | SDL_mixer saturates the int16 sum | Needs an explicit clip/limiter decision. Meters currently ignore it. |
| **Per-voice volume** | `Channel.set_volume` (0-128 steps) | A new engine should use float gain with ramping per block (also fixes zipper noise). |
| **Looping** | `loops=-1/1` | The new voice needs loop count and a loop window (lo..hi) of a shared array. |
| **Windowed playback** | Not supported; the app copies sliced buffers (`cut_sound`, `_tcache`, `_warm_trims`) | With a custom mixer a voice can play `[lo, hi)` of the one cached array with no copy, so `cut_sound`, `trimmed_cached`, `trimmed_put`, `_tcache` and `_warm_trims` could go. Cache accounting (`_cache_total`, `mem_info`) must be adapted. |
| **Voice allocation** | `Sound.play()` finds a channel, returns `None` if none free | New engine must define its own voice limit and error. |
| **Channel finished notice** | `Channel.get_sound()` becoming `None`, `get_busy()` | A callback engine can post an event when a voice ends (see proposal). |
| **Pause/unpause** | `Channel.pause()` | Voice flag in the mixer. |
| **Device open/enumerate** | `mixer.init(devicename=)`, `_sdl2.audio.get_audio_device_names` | Names will differ per host API (e.g. "Dante ... (ASIO)", Core Audio names). Saved `audio_device`, `preview_device`, `mirror_device` strings in `config.json` / `state.json` need a migration or fuzzy match. |
| **Fallback on failure** | `main` (6515-6522) falls back to default; `set_device` (1530-1556) falls back to the old device, then to default | Must be preserved. |
| **Latency/buffer** | `buffer=1024` | A new engine chooses its own buffer; the position model should add output latency. |
| **GIL** | SDL's audio thread is C and independent of Python | A Python PortAudio callback runs under the GIL on the audio thread. The event loop, numpy work and executor threads then compete with it (risk R1). |

## 7. Engine-independent code (would not change)

- Library, playlists, trims, end actions, play modes: `end_of`, `is_loop`, `set_end`, `trim_of`, `trim_range`, `set_trim`, `next_in_order`, `auto_advance`, `play_playlist`, `_bag`.
- Command grammar `command` (2914) and the HTTP/OSC server, `/api/*`, SSE, snapshot variables, `push` to Companion, `VAR_INFO`, Companion module, Stage page, web UI, tour, help, custom layout.
- `fade_out`, `toggle`, `play_default`, `set_duck` and the ducking maths (`duck_key`, `duck_curve`, the control logic of `_duck_loop`), apart from how a gain is delivered to the engine.
- `compute_env`, `lufs_from_pcm`, `norm_gain_db`, `norm_gain`, loudness workers, `ff_*` helpers, file information, format checks, durations (`_probe_dur` apart from its pygame fallback), downloads, import/convert, storage, time warnings, resume files (`save_resume`, `try_resume`), `mem_info`.
- Meter smoothing and publishing (`update_meters`, `meters_json`), as long as the source of levels stays the same.
- Cache policy (`cached`, LRU, warm order, `request_warm`/`_warm_loop`), apart from the object stored and `_tcache`.

## 8. Proposed engine interface

Based on what the code actually calls. The goal is a small class that `Deck` and `set_device` use instead of `Channel` / `mixer`.

```python
class AudioEngine:
    # lifecycle / device
    def open(self, device: str | None) -> Format          # replaces init_mixer; returns (rate, channels, dtype); raises on failure
    def close(self) -> None                                # replaces mixer.quit
    def is_open(self) -> bool                              # replaces mixer.get_init() is None in health()
    def format(self) -> Format                             # replaces mixer.get_init() in cache/_live_*
    @staticmethod
    def list_devices() -> list[str]                        # replaces _sdl2 get_audio_device_names
    def latency_s(self) -> float                           # new: lets position be corrected

    # media
    def make_buffer(self, pcm: bytes | ndarray) -> Buffer # replaces Sound(buffer=...); has .length, .raw
    def load_file(self, path) -> Buffer                    # replaces Sound(path) for WAV; decoder helper stays outside

    # voices
    def play(self, buf, *, start=0.0, end=None, loops=0,   # loops: 0 once, 1 twice, -1 forever
             gain=1.0, paused=False) -> Voice | None       # replaces Sound.play; None = no voice free
    # Voice:
    #   set_gain(g, ramp_ms=0)    replaces Channel.set_volume (adds a sample-accurate ramp)
    #   pause() / resume()
    #   stop()
    #   seek(pos)                  replaces seek_live's cut + replay
    #   position() -> float        frames actually played (new), replaces wall clock
    #   is_active() -> bool        replaces get_sound() is self.sound / get_busy()
    # master
    def set_master(self, g: float) -> None                 # replaces the loop in set_live_volume
```

Events (from the audio thread to the event loop, through a thread-safe queue read in `tick`):

- `voice_ended(voice, natural: bool)` replaces polling `get_sound()` and the `elapsed >= total` check.
- `voice_looped(voice, pass_no)` replaces the wall-clock pass counter.
- `device_lost(reason)` / `xrun(count)` new, for `health()`.
- `peak(voice or mix, l, r)` optional: real post-gain meter data, replacing `Deck.level`.

Preview and Mirror: keep the process-per-output model first (the worker would use the same `AudioEngine`), and keep the JSON-line protocol unchanged so the page and the Companion module do not notice.

## 9. Risks, ranked

| # | Risk | Why |
|---|---|---|
| R1 | **Python audio callback and the GIL** | A PortAudio callback written in Python runs on the audio thread with the GIL. The event loop (50 ms tick, 10 ms duck loop, JSON, aiohttp), numpy analysers and executor threads can hold it and cause underruns. The current design avoids this because SDL's mixing thread is C. The new mixer needs either a callback that only uses numpy/C and tiny work, a ring buffer fed by a writer thread, a separate audio process, or a native/extension mixer. This decides the architecture and needs a prototype. |
| R2 | **ASIO availability and device behaviour on Windows** | Typical PortAudio wheels for Python (e.g. sounddevice) do not include ASIO (verify); it needs a PortAudio build with the Steinberg SDK or another binding. ASIO devices are often exclusive, fixed rate, multichannel, and not shareable between the main output, preview and mirror processes. Device names differ and saved names will not match. |
| R3 | **Format and decode assumptions are hard-coded** | 48 kHz / int16 / stereo in `compute_env`, `duck_key`, `lufs_from_pcm`, `_BPS`, `needs_normalising`, the decode helper, `get_raw` users. A device with another rate (44.1/96 kHz ASIO), more channels, or float samples touches many places. Decoding itself is still pygame (section 6). |
| R4 | **Timing model changes** | Position, remaining time, end detection and auto-advance all rely on wall-clock `Deck` state (section 3). Moving to frame counters changes every consumer (stage page, Companion `remaining`, ducking look-up, resume, mirror sync). Must be done behind `Voice.position()` with a wall-clock fallback and compared side by side. |
| R5 | **Fade/duck/crossfade delivery** | Today gain steps come from the Python tick (50 ms, 10 ms for ducking) quantised to 1/128. A callback engine should receive targets and ramp per block; otherwise the new engine reproduces the stepping and adds callback latency. Equal-power maths must stay identical. |
| R6 | **Mixer correctness** | Must handle clipping, voice limit, loop boundaries, pause, windowed play, and start/stop sample accuracy as well as SDL does. Mono/stereo upmix level and loop-point exactness need listening and null tests. |
| R7 | **Device switching and failure handling** | `set_device` closes everything, clears caches, restores the live track, falls back to old/default device (1530-1556). A new device layer must keep the same guarantees; the cache clear is currently required by pygame (a `Sound` belongs to its mixer), which a pure-array engine would not need. |
| R8 | **Preview/Mirror worker robustness** | The worker opens its mixer without `allowedchanges=0` (151) but assumes 48000x2x2 (156). On a device that forces another format, positions and offsets are wrong today. Mirror sync is by messages at 10 Hz with a 0.3 s drift threshold, with no loop or trim knowledge. This is an existing weakness; moving the worker to the new engine without fixing it carries it over. |
| R9 | **Platform packaging** | `requirements.txt` has `pygame` on Linux/macOS and `pygame-ce` on Windows. Adding PortAudio bindings means a native library per OS, and the headless Debian production machine needs ALSA/PortAudio packages (`nuc-setup.sh`). Linux should stay on SDL until proven. |
| R10 | **Memory/cache accounting** | `cache_put`, `trimmed_put`, `mem_info`, `_warm_trims` assume `Sound` objects with `get_length()` and copies for trims. Changing to shared arrays changes the numbers shown in the header and the eviction rules. |

## 10. Suggested phases

1. **Isolate (no behaviour change).** Add an `AudioEngine` wrapper with the interface above and implement `PygameEngine`, moving all `pygame.mixer` calls behind it (`init_mixer`, `list_devices`, `Deck`, `seek_live`, `_start`, `set_live_volume`, `cache_put`/`cut_sound`, `health`, `h_restart`, `set_device`, and the preview worker). Keep decoding helpers as they are. Validate with the existing curl/Playwright method plus a record-and-compare of the output.
2. **Measure.** Add timing instrumentation behind the interface (play-call to first audio, tick jitter, device latency, drift against the device clock). Produce numbers for the production machine with the Dante adapter and for the Windows target. These decide R1 and R4.
3. **Prototype the callback mixer** outside the app (own script): N voices, windowed play, loops, float gain with ramps, clip policy, `voice_ended` events, Python-callback vs ring-buffer vs separate-process designs. Run for hours under load to settle R1. Test PortAudio+ASIO on Windows and Core Audio on macOS here.
4. **Add `PortAudioEngine`** behind the same interface, selectable by config (`audio_engine`), default stays pygame. Replace wall-clock position with `Voice.position()` plus latency correction, keeping the wall-clock path for the pygame engine.
5. **Move gain and fades into the engine** (ramped `set_gain`, optional sample-accurate crossfade/ducking), remove trim copies (`_tcache`, `cut_sound`) for engines that can play windows.
6. **Preview/Mirror on the new engine,** fix R8 (explicit format, loop/trim awareness, shared timing) and keep the JSON protocol.
7. **Decoding.** Decide whether pygame remains the decoder on all platforms, or replace it (`--decode` / `--probe` / worker `Sound(path)`), and update `requirements.txt`, `run-player.bat`, `nuc-setup.sh`, README, Help and tour.
8. **Soak and switch per platform:** Windows (ASIO) and macOS (Core Audio) first; Linux only after a long production-style soak (the "production readiness checklist").

## Summary: the three biggest risks

1. **The GIL on the audio thread (R1).** The current engine mixes in SDL's C thread, so Python load can never starve the output. A Python PortAudio callback gives that up. The mixer design (callback, ring buffer, separate process or native code) must be settled by a prototype before anything else.
2. **ASIO and device handling on Windows (R2).** Standard Python PortAudio wheels likely lack ASIO. ASIO devices are exclusive and fixed-rate, which also affects the preview and mirror workers and saved device names.
3. **Timing and format assumptions spread through the code (R3, R4).** Position, remaining time, end detection, auto-advance, meters and ducking all depend on a wall-clock model and on 48 kHz / int16 / stereo audio. Changing the engine changes what "now" means for all of them, and pygame is still the decoder in every helper process.
