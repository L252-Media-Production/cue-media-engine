Spec version: 1 (matches v2.8.0)

# Cue Media Engine audio spec

The Python player (`cpl/`) is the reference for what the sound does. Another engine (CueME Stage, Swift / Core Audio) has to behave the same way. This file says **what counts as audio behaviour**, where the code that defines it lives, and which tests and fixtures pin it. The numbers are in `tests/golden-audio/fixtures/*.json` (see `tests/golden-audio/README.md`); the other engine reads those files and must reproduce them.

The spec describes the player as of v2.8.0. Fixing a bug in the player that changes a number is a change of the spec, not a silent fix.

## What counts as audio behaviour

Anything that changes **which samples reach the output, how loud they are, or when**. Function names are in `cpl/` (grep for them; `cpl/legacy.py` still holds the transport).

| Area | What is defined | Where it lives | Fixture | Tests |
|---|---|---|---|---|
| **Fades and equal-power curves** | Every fade is a ramp of the deck's `vol` driven by the clock. Up: `a + (b-a) * sin(x*pi/2)`; down: `b + (a-b) * cos(x*pi/2)`, `x` = elapsed / length. In a crossfade new² + old² = 1. A fade of 0 ms is a cut. Pausing freezes a fade (the pause time is not counted). The channel volume is `vol * gain * duck * duck_in * live_volume`. | `Deck.start_fade`, `Deck.update`, `Deck.apply`, `fade_out`, `resume_all` (`cpl/legacy.py`) | `fades.json` | `tests/engine/test_fades.py`, `tests/api/test_audio_capture.py` |
| **Crossfade time precedence** | Time of a crossfade into track `t`: explicit `?ms=` > the track's own time (`xfades`, 0-30 s, 0 allowed) > master `crossfade_ms`. `play_default` uses it when `default_transition` is `crossfade`; Go uses `go_transition` (`cut` = `/take`, `crossfade` = `/xfade`). | `xfade_of`, `xfade_ms`, `set_xfade` (`cpl/playlists.py`), `play_default` | `xfade.json` | `tests/api/test_trim_xfade.py`, `tests/test_crossfade_unit.py` |
| **End actions and pass counts** | Per track: `default` (follow the playlist play mode), `once` (two passes, then as default), `loop` (`loops=-1`, never ends), `stop` (ends the run whatever the mode). The end is found by `tick()` from `Deck.update`; `remaining()` and `fpos()` are per pass. Switching `once` or `loop` off mid-play lets the running pass finish. Cycle: default > once > loop > stop. | `end_of`, `set_end`, `is_loop` (`cpl/playlists.py`), `_start`, `Deck.update`, `Deck.pass_no`, `auto_advance` | `end_actions.json` | `tests/engine/test_advance.py` |
| **Trim A/B** | Window `[A, B)` of the file, A held 0.5 s before the end, a stored window under 0.5 s falls back to the whole file; `set_trim` refuses a new one under 0.5 s. The deck plays only that window (`base`, `lo`, `hi`). | `trim_range`, `set_trim`, `dur_eff` (`cpl/playlists.py`), `_start`, `cut_sound` | `trim.json` | `tests/api/test_trim_fade.py`, `tests/engine/test_fade_in.py` |
| **Fade in at A** | Applied only on a start at the In point (never a seek or resume part-way in, never while paused, never under a crossfade): `sin` ramp up over `fade_in_ms`, capped to the window minus the out-fade. Cut (default) is bit-identical to the file. | `fade_in_ms_of`, `fade_in_start_ms`, `_start` | `trim.json` | `tests/engine/test_fade_in.py`, `tests/api/test_audio_capture.py` |
| **Fade or cut at B** | With an Out point and `end` = fade (default), the deck fades down (`cos`) over `fade_ms` (own value, else `trim_fade_ms` 1500) so that it reaches 0 at B, then ends by itself; `end` = cut stops dead at B. Capped to the played part. | `fade_ms_of`, `fade_default_ms`, `_start` (`Deck.end_fade_ms`), `Deck.update` | `trim.json` | `tests/api/test_trim_fade.py`, `tests/engine/test_fade_in.py` |
| **Trigger points** | Voice-overs fired from a position in the FILE: `tick()` watches the live deck (or the track under a Play on Top) and fires through the Play on Top core when the playhead crosses `at` (within one 50 ms tick). Before A / at or after B never fires; a seek forward over a point skips it, back re-arms it; `once` = first pass only; a loop fires every pass; a Play on Top already running skips the point (no queue); disabled and disarmed never fire. | `triggers_tick`, `_trig_cross`, `_trig_fire_due`, `_play_on_top` (`cpl/legacy.py`); data in `cpl/triggers_data.py` | `triggers.json` | `tests/test_triggers.py` |
| **Play on Top and sidechain ducking** | The top track plays at `top_track_pct`; the background decks are multiplied by `10^(-gr/20)` (`Deck.duck`). Per 10 ms of the top track: RMS of the louder channel (`duck_key`) → reduction `max(0, dB(key*level) - threshold) * (1 - 1/ratio)`, capped 60 dB (`duck_curve`), optional hold at the 75th-percentile depth; attack / release smoothing every 10 ms with a 20 ms look-ahead (`duck_smooth`). A second top track replaces the first and keeps the background; when it ends the live role goes back to the track under it. The Live input detector (Duck only) uses the same maths with its own threshold. | `cpl/dsp.py` (`duck_key`, `duck_curve`, `duck_smooth`, `input_target_db`), `_duck_loop`, `duck_arm`, `_play_on_top`, `cpl/liveinput.py` | `ducking.json` | `tests/engine/test_ducking_math.py`, `tests/api/test_ducking.py`, `tests/engine/test_live_input_engine.py` |
| **Level match and LUFS** | Integrated loudness (BS.1770 K-weighting, 400 ms blocks, 75 % overlap, gates -70 LUFS and -10 LU) of 48 kHz stereo 16-bit. Per playlist: `off`, `track` (reference track) or `lufs` (target, -60..0). Gain `min(0, target - measured)` dB: it only ever turns a track down. `Deck.gain` follows a change at once. | `lufs_from_pcm` (`cpl/dsp.py`), `norm_gain_db`, `norm_gain`, `set_norm`, `apply_gain_live` (`cpl/loudness.py`) | `levelmatch.json` | `tests/api/test_levelmatch.py` |
| **Play modes and shuffle bag** | After a track ends (and no end action overrides): `stop`, `loop_playlist` (next, wrapping), `next_playlist` (to the end of the list, then the first track of the next list), `shuffle` (every track once per round, never the same one twice in a row; the bag is forgotten when the mode changes). The sequence for a given random seed depends on the Python version and is NOT part of the spec. | `pl_mode`, `set_play_mode`, `next_in_order`, `shuffle_left` (`cpl/playlists.py`), `auto_advance`, `play_playlist` | `play_modes.json` | `tests/engine/test_advance.py`, `tests/api/test_transport.py` |
| **Resume** | While something plays, `resume.json` records the live track (the background track when a top track is on), its file position and the paused flag, every `resume_save_s`; a stop or finished fade removes it. At start-up the track is started at that position (paused if it was), unless older than `resume_max_age_s`; a resumed start never fades in. | `save_resume`, `try_resume`, `_start_when_ready` (`cpl/legacy.py`) | (covered by `trim.json` deck_start, resume row) | `tests/api/test_resume.py`, `tests/engine/test_fade_in.py` |
| **Volume** | `live_volume` (0-1) multiplies every deck; mute remembers the level before. Seeking keeps volume, fades and pause state. | `set_live_volume`, `seek_live` | (formula in `fades.json` about) | `tests/api/test_volume_modes.py`, `tests/api/test_transport.py` |

