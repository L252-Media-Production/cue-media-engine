# Cue Media Engine test harness

Instance management, the control map, API / command / OSC tests (`tests/api/`), in-process tests of the audio engine with a fake clock (`tests/engine/`), an experimental audio-capture suite (marker `audio`), and static gates. Playwright scripts and stress tests are separate stand-alone scripts.

The older stand-alone scripts in this folder (`test_triggers.py`, `test_layout_share.py`, the Playwright ones) are not collected by pytest; `tests/run.py` runs `tests/api/` and `tests/engine/` and then the page-equality, CRLF and gate scripts.

## Quick start

```
python tests/run.py                  # starts a disposable player from a COPY of player.py, tests it, tears it down, writes a report
python tests/run.py -k transport     # any pytest selection argument is passed through (-k, -x, --maxfail, a file name ...)
python tests/run.py -m audio         # only the audio-capture tests (SDL_AUDIODRIVER=disk); -m "not audio" leaves them out
python tests/run.py tests/engine     # (pass the path) only the in-process engine tests
python tests/gen_controls.py         # rewrites tests/controls.csv (the control map)
```

Output: `tests/reports/<platform>-<arch>-<date>-<time>/` with `report.md` (read this), `results.json`, `junit.xml`, `instance.log` (the player's own log).

## What it does to your machine

* Copies `player.py`, `cpl/` and `static/` (the app is `cpl/legacy.py` behind the launcher `player.py` since split step P1) into a new temp folder `cptest-XXXX` and runs it there with `python -I`. The player reads `config.json`, state, playlists and `media/` from the folder of its own script, so **the real project folder, config, library and state are never opened**.
* Own ports, picked at random from 18200-18999 (never 8080 or 9000). Its OSC output goes to a UDP "sink" the harness owns (never to a real Companion), which doubles as the way to check what the player sends.
* `SDL_AUDIODRIVER=dummy`: no sound card is opened, nothing is audible.
* A generated library: 12 WAV files with known tones/lengths (a 120 s mono file for seek tests, loud/quiet pair for level match, a file with spaces and `&` in its name, one in a sub-folder) plus an MP3 and a FLAC when `ffmpeg` is on the PATH.
* Everything (process group, temp folder, sink) is removed afterwards, also on Ctrl-C or a crash (`atexit`).
* It does not stop, restart or reconfigure any `cue-media-engine` (or older `companionplayer`) service, and does not touch `systemctl`. It does share CPU with whatever else is running, so do not run it during a show.

## Testing an instance that is already running (`--base-url`)

The tests delete every playlist, change settings and restart the player, so the harness refuses to point at anything it cannot prove is a disposable test instance:

| target | result |
|---|---|
| a loopback instance whose config file is in a `cptest-*` folder (started by `tests/harness/instance.py`) | allowed |
| anything else (other machine, other folder, port 8080/9000, unreachable, not identifiable) | **refused** (exit code 3) unless you pass `--allow-remote --confirm-target HOST:PORT`, typing the target out exactly |

```
# on the machine under test (Windows, production machine, Pi): start a disposable instance and leave it running (Ctrl-C removes it)
python tests/harness/instance.py start --port 18200
# from any other machine
python tests/run.py --base-url http://HOST:18200 --allow-remote --confirm-target HOST:18200 --osc-port <the OSC port it printed>
```

Without `--osc-port` the OSC-input tests are skipped; the OSC-output, restart, hard-kill and on-disk checks need an instance the harness started itself (a managed run) and are skipped for `--base-url`. For an external target the generated library is uploaded first (an upload cleans odd characters out of names; the tests allow for that).

## Platforms

Only `pip`-installable packages are needed: the player's own `requirements.txt` plus `tests/requirements.txt` (`pytest`, `python-osc`). `ffmpeg` is optional (MP3/FLAC files, level match through ffmpeg; without it those tests skip or use the scipy fallback).

**macOS / Linux (Debian, the production machine, Raspberry Pi OS / ARM)**
```
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt -r tests/requirements.txt
.venv/bin/python tests/run.py
```
Debian / Pi OS: `sudo apt install python3-venv ffmpeg` first (and `libsdl2-mixer-2.0-0` if pygame reports a missing SDL library). On a Pi, 64-bit OS gives pip wheels for pygame, numpy and scipy; on 32-bit a build from source may be needed.

**Windows** (PowerShell, the player's `pygame-ce` marker applies)
```
py -3 -m venv .venv
.venv\Scripts\pip install -r requirements.txt -r tests\requirements.txt
.venv\Scripts\python tests\run.py
```
`test_restart_comes_back...` and the hard-kill test are skipped on Windows (`os.execv` starts a new process there, which the harness cannot supervise).

Verified so far on macOS (arm64, Python 3.12, pygame-ce 2.5.8, ffmpeg 8.1) only; the Windows and Linux paths are written but not yet run.

## Report and severity

Every failed test carries a severity from `@pytest.mark.sev(n)` (default 2):

1. no audio / crash / stuck / wrong track on air
2. wrong behaviour
3. UI or usability glitch
4. cosmetic

The report lists failures most severe first, skipped tests with the reason, the timing of every HTTP call grouped by endpoint (n / min / avg / p95 / max) and the 10 slowest calls, the environment (OS, Python, pygame, local ffmpeg, the sha256 and size of `player.py`, git state if the folder is a repository, ffmpeg/devices as the player sees them), and the control ids exercised by passing tests.

Exit code: 0 all passed, 1 failures, 3 refused target.

## Control map (`controls.csv`)

`gen_controls.py` crawls `player.py` and writes one row per command word of the grammar, HTTP endpoint, OSC behaviour, Companion variable, and web-UI control (buttons, inputs and selects, with the handler functions and the API calls they reach). Columns: `id, area, kind, where, control, expected_result, how_to_verify, preconditions, api_calls, tests, status`. `status` is `api-tested` (a test carries `@pytest.mark.covers("<id>")`; a parent id such as `cmd.duck` covers `cmd.duck.*`), `untested`, `ui-pending (phase 2)`, `UNCLASSIFIED` or `undocumented`.

What the crawler knows by hand is in `controls_meta.py` (expected result, how to verify, preconditions). Anything found in the source that is not listed there is reported as `UNCLASSIFIED` (new command keyword, new route, new variable without text, a UI control without a handler, a test that covers an id that does not exist), so the map cannot silently drift. Run it after changing the grammar, the routes or the UI.

## Writing a test

```python
@pytest.mark.sev(1)
@pytest.mark.covers("cmd.track.play")
def test_something(std):                # std: playlist 0 "A" = tone_a/b/c (3/3/4 s), playlist 1 "B" = short_1s/short_2s/long_120s
    api = std
    assert api.res("0/1") == "ok"      # GET /api/0/1 -> the result word
    api.wait_playing("0/1")
    assert api.state()["live_name"] == "tone_b"
```

Fixtures: `api` (timed HTTP/OSC client), `std`, `scratch(name, folder, secs)` (uploads a small file and removes it afterwards), `preview` (enables a preview device), `needs_osc`, `sink` (OSC-out capture), `managed` (the harness-started instance), `manifest`, `weird_id`. Every test starts from a reset player (stopped, no playlists, default settings, ducking released). `/api/monitor` is the way to observe what is really audible (fades, ducking, level match and master volume are all in a deck's `vol`).

## Engine tests (`tests/engine/`, in-process, fake clock)

These import a COPY of the application in the test process (`harness/appload.py: load_app` purges every `cpl*` module first, so each test starts from fresh state), install a fake clock (`cpl.clock.install`) and drive `tick()` by hand, so a 2-minute track plays in milliseconds and every value is exact. The base class is `harness/engine.py: EngineCase` (a unittest `IsolatedAsyncioTestCase`, so no pytest plugin is needed). Rules (docs/split-plan.md 4.4):

* Time: `self.at(seconds)` sets the fake clock to start + seconds and runs one `tick()`; use binary fractions (0.25, 0.5 ...) for exact values; `self.rebase()` makes "now" the new zero.
* Patching: `self.patch(name, value)` replaces a name on the module that CALLS it (today `cpl.legacy`; the table `MODULE_OF` in `harness/engine.py` is the one place to change when a split step moves a function) and puts it back afterwards. Call cross-module functions as `module.func(...)`, never `from cpl.x import func` (a copy would bypass the patch). Assert that a spy was really called.
* Shared state (`live_deck`, `pending` ...): `self.get_state(name)` / `self.set_state(name, value)` read and write it wherever it lives (`cpl.state` after split step P4).
* The shuffle and the duck loop need a seeded `random` / the fake `asyncio.sleep` (see `test_advance.py`, `test_ducking_math.py`).

| File | Tests | What it asserts |
|---|---|---|
| `test_fades.py` (gap 2) | 13 | equal-power crossfade values at 25/50/75/100 %; the old deck is removed when its fade ends; a zero-length crossfade is a cut; fade-out curve; pause during a fade freezes it and the resume continues from the same point; the Out-point fade starts when the time left equals the fade length, reaches silence at the Out point, is capped at the playing part, and is absent with a cut edge |
| `test_advance.py` (gap 3) | 42 | for each play mode (stop, loop_playlist, next_playlist, shuffle) x each end action (default, once, loop, stop) x a middle and a last track: what is live after the natural end; shuffle covers every other track before repeating; no advance while a load is pending; Play on Top hand-back when the top track ends |
| `test_ducking_math.py` (gap 6) | 16 | golden vectors for `duck_key` and `duck_curve` (new signature) with hold on and off, ratio/threshold/level, the 60 dB cap; the duck loop's attack `1 - exp(-t/tau)` and release `exp(-t/tau)` step by step with a fake `asyncio.sleep`, the 20 ms look-ahead, the loop ending when the duck is released |
| `test_tick_order.py` (gap 7) | 9 | the order of work in `tick()` (update, hand-back, advance, triggers, monitor, meters, resume save), what a pending load suppresses, a top track and a background ending in the same tick, an error in the trigger step is contained |

## Own-instance tests and audio capture (`tests/api/test_resume.py`, `tests/api/test_audio_capture.py`)

* `test_resume.py` (gap 1, 5 tests): starts its own instance with `resume_on_start` on (the shared one has it off), kills it (SIGKILL) and restarts it: same track and about the saved position (tolerance: the saved position is at most `resume_save_s` + 1.5 s behind the true one; the restarted track begins at the saved position), a paused track comes back paused and still, a deliberate stop and a finished fade-out are NOT resumed, SIGTERM records the exact position.
* `test_audio_capture.py` (gap 10, marker `audio`, 6 tests, about 70 s): `SDL_AUDIODRIVER=disk` + `SDL_DISKAUDIOFILE` make SDL write what the mixer renders to a raw file. The disk driver is paced in real time (about 97 % of it: SDL waits a whole number of milliseconds per 1024-sample buffer) and bit-exact (the first test proves it with a known burst), so the tests analyse sample values, not timestamps: tone amplitude per 50 ms window (single-bin DFT), a sine fit, runs of zeros. They assert: the crossfade follows the equal-power curve with no energy dip and no step at its start or end; a cut has no gap; a looped region has no discontinuity over 12 passes; Play on Top ducks the background by the computed dB and releases with the configured time constant; stop all leaves exact silence and no leftover duck. They skip with a message where the disk driver is unavailable. Mutation check of the crossfade test (a scratch copy run with `--project`, tree untouched): a linear crossfade gives a fitted residual of 0.218 and swapped sin/cos curves 0.939, against a limit of 0.06; the real engine gives 0.011-0.017. `Instance(extra_env=...)` passes the SDL variables.

## Release checks (2.7.1)

`python tests/run.py` (pytest 475 passed, 1 skipped on macOS; then the stand-alone scripts: page equality, CRLF, static gates, state identity, no-bare-state, state hooks, `test_launchers.py`, `test_module_version.py`), `python tests/test_triggers.py` (38), the Playwright scripts (`test_trim_dialog.py`, `test_layout_share.py`, `test_move_button.py`, `test_devices_ui.py`), `-m audio` (6, in the normal run), `CPTEST_EXTRA_CONFIG='{"ffmpeg_path": "/nope/ffmpeg"}' python tests/run.py` (the deep format test skips), and `python tests/tools/onset_capture.py` against the previous release. `tests/test_launchers.py`: `run-player.bat` is not empty, uses CRLF and checks `cpl\\__init__.py` and `static\\help.html`; `run-player.command` is executable (file mode and git mode 100755); the deploy scripts are not empty and copy `player.py`, `cpl/` and `static/`. `tests/test_cold_start.py` (stand-alone, about 40 s): a cold start on a clean folder; a hard kill and restart of a folder with playlists (trim, crossfade time, end action, trigger point) and `resume.json`; and an UPGRADE: the data files written by the previous release (`--old-rev`, default `v2.7.0`, started from `git archive`) are read by this build (settings identical, the track resumes). `tests/test_module_version.py`: player and module share major.minor, and the real `checkVersion()` of the module answers ok for a player 2.7.1 with module 2.7.0 (needs node and `companion-module/node_modules`, otherwise that part skips).

## Tools (`tests/tools/`) and gates (`tests/test_gates.py`)

* `verify_move.py` proves that a split step only MOVED code (normalised AST of each moved function, allowed rewrites in `tools/maps/*.json`); `verify_blocks.py` does the same for code that left an `if` block; both have a self-test (`python tests/tools/test_verify_move.py`).
* `onset_capture.py` is a diagnostic (not a test): `python tests/tools/onset_capture.py --app <source tree> --label <name>` plays burst files with a normal Play and with Play on Top, cached and uncached, and reports whether the first samples survive on the live output and on the Solo monitor.
* `tools/state_rewrite.py` (split step P4): rewrites module-level state names to `S.<name>` using `symtable` (which occurrences resolve to the module scope) and the ast offsets, never a regex; `--dry-run` prints the summary (names, read and write sites per function = the writer table) and `--diff` the diff. `verify_move.py` takes the matching map options `state_names`, `local_names_in` (functions where a state name is an ordinary local), `expr_rewrites_in` (an expression rewrite allowed only inside named functions). The maps of P4 are `tools/maps/p4-*.json`; `p4-all.json` proves the whole of P4 against `split-gap`.
* `test_no_bare_state.py` (gates 1-4, 1b, 6 of the plan, with a self-test that plants 13 violations): no `global` of a moved name, no bare module-level use of a moved scalar, `cpl.state` only imported as `S`, containers never rebound, `S.x =` only in the writer table (`WRITERS`, data in the test: a new writer is added on purpose), no rebound global other than the listed module-private ones (`MODULE_PRIVATE`), no by-name import of a function a test patches (`PATCHED`).
* `test_state_identity.py`: `id()` of the 10 stable containers of `cpl.state` is unchanged after import, `load()` (both formats), `stop_all()`, `set_device()` and a rescan. `test_state_hooks.py` (gate 8): `on_change`, `on_save` and `notify` are registered after the import; `bump()` runs `on_change` after `rev += 1`; `save()` runs `on_save` after the file and `bump()`. Tests that replace `request_warm` / `request_loudness` must replace the hook entry as well: `EngineCase.patch()` does it (`HOOK_LISTS`), `test_triggers.py` does it by hand. Read the shared state as `self.S.<name>` (`S` = `cpl.state`), not `P.<name>`.
* `RealHookPath` in `test_state_hooks.py` and `tests/api/test_warmup.py`: the hooks through the REAL path, with nothing replaced in `S.on_change` / `S.on_save`. The spies sit inside the real functions (`_warm_loop` is what `request_warm` starts, `loud_pending` is what `request_loudness` asks first), so they only fire if the hook list really calls them: `load()` and a `bump()` after a playlist change start a warm-up and decode the tracks, `save()` asks for loudness. The black-box test starts an own instance with a saved playlist, restarts it cold, and waits (20 s limit) for `mem.cache_tracks` in `/api/state` to cover the playlist; a playlist edit through the API must warm the added track. With the two `S.on_*.append(...)` lines removed, 5 of the 7 hook tests and both black-box tests fail (checked).
* `CPTEST_EXTRA_CONFIG='{"ffmpeg_path": "/nope/ffmpeg"}' python tests/run.py` merges the JSON into the config of every harness instance: the whole suite without ffmpeg (the fallbacks: waveform by decode + compute_env, loudness by lufs_from_pcm, uploads of convert formats refused with a message). `engine/test_lib_rename.py`: lib_rename + move_track carry trim, crossfade time, end action, trigger points (own and target) and the cache entry.
* `tools/move_defs.py` (split steps P5/P6): moves named top-level definitions from `cpl/legacy.py` into a new module verbatim (`--check` resolves the whole module spec in layer order and stops at any dependency that would need `cpl.legacy`), `tools/verify_step.py OLD_REV --map ...` runs the move verifier over every `cpl/*.py`; the module spec is `tools/maps/p56-spec.json`. `tests/gates/import_allowlist.json` is the MAXIMUM edge set of table 2.1 (plus `util`, `clock`; `devices` also `helpers.common`): a module may import less, never more. Tests patch a function on the module that CALLS it (`MODULE_OF` in `harness/engine.py`: `loudness`, `warm`) and, for hook-registered functions, also its entry in the hook list (`HOOK_LISTS`).
* `ttfs.py` (a measurement, not a test): time from Go on a never-cached track until `/api/state` shows it playing, on a cold start of any git revision (`--rev v2.7.0|split-P4`), with the warm-up working through a 20-track playlist (`--mode working`) or switched off by a launcher shim (`--mode idle`); targets a 15-minute MP3 (`long`) or a 3-second WAV (`short`).
* `test_gates.py`: static gates (time only through `cpl.clock`, no function-local `cpl` imports, helpers import no app code, the import graph equals `tests/gates/import_allowlist.json` and is acyclic).

## Not covered yet

Playwright UI tests in the harness (the `ui-pending` rows; the stand-alone Playwright scripts exist), soak and stress tests, device-change carry-over, `_start_when_ready` races, a second Play on Top, tick-duration measurement, the Companion module, a real download (needs the network), real output devices (the dummy and disk drivers cannot show device-side effects).
