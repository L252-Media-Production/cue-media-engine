# Golden audio fixtures

What the Python player (Cue Media Engine, `cpl/`) does with sound, written as JSON, so that another engine (CueME Stage, Swift / Core Audio) can be checked against it. The contract is `docs/AUDIO-SPEC.md` (spec version, what counts as audio behaviour, the change rule); these files are its numbers.

## Regenerate (one command)

```
PYTHONHASHSEED=0 python tests/golden-audio/generate.py --write     # overwrite tests/golden-audio/fixtures/*.json
PYTHONHASHSEED=0 python tests/golden-audio/generate.py             # check only: exit 1 and a readable diff when they differ
```

It takes about 15 s. It imports a COPY of the app into a temp folder (the real config, library and state are never opened), drives it with the fake clock of `cpl/clock.py` and SDL's dummy mixer, and reads the values from the real code (`Deck.vol`, `trim_range`, `duck_curve`, `lufs_from_pcm`, ...). It changes nothing in `cpl/`. Running it twice gives byte-identical files (checked). `tests/engine/test_golden_audio.py` runs the check inside `python tests/run.py`.

Only regenerate when you MEANT to change audio behaviour. Then bump `SPEC_VERSION` in `generate.py` and the first line of `docs/AUDIO-SPEC.md`, and add an "Audio spec N" line to `CHANGELOG.md`.

## Files (`fixtures/`)

| File | Content |
|---|---|
| `fades.json` | equal-power table; crossfade gain (new / old deck) at fixed fractions for 1 s and 3 s; zero-length crossfade; fade out; pause during a fade |
| `xfade.json` | crossfade time precedence (explicit > per-track > master), limits of the per-track time, the fade length `play_default` starts |
| `trim.json` | what `set_trim` stores, the A/B window and fade lengths, what `_start` sets on the deck (base, window, out-fade, fade-in), the fade-out ahead of B and the fade-in at A |
| `end_actions.json` | once / loop / stop / default on a 2 s track: pass number, remaining time, the moment it ends; switching off mid-play; the cycle |
| `play_modes.json` | what follows a track for every play mode and end action; `next_in_order`; shuffle bag properties |
| `triggers.json` | when trigger points fire (seconds after the start), with trim, seek, loop, `once`, disabled, a busy Play on Top |
| `ducking.json` | `duck_key`, `duck_curve` (hold on / off), `duck_smooth` series, the background multiplier, `input_target_db`, and `duck_loop` (the real loop with the 20 ms look-ahead, sampled every 10 ms) |
| `levelmatch.json` | `lufs_from_pcm` of synthetic signals, `norm_gain_db` for every mode, the gain on a live deck |
| `resume_flow.json` | what the runtime file `resume.json` records, how `try_resume` carries on |

## Format

```
{
 "spec_version": 1,            // matches the first line of docs/AUDIO-SPEC.md
 "name": "fades",
 "about": "what is measured",
 "tolerance": 2e-06,           // numbers match within this (absolute); levelmatch.json also has "tolerance_lufs": 0.01 for LUFS values
 "cases": { "<case name>": { "_info": "...", "rows": [ ... ] } }
}
```

- Numbers are rounded to 6 decimals; times are seconds on the fake clock counted from the start of the scenario (`t_s`), or fractions of a fade (`x`, 0..1).
- Keys that start with `_info` explain a case and are never compared (the Python test ignores them; so should a consumer). `_info_sequence` / `_info_python` (shuffle) are examples, not contract: a random sequence depends on the Python version, only the listed properties are.
- Gains are `Deck.vol` (0..1), before level match, ducking and master volume. The real mixer volume has 128 steps, so another engine should compare `vol`, not the quantised value.
- **Measured vs ideal.** Times in `triggers.json` (`fires`) and `end_actions.json` (`ended_at_s`) are what the Python player measured, so they include its 50 ms tick (a trigger at 10 s fires at 10.05 s; `ended_at_s` is also on the 0.25 s grid the scenario is sampled at). Next to them each case has the IDEAL value (`ideal_fires`: the time at which the playhead reaches `at`, i.e. `at - A` after the start plus whole passes in a loop, `once` first pass only, seeks and busy Play on Top worked out by hand; `ideal_ended_at_s`: the end of the last pass, `null` = never) and `tolerance_s` (0.05 = one tick). Measured is never earlier than ideal and at most one tick later (the generator asserts it). **Another engine compares its own times with the ideal values within `tolerance_s`**, not with the measured ones. The exact Python behaviour behind the tick is listed in "Known Python quirks" in `docs/AUDIO-SPEC.md`.
- `ducking.json` `duck_loop`: the real `_duck_loop` driven by the fake clock (one loop iteration = 10 ms). Columns of equal length in `samples`: `t_s` (0 = start of the background deck), `top_pos_s` (playhead of the voice-over, null before it starts), `target_db` (the `duck_curve` value the loop reads 20 ms ahead of the playhead), `gr_db` (smoothed reduction), `bg_multiplier` (`Deck.duck` of the background). Index 49 is the last sample before the voice-over, index 50 the voice-over starting at the same instant (t = 0.5 s); the settings used are in `settings`. Two cases: production defaults with hold on, and a slow attack / short release with hold off.
- Scenarios are described by the case name and its `_info`; the code that builds them is `generate.py` (readable top to bottom, one function per file).

## Render references

Short WAV renders of real mixes: see `renders/` and its README (separate command, not part of the default run).
