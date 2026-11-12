# AUDIT: splitting player.py

> **Status (2026-11-03):** this audit is the starting point; the plan that was carried out is `docs/split-plan.md` (decisions, deviations, per-step notes). The split stopped at P6 and shipped as 2.7.1: `player.py` is now a 31-line launcher and the code is in `cpl/` (foundation + 15 modules + `legacy.py` for the part not split yet). Line numbers below are those of the audited single file and no longer apply.

Read-only audit. No project file was edited and the service was not touched. The only file written is this one.
Subject: `player.py`, 7,711 lines, 530 KB (CLAUDE.md says about 6,700; README and notes are out of date on this).
Line numbers are for the file as audited (modified Nov 3 09:37). They drift with every edit, so re-run the checks in section 4 step 0 before trusting them.

Method: section headers and `grep` for definitions, plus an `ast` pass (scratch script, not in the project) that assigned every top-level definition to a proposed module and counted cross-module references. The "back-edges" in section 3 come from that pass. The pass is approximate: it follows names, not dynamic access such as `globals()` or `getattr`.

**Headline numbers**

- About 5,260 lines are Python. About 2,450 lines (32%) are HTML/CSS/JS/help text held in four raw strings.
- There are 4 child-process entry points glued into the top of the file (`--probe`, `--decode`, `--dl`, `--preview`). They run before the normal imports (lines 17-332).
- There are 60+ module-level mutable names. 16 of them are *rebound* with `global`, which is what makes a split non-trivial.
- Every deployment and test file runs the single path `player.py`, and the tests copy only that one file (section 5).
- **The project is not a git repository.** The only history is `backups/` (31 files).

---

## 1. Map of the file by area

| Lines | Area | Lines in area |
|---|---|---:|
| 1-116 | Header; helper entry points `--probe` (17), `--decode` (29), `--dl` (47, yt-dlp child) | 116 |
| 118-142 | numpy import, `METER_WIN`, `compute_env` (used by both the main process and `--preview`) | 25 |
| 144-332 | `--preview` worker: its own mixer, JSON lines on stdin/stdout, solo-monitor channels 1-3 | 189 |
| 334-465 | Imports (pygame, aiohttp, python-osc), `BASE/MEDIA/LIB`, `CFG` defaults, `config.json` reader, `state.json` overlay, `warn_clean`, `PLAY_MODES` | 132 |
| 466-544 | State globals (`playlists, library, focus, decks, live_deck, rev ...`), `bump`, `atomic_write`, `log_once`, `spawn`, `body`, `save` | 79 |
| 545-717 | Playlist model: `pl_mode`, end actions (`end_of/set_end/is_loop`), per-track crossfade, trims (`trim_of/set_trim`) | 173 |
| 718-834 | Trigger points, data side (`TRIG`, `_trig_clean`, `set_triggers`) | 117 |
| 835-858 | `valid`, `track`, `fmt`, `fmt_bytes` | 24 |
| 859-906 | Storage limits (`parse_size`, `storage_info`) | 48 |
| 907-1135 | Library: scan, mkdir/rmdir, `lib_rename` (remaps playlists, trims, triggers, caches), duplicates, delete | 229 |
| 1136-1241 | Playlist editing: `add_to_playlist`, `remove_from_playlist`, `move_track` | 106 |
| 1242-1529 | Sound cache (`_cache`, `_tcache`, `_env`, `_key`, LRU), `mem_info`, `decode_in_child`, `_load`, `ensure_loaded`, warm-up (`_warm_loop`, `_warm_trims`) | 288 |
| 1530-1649 | `import_file`, `migrate_old`, `load()` | 120 |
| 1650-1782 | Output devices: `init_mixer`, `list_devices`, `set_device` (swaps mixer and restores decks), `save_state` | 133 |
| 1783-2034 | `Deck` class; `is_paused`, `set_live_volume`, `seek_live`, `stop_all`, `pause_all`, `play` | 252 |
| 2035-2243 | Ducking (`DUCK`, `duck_key`, `duck_curve`, `duck_arm`, `_duck_loop`, `set_duck`) and Play on Top (`play_on_top`, `_play_on_top`, `_start_when_ready`) | 209 |
| 2244-2493 | Loudness / level match (`LOUD`, `lufs_from_pcm`, `norm_gain`, `ff_loudness`, `_loud_worker`) | 250 |
| 2494-2750 | `_start`, `play_default`, `fade_out`, `toggle`, focus moves, shuffle bag, `auto_advance`, resume (`save_resume`, `try_resume`) | 257 |
| 2751-2824 | Meters: `METER_STOPS`, `pct_of`, `update_meters`, `meters_json` | 74 |
| 2825-3098 | Trigger engine (`triggers_tick` and helpers) and **`tick()`**, the 50 ms loop body | 274 |
| 3099-3293 | `Preview`, `Mirror(Preview)`, `preview`/`mirror` singletons, `MONITOR`, `monitor_sync` | 195 |
| 3294-3407 | State out: `osc_out`, `health`, `snapshot`, `list_vars`, `push` (to Companion) | 114 |
| 3408-3653 | `command()`, the Companion command grammar, and `osc_default` | 246 |
| 3654-5792 | **Web page** `UI` (one raw string): head script 3657-3669, CSS 3670-3922 (253), HTML 3923-4131 (209), JS 4132-5790 (1,659) | 2,139 |
| 5793-5886 | `VAR_INFO`, `VARS_PAGE`, `_scale()`, the `UI.replace(...)` templating (5882) | 94 |
| 5887-5958 | `STAGE_PAGE` (self-contained page) | 72 |
| 5959-6099 | `HELP_PAGE` (static) | 141 |
| 6100-6180 | Handlers: stage, help, `h_restart`, vars, `h_ui`, `h_state`, `h_lists` | 81 |
| 6181-6255 | Durations (`durations.json`, `_dur_worker` thread, probe child) | 75 |
| 6256-6366 | Format checks (`formats.json`, `fmt_judge`, `_fmt_run`) | 111 |
| 6367-6561 | File information (`fileinfo.json`, `_info_job`, `info_response`, `h_lib_info`) | 195 |
| 6562-6746 | Handlers: library, settings, warning, transition, folders, top | 185 |
| 6747-6860 | Waveform (`ff_wave`, `get_wave`), `h_meters`, SSE `h_live`, `h_lib_file` | 114 |
| 6861-7146 | Handlers: preview, mirror, devices, playlists, triggers, norm, move, scan | 286 |
| 7147-7371 | Upload plumbing, ffmpeg helpers (`ff_check/ff_run/ff_probe/ff_convert`), `save_upload` | 225 |
| 7372-7546 | Download from a link (`DL`, `_dl_child`, `_dl_run`, handlers) | 175 |
| 7547-7711 | `h_cmd`, `ticker`, `main()` (route table 7600-7670, middleware), `__main__` | 165 |

