# Plan: splitting `player.py` into `cpl/` (steps P1-P9)

> **STATUS (2026-11-03): the split is stopped at P6; P7-P9 are DEFERRED.** Done and released as 2.7.1: P1 launcher and `cpl/`, P2 helper processes, P3 `clock`/`util`/`config`/`dsp`, P4 `state` and hooks, P5+P6+7a the 15 modules `persist, cache, devices, durations, infostore, ffmpeg, playlists, library, triggers_data, loudness, formats, warm, fileinfo, upload, boot` (local tags `split-prep`, `split-P1` ... `split-P6b`; release tag `v2.7.1-rc1`). `cpl/legacy.py` (2,740 lines) still holds the transport (`Deck`, play/stop/crossfade, ducking, Play on Top, device change, resume), `tick()` and the triggers engine, the meters, the preview/mirror workers, the state-out (`snapshot`, `push`, variables), the command grammar, the web handlers and routes, the link download and `main()`. Behaviour is unchanged by the moves (move verifier, golden hashes, the whole suite). Deviations from this plan are in sections 9 and 10.
>
> **What P7 needs first (prerequisites):**
> 1. The gap tests still to write (section 5.4): **4** device change carry-over (`set_device` while playing: position, paused flag, volume, `trig_carry`, the re-decode branch of `_live_restore`, the fallback to the old device), **5** `_start_when_ready` races (stale token, list edited while loading, load error, removed file), **8** a second Play on Top replacing the first (`superseded`, `old_top[0].bg`) and `stop_all` during it, **9** a tick-duration measurement (min/avg/max) so a slow-down is visible. Gaps 1, 2, 3, 6, 7, 10 are written (tag `split-gap`).
> 2. A baseline of tick duration and of time-to-first-sound from the release (`tests/tools/ttfs.py`), the manual checks M1-M5 of section 6 on the production machine, and a soak of the release.
> 3. **Order change:** `tick()`/`ticker` (7e) cannot move before `stateout`, because `ticker` calls `push()` and `tick` reads the state-out; table 2.1 already puts `tick` in layer 9, above `stateout` (layer 8). Do 7b `transport`, 7c `triggers_engine`, 7d `meters` + `preview`, then P8's `stateout`, and only then 7e `tick`.
> 4. The P9 cleanup list (section 3.10): the `_import/` wipe as an explicit start-up call, unused imports in `legacy`, the private cache internals.

Planning document only. No code was changed, no server was started and no test was run to write it. Everything below was read from the code and from `git` (`grep`, `wc`, an `ast` pass kept in a scratch folder, not in the repo).

- **Base:** `main` at `89c9f70` = tag `v2.7.0-rc2` (the release candidate under soak test). This plan lives on the local branch `split`, which is not pushed.
- **Written:** 2026-11-03. Line numbers are for `player.py` at `89c9f70` (5,490 lines, 35 commits of history). They drift with every edit: re-run the checks in section 1.4 before each step.
- **Source audit:** `docs/AUDIT-split.md` (written when `player.py` was 7,711 lines, before the web UI went to `static/`). Where this plan disagrees with the audit, this plan is newer. The differences that matter:
  - The UI steps (U1-U4) are done (tags `post-u3`, `post-ui-cleanup`). `player.py` is now 5,490 lines, of which about 5,160 are Python.
  - The project is now a git repository, with tags `pre-split`, `post-fixes`, `post-u3`, `post-eol`, `post-ui-cleanup`, `v2.7.0-rc1`, `v2.7.0-rc2`.
  - The test harness already copies `player.py` + `cpl/` + `static/` (`tests/harness/appcopy.py`, `copy_app`), fingerprints the whole tree, and has the `CP_TEST_DEVICES` hook instead of source patching. Audit "before starting" items 1, 2 and 4 are therefore mostly done.
  - **18 module-level names are reassigned at runtime, not 15** (24 `global` statements, 47 write sites). The extra three are `_dur_busy`, `_dur_booted`, `_ui_cache`. Section 4 lists them all.
  - `CLAUDE.md` (Layout table) says `player.py` is "about 7,600 lines (the web UI now lives in `static/`)". That is stale: the file has 5,490 lines (about 5,160 of Python), and the audit's 7,711 and 6,700 are older still. Correct the figure in the P1 docs edit, and again in P9 when `player.py` becomes a launcher of about 60 lines.

---

## 0. Summary

