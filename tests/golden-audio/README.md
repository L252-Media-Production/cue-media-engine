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
| `trim.json` | what `set_trim` stores, the A/B window and fade lengths, what `_start` sets on the deck (base, window, out-fade, fade-in), the fade-out ahead of B and the fade-in at A; boundary cases: short stored windows, rounding and thresholds of A / B, fade length limits and clamps, where the out-fade runs (loop / once / default / stop), the fade-in start threshold and its cap |
| `end_actions.json` | once / loop / stop / default on a 2 s track: pass number, remaining time, the moment it ends; switching off mid-play; the cycle; every deliberate from/to pair of an end action switched while playing (`end_action_switched_mid_play`) |
| `play_modes.json` | what follows a track for every play mode and end action; `next_in_order`; shuffle bag properties |
| `triggers.json` | when trigger points fire (seconds after the start), with trim, seek, loop, `once`, disabled, a busy Play on Top |
| `ducking.json` | `duck_key`, `duck_curve` (hold on / off), `duck_curve_hold_percentile`, `duck_smooth` series, the background multiplier, `input_target_db`, and `duck_loop` (the real loop with the 20 ms look-ahead, sampled every 10 ms) |
| `levelmatch.json` | `lufs_from_pcm` of synthetic signals, `norm_gain_db` for every mode, the gain on a live deck |
| `resume_flow.json` | what the runtime file `resume.json` records, how `try_resume` carries on |

## Format

```
{
 "spec_version": 1,            // matches the first line of docs/AUDIO-SPEC.md
 "name": "fades",
 "about": "what is measured",
 "tolerance": 2e-06,           // numbers match within this (absolute); levelmatch.json also has "tolerance_lufs": 0.01 for LUFS values
 "cases": { "<case name>": { "scenario": { ... }, "tolerance": 2e-05 /* optional */, "_info": "...", "rows": [ ... ] } }
}
```