Notes on the map:

- The handlers are scattered: stage/help/state at 6100, settings at 6562, preview/playlists at 6861, plus handlers inside the feature areas (file info, formats, download, upload).
- The ffmpeg helpers are scattered across 2390-2432 (`ff_loudness`, `ff_volume`, `ff_lufs`), 6752 (`ff_wave`) and 7161-7294. They should become one module.
- `tick()` sits at the end of the trigger-engine area but is the central loop body. It rebinds `live_deck` and touches decks, triggers, ducking, meters and monitor.

---

## 2. The web UI

### How it is embedded and served today

| Piece | Lines | Served by | Notes |
|---|---|---|---|
| `UI` | 3655-5790 | `h_ui` (6149) at `/` | `text=UI, content_type="text/html"`. No cache headers, so it is always fresh. |
| `VARS_PAGE` | 5845-5874 | `h_vars_page` at `/variables` | self-contained |
| `STAGE_PAGE` | 5887-5956 | `h_stage` at `/stage`, `/stage/`, `/stage/{v}` | `Cache-Control: no-cache`, deliberately no frame/CSP headers (embedded cross-machine) |
| `HELP_PAGE` | 5959-6099 | `h_help_page` at `/help` | own CSS and 12 sections |
| `TOUR` | 5726-5790 | inside the `UI` script | a JS array in `app.js`, not a separate page |

All four are `r"""..."""` raw strings, so `\n` and backslashes inside the JS are byte-exact. A move to files is lossless as long as the files are read as UTF-8 without translation.

### Every generated or templated piece (this is the full list)

All of it is one statement at line 5882, plus its helper `_scale` (5878):

| Placeholder | In the page at | Replaced by | Source |
|---|---|---|---|
| `/*MST*/[]` | 4516, `const MST=/*MST*/[];` | `json.dumps(METER_STOPS)` | `METER_STOPS` (2759) |
| `@@SCL_BIG@@` | 4007, tall meter scale | `<b style="bottom:..%">..</b>` per tick | `METER_TICKS` (2760) via `pct_of` |
| `@@SCL_SMALL@@` | 4032, preview meter scale | same | `METER_TICKS_SMALL` (2761) |
| `@@AMB@@` | CSS 3744, 5 uses | `pct_of(METER_AMBER_DB)` as `%.1f` | `METER_AMBER_DB` (-17) |
| `@@RED@@` | CSS 3744, 5 uses | `pct_of(METER_RED_DB)` as `%.1f` | `METER_RED_DB` (-6) |

Nothing else is substituted. The other pages have no placeholders. Everything else in the page reaches the JS over HTTP: `/api/state`, `/api/playlists`, `/api/library`, `/api/live` (SSE) and the others. That gives 43 `fetch('/...')` calls and no server-rendered data. One thing to remember: the Python `FOLDER_ICONS` dict is unrelated to the JS `ICONS` constant. The latter is a 21 KB literal on line 4833 and is static.

Facts that shape the move:

