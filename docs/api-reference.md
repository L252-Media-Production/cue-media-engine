# API and data reference

Developer-level detail moved out of the user guide (`docs/wiki/`). Internal names and storage shapes: see also `CLAUDE.md`.

## Library flags (favorite and hidden folders)

- **Favorites and hidden are shared by every browser** (they are saved on the player, in `playlists.json` as `folder_flags`, and follow a rename or move of the folder; a deleted folder drops out). `GET /api/library` has a `flags` object (`{path: {fav: true, hidden: true}}`) and `GET` / `POST /api/library/folder/flags` (`{path, fav?, hidden?}`) reads and sets them. They are for the web page only: nothing goes to Companion.

## End actions: storage, migration and API

The setting is saved with the playlist as `end_actions: {track_id: "once"|"loop"|"stop"}` in `playlists.json` (default is absent),
keyed by the file within that playlist, so it follows renames, re-ordering and moves to another playlist (like trims).
The old `loops` list is read as `loop` and migrated on load (a copy of the old file is kept as `playlists.pre-endactions.json`), and
the old "Loop the track" mode is converted the same way. Over OSC/HTTP: `/<p>/<t>/end/default|once|loop|stop` sets it, `/<p>/<t>/end`
with no value steps to the next setting, `/<p>/<t>/loop` still toggles loop forever (`/loop/1`, `/loop/0`; `/loop` for the focused track).
`/mode/track` toggles loop for the focused track. `/api/playlists` returns `end` for each track plus `loop` (true only for `loop`);
`/api/state` adds `live_end`, `live_pass` and `live_passes`, and `live_rem` is the time left of the current pass.

## RAM indicator numbers

The numbers are in `/api/state` (`ram`: `used_mb`, `budget_mb` (2.8.1: the effective limit = the smallest of `cache_mb`, 25 % of MemTotal and MemTotal minus 1 GB; `mem.cache_budget` is the same in bytes), `tracks_total`, `tracks_in_ram`, `loading`, `full`, `rev`) and `/api/playlists` (`ram`, `ram_in`, `ram_total`). They are for the web page only: nothing about them goes to Companion. They are computed from the cache with lookups, cached for one second, and reading them never changes which track the cache drops first.

## Playlist progress: how the sums are made

The sums are made in the page from `/api/playlists` (`dur_eff`, the seconds of one pass; `shuffle_left`, the ids still to come in a Shuffle round) and the live position; the engine does no extra work.

## Trigger points: data, API, tests

- **Data:** `playlists[p]["triggers"] = {file_id: [{id, at, file, once, enabled}]}`, next to `trims`; it follows renames (both the track and the target), reordering and moves to another playlist.
- **API** (web page only, not Companion): `GET/POST /api/playlists/<p>/triggers` (`track`, `action` = `add|update|delete|set`, `id`, `at`, `file`, `once`, `enabled`, `triggers`), `GET /api/triggers`, `POST /api/triggers/arm {"armed": true|false}`, `POST /api/triggers/skip`. `/api/state` has `triggers_armed`, `next_trigger`, `live_triggers`, `trigger_notice`; `/api/playlists` has `triggers` per track. There are no Companion variables, actions or commands for triggers.
- **Tests:** `SDL_AUDIODRIVER=dummy python3 -I tests/test_triggers.py` (fake clock, no audio device needed).

## File information: API and sources

How it works:

- `GET /api/library/info?id=<library id>` returns all of these as JSON (`null` where not available) with a `status` for each group (`probe`, `loud`, `peak`, `vol`: `ok`, `measuring`, `needs ffmpeg`, `failed` or `unavailable`), a `done` flag, the file-check message if the file has a yellow or red sign, and `error` for a file that cannot be read. An unknown id is a 404, and a listed file that has vanished from the disk is a 404 with "missing from the disk".
- Format, codec, duration, bitrate, sample rate, channels, bit depth and probe score come from ffprobe. LUFS, True Peak and Loudness Range come from one ffmpeg `ebur128` pass, the same pass the level-match worker uses (so a file measured for level matching also has them here, and the other way round). Max Volume and RMS come from one `volumedetect` pass, run only when the popover is opened.
- Everything runs through the same one-at-a-time, low-priority, core-limited ffmpeg runner as the other ffmpeg jobs, and the page asks again once a second while the popover is open and something is still being analyzed (the chips show a pulsing dot and "analyzing…"; the API status value stays `measuring`).
- Results are kept in `fileinfo.json` (per library id, with the file's size and modified time, so a changed file is measured again).

## Health: device probing

- **No device enumeration while audio plays.** `cpl/devwatch.py`: while any deck exists the health report makes no SDL device-list call and opens no device. The Live output is judged by a plain read of `/proc/asound/cards` (Linux): the configured SDL name is matched tolerantly to a card (the card id or its description appears in the name); once matched, the check turns bad only if that card's id (the bracketed name in `/proc/asound/cards`, e.g. `Module`) disappears; the card number is not used, because it changes after a replug. If two cards matched equally at some time (a second identical adapter) and the first one then goes while the other stays, the check reports unknown (one INFO line in the log) instead of guessing. A name that cannot be matched stays `unknown` and only the watchdog's stall signal counts (never a false bad); one INFO line says which card matched. Without `/proc/asound` (macOS) the probe is skipped. When nothing plays the SDL list is refreshed in a worker thread at most every 10 s and never waited for (a hung call leaves the last good list). Copy report uses the last good list. A missing Live output (the player left on the system default or SDL's dummy output) is reported bad and is not treated as a stall: the watchdog makes no restart while the Live output check is bad.

## Level meters: scale internals and API

0 dBFS is the top (nothing is boosted, so ducking thresholds, level match and the gain-reduction meter are unaffected). The scale
is piecewise linear, as a percentage of the meter height from the bottom: 0 dBFS = 100, -5 = 88, -10 = 76, -20 = 60, -30 = 46,
-40 = 33, -50 = 21, -60 = 10, and -90 (labelled -∞) = 0. Both meters carry the same labels, `0 -5 -10 -20 -30 -40 -50 -60 -∞` (0 unsigned, a minus before every other number), at the same heights: one list (`METER_TICKS`) and one formatter (`meter_label`) in `cpl/legacy.py`. The colour zones are green, amber from -17 dBFS (65%) and red from
-6 dBFS (86%). The table lives once in `cpl/legacy.py` (`METER_STOPS`); the page's scale labels, colour zones and JS copy are generated
from it. The meters stretch to the full height of the Live and Preview panels. Bars fall back at 30 dB per second.

- Developers: the web page listens to the server-sent-event stream `GET /api/live` (meters about 14 times a second, the
  preview output's state 4 times a second). `GET /api/meters` still returns one reading,
  `{"live": {"l","r","l_db","r_db"}, "preview": {...}, "enabled": true}` with `l`/`r` as 0-100 on the taper above and `l_db`/`r_db` in dBFS.

## Layout: repair and file format

- **Repair:** on every page load the saved layout is checked and repaired: unknown or missing blocks, blocks outside the grid, sizes that are too small or too large, overlaps, bad numbers and damaged data are all corrected (a missing block is added at the bottom), and layouts saved by earlier versions (rows and widths) are converted. The repaired layout is stored again. Data that cannot be repaired falls back to the standard layout.

- **File format:** `{"app":"cue-media-engine-layout","version":1,"name":"...","exported":"<ISO date>","layout":{"v":3,"b":{"cl":{"x":0,"y":0,"w":12,"h":7},...},"hide":[]},"appearance":{"skin":"console","theme":"dark","waveforms":true}}` (`appearance` only when ticked).

## Output names (output aliases)

## Output names (output aliases)
An output can have a label, a group heading, a hidden flag and a live-only flag without changing which device is used: the saved Live, Preview and Mirror outputs stay the exact SDL device names, so matching, the health check and the Companion `output` variable (raw name) are not affected. The table is `output_aliases` in `state.json`, edited through `GET` / `POST /api/settings/outputs` (`{"aliases": [{"match": "<exact device name>", "label": "...", "group": "...", "hidden": false, "live_only": false}]}`; `{"aliases": null}` brings back the default; at most 32 entries, texts up to 80 characters, no `match` twice; a bad table is refused whole and the old one stays). There is no editor in the page yet. While nothing was ever saved, a built-in rule for the ALSA loopback card of Dante over IP (Inferno) applies: `Loopback, Loopback PCM` reads **Dante over IP** under **Network audio** and is offered for Live only (Preview and Mirror are refused with "Only one program can use Dante over IP. Use it for Live."), and `Loopback, Loopback PCM (2)` is hidden. A saved table replaces that rule completely. A hidden output is listed only while it is the chosen one, or when **Settings > Audio > Show hidden outputs** is on (dimmed, marked hidden). `/api/devices` keeps `devices` as before and adds `output_info` (one object per device: `name`, `label`, `hidden`, `group`, `live_only`) and `output_aliases`. The health panel and Copy report show an aliased output as `Dante over IP (Loopback, Loopback PCM)`. The Companion command `/device/next` skips hidden outputs; `/device/<n>` still counts the full list.

## ElevenLabs (2.9.0)

**Modules.** `cpl/elevenlabs.py` is the only code that talks to ElevenLabs: the key file, `transport()` (the one network function, aiohttp; tests replace it), the error mapping (`ElError`, `map_error`) and the calls (`list_voices`, `usage`, `list_models`, `test_key`, `speech`). `cpl/generate.py` runs one generation at a time (`JOB`, an asyncio task), owns the temporary file in `_import/` (emptied at every start), the one-use preview token, `save_new` and `replace`. Routes are in `cpl/legacy.py` (`h_el_*`). Direct REST, no SDK: nothing new to install.

**ElevenLabs API used** (read from the documentation on 2026-11-23): [authentication](https://elevenlabs.io/docs/api-reference/authentication) header `xi-api-key`; [List voices](https://elevenlabs.io/docs/api-reference/voices/search) `GET /v2/voices?page_size=100[&next_page_token=]` → `{voices[{voice_id, name, category, is_owner, preview_url…}], has_more, next_page_token}` (up to 10 pages are followed); [Get user subscription](https://elevenlabs.io/docs/api-reference/user/subscription/get) `GET /v1/user/subscription` → `character_count`, `character_limit`, `next_character_count_reset_unix`; `GET /v1/models` (`model_id`, `name`, `can_do_text_to_speech`, and `maximum_text_length_per_request` when present: this field name is not confirmed in the docs, so a model without it has no client-side limit and the API's `max_character_limit_exceeded` decides); [Create speech](https://elevenlabs.io/docs/api-reference/text-to-speech/convert) `POST /v1/text-to-speech/{voice_id}?output_format=mp3_44100_128` with `{"text", "model_id"?, "voice_settings"?: {"stability", "similarity_boost"}}` → the audio bytes. No `model_id` is sent unless one is chosen in Advanced: the API then uses its default model (`eleven_multilingual_v2`, 10,000 characters per request, the only limit the page applies by itself). `mp3_44100_128` is the API default and available on every plan. Error bodies are `{"detail": {"status", "message"}}`; the statuses handled are `invalid_api_key`, `quota_exceeded`, `max_character_limit_exceeded`, `voice_not_found`, `too_many_concurrent_requests`, `system_busy` ([400/401](https://elevenlabs.io/docs/help-center/technical/api-error-code-400-or-401.md), [429](https://elevenlabs.io/docs/help-center/technical/api-error-code-429.md)). Not confirmed in the docs and handled defensively: the status string for a scoped key without a permission (any answer whose status or message mentions "permission", and any 403, is "missing permission", named for the call: `text_to_speech`, `voices_read`, `user_read`, `models_read`); `Retry-After` (shown only when the header is present, seconds or an HTTP date; otherwise "Try again in a moment").

**Key storage.** `BASE/elevenlabs.key` (next to `config.json`; in `.gitignore`), created with `os.open(..., 0o600)` and replaced atomically; a looser mode found on read is tightened back to 0600. On Windows `icacls <file> /inheritance:r /grant:r <USERNAME>:F`; when that fails the key is still saved, `key_info().note` carries the amber note and a WARNING is logged (without the key). Never in `CFG`, `config.json`, `state.json`, `playlists.json`, the health report, push messages, variables or any route. Every error text leaving `cpl/elevenlabs.py` goes through `redact()`. The deploy scripts never write to the install folder's data files (`tests/test_deploy_keeps_data.py`).

**Routes** (all under `/api`, so the same-site check applies):

| Route | What it does |
|---|---|
| `GET /api/elevenlabs` | `{key: {set, last4, note}, job, default_folder, default_limit, output_format, preview: {device}}` |
| `POST /api/elevenlabs/key` `{key}` | save (400 for something that cannot be a key); answers `key` as above, never the key |
| `DELETE /api/elevenlabs/key` | remove the key file |
| `POST /api/elevenlabs/test` | `{level: ok|warn|bad, title, msg, usage}`: `GET /v2/voices?page_size=1` decides valid or not (`voices_read`), then the subscription (`user_read`) only adds the usage or a green note |
| `GET /api/elevenlabs/voices[?refresh=1]` | `{voices: [{id, name, kind: own|cloned|library, preview}]}` (cached 5 minutes in memory; a new key forgets it) |
| `GET /api/elevenlabs/usage` | `{usage: {used, limit, left, reset}}`, or `usage: null` + `note` when the key lacks `user_read` |
| `GET /api/elevenlabs/models` | `{models: [{id, name, limit}] or null}` (null = the key can't read models: the page offers "Default model" only) |
| `POST /api/elevenlabs/generate` `{name, text, voice_id, voice_name, model?, stability?, similarity?}` | starts the one generation (409 `busy` while one runs) |
| `GET /api/elevenlabs/job` | `{state: idle|running|done|error|cancelled, n, error, result, elapsed?, has_temp}` |
| `POST /api/elevenlabs/cancel`, `POST /api/elevenlabs/discard` | stop it; delete the temporary file |
| `POST /api/elevenlabs/preview` `{cmd: play|stop|link}` | play / stop on the player's Preview output (`Preview.play_file`, name `Generated: <name>`), or a one-use link valid 60 s |
| `GET /api/elevenlabs/audio?t=<token>` | the temporary file once (`audio/mpeg`, `no-store`); 404 after that or after 60 s. No file path ever leaves the player |
| `POST /api/elevenlabs/save` `{name, folder}` (an existing library folder, `""` = top level) or `{name, new_folder}` (one new top-level name: not empty, no `/` `\`, not starting with `_` or `.`, library characters only, not existing in any letter case: `generate.folder_error`; 409 when it exists; created only now) or `{replace: <file id>}`; anything else is refused with `field` set, so nothing is written outside `media/library`; a duplicate is detected before any folder is made | save as a new track through `upload.import_path` → `upload.finish_import` (the end of every upload: normalise, duplicate check, library entry), or replace a generated track |
| `GET /api/elevenlabs/track?id=` | the stored `{text, voice_id, voice_name, model, created}` of a generated track |

Errors: `{ok: false, kind, error, level, retry_s, perm}`; `kind` is `no_key`, `invalid_key`, `permission`, `network`, `quota`, `rate`, `too_long`, `timeout`, `voice_gone`, `unexpected` (plus `busy`, `input`). None of them writes `ISSUES` or reaches the health, the push messages or Companion.

**Metadata.** `GENERATED` (`cpl/state.py`, a stable container) `{file id: {text, voice_id, voice_name, model, created}}`, saved in `playlists.json` as `generated`, read tolerantly by `boot.load`, re-keyed by `lib_rename` (files and folders), dropped by `delete_from_library` (and so by deleting a folder). A save that `find_duplicate` matches to an existing file returns `duplicate: true` and adds no entry. `/api/library` files carry `gen: true`.

**Replace.** Only for a file in `GENERATED`, with the same extension, and not while it is on a deck, pending or previewing. The file is swapped atomically; `cache_drop` (RAM cache, trimmed copies, meter and ducking data), `DURS.pop`; the waveform, format check, loudness and file information are keyed by size and mtime and are measured again; the trims and trigger points on that track are cleared in every playlist; playlist entries are kept.

**Test hook.** `CP_TEST_ELEVENLABS=<folder>` (inert unless set) replaces `transport` with a fake that reads `<folder>/fake.json` and appends each call (without the key) to `calls.jsonl`. Used by `tests/api/test_elevenlabs_api.py` and `tests/test_elevenlabs_ui.py`; `tests/engine/test_elevenlabs.py` replaces `transport` in-process.