- Numbers are rounded to 6 decimals; times are seconds on the fake clock counted from the start of the scenario (`t_s`), or fractions of a fade (`x`, 0..1).
- Keys that start with `_info` explain a case and are never compared (the Python test ignores them; so should a consumer). `_info_sequence` / `_info_python` (shuffle) are examples, not contract: a random sequence depends on the Python version, only the listed properties are.
- Gains are `Deck.vol` (0..1), before level match, ducking and master volume. The real mixer volume has 128 steps, so another engine should compare `vol`, not the quantised value.
- **Measured vs ideal.** Times in `triggers.json` (`fires`) and `end_actions.json` (`ended_at_s`) are what the Python player measured, so they include its 50 ms tick (a trigger at 10 s fires at 10.05 s; `ended_at_s` is also on the 0.25 s grid the scenario is sampled at). Next to them each case has the IDEAL value (`ideal_fires`: the time at which the playhead reaches `at`, i.e. `at - A` after the start plus whole passes in a loop, `once` first pass only, seeks and busy Play on Top worked out by hand; `ideal_ended_at_s`: the end of the last pass, `null` = never) and `tolerance_s` (0.05 = one tick). Measured is never earlier than ideal and at most one tick later (the generator asserts it). **Another engine compares its own times with the ideal values within `tolerance_s`**, not with the measured ones. The exact Python behaviour behind the tick is listed in "Known Python quirks" in `docs/AUDIO-SPEC.md`.
- `ducking.json` `duck_loop`: the real `_duck_loop` driven by the fake clock (one loop iteration = 10 ms). Columns of equal length in `samples`: `t_s` (0 = start of the background deck), `top_pos_s` (playhead of the voice-over, null before it starts), `target_db` (the `duck_curve` value the loop reads 20 ms ahead of the playhead), `gr_db` (smoothed reduction), `bg_multiplier` (`Deck.duck` of the background). Index 49 is the last sample before the voice-over, index 50 the voice-over starting at the same instant (t = 0.5 s); the settings used are in `settings`. Two cases: production defaults with hold on, and a slow attack / short release with hold off.
- **Tolerance.** `tolerance` at the top of a file is the default (absolute). A case may carry its own `tolerance`, which **overrides the file-level one for that case** (including its nested cases). `ducking.json` `duck_curve` and `duck_curve_hold_percentile` have 2e-05 (dB): the Python level key is float32 and carries about 1e-6 relative noise on the quiet windows, which moves the reduction by up to about 1.2e-5 dB. `levelmatch.json` keeps `tolerance_lufs` (0.01) for LUFS values. **`tolerance_by_key`** (case level, optional, applies to nested cases too): a map `{value key: tolerance}` that overrides both the file-level and the case-level `tolerance` for the numbers under that key only (the nearest object key above the number, so every element of a `rows` list counts). It is for positions and durations in file seconds: the Python player derives some from whole frames truncated with `int()` and others from the exact float seconds, so they differ by up to a sample or two; those keys get 2.5e-5 s (just over one sample at 48 kHz, 1/48000 = 2.083e-5 s). A case that has it carries a `_info_tolerance_by_key` note saying why. Gain values never use it. Used by `trim.json` `short_window_stored` (`base_s`, `lo_s`, `hi_s`, `duration_s`, `dur_eff_s`, `range_s`) and `fade_in_start_threshold` (`base_s`, `offset_s`).
- **Hold percentile.** `ducking.json` `duck_curve_hold_percentile` pins the percentile of the hold mode (the 75th): its ramp gives clearly different depths for the 60th, 90th and 75th (`_info_alternatives`), and the generator asserts that the committed values differ from both. Its columns: `hold_depth_db`, `reduction_db_hold_off`, `reduction_db_hold_on` (one value per 10 ms window).
- **Self-describing cases (`scenario`).** Every case, in every file (and each nested case of `duck_loop`), has a `scenario` object with the inputs it was generated from. The generator writes it from the same variables that run the scenario, so a consumer does not need to read `generate.py`. Common keys: `library_s` (file -> length in seconds of the generated WAVs), `playlist` / `playlists` (track file names, index = track number), `steps` (what is done, in order), `row_inputs` (row label -> the inputs of that row, for files whose rows are labelled), `input` (one sentence for tables where every row carries its own inputs). Keys per file:
  - `fades.json`: `x_values` (equal_power_formula); crossfades: `library_s`, `playlist`, `sampled_at_fractions`, `steps`, `fade_ms`; `pause_freezes_a_fade` also `sample_1_at_s`, `sample_2_at_s`, `sample_3_at_s`.
  - `xfade.json`: `library_s`, `playlist`, `target_track`, `master_crossfade_ms`, `input`; `play_default_uses_it` also `default_transition`, `steps`, `row_inputs` {row label: `own_time_s`}.
  - `trim.json`: `library_s`, `playlist`, `track_under_test`, `file_length_s`, `config` (`trim_fade_ms`, `trim_fadein_ms`), `input`; `fade_out_ahead_of_B` / `fade_in_at_A` also `trim` (the trim dict set), `steps`, `sampled_at_s` or `sampled_at_fractions`, `ended_check_at_s`.
  - `trim.json` boundary cases (all have `library_s`, `playlist`, `config`, `track_under_test`, `file_length_s`, `input`): `short_window_stored` rows `{stored, range_s, dur_eff_s, deck}` (the `stored` dict is written straight into `trims`); `set_trim_rounding_a_b`, `set_trim_minimum_window`, `set_trim_out_vs_file_length`, `fade_length_limits`, `fade_length_held_to_window`: rows `{set, accepted, stored, range_s}` (`accepted` false = refused, nothing stored; the `previous` key says what was kept); `fade_length_follows_window_changes`: the same rows, run one after the other WITHOUT clearing; `default_fade_longer_than_window` and `out_fade_placement_loop|once|default|stop`, `out_fade_once_switched_off_in_pass_1`: `tick_step_s`, `sampled_at_s`, `trim`, `end_action`, `switch_off_to` / `switch_off_at_s`, rows `{t_s, vol, live}`, `ended_at_s` / `ideal_ended_at_s` / `tolerance_s` (null = never); `loop_switched_off_in_pass_1_end`: only `ended_at_s` is contract, the levels are `_info_python_vol`; `fade_in_start_threshold`: rows `{case, trim, offset_s, deck {base_s, fade_in_ms, start_vol, fresh, loop}}` (+ `paused`, `crossfade_ms`), the end action is `loop` throughout; `fade_in_cap`: rows `{case, set, accepted, stored, window_s, deck {end_fade_ms, fade_in_ms, fade_in_ramp_s}}`; `fade_in_out_fade_overlap_901|1000`: `deck` pinned, `_info_python_vol` not.
  - `end_actions.json` also `end_action_switched_mid_play`: `play_modes` (`stop`, `loop_playlist`), `tick_step_s`, `run_s`, `row_inputs`; rows `{from, to, switch_at_s, ideal_ended_at_s, play_mode_stop|play_mode_loop_playlist {ended_at_s, live_at_that_tick}}` (`live_at_that_tick`: track index and `pass_no` live right after the tick that ended the deck, null = nothing). Switching TO `once` is deliberately not in it (quirk 12).
  - `end_actions.json` (the cases above): `library_s`, `playlist`, `play_mode`, `tick_step_s`, `rows_at_s`, `end_action`, `run_s`, `steps`; the two "switched off" cases also `switch_off_to` and `switch_off_at_s` (seconds of play); `end_action_cycle`: `playlist`, `input`.
  - `play_modes.json`: `library_s`, `playlists` (name -> tracks), `playlist_under_test`; `after_a_track_ends`: `play_modes`, `end_actions`, `from_tracks`, `mode_set_on_playlists`, `tick_step_s`, `max_ticks`, `shuffle_random_seed`, `steps`; `next_in_order`: `row_inputs` {row label: `play_mode` and, for the loop row, `end_action_of_track_1`}, `input` (every row also has `from_track`); `shuffle_bag`: `play_mode`, `start_track`, `draws_for_sequence`, `draws_for_fair_share`, `python_random_seeds`.
  - `triggers.json`: `library_s`, `playlist`, `main_track`, `main_track_length_s`, `voice_over_lengths_s`, `end_action` (`loop` or `default`), `run_s`, `trim`, `seek` (`{at_s, to_s}` in seconds of play, or null), `triggers` (the trigger list as given: `at` in file seconds, `file`, optional `once` / `enabled`), `tick_s`, `steps`. (`triggers` and `trim` are also still at the top of the case.)
  - `triggers.json`, added cases: `seeks` in the scenario (a list of `{at_s, to_s}`, next to the single `seek`) for the `once_*` cases; `point_at_or_near_A_start_at_A` and `point_near_A_start_with_offset` have `rows` `{A_s | offset_s, start_s, at, fired, first_fire_t_s, ideal_fired, ideal_t_s}` (`first_fire_t_s` = seconds after the start of play, null = never; `ideal_fired` true / false / null = not defined, `python_differs` true where Python deviates from the ideal: compare with the IDEAL, quirk 13; times within `tolerance_s`, `start_s` / `offset_s` / `at` within `tolerance_by_key`); `target_ready_after_1s` / `target_never_ready` have `target_decoded_at_s` (null = never) in the scenario; `voice_level_and_second_point` has rows per `top_track_pct` (`voice_vol`, `voice_gain`, `voice_is_live`, `at_12_5_s.tops` = number of top decks, `trigger_fires_so_far`); `new_track_*_while_voice_on_top` have `rows` `{t_s, event?, live, decks [{name, top, vol, ducked, ending}]}` (the real `_duck_loop` runs under the fake clock; keys named `_info_python_*` (duck multiplier, depth in dB, armed flag) are Python's internal state and are not compared).
  - `ducking.json`: `duck_key` / `duck_curve`: `format`, `window_samples`, `window_s`, `windows` (list of `{windows: n, left, right}`: n consecutive 10 ms windows, each holding ONE constant 16-bit sample value per channel), `input`; `duck_curve_hold_percentile`: `format`, `window_samples`, `windows`, `level`, `ratio`, `threshold_db`, `input`; `duck_smooth`: `initial_gr_db`, `dt_s`, `input`; `background_gain`, `input_target_db`: `input`; `duck_loop` (and each nested case): `background`, `background_alone_s`, `voice_over` (file, `segments_s_and_sample_value` = [seconds, constant sample value]), `step_s`, `tick_every_steps`, `max_steps`.
  - `levelmatch.json`: `lufs_from_pcm`: `format`, `synthesis`, `signals` (per signal, same order as the rows: `kind` sine / silence, `frequency_hz`, `peak_dbfs`, `amplitude`, `duration_s`, `channels`, `second_channel`); `norm_gain`: `playlist`, `measured_lufs`, `input`, `lufs_clamp_db` {min, max, step}; each row has `typed` (what was passed to `set_norm`) next to `stored` (what was kept; typed -80 -> stored -60); `applied_to_deck`: `playlist`, `measured_lufs`, `playing`, `row_inputs`.
  - `resume_flow.json`: `library_s`, `playlist`, `track_ids` (track number -> file id), `config` (`resume_on_start`, `resume_max_age_s` 1800, `resume_save_s`), `age_limit_s`; `record`: `row_inputs`, `input`; `try_resume`: `input`; `resume_inside_a_trim`: `trim_of_track_0`, `record`, `age_s`.
- **`live_after`.** In `fades.json` (`fade_out_2000ms`) and `trim.json` (`fade_out_ahead_of_B`) `live_after: true` means that NOTHING is live any more (the key name is kept for compatibility; each case says so in an `_info_live_after`).

## What the boundary cases are meant to catch

A case only pins a rule if a plausible WRONG implementation records different values. For every case added in `316febc` (trim, end actions) and `1241963` (trigger points) the table names the wrong behaviour and the key that shows it. Each wrong behaviour was built as a throwaway variant of the real code (a text edit of the generator's private copy of the app, not committed) and the committed fixtures were compared with what it recorded: "caught" = the recorded values differ (or the generator's own check against the ideal values in the fixture fails); two entries are marked as reasoned or not caught. Keys are in the rows of the case unless noted.

| Case | Wrong behaviour it catches | Key that shows it |
|---|---|---|
| `short_window_stored` | a too-short window falls back to the whole file (A dropped); exactly 0.5 s counted as too short | `range_s`, `dur_eff_s`, `deck.lo_s`, `deck.duration_s` |
| `set_trim_rounding_a_b` | A and B rounded to 1 ms instead of 10 ms; an A of 0.01 s stored | `stored`, `range_s` |
| `set_trim_minimum_window` | the 0.5 s minimum window not enforced, or enforced with `<=` | `accepted`, `stored` |
| `set_trim_out_vs_file_length` | a B within 10 ms of the end stored; the check made against a rounded file length (10.004 s counted as 10.0) | `accepted`, `stored.out` |
| `fade_length_limits` | smallest fade 50 ms instead of 100; values under 100 ms accepted or not rounded to whole ms | `accepted`, `stored.fade_ms` |
| `fade_length_held_to_window` | the stored fade or fade-in left longer than the window B - A | `stored.fade_ms`, `stored.fade_in_ms` |
| `fade_length_follows_window_changes` | a fade that was held to a small window is not clamped any more (caught by removing the clamp); a fade that "remembers" the longer request and grows back when the window grows (reasoned: the stored 3000 stays 3000 after `out` 20) | `stored.fade_ms` in rows 2 to 6 |
| `default_fade_longer_than_window` | a default fade longer than the window is dropped, or keeps its full length instead of being held to the window | `rows[].vol` (a 1.5 s curve gives 0.991 at 0.125 s, the right one 0.981) |
| `fade_in_cap` | the fade-in ignores the out-fade when it is capped; the 100 ms floor missing | `deck.fade_in_ms`, `deck.fade_in_ramp_s` |
| `fade_in_out_fade_overlap_901`, `_1000` | the out-fade shortened to make room for the fade-in (both lengths must stay) | `deck.end_fade_ms`, `deck.fade_in_ms` |
| `fade_in_start_threshold` | the fade-in limit exclusive (< 0.05 s) or 0.06 s; the "fresh" limit inclusive or 0.05 s | `deck.fade_in_ms`, `deck.start_vol`, `deck.fresh` per offset |
| `loop_switched_off_in_pass_1_end` | a loop switched off in pass 1 ends at once instead of at the end of the pass | `ended_at_s` (checked against `ideal_ended_at_s`) |
| `out_fade_once_switched_off_in_pass_1` | a `once` switched off in pass 1 does not make pass 1 the last one (no out-fade at the end of pass 1, or a second pass) | `rows[].vol`, `ended_at_s` |
| `out_fade_placement_default`, `_stop` | no out-fade at B for `default` / `stop` | `rows[].vol` at 3.25 to 3.75 s, `ended_at_s` |
| `out_fade_placement_loop` | an out-fade while looping | `rows[].vol` at 3.25 to 4.25 s |
| `out_fade_placement_once` | the out-fade in pass 1 instead of pass 2 | `rows[].vol` at 2.75 to 4.25 s and at 6.75 to 8.25 s, `ended_at_s` |
| `end_action_switched_mid_play` (end_actions.json) | the new action ignored; a switched-off loop or once ending at once instead of after the running pass | `ended_at_s`, `live_at_that_tick` |
| `once_seek_back_in_pass_1` | a `once` point spent for good after it fired | second entry of `fires` (22 s) |
| `once_skipped_by_seek_forward_then_back` | a seek over a `once` point spends it | `fires` (9 s) |
| `once_loop_seek_back_in_lap_1` | no re-arming after a seek in lap 1 | second entry of `fires` (5.5 s) |
| `once_loop_seek_back_in_lap_2` | a seek makes the pass count start again (re-armed after pass 2); `once` firing in every pass (also caught by `once_flag`) | `fires` has no entry after 1 s |
| `point_at_or_near_A_start_at_A` | the margin off by one tick (A missed, A - 1 ms fired, a point 51 ms after A on the first tick) | `rows[].fired`, `first_fire_t_s`, `ideal_fired` |
| `point_near_A_start_with_offset` | the "fresh" window 0.05 s instead of 0.06 s | `rows[].fired` for offsets 2.05 / 2.059 |
| `target_ready_after_1s` | a point dropped when its target is not decoded at its time | `fires` (6 s) |
| `target_never_ready` | a voice-over fired anyway or the track disturbed. NOT caught: waiting forever instead of giving up (nothing fires either way; the 30 s is an implementation limit, quirk 15) | `fires` |
| `target_never_ready_does_not_block_next_point` | a point that waits holds up the points behind it | `fires` (vo2 at 10 s) |
| `voice_level_and_second_point` | the voice-over ignoring `top_track_pct`; a second point replacing the voice-over, overlapping it or queued behind it | `voice_vol`; `at_12_5_s.voice` and `.tops`; `at_20_s.live`, `.tops` |
| `new_track_cut_while_voice_on_top` | the voice-over (or the old background) surviving a cut; the new track starting ducked | `voice.present`, `old_background.present`, `new_track.ducked` |
| `new_track_crossfade_while_voice_on_top` | the voice-over removed at once; left playing with the other decks fading; fading for another time (`top_fade_ms`) or with a linear curve; the new track ducked | `voice.present` and `voice.vol` at 4.05 to 4.95 s, `voice.present` false at 5.1 s, `old_background.*`, `new_track.vol`, `new_track.ducked` |

`new_track_*_while_voice_on_top` rows have three summary objects next to `decks`: `voice`, `old_background` and `new_track`, each `{present, vol, ducked, fading_out}` (`vol` = the deck's fade gain at that tick, compared like the other fades; the values are null while the deck is absent). Sampled at 3.95 s (before), 4.0 s (the start) and then 4.05, 4.25, 4.5, 4.75, 4.95 (during the 1 s crossfade), 5.1, 5.5 and 7.0 s (after it).

## Render references

Short WAV renders of real mixes: see `renders/` and its README (separate command, not part of the default run).