- 148 inline `on*=` handlers exist, so the JS must stay a **classic script** (globals), not an ES module.
- The JS uses element ids as globals (`dfi_curi.innerHTML`, `trmsg.textContent`). The script tag must stay at the end of the body.
- The head script at 3657-3669 (skin/theme, `localStorage`) is deliberately inline and blocking so the page does not flash. It must stay inline or become a tiny blocking `<script src>` placed before the CSS.
- `/*MST*/[]` is valid JS, so `app.js` still passes `node --check` with the placeholder in it.

### Plan: static files, generated pieces stay server-side

```
static/
  index.html     (head script, <style> link, body, <script> tags)
  style.css      (CSS 3670-3922; keeps @@AMB@@ / @@RED@@)
  app.js         (JS 4132-5790 minus ICONS; keeps /*MST*/[])
  icons.js       (const ICONS=... line 4833, 21 KB, split out for readability)
  tour.js        (TOUR array, 5726-5790; so the tour text can be edited on its own)
  help.html      (HELP_PAGE)
  stage.html     (STAGE_PAGE)
  variables.html (VARS_PAGE)
```

Server side:

1. `ui_assets.py` (or a function in `web.py`) reads these files at start-up and does the same five replacements, using the same `_scale`, `pct_of` and `METER_*` values. Result: byte-identical `index.html`, `style.css` and `app.js` bodies compared with today. Cache them in memory.
2. Serve through routes `/`, `/static/{name}` (a fixed whitelist, not directory serving), `/help`, `/stage...`, `/variables`.
3. **Cache headers matter.** Today the page can never be stale. With separate files the browser will cache `app.js`, so a replaced `player.py` could leave an operator running old JS against a new API. Use `Cache-Control: no-cache` plus an ETag (hash of the rendered body), or reference `app.js?v=<hash>` from `index.html`. Recommend the ETag with `no-cache`: it is one line and needs no URL rewriting. Keep the stage page's "no frame/CSP headers" behaviour exactly.
4. The `same_site_only` middleware only guards `/api`, so static routes need no change.
5. Optional later step: replace `@@AMB@@`/`@@RED@@` with CSS custom properties and the scale labels with a JSON endpoint. That removes server-side templating entirely but changes behaviour risk, so it is **not** part of the first move.

### What changes for the syntax check and the tests

- CLAUDE.md "Testing" step 3 (extract with `re.findall(r'<script>(.*?)</script>', UI, re.S)[-1]` and `node --check`) becomes `node --check static/app.js static/icons.js static/tour.js`. This is simpler, and `index.html` and `stage.html` get a tiny extractor for their inline script only.
- `tests/gen_controls.py` line 57 does `re.search(r'^UI = r"""(.*?)"""', src, ...)` to crawl the UI. It must read `static/index.html` + `app.js` instead. Everything else it does (`command()` words, routes, OSC, variables) reads `player.py` by `ast` and will need to follow the code into its new modules.
- `tests/test_layout_share.py`, `test_move_button.py`, `test_devices_ui.py` and `test_live_output.py` drive the page with Playwright. They need the `static/` folder to be copied next to `player.py` (see section 5). No other change.
- A byte-equality test (rendered page before vs after the move) is cheap and is the main safety net for this step. See section 4, step U1.
- `README.md` line 537 "replace only `player.py`" becomes "replace `player.py`, `cpl/` and `static/`" (or the build artifact, section 5).

---

## 3. Module-level mutable state and import cycles

### Inventory

"Rebound" = assigned with `global` somewhere (a plain `from x import name` copy would go stale). "Mutated" = changed in place. R = number of functions that read the name. The `ast` pass is approximate on mutation (it detects subscript stores and common mutating methods).

**Shared core (touched by most areas)**

| Name (line) | Kind | Rebound by | Notes |
|---|---|---|---|
| `CFG` (345) | dict | none | read by 64 functions, mutated by 19. Overlaid from `config.json`, then `state.json` at import time. |
| `playlists` (467) | list | `load` | mutated by editing, trims, triggers, end actions. Fix: `playlists[:] = ...` in `load` so it never needs rebinding. |
| `library` (471), `LIBDIRS` (470), `FOLDER_COLORS` (468), `FOLDER_ICONS` (469) | dict/set | none | written by library functions and handlers |
| `focus` (472) | list | none | 17 readers, 12 mutators |
| `cue_cleared` (473) | bool | `command` | |
| `decks` (474) | list | none | 22 readers; `tick`, `_start`, `stop_all` mutate |
| **`live_deck` (475)** | Deck/None | **`_start`, `stop_all`, `tick`** | 15 readers. The most delicate piece of state. |
| `rev` (476) | int | `bump` | read in `h_state` |
| `known` (477), `last_scan` (478) | | `lib_rename`, `load`, `rescan_library` | |
| `ISSUES` (3304), `LAST_LOAD_ERR` (3305), `_boot_done` (3306) | dict/tuple/bool | `_start_when_ready`; `main` | `ISSUES` is written by devices, loudness, main |

**Cache and playback**