| | |
|---|---|
| Target | `player.py` becomes a launcher of about 60 lines; the code moves to about 30 small modules under `cpl/`, plus `cpl/helpers/` (the four child-process entry points) and `cpl/web/` (HTTP handlers). `static/` is unchanged. |
| Deployment | Directory copy: `player.py` + `cpl/` + `static/` (the audit's option A). Companion module untouched (HTTP only). |
| Order | P1 launcher -> P2 helpers -> P3 leaves + clock seam -> P4 state -> P5 ffmpeg and caches of file facts -> P6 playlists, library, cache, warm -> P7 transport, tick, triggers engine, meters, preview -> P8 stateout, commands, web -> P9 boot, app, cleanup. |
| Import graph | Acyclic, with **3 hook lists** (`on_change`, `on_save`, `notify`) and **5 relocations** (section 2.3). Checked with an `ast` pass over the current code: with those changes the graph has no cycle. |
| Highest risk | P4 (state) and P7 (transport/tick): section 4 and section 5. |
| Not changed | Behaviour, HTTP bodies, OSC, command grammar, config keys, file formats, the Companion module. Every step is a move, verified by the suite, the golden hashes, and an AST comparison (section 3.4). |
| Effort | About 29-41 h of Claude Code working time over all steps plus about 3.5-4 h of your time for production machine listening checks (section 8). |

Stop points: P1-P6 are safe, non-audio moves (about 2,300 lines leave the main file). **P7 gates everything above it**: `commands`, `stateout`, `tick` and all HTTP handlers use `transport`, so they cannot move until it has moved (an extracted module may never import the temporary `legacy` module). So "stop after P6" leaves about 2,400 lines (the audio core and everything that calls it) in `cpl/legacy.py`.

---

## 1. Ground rules and verification toolkit

### 1.1 Branch and rollback

- Work happens only on the local branch `split`. Never push it, never set an upstream, never touch `main`. If `main` gets a hotfix during the split, cherry-pick it into `split` by hand (the later the step, the more painful; see Decision 8).
- One commit (or a short series) per step, message `Split P<n>: ...`. The commit hash before a step is its rollback point: `git reset --hard <hash>` on `split` (safe because `split` is local; nothing else points at it).
- Optional local tags `split-P<n>` after each green step. **No tags are created by this task.** Decision 7 asks whether you want them.
- Rolling back a single step does not need a rebuild of anything: `player.py`, `cpl/` and `static/` are the whole product.

### 1.2 What "green" means after every commit

1. `python tests/run.py` -> **370 passed, 0 failed, 1 skipped** (baseline `tests/reports/baseline-post-fixes/`; the skip is the memory readout on macOS). Compare with `grep -E '^(FAILED|SKIPPED)' <output> | sort | diff - tests/reports/baseline-post-fixes/failed-and-skipped.txt`.
2. `python tests/test_pages_equal.py` -> golden hashes unchanged (`/`, `/help`, `/stage`, `/variables`, `/api/state`, `/api/playlists`, `/api/variables`, `/api/library`). It runs at the end of `tests/run.py` too.
3. `python tests/test_triggers.py` (in-process, fake clock, 38 tests), `python tests/test_devices.py`, `test_static_crlf.py`.
4. From P3 on: the move verifier and the no-bare-state gate (3.4, 4.5).
5. `PYTHONHASHSEED=0 python tests/gen_controls.py` -> `tests/controls.csv` differs from the committed one **only in the `where` column** (see 1.3).
6. For P1, P2, P7, P9: the manual checks listed in the step.

### 1.3 Test tooling that must change (one-time, in P1)

| Item | Today | Needed |
|---|---|---|
| `tests/test_triggers.py` | loads `player.py` with `spec_from_file_location` as a fresh module per test (fresh globals each time) and sets `P.time`, `P.request_loudness`, `P.request_warm`, `P._warm_loop`, `P._play_on_top`, `P.DURS`, `P.playlists` | A helper `load_app(dir)` that puts the copy on `sys.path`, **purges every `cpl*` entry from `sys.modules`** (otherwise state is shared between tests and between test and test), imports, and returns a small namespace of the modules. Patches move to the module that owns the name (section 4.4). |
| `tests/gen_controls.py` | `ast`-parses `player.py` for `command()`, the route table, `VAR_INFO`, `snapshot()`, `list_vars()`; control locations are `player.py:<line>` | Read all of `player.py` + `cpl/**/*.py` (sorted) and keep a file:line map. Locations change in every row, hence "only the `where` column may differ" in 1.2 item 5. |
| `tests/harness/report.py` | already hashes `player.py` + `cpl/` + `static/` (`tree_hash`) | none |
| `tests/harness/appcopy.py` | already copies `cpl/` and `static/` (ignoring `__pycache__`) | none |
| `tests/test_devices.py`, `test_devices_ui.py`, `test_live_output.py`, `test_layout_share.py` | black-box over HTTP/Playwright via `copy_app` and `python -I` | none expected; they are the `-I` smoke test. |

### 1.4 Re-verification commands for line ranges (read-only)

```
python3 - <<'EOF'      # lists every top-level def/class/assignment with its range (what this plan used)
import ast; t=ast.parse(open('player.py').read())
for n in t.body: print(n.lineno, n.end_lineno, type(n).__name__, getattr(n,'name',''))
EOF
grep -n "^\s*global " player.py              # 24 statements today
grep -nE "time\.(monotonic|time|sleep|time_ns)" player.py | wc -l     # 44 uses today
grep -n "__file__" player.py                 # 5 uses: BASE + 4 child-process spawn sites
```

---

## 2. Target layout

### 2.1 Modules, contents, size, imports

"Lines" = the lines of the definitions (from the `ast` pass; blank lines and comments between definitions are not counted, so a module is slightly longer on disk). Ranges are `player.py` line numbers at `89c9f70`. "May import" lists only `cpl` modules; any module may also import `clock` and `util`, and the third-party libraries it needs today. **No module imports anything from a module listed above it.** `cpl/__init__.py` is empty (a helper process must not import the app by accident).

| Layer | Module | Lines | Purpose | What moves in (name range) | May import |
|---|---|---:|---|---|---|
| 0 | `clock` | ~15 new | The one time source (test seam) | new; replaces the 44 `time.*` uses | nothing |
| 0 | `util` | 79 | Small helpers with no app knowledge | `atomic_write` 515-522, `_log_seen`/`_tasks` 525-526, `log_once` 529-534, `spawn` 537-548, `is_uint` 551-553, `route_int` 556-561, `finite_float` 564-570, `body` 573-579, `fmt` 928-930, `fmt_bytes` 933-938, `_UNITS` 942-943, `_warned` 944, `parse_size` 947-961, `_sc` 964 | nothing |
| 0 | `dsp` | 83 | numpy-only maths, usable by the helpers | `METER_WIN` 132, `compute_env` 135-151, `DUCK_STEP` 2133, `duck_key` 2137-2153, `duck_curve` 2156-2170 (**takes ratio/threshold/hold as arguments**, Fix F1), `lufs_from_pcm` 2363-2394, the numpy import try-block 128-131 | nothing |
| 0 | `state` | ~60 | The shared mutable state and the three hook lists (section 4) | `playlists` 495, `FOLDER_COLORS` 496, `FOLDER_ICONS` 497, `LIBDIRS` 498, `library` 499, `focus` 500, `cue_cleared` 501, `decks` 502, `live_deck` 503, `rev` 504, `known` 505, `last_scan` 506, `bump` 509-512, `pending` 1333, `_pending_n` 1334, `DEV_MISSING` 1775, `MONITOR` 3346, `ISSUES` 3400, `LAST_LOAD_ERR` 3401, `_boot_done` 3402, `DURS` 3933 | nothing |
| 1 | `config` | ~140 | Paths, `CFG`, config/state file reading | `APP_VERSION` 17, `_test_dev_dir` 20-24, `BASE/MEDIA/LIB` 355-357, `DATA` 372, `CFG` 373-417, `cfg_file`/`read_config_file` 418-435, the overlay statements 438-449, `RESUME/STATE` 440-441, `WARN_*`/`_warn_item`/`warn_clean` 450-481, 484-487, `PLAY_MODES` 488-490, `AUDIO_EXT` 492, `save_config_keys` 3394-3398. `BASE` becomes the **launcher's folder** (`parent.parent`), not `cpl/`. | `util` |
| 2 | `persist` | 18 | Writing `playlists.json` and `state.json` | `save` 582-592 (calls `bump()` then the `on_save` hooks, Fix F3), `save_state` 1864-1870 | `config`, `state` |
| 2 | `cache` | 171 | Decoded-sound LRU, decode child, trimmed cuts | `_cache` 1329, `_cache_lock` 1330, `_loading` 1331, `_gen` 1332, `resolve_path` 1338-1346, `_env` 1349, `cached` 1352-1357, `_tcache` 1360, `_key` 1361, `_cache_total` 1364-1365, `cache_bytes` 1368-1370, `cache_drop` 1373-1380, `cache_put` 1383-1395, `cut_sound` 1398-1402 (uses pygame, so it is here, not in `dsp`), `trimmed_cached/put` 1405-1416, `mem_info` 1419-1463, `decode_in_child` 1466-1483, `_load` 1486-1514, `ensure_loaded` 1517-1532. New: `invalidate_all()` (bumps `_gen`, clears `_loading`, `_cache`, `_tcache`, used by `set_device`) and `rename_path(old, new)` (used by `lib_rename`). | `config`, `dsp` |
| 2 | `devices` | 47 | Output device listing and mixer open | `init_mixer` 1733-1753, `_natkey` 1756-1759, `list_devices` 1762-1772, `dev_notices` 1778-1788 | `config`, `state` |
| 2 | `durations` | 62 | Track lengths, one worker thread | `DURFILE` 3932, `_dur_busy` 3934, `_dur_booted` 3935, `_dur_load/_save` 3938-3954, `_probe_dur` 3957-3973, `_dur_worker` 3976-3996, `durations` 3999-4004. New `status()` returns `(busy, booted)` for `health`. | `config`, `state` |
| 2 | `infostore` | 45 | The file-information store (split out of `fileinfo`, Fix F5) | `INFOFILE` 4119, `INFO` 4120, `_info_load/_save` 4124-4139, `_info_pending` 4142, `info_save_soon` 4145-4159, `info_entry` 4162-4167, `info_store` 4170-4176 | `config`, `state` |
| 3 | `ffmpeg` | 210 | All ffmpeg/ffprobe use in one place | `_num` 2484-2490, `ff_loudness` 2493-2509, `ff_lufs` 2512-2514, `ff_volume` 2517-2524, `_wave` 4501, `WAVE_BINS` 4502, `_wave_lock` 4503, `ff_wave` 4506-4526, `get_wave` 4529-4563, `CONVERT_EXT` 4934-4935, `FF` 4936, `_ff_sem` 4937, `ff_check` 4940-4964, `ff_prefix` 4967-4980, `ff_run` 4983-5011, `ff_probe` 5014-5039, `ff_convert` 5042-5056, `needs_normalising` 5059-5061 | `config`, `dsp`, `cache` |
| 3 | `playlists` | 323 | The playlist model | `pl_mode` 595-599, `END_ACTIONS` 602, `end_of/is_loop/set_end/set_loop` 605-649, `xfade_of/xfade_ms/set_xfade` 652-689, `_file_len` 692-695, `trim_of` 698-702, `FADE_*` 705, `fade_default_ms/fade_ms_of` 708-719, `trim_range` 722-730, `set_trim` 733-797, `valid` 917-918, `track` 921-925, `clamp_focus` 1219-1225, `remap_all` 1228-1236, `add_to_playlist` 1239-1254, `remove_from_playlist` 1257-1272, `move_track` 1275-1321, `move_focus/move_playlist` 2681-2692, `_bag` 2695, `set_play_mode` 2698-2714, `next_in_order` 2717-2735 | `config`, `persist`, `state` |
| 4 | `library` | 224 | Library scan and file operations | `storage_info` 967-981, `invalidate_storage` 984-986, `scan_library` 990-1009, `unique_in_lib` 1012-1017, `_safe_rel` 1020-1033, `mkdir_new` 1036-1048, `lib_mkdir` 1051-1059, `lib_rmdir` 1062-1087, `lib_rename` 1090-1165 (calls `cache.rename_path`, no direct `_cache` access), `find_duplicate` 1168-1177, `missing_refs` 1180-1186, `rescan_library` 1189-1195, `delete_from_library` 1198-1215 | `config`, `state`, `persist`, `cache`, `playlists` |
| 4 | `triggers_data` | 115 | Trigger points, data side | `TRIG_MAX` 804, `TRIG` 805, `_truthy` 808, `triggers_of` 812-816, `trigger_json` 819-826, `trigger_target_ok` 829-830, `_trig_clean` 833-857, `set_triggers` 860-914, plus `trig_deck` 2939-2944 and `trigger_targets` 2947-2956 (Fix F4) | `config`, `state`, `persist`, `playlists` |
| 4 | `loudness` | 148 | Level match | `LOUDFILE` 2339, `LOUD` 2340, `_loud` 2341, `NORM_DEFAULT` 2342, `_loud_load/_save` 2345-2360, `norm_cfg` 2397-2401, `_lufs_of` 2404-2406, `norm_gain_db` 2409-2423, `norm_gain` 2426-2428, `apply_gain_live` 2431-2434, `_scipy_ok` 2437-2442, `loud_pending` 2445-2462, `request_loudness` 2465-2481, `_loud_worker` 2527-2555 (stores through `infostore`), `set_norm` 2558-2587 | `config`, `state`, `persist`, `cache`, `dsp`, `ffmpeg`, `infostore`, `playlists` |
| 4 | `formats` | 86 | Format checks | `FMTFILE` 4007, `FMT` 4008, `FMT_STATE` 4009, `_fmt_load/_fmt_save` 4012-4027, `fmt_judge` 4030-4052, `_fmt_run` 4055-4092, `fmt_kick` 4095-4102 | `config`, `state`, `ffmpeg` |
| 4 | `preview` | 180 | Preview/Mirror workers and Solo monitor | `Preview` 3196-3316, `Mirror` 3319-3340, `preview`/`mirror` 3343-3344, `_mon` 3347, `monitor_set` 3350-3354, `monitor_decks` 3357-3368, `monitor_sync` 3371-3387 | `config`, `state`, `persist`, `playlists` |
| 5 | `warm` | 72 | Warm-up policy (what to decode ahead) | `_warm` 1335, `request_warm` 1535-1544, `_warm_loop` 1547-1575, `_warm_trims` 1578-1609 | `config`, `state`, `cache`, `playlists`, `triggers_data` |
| 5 | `fileinfo` | 111 | The "i" popover | `_info_jobs` 4121, `_wav_basic` 4179-4189, `_info_job` 4192-4241, `info_response` 4244-4292 | `config`, `state`, `cache`, `dsp`, `ffmpeg`, `formats`, `infostore`, `loudness` |
| 5 | `upload` | 103 | Upload plumbing | `import_file` 1613-1635, `NoSpace` 4916, `drain` 4920-4922, `space_error` 4925-4927, `IMPORT_DIR` 5064, `save_upload` 5068-5138 | `config`, `state`, `ffmpeg`, `library` |
| 6 | `transport` | 640 | The audio core (kept as ONE module) | `_live_snapshot` 1791-1802, `_live_restore` 1805-1825, `set_device` 1828-1861, `Deck` 1874-2019, `is_paused/is_fading_out` 2022-2027, `_vol_before_mute` 2030, `set_live_volume` 2033-2045, `seek_live` 2048-2082, `stop_all/pause_all/resume_all` 2085-2104, `play` 2107-2126, `DUCK` 2134, `duck_arm` 2173-2208, `_duck_loop` 2211-2245, `DUCK_LIMITS/STEPS` 2248-2252, `set_duck` 2255-2277, `play_on_top` 2280-2288, `_play_on_top` 2291-2305, `_start_when_ready` 2308-2335, `_start` 2590-2652, `play_default` 2655-2658, `fade_out` 2661-2671, `toggle` 2674-2678, `play_playlist` 2738-2751, `auto_advance` 2754-2773, `_rs` 2776, `save_resume` 2779-2811, `try_resume` 2814-2844, `trig_carry_of` 2959-2964 (Fix F4) | `config`, `state`, `persist`, `cache`, `dsp`, `devices`, `loudness`, `playlists`, `warm` |
| 6 | `boot` | 90 | Start-up data loading | `migrate_old` 1638-1666, `load` 1669-1729 | `config`, `state`, `persist`, `cache`, `library`, `playlists`, `upload` |
| 7 | `meters` | 60 | Level taper and meter values | `METER` 2847, `METER_PUB` 2848-2849, `_meter_t` 2850, `METER_FLOOR/DECAY` 2851, `BAR` 2852, `METER_STOPS/TICKS/TICKS_SMALL/AMBER_DB/RED_DB` 2855-2858, `to_db` 2861, `pct_of` 2865-2872, `pct_lin` 2875, `db_text` 2880, `update_meters` 2884-2910, `meters_json` 2913-2918 | `config`, `state`, `dsp`, `preview`, `transport` |
| 7 | `triggers_engine` | 171 | Trigger points, run-time side | `TRIG_WAIT_S` 2928, `_trig_load_err` 2929, `trig_notice` 2932-2936, `_trig_init` 2967-2983, `_trig_eligible` 2986-2988, `_trig_cross` 2991-3002, `_trig_load` 3005-3018, `_trig_fire_due` 3021-3058, `triggers_tick` 3061-3090, `next_trigger` 3093-3111, `_nt_json` 3114-3116, `skip_next_trigger` 3119-3126, `set_triggers_armed` 3129-3132, `live_triggers_json` 3135-3144, `triggers_json` 3147-3152 | `config`, `state`, `cache`, `triggers_data`, `transport`, `warm` |
| 8 | `stateout` | ~151 | Variables out to Companion, health, snapshot | `osc_out` 3391 (module-local; `rebuild_osc()` replaces the write in `h_set_settings`), `last_sent` 3399, `health` 3405-3418, `snapshot` 3421-3468, `_list_keys` 3471, `list_vars` 3474-3489, `push` 3492-3502, `VAR_INFO` 3750-3800, plus `warn_json` 4382-4387 and `duck_json` 4435-4438 (Fix F7). Registers itself as `state.notify` at import. | `config`, `state`, `durations`, `library`, `meters`, `playlists`, `preview`, `transport` |
| 8 | `ui_assets` | 38 | Reads `static/`, builds the page | `STATIC` 358, `_static` 361-364, `_STATIC_FILES` 367, `_missing` 368 (the "folder incomplete" exit moves to the launcher as well), `VARS_PAGE` 3802, `_scale` 3806, `_include` 3810, `build_ui` 3816-3827, `UI_DEV` 3830, `_ui_cache` 3831, `ui_page` 3834-3841, `STAGE_PAGE` 3848, `HELP_PAGE` 3851 | `config`, `meters` |
| 9 | `commands` | 236 | Companion command grammar | `command` 3506-3737, `osc_default` 3740-3743 | `config`, `state`, `devices`, `library`, `loudness`, `persist`, `playlists`, `preview`, `stateout`, `transport`, `warm` |
| 9 | `tick` | 55 | The 50 ms loop | `tick` 3155-3192, `ticker` 5334-5350 | `state`, `meters`, `preview`, `stateout`, `transport`, `triggers_engine` |
| 9 | `download` | 129 | Link download (parent side) | `DL_FORMATS` 5142, `DL` 5143, `_dl_task` 5144 (module-local), `ytdl_module` 5147-5154, `_dl_clean` 5157-5159, `_dl_child` 5162-5198, `_dl_run` 5201-5252, `h_dl_start/state/clear` 5255-5284 | `config`, `state`, `ffmpeg`, `library`, `persist`, `stateout`, `upload` |
| 9 | `web/library.py` | 150 | Library, file info, upload, waveform handlers | `h_formats` 4105, `h_lib_info` 4295, `h_library` 4313, `h_lib_rename/mkdir/color/rmdir` 4327-4369, `h_storage` 4372, `h_waveform` 4566, `h_lib_file` 4607, `h_ffmpeg` 4877, `h_lib_delete` 4884, `h_move` 4890, `h_scan` 4912, `h_upload` 5287-5323 | many, all below it |
| 9 | `web/output.py` | 100 | Meters, SSE, preview, mirror, devices | `h_meters` 4576, `_live_subs` 4580, `h_live` 4583-4604, `h_pv_*` 4616-4661, `h_mirror_*` 4664-4678, `h_devices` 4681, `h_set_device` 4689, `h_monitor` 4901 | |
| 9 | `web/playlists.py` | 149 | Playlist/trigger handlers | `PL_NAME_MAX` 4698, `h_add_list` ... `h_pl_remove` 4701-4874, `move_playlist_to` 4709-4737 | |
| 9 | `web/settings.py` | ~93 | Settings handlers | `h_get_settings` 4376, `h_warn_*` 4390-4408, `h_tr_*` 4411-4432, `h_folders_*` 4441-4455, `h_top_*` 4458-4469, `h_set_settings` 4472-4498 | |
| 10 | `web/pages.py` | 67 | Page, state and command handlers | `h_stage` 3854, `h_help_page` 3863, `h_restart` 3867-3884, `h_vars_page/h_vars` 3887-3897, `h_ui` 3900, `h_state` 3904-3919, `h_lists` 3922-3929, `h_cmd` 5326-5330 | |
| 11 | `app` | 131 | The route table, middleware, `main()` | `main` 5353-5483 | everything |
| - | `helpers/probe.py`, `decode.py`, `dl.py`, `preview_worker.py` | 11, 17, 70, 193 | The four child-process entry points | lines 27-37, 39-55, 57-126, 154-346 | **stdlib, pygame, numpy and `cpl.dsp` only. Never `cpl.config`, `aiohttp`, `pythonosc`.** |
| - | `player.py` (launcher) | ~60 | `sys.path` fix, missing-folder check, helper dispatch **before** any app import, then `cpl.app.main()` | new | `cpl.helpers.*`, then `cpl.app` |

`cpl/legacy.py` exists only between P1 and P9 (all not-yet-moved code, verbatim). Nothing already extracted may import it.

### 2.2 Import graph (confirmed acyclic)

The edge lists in the table above are the whole graph. By layer, each module imports only from lower layers (0 = no `cpl` imports apart from `clock`/`util`): `clock, util, dsp, state` -> `config` -> `persist, cache, devices, durations, infostore` -> `ffmpeg, playlists` -> `library, triggers_data, loudness, formats, preview` -> `warm, fileinfo, upload` -> `transport, boot` -> `meters, triggers_engine` -> `stateout, ui_assets` -> `commands, tick, download, web/*` -> `app`.

How this was checked: an `ast` pass assigned every top-level name of the current `player.py` to a module of the table above, followed every name reference between modules, and ran a strongly-connected-component search. Result with the fixes of 2.3 applied: **no component with more than one module, no upward edge**. Without the fixes the same pass finds one component of 14 modules (`devices, durations, infostore, library, loudness, meters, persist, plmodel, preview, state, stateout, transport, trigdata, warm`). The pass follows names, not `getattr`/`globals()`; there is no use of `globals()` or `sys.modules` in `player.py` (checked with grep). The check must be re-run as a script gate (4.5, `tests/test_import_graph.py`) so that it keeps holding.

### 2.3 The back-edges and their fixes

| # | From -> to (symbols) | Fix | Behaviour change? |
|---|---|---|---|
| F1 | `dsp` -> `config` (`duck_curve` reads `CFG["duck_ratio"]`, `["duck_threshold_db"]`, `["duck_hold"]`) | `duck_curve(key, level, ratio, threshold_db, hold)`; both call sites (`duck_arm`'s `fit` and `late`) pass the values read at the same moment as today | none (values read at the same point of the same call) |
| F2 | `state` -> `warm` (`bump()` calls `request_warm()`) | `state.on_change` (list of callables); `bump()` runs them in order; `warm` registers `request_warm` at import | none, if registered (gate: test that the list is non-empty after `app` import) |
| F3 | `persist` -> `loudness` (`save()` calls `request_loudness()` after `bump()`) | `state.on_save` list run after `bump()`; `loudness` registers at import. Order preserved: `atomic_write`, `bump` (-> `on_change`), then `on_save` | none |
| F4 | `warm` -> `triggers_engine` (`trigger_targets`), `transport` -> `triggers_engine` (`trig_carry_of`) | `trigger_targets` and `trig_deck` only read `live_deck`, `decks` and trigger data: move to `triggers_data`. `trig_carry_of` only reads a `Deck` attribute: move to `transport` | none |
| F5 | `loudness` <-> `fileinfo` (`_loud_worker` -> `info_store`, `_info_job` -> `LOUD`, `apply_gain_live`) | the store (`INFO`, `info_entry`, `info_store`, `_info_save`, `info_save_soon`, `_info_load`) becomes `infostore`, below both | none |
| F6 | `loudness` -> `stateout` (`push` in `_loud_worker`, `set_norm`) and `transport` -> `stateout` (`push` in `_start_when_ready`, `auto_advance`, `play_playlist`) | `state.notify`: a callable, default no-op, that `stateout` sets at import to `push`. Callers do `S.notify()` where they did `push()` | none if registered; if not registered the call is silently skipped (gate: the registration test, and `ticker` already pushes changed values every 50 ms) |
| F7 | `web_core.h_state` -> `warn_json`/`duck_json` (settings) | both functions are tiny JSON builders over `CFG`: move to `stateout` | none |
| F8 | `library` -> `cache` internals (`lib_rename` touches `_cache`, `_cache_lock`, `_env`, `_key`, `_tcache`) | `cache.rename_path(old, new)`; `delete_from_library` already uses `cache_drop` | none (same operations in the same order, still under `_cache_lock`) |
| F9 | `plmodel` -> `durations` (`_file_len` reads `DURS`) | the `DURS` dict lives in `state` (it is a plain dict never rebound; `durations` fills it) | none |
| F10 | `meters` -> `preview` (`update_meters` reads `preview`, `MONITOR`) | ordering only: `preview` is below `meters` | none |
| F11 | `download` -> `upload` (`space_error`), `config` -> `util` (`atomic_write`) | ordering only | none |
| F12 | `set_device`, `_live_snapshot`, `_live_restore` live in `devices` (audit) but call `stop_all`, `_start`, `_start_when_ready` | they are transport operations: they live in `transport`; `devices` keeps `init_mixer`/`list_devices` | none |
| F13 | `main` -> all handlers | `main` lives in `app`, the top | none |
| F14 | `set_device` -> `_gen` rebinding | `cache.invalidate_all()` owns `_gen`; `set_device` calls it in the same place (after `stop_all()`), then keeps `with _cache_lock: _cache.clear(); _tcache.clear()` inside it. `_load` reads `_gen` locally. | none |

Three of the audit's items did not survive contact with the current code: `cut_sound` cannot be numpy-only `dsp` (it uses `pygame.mixer`, so it goes to `cache`), `fmt` appears as a "reference" only because `cut_sound` has a local variable of that name (a false positive of the name-based pass), and `load()` needs `upload` (`import_file`) and `library`, so `boot` sits above them.

---

## 3. Steps P1-P9

Risk scale: low (no audio path, easy to see), medium (shared state or process start-up), high (audio path or shared mutable state). "Rollback" is always `git reset --hard <hash of the commit before the step>` on `split`.

### 3.1 P1: launcher and `cpl/` skeleton

- **Modules touched:** `player.py`, new `cpl/__init__.py` (empty), new `cpl/legacy.py`.
- **Scope:** move the whole of the current `player.py` into `cpl/legacy.py` verbatim, with four mechanical edits: `BASE = Path(__file__).resolve().parent.parent`; `LAUNCHER = BASE / "player.py"` and the 4 spawn sites use `str(LAUNCHER)` instead of `str(Path(__file__).resolve())` (the four spawn sites: `decode_in_child` 1469, `Preview._spawn` 3237, `_probe_dur` 3968, `_dl_child` 5172; `h_restart` uses `sys.argv` and needs no change); the `if __name__ == "__main__"` block becomes `def run()`. `player.py` becomes: insert its own folder at `sys.path[0]` (needed because the tests and the documented run command use `python -I`, which removes the script folder), check that `cpl/` and `static/` exist (clear message, `sys.exit`), `import cpl.legacy as app; app.run()`. The helper blocks (lines 27-346) stay at the top of `legacy.py` for now and still run at import time, before `import pygame`/`aiohttp` (line 348), exactly as today.
- **Stays until later:** everything.
- **Also in P1:** `load_app()` for `tests/test_triggers.py`, the `gen_controls.py` change (1.3), `tests/README.md` and `CLAUDE.md` layout table (one line each, the rest at P9).
- **Verification:** full 1.2; plus `python -I player.py` from a scratch copy (proves the `sys.path` fix); `POST /api/restart` and the page reconnects (the `os.execv` restart keeps `sys.argv[0] = player.py`); the four helper modes each run alone: `python -I player.py --probe media/library/x.wav` prints a float; `python -I player.py --decode x.wav 48000 -16 2 | wc -c` prints the byte count; `printf '{"cmd":"stop"}\n' | SDL_AUDIODRIVER=dummy python -I player.py --preview ""` prints status lines; `python -I player.py --dl '{...}'` (needs the network, so use the existing download test or skip and note it). Windows: `run-player.bat` flow on `the Windows install folder`: copy the three items, start, `pip install --upgrade -r requirements.txt` still runs, the page loads. Linux/production machine (quiet moment): `systemctl cat companionplayer` (the unit is not in this repo) shows `ExecStart=... player.py` with `WorkingDirectory` at the install folder; start/stop/restart once.
- **Rollback:** the commit before P1 (equal to `v2.7.0-rc2` if nothing else has been committed on `split`).
- **Risk: medium.** Not because of the code (it is moved verbatim) but because it changes how the process is started: `-I`, `__file__`-relative paths, helper start-up, and a partial deploy (`player.py` without `cpl/`). The failure modes are loud (the player does not start or a child does not spawn), which is why it is done first and alone.

### 3.2 P2: helper processes to `cpl/helpers/`

- **Modules touched:** `legacy.py` (loses the four helper blocks, lines 27-126 and 154-346; `_test_dev_dir` 20-24 stays until `config` exists in P3), new `cpl/helpers/{__init__,probe,decode,dl,preview_worker}.py`, `player.py` (dispatch).
- **Scope:** the launcher inspects `sys.argv[1]` first and `runpy`/imports only the matching helper; **the app is not imported for a helper**. `compute_env` + `METER_WIN` + the numpy import move to `cpl/dsp.py` now (the `--preview` worker needs them, and `dsp` is the right final home); `_test_dev_dir` is duplicated as a 5-line function in the helper package until `config` exists (P3 deletes the duplicate; both read the same env var).
- **Stays:** everything else in `legacy.py`.
- **Verification:** the four helper modes again, with these additions: (a) measure helper start time before and after (`--decode` runs once per decoded track, on the production machine under `nice`): `python -X importtime -I player.py --decode ... 2>&1 | grep -E "aiohttp|pythonosc|cpl"` must show **no** aiohttp/pythonosc and only `cpl.dsp`/helper imports; (b) `tests/api/test_preview.py` (preview and mirror worker in the dummy driver), the download test, `test_devices.py` (checks `worker.log`); (c) golden hashes.
- **Rollback:** the P1 commit.
- **Risk: low-medium.** The helpers have no shared state, but an accidental import of the app makes every decode slower and heavier; the `-X importtime` check is the proof.

### 3.3 P3: leaves (`util`, `clock`, `config`, `dsp`) and the clock seam

- **Modules touched:** `legacy.py`, new `cpl/util.py`, `cpl/clock.py`, `cpl/config.py`, `cpl/dsp.py` (complete), `tests/test_triggers.py`.
- **Scope:** exact contents in the table in 2.1. `config` keeps its import-time behaviour (read `config.json`, overlay `state.json`, create `media/library`); it must be imported before anything reads `CFG`. `duck_curve` takes its parameters (F1). **The clock seam** (section 5.3) lands here as a separate commit before the moves: first `clock.py`, then replace all `time.monotonic()/time.time()/time.sleep()` in `legacy.py` by `clock.*` (44 sites, a mechanical edit; `time.time_ns()` at 5090/5116 stays real, it names temp files), then change `test_triggers.py` to `clock.install(fake)`, run it and the suite, and only then move code.
- **Stays:** everything else.
- **Verification:** 1.2 with special attention to `tests/test_triggers.py` (38 timing tests) and `tests/api/test_ducking.py` (`duck_curve` signature); the move verifier (3.4) on every moved function; a check that no module outside `clock.py` still contains `import time` (grep gate, section 5.3).
- **Rollback:** the P2 commit (or the sub-commit before the clock replacement if only that is wrong).
- **Risk: low.** Pure functions and constants. The one place with a behavioural subtlety is the clock: see 5.3.

### 3.4 The move verifier (used from P3 on)

A script `tests/tools/verify_move.py` (to be written in P3; **not written by this task**) takes two git revisions and a name-to-module map. For every moved function/class it compares the normalised AST of the old and new definitions: bare names in the "moved to state" set are rewritten to `S.<name>`, `global` statements are dropped, references to other moved functions are rewritten to `module.func` form; everything else must be identical, node for node. Any difference fails. This proves a step was only a move, including that no `await` was added or removed and no statement order changed. It is the main safety net for the parts the suite cannot hear.

### 3.5 P4: the state module

Detailed in section 4. In short: `cpl/state.py` is created with the cross-module shared names; the 11 cross-module reassigned names become `S.x` (everywhere, via a rewrite script, one group per commit); the 7 module-private ones stay `global` inside their own future module; three hook lists are added. All of it still inside `legacy.py` (only `state.py` is new).
- **Verification:** full 1.2 after every commit, `tests/test_no_bare_state.py` (4.5) from the first commit, then the manual run: play, fade, cut, Play on Top, device change, restart with resume (resume is off in the harness config; this is manual, see section 6).
- **Rollback:** the P3 commit, or the last green sub-commit.
- **Risk: high.** 47 write sites, and readers in many functions (`playlists` alone is read by 47), of names that every audio function touches; a miss creates a local variable or a stale copy and fails only on a specific path. Mitigation: the rewrite is scripted, the gate is static, and the failure mode of a *forgotten read* is a loud `NameError` once the old module-level name is deleted (4.3).

### 3.6 P5: file-fact modules

- **Modules:** `ffmpeg`, `infostore`, `fileinfo`, `durations`, `formats`, `loudness` (+ the `devices` module, which is a pure leaf and rides along).
- **Scope:** table 2.1. `ff_*` helpers, which today sit in four places (2484-2524, 4506-4563, 4934-5061), become one module. Two behaviours to carry over exactly: `ff_check` is cached for 60 s and is never called on the event loop (only through `run_in_executor`); `_scipy_ok` likewise. `_dur_worker` is the only real Python thread besides executors; its `_dur_busy/_dur_booted` writes stay module-local to `durations` and are read by `health` through `durations.status()` (this keeps the exact atomicity of today: two plain bool writes, one writer thread).
- **Stays:** everything from `library` upward.
- **Verification:** 1.2; ffmpeg tests **with and without ffmpeg**: re-run `tests/run.py` once with `"ffmpeg_path": "/nope/ffmpeg"` in the harness config (CLAUDE.md "Testing" step 5) to prove the fallbacks (`decode_in_child` + `compute_env` for waveforms, `lufs_from_pcm` for loudness); upload of an MP3 and a FLAC; the "i" popover on a file (fresh and cached); format check run; `durations.json` written after a rescan.
- **Rollback:** the P4 commit.
- **Risk: medium.** Self-contained, but ffmpeg subprocess handling (`nice`, `taskset`, one-job semaphore) has OS-specific branches that the Mac suite does not exercise: check on Linux (production machine or the Pi) and on Windows once.

### 3.7 P6: model, library, cache, warm, trigger data

- **Modules:** `persist`, `cache`, `playlists`, `library`, `warm`, `triggers_data`, `boot`'s dependencies (`upload`).
- **Scope:** table 2.1 including F2, F3, F4, F8, F9, F14. `cache._gen` becomes module-private; `set_device` (still in `legacy`) calls `cache.invalidate_all()`. `save()`'s sequence is `atomic_write`, `bump()`, `on_save` hooks (order unchanged). `lib_rename` still remaps playlists, end actions, xfades, trims, triggers and caches in the same order.
- **Stays:** `transport` and above, `boot`.
- **Verification:** 1.2; `tests/api/test_library.py`, `test_playlists.py`, `test_trim_xfade.py`, `test_trim_fade.py`, `test_triggers.py`; manual: rename a track that has a trim, a crossfade time, an end action and a trigger point, then move it to another playlist, and check all four follow; delete a track that is cued; upload during playback; warm-up still decodes the next tracks (watch the cache figure in the header).
- **Rollback:** the P5 commit.
- **Risk: medium.** Many call sites of `save()`, `bump()`, `request_warm()`, and the cache dicts; the hooks must be registered.

### 3.8 P7: transport, tick, triggers engine, meters, preview

Detailed in section 5.
- **Rollback:** the P6 commit; the step is split into sub-commits (7a `clock`-free pure parts `Deck` and ducking maths; 7b `transport` entire; 7c `triggers_engine`; 7d `meters` + `preview`; 7e `tick`) so a bad sub-step can be reverted alone.
- **Risk: high.** The audio path.

### 3.9 P8: `stateout`, `commands`, `ui_assets`, `download`, `web/*`

- **Scope:** table 2.1. The route table stays in `app.main()` until P9; handlers move by topic. **The catch-all `web.get("/api/{tail:.*}", h_cmd)` must stay registered last** (it is the last entry of the route list today, `player.py:5449`). `h_set_settings` calls `stateout.rebuild_osc()` instead of rebinding `osc_out`. `h_dl_start`'s `_dl_task` stays inside `download`.
- **Verification:** 1.2 complete including `controls.csv`; `tests/api/test_osc.py` (OSC out content and OSC in commands), `test_meters_variables.py`, `test_pages_state.py`, `test_fuzz_commands.py`; a Companion check: point the real Companion module at the test instance and confirm variables and a button press (Companion 5.1.1 on the production machine; module unchanged); `/api/live` (SSE) stays connected for 60 s with the page open.
- **Rollback:** the P7 commit.
- **Risk: medium.** Large but mechanical; the web layer has no audio state of its own. The risks are a wrong route order, a handler whose `import` now needs a new module, and `stateout.push` being registered as `notify` too late (import order in `app`).

### 3.10 P9: `boot`, `app`, delete `legacy`

- **Scope:** `main()` into `app`, `load()`/`migrate_old` into `boot`, `cpl/legacy.py` deleted (must be empty by then), `player.py` calls `cpl.app.main()`. Docs: `CLAUDE.md` (Layout table, architecture paths, line counts, testing), `README.md` (folder layout, "replace `player.py`, `cpl/` and `static/`"), `tests/README.md`, `docs/AUDIT-split.md` pointer, `CHANGELOG`. Remove the helper duplicate of `_test_dev_dir`. **P9 cleanup list:** (a) the `shutil.rmtree(IMPORT_DIR, ignore_errors=True)` that wipes `_import/` runs as a side effect of importing `cpl.upload` (since P5/P6; before, at a line near the end of `player.py`): move it to an explicit start-up call in `boot` / `app` (same moment: before `main()` serves anything); (b) prune the by-name imports `legacy` no longer uses; (c) make the cache internals (`_env`, `_key`, `_loading`, `_cache_lock`, `_tcache`) private to `cache` behind small functions, or document the exceptions.
- **Verification:** cold start on a clean folder and on a folder with existing `state.json`, `playlists.json`, `resume.json`; `systemctl restart companionplayer` on the production machine at a quiet time (section 6); `run-player.bat` on Windows; the whole of 1.2; soak of at least the same length as the rc2 soak (it is the same product, and a soak is the only test of leaks and slow drift).
- **Rollback:** the P8 commit.
- **Risk: low.** If P1-P8 are green. The risk that remains is deployment (partial copy), covered by the launcher check.

---

## 4. P4 in detail: the state module

### 4.1 Every reassigned module-level name

All 18 names that the code rebinds with `global` (24 `global` statements, 47 write sites). "Thread" = what runs the writer. **Everything below runs on the single asyncio event-loop thread** (aiohttp handlers, the OSC datagram handler, the `ticker` task, background tasks started with `spawn`, `main()` start-up, and the `SIGTERM` handler) **except `_dur_worker`, which is a real `threading.Thread`**, and the executor jobs (`run_in_executor`: `compute_env`, `duck_key`, `cut_sound`, `lufs_from_pcm`, `ff_check`, `_scipy_ok`, `find_duplicate`, file writes), which touch none of these names. The `--preview` worker is a separate process with its own state and is out of scope. Under pytest/unittest the same functions are called directly from the test's loop (`tests/test_triggers.py` calls `tick()` by hand).

"Readers" counts functions that load the name (from the `ast` pass). Destination: **S** = becomes `S.<name>` in `cpl/state.py` (cross-module); **local** = stays a plain `global` inside the one module that owns all its readers and writers.

| # | Name (defined) | Writers (function:line) | Readers | Thread of writers | Destination |
|---|---|---|---|---|---|
| 1 | `live_deck` (503) | `stop_all`:2091, `_start`:2647, `tick`:3177, 3179, 3183 | 15: `_live_restore, _live_snapshot, _start, _start_when_ready, _trig_fire_due, h_del_list, h_state, is_fading_out, is_paused, save_resume, seek_live, snapshot, tick, toggle, trig_deck` | loop (handlers, OSC, tick, tasks) | **S** |
| 2 | `pending` (1333) | `_live_restore`:1822, `stop_all`:2087, `play`:2117, 2123, `_play_on_top`:2297, 2303, `_start_when_ready`:2317, 2322, `fade_out`:2663, `try_resume`:2838 | 8: `_start_when_ready, fmt_kick, info_response, lib_rename, move_playlist_to, save_resume, snapshot, tick` | loop | **S** |
| 3 | `_pending_n` (1334) | `_live_restore`:1821, `play`:2122, `_play_on_top`:2302, `try_resume`:2837 (all `+= 1`) | the same 4 writers | loop | **S** (as `pending_n`) |
| 4 | `cue_cleared` (501) | `command`:3552, 3584, 3586, 3589, 3592, 3595, 3712 | 2: `command, snapshot` | loop | **S** |
| 5 | `rev` (504) | `bump`:511 | 1: `h_state` | loop (`bump` is called from `save()`, from handlers and from load) | **S** (`bump` itself lives in `state`) |
| 6 | `known` (505) | `lib_rename`:1133, `load`:1698, 1702 | 2: `lib_rename, load` | loop | **S** |
| 7 | `last_scan` (506) | `rescan_library`:1193, `load`:1718 | 2: `h_scan, load` | loop | **S** |
| 8 | `playlists` (495) | `load`:1697, 1701 | 47 functions | loop, start-up only | **S container, never rebound**: `load` does `playlists[:] = ...` (4.2) |
| 9 | `LAST_LOAD_ERR` (3401) | `_start_when_ready`:2315, 2323 | 1: `health` | loop | **S** |
| 10 | `MONITOR` (3346) | `monitor_set`:3352 | 7: `Preview._spawn, Preview.info, command, monitor_set, monitor_sync, snapshot, update_meters` | loop | **S** |
| 11 | `_boot_done` (3402) | `main`:5476 | 1: `health` | loop (start-up) | **S** (as `boot_done`) |
| 12 | `osc_out` (3391) | `h_set_settings`:4493 | 1: `push` | loop | local to `stateout` (`rebuild_osc()`) |
| 13 | `_gen` (1332) | `set_device`:1834 | 1: `_load` | loop | local to `cache` (`invalidate_all()`) |
| 14 | `_list_keys` (3471) | `push`:3498 | 1: `push` | loop | local to `stateout` |
| 15 | `_ui_cache` (3831) | `ui_page`:3840 | 1: `ui_page` | loop | local to `ui_assets` |
| 16 | `_dl_task` (5144) | `h_dl_start`:5273 | 2: `h_dl_start, h_dl_clear` | loop | local to `download` |
| 17 | `_dur_busy` (3934) | `_dur_worker`:3995 (**worker thread**), `durations`:4002 (loop) | 2 + `health` | thread + loop | local to `durations` (`status()`) |
| 18 | `_dur_booted` (3935) | `_dur_worker`:3996 (**worker thread**) | 1: `health` | thread | local to `durations` (`status()`) |

So P4 converts **11 names** (rows 1-11), not 18; rows 12-18 need no `S` because after their module moves every reader and writer is inside it. Until their module moves they stay as `global` in `legacy.py` and the gate does not cover them.

Two oddities the rewrite must handle: `try_resume` has its `global pending, _pending_n` statement in the middle of the function (2833), and `_start_when_ready` has a second `global LAST_LOAD_ERR` in its body (2314). Both are legal today; the rewrite removes them.

### 4.2 Design

`cpl/state.py` is a plain module (not a class instance), imported everywhere as `from cpl import state as S`. It holds:

- **Rebindable scalars** (rows 1-7, 9-11): `S.live_deck`, `S.pending`, `S.pending_n`, `S.cue_cleared`, `S.rev`, `S.known`, `S.last_scan`, `S.LAST_LOAD_ERR`, `S.MONITOR`, `S.boot_done`. Always read and written as `S.name`; never `from cpl.state import name`.
- **Stable containers** (never rebound, mutated in place): `playlists`, `FOLDER_COLORS`, `FOLDER_ICONS`, `LIBDIRS`, `library`, `focus`, `decks`, `ISSUES`, `DEV_MISSING`, `DURS`. These may be imported by name for readability **only because identity is guaranteed**: the one place that rebinds a container (row 8) is changed in a preparatory commit to `playlists[:] = migrate_old(data)` / `playlists[:] = data.get("playlists", [])`. A test `tests/test_state_identity.py` records `id()` of every container at import and asserts it is unchanged after `load()`, `stop_all()`, `set_device()` and a rescan; the gate forbids any assignment to these names outside `state.py`.
- `bump()` (it owns `rev`), and the **three hook lists**: `on_change` (run by `bump`), `on_save` (run by `save` after `bump`), `notify` (a callable, default no-op). Registration is done by the module that owns the handler, at import (`warm`, `loudness`, `stateout`); `app` imports them all.

Why a module and not a `Player` object (the audit's approach 2): tests already patch `P.name`, so attribute access on a module is the same shape; no object has to be threaded through 600 call sites.

Naming: names lose the leading underscore on `S` (`pending_n`, `boot_done`) because they are public in that module; `S.name` is the only way to reach them.

### 4.3 Threading, locking and visibility: what the move changes and what it does not

**Locks today.** The only `threading.Lock` in the player process is `_cache_lock` (cache.py after the move): it guards `_cache`/`_tcache` in `cached`, `cache_put`, `cache_bytes`, `cache_drop`, `trimmed_*`, `mem_info`, `lib_rename` (1134, 1148), `_warm_trims` (1594) and `set_device` (1836). `_wave_lock` and `_ff_sem` are asyncio primitives created lazily inside the loop. **None of the 18 names above is protected by any lock**: they are safe because every access runs on the event-loop thread and the loop is cooperative (a sync function runs to completion). The two exceptions are the `_dur_*` flags (a bare bool assigned by one thread and read by the loop; atomic under the GIL, and they remain exactly that after the move).

**What the move does not change.** A split adds no `await`, no thread and no lock, and (verified by the move verifier) does not reorder statements. A `global x; x = v` and `S.x = v` are each one store into a module `__dict__`; both are atomic under the GIL and become visible to every other reader at once. A read-modify-write such as `_pending_n += 1` is non-atomic in both forms, and equally safe because no `await` or thread switch happens inside it.

**Where an attribute assignment differs from a module global (the traps):**

| Trap | Why it matters here | Handling |
|---|---|---|
| `global` statements | A function that assigns a module global needs `global x`; `S.x = v` needs nothing. **Forgetting to convert a write silently creates a local** (the exact bug the audit feared); forgetting to convert a read raises `NameError` only if the old module-level name has been deleted. | The old definition is deleted in the same commit, so a missed read fails loudly; the gate finds missed writes statically (4.5). |
| `from cpl.state import live_deck` | Copies the binding at import: stale forever. | Gate forbids any `from ... import <S scalar>` and any `from cpl.state import` of a scalar; containers are allowed (identity test). |
| Closures | `late()` in `duck_arm`, `go()` in `_trig_load`, `lambda: (save_resume(True), os._exit(0))` in `main`, `done` in `ensure_loaded`. They look names up at call time. | No change: attribute lookup is also call-time. Nothing captures a state name as a default argument: an `ast` scan of all `def`s found one non-constant default (`done(f, p=path)`, line 1526, a local, not state). |
| Default arguments evaluated at import | would freeze a value | none exist (above). |
| Import-time side effects | `config` reads `config.json`; `osc_out = SimpleUDPClient(CFG[...])` and `preview = Preview()` run at import; `_missing` can `sys.exit` | `config` is imported before anything reads `CFG`; `stateout` imports `config`. `Preview.__init__` reads nothing from `CFG`. The folder check moves to the launcher. |
| Aliases to a state object across an await or a call | e.g. `d = live_deck; ... auto_advance(...)` then using `d` | unchanged by the move: the same aliasing exists today. `tick()` order (4.4 / 5.2) is preserved. |
| Speed | `S.x` is a module-attribute load, slightly slower than a global load | negligible: a tick touches `S.*` a few dozen times per 50 ms. |
| Tests that set `P.name = ...` | would now set an attribute on a different object | section 4.4. |

### 4.4 Test patch points and the clock seam

Only `tests/test_triggers.py` imports the application in-process (the suite under `tests/api/` and the Playwright scripts are black-box over HTTP). It patches:

| Today | After | Notes |
|---|---|---|
| `P.time = FakeTime()` | `clock.install(fake)` | 5.3. `FakeTime` already forwards unknown attributes to the real `time` (`sleep` etc.). |
| `P.request_loudness = lambda: None` | `loudness.request_loudness = ...` **and** because `save()` reaches it only through `S.on_save`, the test clears/replaces the hook: `S.on_save[:] = []` | Patching the function object no longer works once it is registered in a list: the test must patch the list, not the name. |
| `P.request_warm = spy_warm` (it also calls the real one) | replace the entry in `S.on_change`, **and** patch `warm.request_warm` for direct callers (`play_playlist`, `auto_advance`, `commands`) | Two patch points, because the same function is now reachable two ways. |
| `P._warm_loop = idle` | `warm._warm_loop = idle` | same module as `request_warm`, so a name patch works. |
| `P._play_on_top = spy_top` | `transport._play_on_top = spy_top` | `triggers_engine._trig_fire_due` must call it as `transport._play_on_top(...)` (attribute lookup), **not** `from cpl.transport import _play_on_top` (that copy would bypass the spy and the fake-clock test would still pass while testing nothing). |
| `P.DURS[...]`, `P.playlists[:] = ...` | `S.DURS`, `S.playlists` | containers: in-place mutation, as before. |
| `P.live_deck`, `P.TRIG` etc. read in assertions | `S.live_deck`, `triggers_data.TRIG` | |

**Convention for the whole code base:** any function that a test (or a future test) may patch is called as `module.func(...)`, never imported by name. The gate (4.5) bans `from cpl.<mod> import <function>` for the patched list `request_warm, request_loudness, _warm_loop, _play_on_top, push`, and a test asserts that the spies were actually called (the existing test already asserts `warm_calls`/`fires`, which would be empty if the patch were bypassed; keep those assertions).

Because each test needs fresh state, `load_app()` purges `sys.modules["cpl*"]` (1.3). Without that, the second test would see the first test's `S.decks`.

### 4.5 Mechanical rewrite and the gates

**Rewrite script** `tests/tools/state_rewrite.py` (to be written in P4, not now): uses `symtable` to find, per function, every name that resolves to the module scope and is in the S-set; rewrites each occurrence in place (using `ast` line/column offsets, no regex over source) to `S.<new name>`; deletes the corresponding names from `global` statements and deletes empty `global` lines; leaves local variables of the same spelling alone (`focus`, `decks`, `library`, `pending` are common local names, which is why a regex is not good enough); prints a unified diff in dry-run mode and a summary (names, sites). It is run once per group (4.6), the output is reviewed as a diff, and the move verifier (3.4) then proves the result equals the original modulo the rewrite.

**Gates** (a pytest file, `tests/test_no_bare_state.py`, run in `tests/run.py` and standalone, using `ast` + `symtable`, no new dependency):
1. No `global` statement anywhere names an S-set name.
2. No bare `Name` (load, store, del, augassign) resolving to module scope has an S-set name, outside `state.py`.
3. No `from cpl.state import <scalar>`, and no `import cpl.state` bound to any name other than `S`.
4. No assignment to a container name outside `state.py`; `S.<scalar> = ...` appears only in the functions of the writer table of 4.1 (the table is data in the test; a new writer must be added to it on purpose).
5. No `import time` / `from time import` outside `clock.py` (except `time_ns`), and no `from cpl.clock import`.
6. No `from cpl.<mod> import <patched function>` for the patch list in 4.4.
7. No function-local `import cpl...` (all imports at module top, so the first Play never triggers a disk read; 5.2).
8. After `import cpl.app`, `S.on_change`, `S.on_save` are non-empty and `S.notify` is not the default no-op.
9. Import graph: the module-to-module imports found by `ast` equal an allow-list file (the table of 2.1) and contain no cycle.

### 4.6 Order of commits (suite green after each)

Preconditions: P1-P3 done (clock seam in, `load_app` in, move verifier in).

1. **State identity prep:** `playlists[:] =` in `load` (two sites, rows 8) plus `tests/test_state_identity.py`. No other change. (One tiny behavioural difference to note and test: the list object stays the same, its elements are the same dicts.)
2. **Create `cpl/state.py`** with the stable containers and `bump` only; `legacy.py` imports the containers by name and calls `S.bump()` (`rev` moves with it: row 5). Gate items 1-4 enabled for the names moved so far. Suite.
3. **Group A, single-writer scalars:** `cue_cleared`, `known`, `last_scan`, `boot_done`, `LAST_LOAD_ERR`, `MONITOR`. Rewrite script, move verifier, suite, `test_triggers`.
4. **Group B, the pending pair:** `pending` and `pending_n` together (7 functions write them, and `_start_when_ready`'s token check reads both). Suite, `test_triggers`, and the API tests for "stop while a track is still loading" and "last command wins".
5. **Group C, `live_deck`:** last, because it is the most widely read. Suite, `test_triggers`, then the manual run (section 6, check M1).
6. **Hooks:** (a) `on_change` for `bump` -> `request_warm` (F2); (b) `on_save` for `request_loudness` (F3); (c) `notify` for the five `push()` sites below `stateout` (F6). Each is its own commit with gate item 8.
7. **Turn on the full gate** and mark the 7 module-private names in a comment list "to localise in P5/P6/P8".

Each commit: `python tests/run.py` (full), `python tests/test_triggers.py`, golden hashes.

---

## 5. P7 in detail: transport and tick

### 5.1 What is involved

All of this runs **on the event-loop thread**; there is no lock. Timing comes from `time.monotonic()` (wall clock), not from the mixer: a `Deck`'s position is `base + (now - started)`, and fades are `now - t0` against a length.

| Function | Where | Called from (thread) | Reads / writes |
|---|---|---|---|
| `Deck` (init, `elapsed`, `fpos`, `remaining`, `level`, `set_vol`, `apply`, `start_fade`, `pause`, `resume`, `stop`, `update`) | 1874-2019 | loop (tick drives `update`) | `time.monotonic()` x14; reads `CFG["live_volume"]`, `_env`, `METER_WIN`, `end_of/is_loop`; writes pygame channel volume |
| `play` | 2107 | handlers, `command`, OSC, `auto_advance`, `_live_restore` (loop) | `S.pending`, `S.pending_n`, `S.focus`; calls `_start` or `spawn(_start_when_ready)` |
| `_start_when_ready` | 2308 | task (loop) | `ensure_loaded`, `S.pending`, `LAST_LOAD_ERR`, `S.live_deck`, `push` |
| `_start` | 2590 | `play`, `_play_on_top`, `_start_when_ready`, `_live_restore` | decks, `S.live_deck`, `focus`, `stop_all`, `resume_all`, `cut_sound`, `trimmed_cached`, `norm_gain`, `duck_arm`; `play_snd.play()` then `Deck(...)` (so `Deck.started` is taken right after the channel starts) |
| `stop_all`, `fade_out`, `pause_all`, `resume_all`, `toggle`, `play_default` | 2085-2104, 2655-2678 | handlers/commands/tick | decks, `S.pending`, `S.live_deck`, `DUCK` reset |
| crossfade / go / take | `play(..., xfade_ms)` + `_start` (`start_fade(0, ms, kill=True)` on old decks, new deck `set_vol(0)` + `start_fade(1.0, ms)`); the Go button is `command()` (`/take`, `/xfade`, `go_transition`) | loop | equal-power curves in `Deck.update` |
| `play_on_top`, `_play_on_top`, `duck_arm`, `_duck_loop`, `set_duck` | 2173-2305 | handlers; `_trig_fire_due` (via tick) | `DUCK` dict, `_key`, `CFG["duck_*"]`; `_duck_loop` is its own asyncio task, `await asyncio.sleep(0.01)` per step, `time.monotonic()` for `dt` |
| `auto_advance`, `next_in_order`, `play_playlist` | 2754, 2717, 2738 | `tick` | playlists, `_bag` (random), `request_warm`, `push` |
| `seek_live` | 2048 | handlers | rebuilds the deck's sound with `cut_sound` **on the event loop** (pre-existing), `time.monotonic()` |
| `set_device`, `_live_snapshot`, `_live_restore` | 1791-1861 | handler | blocks the loop while `pygame.mixer.quit()/init` runs (pre-existing) |
| `save_resume`, `try_resume` | 2779, 2814 | `tick` (every tick, throttled by `_rs`), SIGTERM handler, `main` | `RESUME` file, `time.time()` for the saved stamp |
| `tick` | 3155 | `ticker` task (loop) | order below |
| `ticker` | 5334 | `main` | `tick()`, then `push()` (full resend every 5 s), then `await asyncio.sleep(0.05)`; exceptions are swallowed with a throttled traceback |

**`tick()` order, a contract the move must keep:** (1) `d.update()` for every deck, remove finished ones and note `ended` / `tops_done` / `under_ended`; (2) Play-on-Top hand-back: pick the new `live_deck` from `under`/`bg`; (3) `if live_deck not in decks: live_deck = None`; (4) `auto_advance(ended)` unless a load is `pending`; (5) `triggers_tick()` inside its own `try/except`; (6) `monitor_sync()`; (7) `update_meters()`; (8) `save_resume()`. Then `push()`; then sleep. The period is 50 ms plus the tick's own run time.

### 5.2 Timing and ordering assumptions, and what could change them

- `Deck.started` is set in `Deck.__init__`, right after `play_snd.play()` returns inside `_start`. Any extra work between those two lines delays `started` relative to the sound, shifting every later position and trigger time by that amount. **A move must not insert anything there** (no lazy import, no logging, no hook call). The move verifier catches an inserted statement.
- `_start` must keep `top = bool(top and decks)`, the stop/crossfade branch and the `Deck` construction in the same order, because `stop_all()` rebinds `live_deck` and resets `DUCK` before the new deck exists.
- Lazy imports: a function-local `import` runs file I/O the first time it is hit, on the loop, during a show. Today there is one (`import traceback` in the exception path of `ticker`). The split must not add any; all `cpl` modules are imported at start-up (gate item 7).
- `.pyc`: the service user must be able to write `cpl/__pycache__` or the production machine compiles all modules at every start (a few hundred ms, only at start-up, never during play). Not a correctness issue; note it in the deploy checklist.
- Hook calls (`S.notify()` instead of `push()`) add one function call at the same point. If the hook were not registered the push is skipped; `ticker` pushes changed values every 50 ms anyway, so the result is a delay of at most one tick, not a loss. Gate item 8 makes this impossible to ship.
- `Deck.update()` calls `clock.monotonic()` several times per deck per tick; with the seam this is one extra Python call each, a fraction of a microsecond.
- Event ordering between tasks (`_duck_loop` at 10 ms, `ticker` at 50 ms, `_start_when_ready` tasks) is decided by the asyncio scheduler; a split changes neither the tasks nor their sleeps. `_duck_loop` is started with `asyncio.ensure_future` inside `duck_arm` and must stay that way (not `spawn`, because `DUCK["task"]` holds the reference).
- Blocking work on the loop that already exists (`set_device`, `seek_live` -> `cut_sound`, `_live_restore`) stays exactly as it is; moving it must not "improve" it in the same step.

### 5.3 The clock seam

```python
# cpl/clock.py
import time as _time
_src = _time
def monotonic(): return _src.monotonic()
def time():      return _src.time()
def sleep(s):    return _src.sleep(s)
def install(src):          # tests only; None restores the real clock
    global _src
    _src = src or _time
```

Introduced in **P3, before any code moves**, in its own commit inside the single file: the 44 uses become `clock.monotonic()` / `clock.time()` / `clock.sleep()`; `time.time_ns()` (temp file names, lines 5090, 5116) stays real. `tests/test_triggers.py` changes from `P.time = fake` to `clock.install(fake)`. Behaviour is identical: it is the same calls, one level of indirection. The rule "always `clock.monotonic()`, never `from cpl.clock import monotonic`" is in the gate (a by-name import would copy the function and the fake would be ignored). `asyncio.sleep` is not part of the seam (the fake does not cover it today either; the tests call `tick()` by hand).

### 5.4 Coverage today and gaps (listed, not written)

Existing coverage of the audio path:

| Area | Tests |
|---|---|
| Commands, play, take, cut, crossfade by command, pause, fade out, toggle, seek, cue navigation, Play on Top, stop while loading, rapid-fire | `tests/api/test_transport.py` (20) |
| Ducking settings and the duck leak cases (stop-all while ducked, fade-out while ducked, release time) | `tests/api/test_ducking.py` (13) |
| Play modes, end actions, volume modes | `tests/api/test_volume_modes.py` (18), `test_trim_xfade.py` (14), `test_trim_fade.py` (8) |
| Preview and mirror worker | `tests/api/test_preview.py` (9) |
| Trigger points, loop/once, seek, pause, trims, Play on Top interplay, **with a fake clock and direct `tick()`** | `tests/test_triggers.py` (38) |
| Device list, selection, saved state (dummy driver, mocked device list) | `tests/test_devices.py` (24 checks), `test_devices_ui.py`, `test_live_output.py` |
| Restart keeps playlists and settings; hard kill keeps JSON files | `tests/api/test_lifecycle.py` (4) |

Gaps that matter for P7 (to be written **before** 7a, by you or by a later task; Decision 5):

1. **Resume on start / `save_resume` / `try_resume`:** the harness config sets `resume_on_start` off (`test_lifecycle.py:66` says so), so the resume path has no automated test at all. Needs a test with it on: play, wait for `resume.json`, kill, restart, assert the same track at about the saved position and the paused flag.
2. **Fade and crossfade shape in time:** no test checks `Deck.update` volumes at known times. With the fake clock: equal-power values at 25/50/75 % of a crossfade; the kill-on-fade-end removal; the Out-point fade (`end_fade_ms`) starting at the right moment; pause during a fade (`resume` shifts `t0`).
3. **Natural end and advance:** `auto_advance` for each play mode and for the `stop` end action, with `pending` set (it must not advance), and for a Play-on-Top hand-back (`under_ended`).
4. **Device change carry-over:** `set_device` while playing: position continuity, paused flag, volume, trigger state (`trig_carry`), the "new device runs at another rate -> decode again" branch (`_live_restore` pending path), and the failure fallback to the old device. The Box tests use a mocked device list and the dummy driver; I did not find an assertion on position continuity (not exhaustively checked).
5. **`_start_when_ready` races:** stale token, track list edited while loading (the re-find branch), load error (`LAST_LOAD_ERR`), file removed.
6. **Ducking maths golden vectors:** `duck_key`/`duck_curve` on a synthetic signal with fixed settings (hold on/off), so the P3 signature change (F1) and any later move are checked numerically; the `_duck_loop` attack/release behaviour with the fake clock.
7. **`tick()` ordering contract:** one test that builds a state with a finished live deck, a finished top deck and a pending load, and asserts what `tick()` does and does not do, in order.
8. **Second Play on Top replacing the first** (`superseded`, `old_top[0].bg` reuse) and `stop_all` during it.
9. **A tick-duration measurement:** a test or a log line that records `tick()` run time (min/avg/max) so a slow-down is visible (Decision 6).
10. **Audio content:** nothing hears the output. The dummy driver cannot verify a crossfade, a loop point or a ducking depth. An audio-capture test (render to a file with `SDL_AUDIODRIVER=disk`, analyse with numpy) would close the largest gap; it is listed as "not written yet" in `CLAUDE.md`.

### 5.5 Sub-steps

- **7a** `Deck` plus the pure ducking maths stay in `legacy` until 7b; this sub-step only moves `triggers_data.trig_deck/trigger_targets` and `trig_carry_of` (F4) and runs the suite. Rollback: P6 commit.
- **7b** `transport` complete (one commit; the move verifier on every function). Suite, `test_triggers`, then check M1-M4 (section 6).
- **7c** `triggers_engine`: `_trig_fire_due` calls `transport._play_on_top`. `test_triggers` is the proof (38 tests, fake clock).
- **7d** `meters`, `preview`: `update_meters` reads `S.MONITOR` and `preview`. `test_preview`, meters tests, then M5.
- **7e** `tick`/`ticker`. Add the tick-duration log (Decision 6) first as its own commit and record a baseline from `main` for comparison.

---

## 6. Risks and how we would notice a regression

### 6.1 Risks, ranked

| # | Risk | How it would show | Mitigation / detection |
|---|---|---|---|
| 1 | **A state name converted wrongly in P4** (a write becomes a local, a read becomes a stale copy) | A deck that is "playing" but not `live_deck`; `pending` never cleared (a track "loading" forever, or auto-advance blocked); Go cue stuck; meters/Live card show the wrong track. May appear only on one path (fade, trigger, device change). | Scripted rewrite, static gate, deleted old names (loud `NameError`), move verifier, `test_triggers`, manual M1-M3 |
| 2 | **Tests that patch `P.*` keep passing without testing** (the patch hits a different object after the split) | Green suite, and the next regression is invisible | patch convention + gate item 6 + the spy-called assertions; `load_app` purge |
| 3 | **Packaging and start-up** (`-I`, `__file__` paths, partial or stale deploy, helper imports too much) | Player will not start; decode children fail; every decode slower and heavier; wrong `cpl/` with a new `player.py` | P1 alone with the manual checks; launcher folder check; `-X importtime` on helpers; deploy `rsync --delete` of `cpl/` and `static/`; `APP_VERSION` printed at start-up |
| 4 | **Hooks not registered** (`on_change`, `on_save`, `notify`) | No warm-up after edits (first cue after an edit is slow: audible as a late start), no loudness measurement, Companion variables update a tick late | gate item 8; the existing warm-up tests; header cache figure |
| 5 | **Timing shift in `_start`/`Deck`** from a statement inserted or moved | Trigger points fire a few ms early/late; end fades start at the wrong time | move verifier (no statement added), `test_triggers` (fake clock, exact times) |
| 6 | **The audio-quality failures the suite cannot hear:** ducking depth/attack/release, crossfade shape, loop point (seamless `loops=-1`), stop-all during ducking, device change gap | A click, a dip that is too deep, a missed loop, a gap or a restart of the track on device change | not covered by automation: M1-M5 below; the numeric ducking vectors (gap 6) |
| 7 | **Cycle or import-order regression later** | `ImportError`, or a hook registered after first use | gate item 9 |
| 8 | **Documentation drift:** `CLAUDE.md`/`README.md` describe one file | A later session edits the wrong place | update the docs in the step that moves things (at least the layout table in P1 and per-step path notes), full pass in P9 |
| 9 | **Merge cost** of a hotfix on `main` against moved code | conflicts | freeze features on `main` while a step is open; cherry-pick small fixes by hand (Decision 8) |

### 6.2 Manual listening checks on the production machine (after each risky step)

Do these with real hardware (Dante USB adapter), at a time when no show depends on the box. About 10 minutes each time. Use two music tracks (A, B) of at least 2 minutes and one short voice-over file (V).

- **M1 (after P4 group C and P7b): cue, cut, fade.** Play A; Cut to B (`/take`); play A again with a 3 s crossfade to B: listen for clicks at the start of B, no dip in loudness in the middle; fade out over 5 s; stop. In the web page the Live card must always name the track you hear.
- **M2 (after P7b): loop and once.** Set A to Loop, a short 5 s trimmed region: no gap or click at the loop point for 10 passes. Set B to Once: it plays twice then stops.
- **M3 (after P7b): Play on Top and ducking.** Play A, trigger V on top: A goes down while V speaks, comes back over the release time, no step in the level when V ends. Trigger V twice quickly (second replaces first). During V press Stop All: silence, and the next Play on Top starts from clean levels (no leftover dip).
- **M4 (after P7b): device change.** While A plays, change the output (and back): the track carries on from the same point after a short gap; paused state is kept; with a second device that has another rate, check the pending path.
- **M5 (after P7d): Solo and preview.** Solo on, headphones hear the live track; preview volume slider; mirror on.
- **M6 (after P7e and P9): restart.** With `resume_on_start` on: play A for 30 s, `systemctl restart companionplayer`, it should resume near the same point (and not resume after a deliberate Stop). Companion reconnects without a button press.
- **M7 (after P9): soak.** Leave it running with a playlist set to loop for the length of the rc2 soak; compare the RAM figure and CPU with the rc2 numbers.

During every check have `journalctl -u companionplayer -f` open: any traceback or "trigger points: error in the tick" line is a failure.

---

## 7. Decisions I need from you

1. **Shared-state access.** Recommend: module `cpl/state.py`, scalars as `S.x` only, containers imported by name with an identity test and a gate (4.2). Reason: closest to how tests patch today, no object to pass around. Alternative (a `Player` object) is more invasive for no gain at this size.
2. **The clock.** Recommend: `cpl/clock.py` with `install()` as in 5.3, introduced in P3 before any move. Reason: it is the only way to keep the fake-clock trigger tests working after each module gets its own `time`, and it can be proven behaviour-neutral on its own.
3. **Hooks versus direct calls** for the three upward edges. Recommend: plain callable lists/attribute in `state` (`on_change`, `on_save`, `notify`) registered at import, with a registration test. Reason: five call sites for `push`, one each for the other two; far less disturbance than re-architecting `warm`/`loudness`/`stateout`.
4. **Granularity.** Recommend: about 30 modules as in 2.1, with `transport` kept whole (640 lines: `Deck`, play/stop/crossfade, ducking, Play on Top, device switch, resume). Do not split ducking out of it until after P9. Reason: they call each other in both directions; separating them would need more hooks, and this is the code you least want to restructure.
5. **Tests before P7.** Recommend: write gaps 1, 2, 3, 6, 7 of 5.4 (resume, fade/crossfade shape, advance, ducking vectors, tick order) **before** 7b, on `main`'s code, as a separate small piece of work; they run on the current single file and then protect the move. Gap 4 (device change) and 10 (audio capture) are valuable but bigger; your call on whether to schedule them. Reason: P7 is the one step where "the suite is green" says little, and these tests are cheap with the fake clock.
6. **A tick-duration log.** Recommend: add one low-overhead measurement (running min/avg/max of `tick()` in `/api/state` `health` or the debug log) in P7e before moving `tick`, baseline recorded from the rc2 code. Reason: CLAUDE.md says audio glitches are the failure that matters most; this makes a slowdown visible. It adds a small field, so it should be a separate, reviewed commit and it changes the golden `/api/state` hash if it is exposed there (keep it log-only to avoid that).
7. **Local tags.** Recommend: create lightweight local tags `split-P1` ... `split-P9` after each green step (never pushed). Reason: easy rollback targets and easy `git diff split-P4 split-P5`. This task created none; say yes and the next session will.
8. **Policy for fixes on `main` during the split.** Recommend: only cherry-pick fixes that are needed for the release; do them as a small commit on `main` first, then `git cherry-pick` onto `split` and re-run the suite, and never merge `main` into `split` mid-step. Reason: a merge through moved code produces conflicts that are hard to resolve correctly. The alternative (rebasing `split` onto `main`) rewrites hashes that the rollback points depend on.
9. **When to start.** Recommend: not until rc2 has passed its soak and is tagged as the release; do P1-P3 first (low audio risk) and decide on P4+ after a pause. Reason: P1 changes how the process starts, and you want the split's first deployment on a quiet day, not on top of an open soak.
10. **Where to stop.** Recommend: commit to P1-P6 now, and treat P7-P9 as a second decision once P1-P6 are proven and gap tests exist. Reason: P1-P6 take about 2,300 lines out with little audio risk; the cost/benefit changes at P7 (section 3.8 and the summary).
11. **Deployment shape.** Recommend: directory copy (`player.py`, `cpl/`, `static/`) with the launcher check, plus a `make-release.py` that zips the three items with the version in the name. Reason: no build step, no second source tree, nothing in `systemd` or `run-player.bat` changes. A single-file build or `.pyz` can be added later if wanted.
12. **`controls.csv` locations.** Recommend: accept that every row's `where` changes (P1 and again at each move) and compare the other columns only. Reason: the file:line column cannot stay stable through a move; the information in the other columns is what the file is for.
13. **Version.** Recommend: no `APP_VERSION` change during the split (the Companion module compares major.minor and the golden `/api/state` contains it); bump once at the final merge, together with `CHANGELOG.md`. Reason: the split has no user-visible change.

---

## 7b. Decisions (answered)

Your answers to section 7, recorded 2026-11-03. The numbers match section 7; the recommendation text there is left as written.

| # | Answer | What it means for the plan |
|---|---|---|
| 1 | Yes | `cpl/state.py` as a module; scalars as `S.x`; containers by name with the identity test and the gate. |
| 2 | Yes | `cpl/clock.py` with `install()`, introduced in P3 before any move. |
| 3 | Yes | Hook lists `on_change`, `on_save` and `notify`, registered at import, with the registration test (gate item 8). |
| 4 | Keep `transport` whole; merge modules under about 60 lines into their single consumer when that removes a hook or a relocation without creating a cycle | Proposal in the table below. Sections 2.1 and 2.3 are **not** changed until you approve the table. |
| 5 | Yes: gaps 1, 2, 3, 6, 7 **plus gap 10** (audio capture with `SDL_AUDIODRIVER=disk`), as tests-only commits after v2.7.0 is tagged | They go in after the tag, touch only `tests/`, and come before P7b. Where they land (on `main` and cherry-picked into `split`, or directly on `split`) is not decided; see the note under the table. |
| 6 | Yes, log-only | The tick-duration measurement goes to the log, not to `/api/state`, so the golden hashes stay unchanged. |
| 7 | Yes | Lightweight local tags `split-P1` ... `split-P9` after each green step, never pushed. **None exist yet**; this task created none. |
| 8 | Yes | Fixes on `main` go in as a small commit on `main` first and are cherry-picked onto `split`; `main` is never merged into `split` mid-step. |
| 9 | Yes | No P1 until the rc2 soak has passed and the release is tagged. |
| 10 | P1-P6 first, then decide | P7-P9 are a separate go/no-go after P6 is proven (section 3.8 and the summary). |
| 11 | Directory copy | `player.py` + `cpl/` + `static/`, launcher check, optional `make-release.py` zip. |
| 12 | Yes | `controls.csv` comparisons ignore the `where` column. |
| 13 | Yes | `APP_VERSION` unchanged during the split; one bump at the final merge with `CHANGELOG.md`. |

### Decision 4: merge candidates

Rule applied: a module of about 60 lines or less is merged into its single consumer only if that removes a hook or a relocation from 2.3 and creates no cycle. Sizes are definition lines from 2.1. I re-read the import lists of 2.1 to find each module's consumers.

| Module (lines) | Consumers | Merge into | Removes | Cycle? | Verdict |
|---|---|---|---|---|---|
| `infostore` (45) | `loudness`, `fileinfo` (and `app` for `_info_load`) | `loudness` | **Relocation F5** and the extra module: `_loud_worker` then calls the store in its own module; `fileinfo` already imports `loudness`, so the only edge is `fileinfo` -> `loudness`, as today | none | **Merge.** `loudness` grows to about 193 lines; `fileinfo` imports its store from `loudness` |
| `persist` (18) | `playlists`, `library`, `loudness`, `triggers_data`, `preview`, `boot`, `commands`, `download`, `web/*` | `state` or `config` | nothing: `save()` still has to reach `request_loudness`, so hook F3 stays | none | Do not merge (many consumers, no hook or relocation removed) |
| `state` (about 60) | everything | n/a | n/a | n/a | Stays: it is the base of the graph |
| `clock` (about 15) | everything | n/a | n/a | n/a | Stays: it is the test seam |
| `devices` (47) | `transport`, `commands`, `web/output`, `app` | `transport` | nothing: F12 is already resolved by keeping `set_device` in `transport` | none | Do not merge (four consumers; `transport` must stay as it is) |
| `tick` (55) | `app` only | `app` | nothing | none | Do not merge (no hook or relocation involved; `tick` should stay separately readable) |
| `ui_assets` (38) | `web/pages`, `app` | `web/pages` | nothing | none | Do not merge |
| `meters` (60) | `stateout`, `tick`, `ui_assets`, `web/output` | n/a | F10 is ordering only | n/a | Do not merge |
| `durations` (62) | `stateout`, `web/*`, `app` | n/a | its `status()` accessor is not a hook | n/a | Do not merge |

Result: **one merge** (`infostore` into `loudness`). It removes relocation F5 and one module; the module count goes from about 30 to about 29, and no hook disappears, because all three hooks (F2, F3, F6) come from modules larger than 60 lines or from `state` itself. If you approve, sections 2.1, 2.2, 2.3 (F5) and the P5 step are updated in a follow-up edit.

Note on decision 5: I did not check that pygame's `disk` audio driver works on all three platforms (macOS, Linux, Windows) or where it writes its file (SDL reads `SDL_DISKAUDIOFILE`); that is the first thing to verify when the capture test is written.

### Testing a split build on the production machine or Windows

The `split` branch is local. To test a split build on the production machine or on Windows (`the Windows install folder`), the branch (or a tag on it) has to be pushed to the private repo first, because those machines get the code from the repo. That is an outward-facing step and was not done: nothing has been pushed, and this plan does not push it. You told me that `deploy.sh` and `deploy.ps1` accept a branch name, so a test deploy would be `deploy.sh split` (or `deploy.ps1 split`), or the name of a tag. Those two scripts are not in this repository (`git ls-files` shows no deploy files), so I have not read them: check that they copy `cpl/` and `static/` as well as `player.py` and that they remove files that no longer exist, before the first split deploy (P1).

---

## 8. Effort estimates

Assumes Claude Code does the moves, the suite + golden hashes + the move verifier check them, and you do the production machine listening and approve each step. Hours are Claude Code working time including re-runs of the suite (a full `python tests/run.py` takes minutes, not seconds; I did not time it here). They are rough: +/-50 %.

| Step | Work | Claude Code | Your time |
|---|---|---:|---:|
| Prep | `load_app`, `gen_controls` multi-file, `verify_move.py`, gate scaffolding | 3-4 h | review 0.5 h |
| Gap tests before P7 (Decision 5: items 1, 2, 3, 6, 7) | new tests on the current single file | 4-6 h | review 0.5 h |
| P1 launcher | 1.5-2 h | | production machine/Windows start check 0.5 h |
| P2 helpers | 1-1.5 h | | 0.2 h |
| P3 leaves + clock | 2-3 h | | |
| P4 state | 3-4 h (rewrite script 1 h, six commits with full suite) | | production machine M1 0.3 h |
| P5 ffmpeg and file-fact modules | 2-3 h | | Linux ffmpeg check 0.3 h |
| P6 playlists, library, cache, warm, trigger data | 3-4 h | | 0.2 h |
| P7 transport, tick, triggers engine, meters, preview | 5-7 h (five sub-commits) | | production machine M1-M5 0.7 h |
| P8 stateout, commands, ui_assets, download, web | 3-4 h | | Companion check 0.3 h |
| P9 boot, app, delete `legacy`, docs | 2-3 h | | production machine M6 + soak setup 0.5 h |
| **Total** | **about 29-41 h** | | **about 3.5-4 h** plus the soak waiting time |

Dependencies that decide the calendar, not the hours: the rc2 soak, a quiet window on the production machine for each of M1-M7, and (Decision 5) the gap tests being written before P7.

## 9. Notes from the implementation of P4 (what differed from sections 3.5 and 4)

* **Reader lists in 4.1 are name-based and over-counted.** `pending` was listed with `fmt_kick` and `info_response` as readers; both only use a local variable / local function of that name. The `symtable` pass of `state_rewrite.py` counts real readers only (`pending`: 6 functions; `live_deck`: the 15 listed). Writers were exactly as in the table. The move verifier is not scope aware, so its map has `local_names_in` for those two functions.
* **Commit 2 (state module) kept a two-line `bump()` wrapper** (`S.bump()` then `request_warm()`) because `state` cannot import `warm` and the `on_change` hook only comes in commit 6a; 6a replaced the wrapper (`bump` is now `from cpl.state import bump`, and `S.on_change.append(request_warm)` follows the definition of `request_warm`).
* **F6 has 7 call sites, not 5**: `push()` is called 3 times in `_start_when_ready`, once each in `_loud_worker`, `set_norm`, `play_playlist` and `auto_advance` (5 functions). All 7 became `S.notify()`; the other `push` calls (commands, handlers, `ticker`, `main`) are above `stateout` and stay direct.
* **Tests that read `P.live_deck`** (engine tests, `test_triggers.py`) now read `self.S.live_deck`; `EngineCase.patch()` also replaces the entry of a patched function in its hook list (`HOOK_LISTS`).
* **Gate numbering:** `tests/test_no_bare_state.py` implements 1-4, 6 and a closing check "1b" (only the 7 module-private names, plus `clock._src`, may still be rebound with `global`); gate 8 is `tests/test_state_hooks.py`; 5, 7, 9, 10 are in `tests/test_gates.py`.
* **Edge case of the identity prep:** `playlists[:] = data.get("playlists", [])` raises immediately if `playlists.json` holds `"playlists": null` (the old code bound `None` and failed later). Not a valid file; not changed.

## 10. Notes from P5 + P6 + 7a (layers 2-6, 15 modules, local tags split-P56a, split-P56b, split-P6)

* **Order.** The plan's P5-before-P6 order does not work (the import table makes `ffmpeg`, `loudness` and `fileinfo` depend on `cache`, `persist` and `playlists`, and an extracted module may never import `cpl.legacy`). The modules were moved strictly in the layer order of table 2.1: `persist, cache, devices, durations, infostore` (stop 1, tag `split-P56a`), `ffmpeg, playlists, library, triggers_data, loudness, formats` (stop 2, `split-P56b`), `warm, fileinfo, upload, boot` (stop 3, `split-P6`). `tests/tools/move_defs.py --check` resolved the whole list in that order with no upward edge and no cycle before anything was moved.
* **Alias decision.** `state.playlists` (the list) and `cpl.playlists` (the module) share a name, as do `state.library` / `cpl.library` and the function `durations` / `cpl.durations`. The moved definitions are imported BY NAME (`from cpl.playlists import track`), which keeps every moved body identical to the original; where a module object is needed the aliases are `plm` (playlists), `libm` (library), `durm` (durations); other modules use their own name (`cache`, `loudness`, `warm`). No alias for `playlists`/`library` is needed so far.
* **Deviations from table 2.1.** (1) `devices` also imports `cpl.helpers.common` (`test_dev_dir`, shared with the helper processes since P2; the table assumed it lived in `config`). (2) `cache.rename_path(m)` takes the id-mapping function `m` that `lib_rename` builds (the table said `(old, new)`): the same statements moved, no copy of the mapping logic. (3) `cache.invalidate_all()` is exactly the five statements of `set_device` in the same order (`_gen += 1`, `_loading.clear()`, `_cache.clear()`, `_tcache.clear()` under `_cache_lock`). (4) `health()` reads `durm.status()` (both flags at once) before testing them, where it read the two module flags inside one `if`; the flags are plain bools written by one thread, as before. (5) The `shutil.rmtree(IMPORT_DIR)` that wipes `_import/` runs when `cpl.upload` is imported (the top of `legacy`), not at its old line near the end of the file; both are before `main()`. (6) Hook registrations moved with their functions (`S.on_save.append(request_loudness)` in `loudness`, `S.on_change.append(request_warm)` in `warm`); `legacy` imports both modules, so they register at import.
* **Module sizes (definition lines, plan in brackets).** persist 23 (18), cache 202 (171), devices 51 (47), durations 69 (62), infostore 49 (45), ffmpeg 214 (210), playlists 326 (323), library 211 (224), triggers_data 119 (115), loudness 153 (148), formats 90 (86), warm 77 (72), fileinfo 115 (111), upload 108 (103), boot 93 (90). The plan counted only `def`/`class` lines; the extra lines are blank/continuation lines inside definitions and the two new functions of `cache` and `status()` of `durations`. `cpl/legacy.py` is 2,740 lines.
* **Tests that moved with the code.** `test_triggers.py`, `harness/engine.py` (`MODULE_OF`, `HOOK_LISTS`), `test_state_hooks.py` and `test_state_identity.py` patch `loudness.*` / `warm.*` and the hook lists; `P.TRIG_MAX` is read from `triggers_data`.
* **Found while testing (not application changes).** The audio crossfade test failed 1 run in 10, also on `split-P4`: the disk driver renders at about 97 % of real time while the fade follows the wall clock, so the test now fits that time scale (residual 0.011-0.017, limit 0.06). `test_storage_formats_ffmpeg_shapes` fails when the player has no ffmpeg (`/api/formats?deep=1` answers 415); it fails the same on `split-P4`.