Decoding and rendering: the mixer runs at 48 kHz, 16-bit, stereo (`cpl/devices.py`, `allowedchanges=0`); every track is decoded into RAM first and played from there (a mono file is played on both channels, other rates are converted on load). A render of the real mixer output is checked in `tests/api/test_audio_capture.py` and `tests/golden-audio/renders/`.

## What is NOT audio behaviour

Not part of the spec, free to differ in another engine (and often should):

- The web page (`static/`, layout, skins, tour, Help), the stage page, the Variables page.
- HTTP routes, OSC in and out, the command grammar, Companion variables and the module (the *effect* of a command on the audio is covered above; the spelling is not).
- Health panel, watchdog, push messages, sound-card matching, report text.
- Settings pages, output aliases and labels, device lists, RAM indicator, memory readout.
- Downloads (yt-dlp), uploads, ffmpeg conversion, file information, format checks, library scan, waveforms.
- Level METERS (taper, scale, variables): they show the sound, they do not change it.
- Preview and Mirror outputs, Solo, Loop A-B in the preview (they never touch the live decks).
- Persistence formats (`playlists.json`, `state.json`), except the fields named in the table.
- Timing of the 50 ms tick itself: fixtures are taken at fixed fake-clock times and carry a tolerance.

## The rule

> Any change that alters audio behaviour must **regenerate the fixtures** (`PYTHONHASHSEED=0 python tests/golden-audio/generate.py --write`), **bump the spec version** (`SPEC_VERSION` in `tests/golden-audio/generate.py`, the first line of this file, and `spec_version` in every fixture, which the generator writes), and add a CHANGELOG line **"Audio spec N"** saying what changed and why.

`tests/engine/test_golden_audio.py` (run by `tests/run.py`) fails with a readable diff when the committed fixtures differ from what the code does. The other engine pins the spec version it implements and compares its output with the fixtures of that version.