| Name | Kind | Rebound by | Notes |
|---|---|---|---|
| `_cache`, `_cache_lock`, `_loading`, `_env`, `_tcache`, `_key` (1247-1279) | OrderedDict/dict/Lock | none | the only `threading.Lock`. `_cache` is also touched from `library` (`lib_rename`, delete) and `set_device`. |
| `_gen` (1250) | int | `set_device` | invalidates cached sounds on a device change |
| **`pending` (1251)**, `_pending_n` (1252) | dict/None, int | `pending`: `_live_restore, _play_on_top, _start_when_ready, fade_out, play, stop_all, try_resume`; `_pending_n`: 4 of the same | a trigger waiting for its track. Rebound in 7 places. |
| `_warm` (1253) | dict | none | warm-up task state |
| `DUCK` (2040) | dict | none | ducking runtime state |
| `_vol_before_mute` (1939), `_bag` (2599), `_rs` (2680) | list/dict | none | mute memory, shuffle bags, resume throttle |
| `TRIG` (723), `_trig_load_err` (2833) | dict | none | trigger notice, load errors |

**Output side**

| Name | Kind | Rebound by | Notes |
|---|---|---|---|
| `preview` (3247), `mirror` (3248) | `Preview` / `Mirror` instances | none | each owns a subprocess, a queue and status |
| `MONITOR` (3250) | bool | `monitor_set` | read by 6 places incl. `Preview.info`, `update_meters` |
| `_mon` (3251), `METER` (2751), `_meter_t` (2754), `last_sent` (3303), `_list_keys` (3374) | dicts | `push` rebinds `_list_keys` | |
| `osc_out` (3295) | UDP client | `h_set_settings` | rebuilt when the Companion address changes |
| `DEV_MISSING` (1684) | dict | none | |
| `LOUD` (2246), `_loud` (2247) | dict | none | loudness results and task |
| `DURS`, `FMT`, `FMT_STATE`, `INFO`, `_info_jobs`, `_info_pending` (6182-6391) | dicts, one thread (`_dur_worker`) | none | caches persisted to json files |
| `_wave`, `_wave_lock`, `_live_subs` (6747-6826) | | none | |
| `FF`, `_ff_sem` (7167) | dict | none | ffmpeg detection (cached 60 s), one-job semaphore |
| `DL`, `_dl_task` (7374) | dict, Task | `h_dl_start` | |
| `_tasks`, `_log_seen`, `_warned`, `_sc` | sets/dicts | none | small helpers |

**Totals.** Names rebound with `global`: `playlists, cue_cleared, live_deck, rev, known, last_scan, _gen, pending, _pending_n, MONITOR, LAST_LOAD_ERR, _boot_done, _list_keys, osc_out, _dl_task` (15; `np` is also module-level but set once). 23 `global` statements.
Threads: `_dur_worker` (6252) and executor jobs (`run_in_executor`, 20+ call sites). Background asyncio tasks: warm-up, loudness, format check, download, the ticker, `_duck_loop`, the preview readers. Timers: the 50 ms ticker, a 5 s full push, `save_resume` throttling, `info_save_soon`. There is no `call_later`.

The clock matters for tests: `time.monotonic()` is used 44 times. `tests/test_triggers.py` replaces the module's `time` with a fake (`P.time = FakeTime()`). After a split each module has its own `time` binding, so that trick stops working unless there is one shared clock module.

### Why a naive split creates cycles

A mechanical split by area (same assignment as the table in section 1) gives **one strongly connected component of 20 modules**: nearly everything depends on everything. The back-edges that cause it (a module reaching *up* to one that depends on it) are few and specific:

| From | To | What | How to break |
|---|---|---|---|
| `state` | `cache` | `bump()` calls `request_warm()` (9 call sites of `request_warm`) | `state.on_change` hook list; the warm module registers itself at start-up |
| playlists, library, loudness, trigger data | `store` (`save`) | `save()` writes `playlists.json` | put `save`/`atomic_write` in a low `persist` module that depends only on config and state. `load()` and `migrate_old` (which need library, loudness, cache) go to a high `boot` module. |
| `cache` | `ducking` | `_load` calls `duck_key` | `duck_key` and `duck_curve` are pure numpy: move to a leaf `dsp` module together with `compute_env`, `lufs_from_pcm`, `cut_sound` |
| `cache` | `triggers_engine` | warm loop asks `trigger_targets()` | split the cache: a pure `cache` (LRU, decode child, `_load`) and a `warm` policy module above playlists and triggers |
| `library` | `cache` | `lib_rename`/delete reach into `_cache`, `_env`, `_key`, `_tcache`, `pending` | direction is correct (library above cache), but add `cache.rename_path`/`cache_drop` so library does not touch the dicts. `pending` belongs to playback: give it a function. |
| `devices` | `playback`, `ducking`, `triggers_engine`, `engine` | `set_device` calls `stop_all`, `_start`, `_start_when_ready`, `trig_carry_of` | `set_device`, `_live_snapshot`, `_live_restore` are transport operations. Move them into the transport module. `devices` keeps `list_devices`/`init_mixer`. |
| `engine`, `ducking`, `playback` | each other | `Deck`, `stop_all`, `_start`, `_start_when_ready`, `play_default`, `duck_arm` | one cohesive unit (about 700 lines). Keep as one `transport` module, with the pure math split out to `dsp`. |
| ducking, loudness, playback, handlers | `stateout` | `push()` (about 40 call sites); `ISSUES`, `LAST_LOAD_ERR` | `ISSUES`/`LAST_LOAD_ERR` move to the state module. `push` is called through `state.notify()`, a callback registered by `stateout` at start-up. The ticker already pushes changed values every 50 ms, so an unregistered notify is harmless. |
| `loudness` | `fileinfo` | `info_store` | move the fileinfo store (`INFO`, `info_entry/info_store/_info_save`) to a low module |
| `meters` | `preview` | `update_meters` reads `MONITOR`, `preview` | `preview` does not depend on `meters`, so order `meters` above `preview`, or pass the preview level in |
| `h_core` | `h_misc` | `warn_json` | one function; move to settings |
| `config` | `util` | `atomic_write` | order only |
| `envelope` / `ffmpeg` | misc | `METER_WIN`, `WAVE_BINS` | constants: put in the leaf module |

### Shared-state strategy

Two workable approaches; recommendation is the first.

1. **A `state` module accessed as an attribute** (`import cpl.state as S; S.live_deck`). Mutate-only names can also be imported by name. Rebound names (`live_deck`, `pending`, `_pending_n`, `MONITOR`, `osc_out`, and others in the list above) must be accessed as `S.x` everywhere, or converted to a one-field holder. About 60 reference sites change, almost all in `tick`, `_start`, `stop_all`, `play`, `_play_on_top`, `try_resume`.
2. Keep one big `Player` object and hand it to every module. More invasive, and the tests patch `P.name` today, so approach 1 is closer to the present shape.

Either way, the **clock** needs a shared indirection (`clock.py` with `now()` and `sleep`), and `tests/test_triggers.py` patches that instead of `P.time`.

Dependency passing and events are only needed at the seven places in the table above (`bump -> warm`, `save`, `push`, `warm targets`). Everything else is a plain downward import.

---

## 4. Proposed layout and order of moves

### Layout

```
player.py                 launcher only (~60 lines): sys.path fix, helper dispatch, then cpl.app.main
cpl/
  __init__.py             EMPTY (helpers must not import the app by accident)
  helpers/                probe.py  decode.py  dl.py  preview_worker.py   (stdlib + pygame + dsp only)
  dsp.py                  compute_env, duck_key, duck_curve, lufs_from_pcm, cut_sound  (numpy only)
  util.py                 atomic_write, log_once, spawn, body, fmt, fmt_bytes, parse_size
  clock.py                now(), sleep() (test seam)
  config.py               BASE, paths, CFG, read_config_file, warn_clean, PLAY_MODES, save_config_keys
  state.py                the shared mutable names (S.*), hooks: on_change, notify; ISSUES
  persist.py              save, save_state, resume files        (low)
  playlists.py            model, end actions, xfade, trims, editing, move_track
  triggers.py             data side + engine (triggers_tick), minus tick()
  library.py              scan, mkdir, rename, delete, storage limits
  cache.py                LRU, decode child, _load, trimmed cache
  warm.py                 warm-up policy
  ffmpeg.py               ff_check/run/probe/convert/loudness/volume/wave
  loudness.py  fileinfo.py  durations.py  formats.py
  devices.py              list_devices, init_mixer
  transport.py            Deck, _start, play, stop_all, seek, ducking arm, Play on Top, set_device, auto_advance, resume
  meters.py  preview.py (Preview, Mirror, monitor)
  stateout.py             health, snapshot, list_vars, push, VAR_INFO
  commands.py             command(), osc_default
  tick.py                 tick(), ticker()
  boot.py                 load(), migrate_old, import_file, startup order
  web/                    routes.py  (route table + middleware), pages.py, api_*.py (state, library, playlists, settings, preview, download, upload)
  ui_assets.py            reads static/, applies the 5 replacements, ETag
static/                   index.html style.css app.js icons.js tour.js help.html stage.html variables.html
```

About 20 modules plus `web/`. Largest expected: `transport.py` (about 700), `library.py` (about 340), `commands.py` (about 250). The web handlers are about 1,600 lines in total and get split by topic.

### Order of moves

Each step must leave a working app that passes the checks listed. Steps are small enough to ship one at a time. **Behaviour-neutral** means the same HTTP bodies, same `/api/state`, same command results.

**Step 0: safety net (before any move).** Details in the recommendation section.
- Create a git repository and commit the current tree. Tag it.
- Run `python tests/run.py`; record the report. Run `tests/test_triggers.py`, `test_devices.py`, and the Playwright tests; record results.
- Capture a golden set: `GET /`, `/help`, `/stage`, `/variables`, `/api/state`, `/api/playlists`, `/api/variables`, `/api/library` from a test instance with a fixed library.

**UI steps**
- **U1. Rendered-page equality test.** Write a script that fetches the five pages and stores their sha256. This is the check for U2-U4. Verify: it passes on today's code twice in a row.
- **U2. Move `HELP_PAGE`, `STAGE_PAGE`, `VARS_PAGE` to `static/*.html`** with a small loader. No placeholders, so output is byte-identical. Verify: hashes match; `/stage?name=x&bar=1&bg=000` still serves with no frame/CSP headers; `no-cache` kept.
- **U3. Split `UI` into `index.html`, `style.css`, `app.js`, `icons.js`, `tour.js`**, with `ui_assets.py` doing the five replacements and concatenating into the same bytes (serve the pieces separately only in U4). Verify: the rendered `/` is byte-identical when the loader concatenates; `node --check` on each JS file; update `gen_controls.py` line 57; run `tests/gen_controls.py` and diff `controls.csv` (expect no change).
- **U4. Serve the pieces as separate URLs** with ETag + `no-cache`. This is the first browser-visible change. Verify: Playwright suite (layout share, move button, devices UI, live output), a manual check of the tour, skins (console/studio/stage), custom layout, SSE meters, and a hard reload after changing a file.

**Python steps** (leaf first, so each move only needs imports pointing downward)
- **P1. Launcher + `cpl/` skeleton.** `player.py` keeps all code in place but becomes a thin file that imports `cpl.legacy` (the old code moved verbatim). This proves the packaging, `-I`, the `execv` restart, `BASE` and the four spawn sites. Verify: full test run; `POST /api/restart` works and the page reconnects; `--decode` and `--preview` children start (use a preview device test); `python -I player.py` works.
- **P2. Helper processes** to `cpl/helpers/*`. Lines 17-332. Verify: `--probe`, `--decode`, `--dl` and `--preview` each run alone from the command line; a download and a solo/preview test; startup time of a helper (it must not import aiohttp/python-osc: measure before and after).
- **P3. Leaves:** `dsp`, `util`, `clock`, `config`. Verify: `tests/api` plus `test_triggers.py` (after it patches `clock`).
- **P4. `state` + `persist` + hooks** (`bump` -> `on_change`, `save`, `ISSUES`). Convert the 15 rebound names to `S.x`. This is the riskiest mechanical edit. Verify: grep that no `global` statement remains for moved names; full tests; a manual run of play, fade, cut, device change, resume after kill.
- **P5. `ffmpeg`, `fileinfo`, `durations`, `formats`, `loudness`.** Mostly self-contained; they were assigned by area already. Verify: the ffmpeg tests with and without `"ffmpeg_path": "/nope/ffmpeg"` (CLAUDE.md step 5), upload and download, the "i" popover.
- **P6. `playlists`, `library`, `cache`, `warm`, `triggers` (data)**. Verify: `tests/api/test_library.py`, `test_playlists.py`, `test_trim_xfade.py`, `test_triggers.py`; rename and move a track and check trims/triggers/xfades follow.
- **P7. `transport`** (Deck, `_start`, play, stop, seek, ducking arm, Play on Top, `set_device`, advance, resume), then **`triggers` (engine)**, `meters`, `preview`, `tick`. This is the audio core and the most dangerous move. Verify: `test_transport.py`, `test_ducking.py`, `test_preview.py`, `test_volume_modes.py`, `test_triggers.py`, `test_live_output.py`, `test_devices.py`; then listen: crossfade, loop, Play on Top ducking, device change, restart with resume, with real hardware on the production machine. Check that the 50 ms tick does not get slower (add a timing log before and after).
- **P8. `stateout`, `commands`** then **`web/`** (route table, handlers by topic). Keep the catch-all `/api/{tail:.*}` route registered **last** (7670). Verify: `tests/api` entire suite and `controls.csv` regeneration.
- **P9. `boot`, `app.main`, delete `cpl/legacy.py`.** Verify: cold start on a clean folder and on a folder with existing `state.json`, `playlists.json`, `resume.json`; service restart on the production machine during a quiet period.

If any step fails its check, revert that step only (git).

### Effort estimates

Hours of focused work including verification, for one person who knows the code. Not including the production machine listening tests, which need access to the hardware.

| Step | Effort | Risk |
|---|---:|---|
| 0 safety net (git, baseline, golden) | 2-3 h | none |
| U1-U2 equality test, help/stage/vars out | 2-3 h | low |
| U3 split `UI` | 3-5 h | low-medium |
| U4 separate URLs, ETag, Playwright check | 3-4 h | medium |
| P1 launcher + packaging proof | 3-4 h | medium |
| P2 helper processes | 3-4 h | low-medium |
| P3 leaves | 2-3 h | low |
| P4 state module, rebound names | 5-8 h | **high** |
| P5 ffmpeg/fileinfo/durations/formats/loudness | 4-6 h | medium |
| P6 playlists/library/cache/warm/triggers data | 6-8 h | medium |
| P7 transport, triggers engine, meters, preview, tick | 8-12 h | **high** |
| P8 stateout, commands, web handlers | 6-8 h | medium |
| P9 boot, cleanup, docs | 3-4 h | low |
| Tests and tooling adaptation (section 5) | 4-6 h, spread across steps | medium |
| **Total** | **about 55-80 h** (UI part about 10-15 h, Python part about 40-60 h) | |

---

## 5. Deployment impact

### What is hard-wired to a single `player.py`

| Item | Where | Effect of a split |
|---|---|---|
| Spawn of helper children | `decode_in_child` (1387), `Preview._spawn` (3141), `_probe_dur` (6217), `_dl_child` (7403): `sys.executable str(Path(__file__).resolve()) --flag` | `__file__` would point inside `cpl/`. Replace with the launcher path (for example `BASE / "player.py"` or `sys.argv[0]`). The launcher must dispatch the flags **before** importing the app so a helper never loads aiohttp or the whole player. |
| In-place restart | `h_restart` (6131): `os.execv(sys.executable, [sys.executable] + sys.argv)` | works unchanged if the launcher stays at the same path; works for a `.pyz` too |
| Data folder | `BASE = Path(__file__).resolve().parent` (341); config, state, playlists, media, `_import/` all hang off it | in `cpl/config.py` `BASE` must be the *launcher* folder (`parent.parent`), not the package folder |
| **Isolated mode** | CLAUDE.md step 1 and every test run `python -I player.py` | `-I` drops the script's folder from `sys.path`, so `import cpl` fails. The launcher must do `sys.path.insert(0, <its own folder>)` first. Production (systemd) does not use `-I`, which would hide this bug until the first test run. |
| Test harness copies one file | `tests/harness/instance.py:96`, `test_layout_share.py:27`, `test_triggers.py:47`, `test_devices.py:32-43` | each must copy `player.py` + `cpl/` + `static/` (add one helper `copy_app(dest)` in `tests/harness`) |
| Source patching in tests | `tests/test_devices.py` does `str.replace` on three exact source lines (`list_devices` body, `init_mixer` head, `_dev = sys.argv[2] or None`) | those lines move to different files; better to replace the patching with test-only env hooks (for example `CP_TEST_DEVICES`), added behind a clear guard |
| Module-attribute patching | `test_triggers.py` sets `P.time`, `P.request_loudness`, `P.request_warm`, `P._warm_loop`, `P._play_on_top`, `P.DURS`, `P.playlists` | needs the `clock` seam and patching in the right submodules; the test needs rewriting, not just re-pointing |
| Report fingerprint | `tests/harness/report.py:36-42` hashes `player.py` and runs `git status` | hash the whole tree |
| Control map | `tests/gen_controls.py` regex on `UI = r"""` (57) and `ast` on `command()` in one file | follow `static/` and `cpl/commands.py` |

### Distribution options

| Option | How | For | Against |
|---|---|---|---|
| **A. Directory (recommended)** | copy `player.py`, `cpl/`, `static/` | no tooling; `systemd`, `.bat` and `nuc-setup.sh` unchanged; easy to edit one file on the production machine | "replace only `player.py`" is no longer true: three things to copy (a one-line `rsync`/`scp -r`, or a release zip) |
| B. Concatenation build | `build.py` joins modules (and inlines `static/`) into one generated `player.py` | keeps one-file deployment and the README line; the production file stays as it is | modules must refer to each other by bare names, which contradicts the `S.x` state approach in section 3; two source trees (dev vs generated) double the chance of a stale build; tracebacks point at generated lines |
| C. zipapp (`player.pyz`) | `python -m zipapp` | one file; static files via `importlib.resources` | `Path(__file__)`-based `BASE`, the spawn paths and static loading all have to be written for zip imports; needs a check that `-I` and `os.execv` behave; hard to hot-edit on the production machine |

Recommendation: **A** for development and for the production machine; add **B or C only if a one-file release is really wanted**, as a later optional step. A cheap middle path is a `make-release.py` that zips the three items into `companionplayer-<version>.zip`.

### Other files

- **`run-player.bat`**: runs `".venv\Scripts\python.exe" player.py %*`, so it works unchanged with the launcher. The only risk is shipping `player.py` without `cpl/`: add a startup check in the launcher that prints a clear message if `cpl/` or `static/` is missing.
- **systemd unit** (in `nuc-setup.sh` line 200): `WorkingDirectory=/opt/media-player`, `ExecStart=.../python player.py`. No change needed. `nuc-setup.sh` itself copies no application files (it installs requirements from `/opt/media-player/requirements.txt`), so check how the player files are placed there (the README says to copy `player.py` by hand).
- **`requirements.txt`**: no change. Check that nothing new imports beyond it (the `-I` run also ignores user site-packages).
- **`README.md`**: lines 14 and 531-537 (folder layout and "replace only player.py"), 564-579 (run and systemd examples are fine), the "Tests" line 201, plus the layout tree. Add the new tree.
- **`CLAUDE.md`**: the Layout table, "About 6,700 lines" (now 7,711), the testing steps (UI extraction, harness copies), "Single-file app: keep it one file" (convention would change), "Update README and the in-page Help and tour (`TOUR`)" (point at `static/help.html` and `static/tour.js`), and every `player.py`-specific reference in Architecture. Keep the Architecture text but replace "(`player.py`)" with the new module names as each step lands.
- **`backups/`**: the convention is `player.pre-*.py`. A split needs a directory snapshot, but git replaces this; keep `backups/` for the pre-split snapshot only.
- **Companion module**: no dependency on the player's file layout (HTTP only). No change.

---

## 6. Risks, ranked

1. **Audio-path regressions in the transport/tick move (P7).** `live_deck`, `pending`, `_pending_n` are rebound in many places and `tick()` runs every 50 ms. A missed `global`-to-`S.x` conversion fails silently (a local variable is created, or a stale copy is read) and may only show during a fade, a trigger or a device change. This is the failure that matters most (CLAUDE.md: audio glitches). Mitigation: do P4 as its own step, grep for leftover `global`, run all `tests/api` plus `test_triggers.py`, then listen on the production machine.
2. **No version control.** Without git, a bad step cannot be reverted cleanly; `backups/` copies are whole files. Mitigation: step 0.
3. **Test suite coverage is weaker than the change.** 156 API tests exist, but Playwright, audio-capture and stress tests are marked "not written yet" in CLAUDE.md. Several tests patch module internals (`test_triggers.py`, `test_devices.py`) and will fail for packaging reasons before they say anything about behaviour. Mitigation: fix the harness first (step 0/P1) and treat any new failure as a harness bug until proven otherwise.
4. **Isolated-mode import failure** (`python -I player.py` drops the script folder). Easy to fix, but tests and CLAUDE.md use `-I` and production does not, so it can hide. Mitigation: the launcher inserts its folder; P1 tests both modes.
5. **Browser caching of split static files** (U4): a stale `app.js` against a new API. Mitigation: ETag + `no-cache`, tested with a hard-reload and a changed file.
6. **Helper processes importing too much.** `--decode` and `--preview` are launched often; `--decode` runs per track load. If the launcher or `cpl/__init__.py` import the app, startup time and RAM per helper grow and the nice level does not help. Mitigation: empty `__init__.py`, dispatch before import, measure helper start time before/after.
7. **Template drift**: the five placeholders replaced at 5882 are easy to lose; a missing one gives a broken meter scale and no error. Mitigation: U1 byte-equality, plus an assertion that no `@@` remains in the served output.
8. **Documentation drift**: CLAUDE.md and README describe a single file in many places, and CLAUDE.md is the primary source for future sessions. Mitigation: update both in each step, not at the end.
9. **Deployment mismatch**: shipping `player.py` alone, or an old `cpl/` with a new launcher. Mitigation: the missing-folder check, optionally a version string checked by the launcher.
10. **Merge cost for in-flight edits**: any feature work during the split edits moved code. Mitigation: freeze features during a step, or do steps in one sitting.

---

## Recommendation

**Split the UI first, the Python second, and do both only after step 0.**

- **UI first.** It is 32% of the file, has a small and fully known set of generated pieces (five placeholders, one statement), and the output can be proven byte-identical. It carries no audio risk. It also gives the most daily benefit (editing JS/CSS with real tooling, `node --check` directly, smaller diffs). Do U1-U3 now. U4 (separate URLs) is the only part with user-visible risk, so do it last and test it in a browser.
- **Python second, in small steps from the leaves up** (P1-P9). It has a real payoff (the file is about 5,260 lines of Python with tangled globals), but it also carries the audio risk. The cycles are fewer than they look: about 12 back-edges, all with a known fix (section 3). If effort is limited, stop after P5-P6: that already removes about 2,000 lines of non-audio code from the main file and leaves `transport`/`tick` as the one remaining large unit.
- **Do not do a one-shot rewrite.** The 15 rebound globals make a mechanical move in one pass very error-prone.

**What must be done before starting**

1. `git init` and commit the current tree (there is no version control now). Tag it, for example `pre-split`.
2. Run `python tests/run.py` and the stand-alone tests; keep the reports as the baseline. Capture the golden page and API outputs (step 0, U1).
3. Decide distribution: directory copy (recommended) or a build step. This decides whether modules may use `S.x` state access.
4. Update the test harness so it copies `player.py` + `cpl/` + `static/`, add the `clock` seam, and replace the source-string patching in `test_devices.py`. Do this first so a red test means a real regression.
5. Make the launcher requirements explicit: insert its own folder into `sys.path` (for `-I`), dispatch helper flags before any heavy import, empty `cpl/__init__.py`, fixed `BASE`.
6. Agree a feature freeze during each step, and plan the production machine listening test (crossfade, loop, Play on Top, device change, restart with resume) for the end of P7 and P9 when the show schedule allows.
