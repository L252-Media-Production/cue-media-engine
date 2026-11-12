# Changelog

Newest first. The player (`player.py` + `static/`) and the Companion module share the major.minor version; the module warns when they differ.

## Rename: Cue Media Engine (CueME)

The product is now called **Cue Media Engine** (short form **CueME**; before: CompanionPlayer). The version is still 2.8.0. Only what a user sees changed: page title and header, Help, tour, Settings footer, README, messages and the Companion module's names. Unchanged on purpose, so nothing breaks: the `cpl/` package and `player.py`, API paths, OSC addresses, variable names and the `mp_` prefix, config and data file names, `cp_*` browser keys, the `X-CompanionPlayer-Client` header, and the `player_version` field.
- Layout files are now written with `"app": "cue-media-engine-layout"` and the file name `cue-media-engine-layout-<name>.json`; import accepts both that and the old `companionplayer-layout`.
- Companion module: new id `cue-media-engine` (the old id `companionplayer` is in `legacyIds`), new name, short name and description. Behaviour unchanged.

## 2.8.0 (2026-11-11, release)

2.8.0 is the health release (health panel, watchdog, push messages, Companion health variables, feedback and preset, sound-card matching, report lines; described in the next section) plus output labels and hidden outputs: the built-in "Dante over IP" rule and `/api/settings/outputs`, described here.

- **Output aliases** (`cpl/outalias.py`, `output_aliases` in `state.json`): a label, a group heading, `hidden` and `live_only` for an output name, matched exactly (capitals count) on the raw SDL name. Built-in default while nothing was saved: the Inferno loopback pair (`Loopback, Loopback PCM` = Dante over IP, Network audio, Live only; `... (2)` hidden); a saved table replaces it. Validated on save (types, 80 characters, 32 entries, no duplicate `match`), a bad table is refused whole. The saved outputs stay the raw SDL names (no migration).
- **API:** `/api/devices` keeps `devices` and `current` and adds `output_info` and `output_aliases`; `GET` / `POST /api/settings/outputs`; Preview and Mirror refuse a live-only output with "Only one program can use Dante over IP. Use it for Live."; Companion `/device/next` skips hidden outputs. Companion action ids, variables (`output` stays the raw name) and OSC addresses are unchanged.
- **Page:** the Live, Preview, Mirror and Settings > Audio menus show the label, group headings, the raw name in the hover text; hidden outputs only when selected or with Settings > Audio > Show hidden outputs (dimmed, marked hidden); live-only only in the Live menu. The new switch has a ring in its off state (the shared switch track is 1.3:1 against the row).
- **Health and report:** `Live output: Dante over IP (Loopback, Loopback PCM) (found in the device list)`; matching and rules unchanged.
- Tests: `tests/engine/test_outalias.py`, `test_outalias_health.py`, `tests/api/test_output_alias.py`, `test_output_alias_health.py`, `tests/test_output_alias_ui.py` (Playwright, by hand). Help and README updated; golden `/` and `/help` updated for the page changes only.

## 2.8.0, health (what the release adds, with follow-up 3)

What 2.8.0 adds, in plain words (the three sections below have the detail of each step):

- **Health dot and panel.** The dot beside the title is a button with four states, each its own shape and colour: starting (orange ring), ready (green circle), degraded (amber triangle, something needs attention but the audio works) and problem (red diamond). It opens a panel with seven checks: Live output, Preview output, Audio engine, Companion, Media drive space, Track cache and Player uptime. **Copy report** (`GET /api/health/report`) gives a plain-text report for a chat, with no addresses and no file paths.
- **Watchdog** (Settings > System > Health and alerts, on by default): if the audio output stops moving for 10 seconds while something plays, it restarts the audio engine only (never the service); at most 3 restarts in 10 minutes, then the Audio engine check stays red.
- **Push messages** (off by default): a webhook message when a problem starts, when it recovers, when degraded lasts over 5 minutes and when the watchdog restarts the engine; a Send a test message button; an optional Player name.
- **Companion** (module 2.8.0): variables `health_state` and `health_text`, the feedback *Player health* and the preset *Health* (amber when degraded, red on a problem).
- **Sound-card matching** on Linux: the Live output is judged from `/proc/asound/cards` while audio plays (no device enumeration that could disturb the stream), by the card id and description.
- Logs are line-buffered at start-up; an unregistered `POST /api/test/*` answers 404.
- **Stage skin close buttons** are round (they were ovals), and the playlist toast close button (the cross) is a small square box in every skin, Console and Studio included.

Follow-up 3 (this release candidate), from `v2.8.0-health-rc3`:

- **Audio driver in the report.** It said `unknown` on every machine because pygame has no `mixer.get_driver()`. It now asks SDL (`SDL_GetCurrentAudioDriver`, through the SDL2 library pygame loaded; `cpl/audiodrv.py`) once a device is open, keeps the answer and shows it as SDL names it (`alsa`, `coreaudio`, `pipewire`, `pulseaudio`, `dummy`). Before a device is open, or if SDL names none, it says `not detected` with the reason.
- **Free-space percentage.** `2.0 GB free (2 %)`: free divided by total of the same drive, rounded to a whole number, between 0 and 100, `less than 1 %` for a small non-zero share (it said `0 %`), and no percentage when the total is unknown. The limits are unchanged (warning below 10 % or 5 GB, problem below 1 GB). The test hook `CP_TEST_DISK_FREE_GB` keeps the drive's real total; `CP_TEST_DISK_TOTAL_GB` sets a fake one.
- **Sound cards are tracked by id.** rc3 remembered the card number, which changes after a replug. It now remembers the id (e.g. `Module`). If a second identical adapter appeared and the first is then unplugged, the check reports unknown with one INFO line instead of guessing (never red).
- **Soak support.** The report has two read-only lines, `Process memory: N MB` and `Open files: N` (Linux: VmRSS and `/proc/self/fd`; macOS: getrusage for memory; `not available` elsewhere). They change no check, state, dot or push message.
- Help, README updated. Companion module unchanged (still 2.8.0).
- Tests: `tests/engine/test_audiodrv.py`, `test_health_soak_lines.py`, new cases in `test_health_model.py`, `test_devwatch.py`, `test_health_defaults.py`, `tests/api/test_health_api.py`.

## 2.8.0, health follow-up 2 (`v2.8.0-health-followup2`, from `v2.8.0-health-rc2`)

- **Sound-card matching** (`cpl/devwatch.py`): a card is identified by its id and its descriptive name only (the driver name and the address line are not used); texts under 4 characters and generic words (audio, usb, analog, digital, device, card, output, speaker, headphones, hdmi, usbaudio, hdaintel) do not count. The longest contained text wins; a tie is unknown (INFO line names the cards), never bad. Fixtures: real `/proc/asound/cards` of the NUC and the Pi (`tests/fixtures/audio/`). No output device configured = no probe.
- The OSC-gap test flake was the test's own 3 s track ending inside the window (the `--:--` value and the 5 s full resend leave a 1.4-1.5 s gap; v2.7.5 shows it as often). The test plays the 120 s file; `tests/engine/test_push_cadence.py` checks the send cadence with the fake clock; `tests/tools/loop_probe.py` measures event-loop stalls and gaps. Measured: no stall above 100 ms attributable to health.
- stdout/stderr are line-buffered at start-up (a service without `PYTHONUNBUFFERED=1` logs promptly). An unregistered `POST /api/test/*` answers 404 (was 405).
- **Stage skin close buttons** were ovals (the generic button rule's `min-height:var(--btn)` = 46 px against a 26-35 px width): Settings, Health panel, download and playlist toasts, file-information and level-match popovers are now square circles; the Health button no longer collapses next to a wrapping title. Test: `tests/test_close_buttons_ui.py`.

## 2.8.0, health follow-up (`v2.8.0-health-followup`, from `v2.8.0-health-rc1`)

- **No SDL device enumeration while audio plays** (`cpl/devwatch.py`): the health report's 3 s device-list query on the event loop is gone. Playing: `/proc/asound/cards` read (matched tolerantly; unmatched = unknown, never a false bad). Idle: a worker thread, at most every 10 s, never waited for. Copy report no longer enumerates.
- A missing Live output (system default / dummy output) is bad and names the device; the watchdog makes no restart then.
- Settings > System > Health and alerts > **Player name**. The Audio engine row shows "Restarted N times since start" (also in the report); an hourly INFO line while playing.
- Companion polls: after the first poll with the client header only the header counts.
- Tests: `test_devwatch.py`, `test_health_defaults.py` (default on, inert hooks, dummy output), `test_companion_poll.py`; `tests/run.py` runs the module tests and fails if they leave a tracked file modified.

## 2.8.0, health (first step, `v2.8.0-health`)

- **Health panel, watchdog and push.** The header dot is now a button with four states (starting ring, ready circle, degraded triangle, problem diamond; shape as well as colour) and opens a panel with seven checks: Live output, Preview output, Audio engine, Companion, Media drive space, Track cache, Player uptime, with Copy report and Open Variables. `/api/state` `health` gained `state`, `summary` and `checks` (`status` / `detail` unchanged). New: `cpl/health.py` (pure model), `cpl/watchdog.py` (a silent heartbeat on reserved mixer channel 0 and the stall logic), `cpl/alerts.py` (webhook push). Settings > System > Health and alerts: Watchdog, Amber for a missing Preview output, Push on state change, Send to, Webhook address, events, Hold messages until nothing is playing, Send a test message.
- **Watchdog**: restarts only the audio engine when the output stops moving for 10 s while playing (the live track resumes where it was). Added beyond the design: at most 3 restarts in 10 minutes, then the Audio engine check stays bad.
- **Push**: added beyond the design: a state must hold 5 s before it produces a message. Messages carry `text` and `content`; the webhook address is never logged or sent to the page in full.
- Companion module 2.8.0: variables `health_state`, `health_text`, feedback *Player health*, preset *Health*; its requests carry `X-CompanionPlayer-Client` so the player can tell its polls from a browser's.
- The mixer reserves channel 0 (`pygame.mixer.set_reserved(1)`); tracks use the other 15.
- Tests: `tests/engine/test_health_model.py`, `test_watchdog.py`, `test_watchdog_engine.py`, `test_alerts.py`, `tests/api/test_health_api.py`, `tests/api/test_health_isolation.py` (real rendered output, disk driver), `tests/test_health_ui.py` (Playwright), `companion-module/test/health.test.mjs`. Golden files: only the `health` block of `api_state.json` gained keys (masked) and the page / Help changed.

## 2.7.5 (2026-11-10, release; finish run `v2.7.5-finish`)

- **Bluetooth output is deferred to a later release.** It is not part of 2.7.5. The output menus keep their group headers and the `bt` argument of `devOpts` is kept (reserved for a future group); README and comments no longer say a Bluetooth group is coming in 2.7.5.
- Tests only otherwise: the forced-ducking Live input test reads the depth after it has settled; `test_devices.py` picks the OSC input port as a free UDP port.

## 2.7.5, feature 3 of 4: Live input, the block fits in a custom layout (`v2.7.5-input-layout-fit`)

- **Live input block height:** `LB.inpc.h` is now 5 rows (was 3, enough for the collapsed card only), measured: the open card needs 4 rows in console / studio and 5 in stage at 860 px and wider (6 rows at the narrowest desktop width, 545 px, where the labels sit above the menus: use the block's fit height). `layMeasure` (the first Edit layout, which measures the page as drawn with the card collapsed) keeps at least that height for this block, so a fresh custom layout shows the open card without an inner scrollbar. Layouts already saved keep their saved heights (not migrated); the block's fit height button still works. The `#lay>*` rule (overflow:auto) is unchanged. A collapsed card sits centred in the taller block.
- **Companion module 2.7.12:** the Input armed toggle's text size is `'14'` again (the string, like the other presets; tested on a real Companion button), in both looks, from one constant. Texts, colours, the action and the feedback are unchanged.
- Test: `tests/test_input_layout_fit.py`.

## 2.7.5, feature 3 of 4: Live input, Armed in one place, the Input Gain hint, a smaller card (`v2.7.5-input-arm-font-hint`)

- **Armed only in the Cue container:** the Live input card has no Armed switch on desktop (it is hidden above 34 rem; the switch and its ids stay in the page, so the phone-width window is as before, and Settings > Audio keeps its Armed switch). The card keeps "armed" / "not armed" as plain text. The Armed API, the saved setting, the Companion variable and button are unchanged.
- **Input Gain hint:** an (i) button next to the Cue container's "Input Gain" opens a small popover (click, Enter or Space; Escape, a click outside or a second click closes it; kept inside the viewport; hidden at phone width): "Level of the track played on top (Play on Top). This is not the Live input gain, which is on the Live input card." Generic `[data-hint]` handler (`hintOpen`, `hintClose`, `hintPlace`) and `#hintpop`.
- **The threshold is set only on the meter:** the "Duck above" row of the card (slider, number, Reset) is hidden above 34 rem (still in the markup, so the phone-width page script keeps its ids). Added: a click, or a press and drag, on the bars moves the mark there; a double-click on the mark returns to the default (-30 dB), and its title says so. The readout under the meter follows live. The setting, the API, the saved value and the validation are unchanged. Settings > Audio keeps its Duck above field.
- **Device and Channels menus** are as small as the Duck now / Solo chips (same font size, padding and height, at least 24 px). Settings menus unchanged.
- **Inner scrollbar:** in the standard layout the card never scrolled; in a custom layout (Edit layout) blocks are `overflow:auto` with a fixed height (`#lay>*`), and the Live input block is 3 rows high by default (`LB.inpc.h`), enough for the collapsed card only, so an open card scrolled inside it. Use the block's "fit height" button, or make it taller. No change was made to that rule.
- **Companion module 2.7.11:** the Input armed toggle's text size is 26 in both looks (the default unarmed look and the armed feedback style). Needs no new player.
- Tests: `tests/test_input_hint_ui.py` (new), `tests/test_input_layout_ui.py`, `tests/test_input_card_ui.py`, `tests/test_input_stereo_ui.py`, `companion-module/test/armed-button.test.mjs`. Check A (`test_crossfade_unit.py`, 12 phone / touch Cue-panel height failures) fails identically on rc2, rc3, rc4 and clean release/2.7.5: a known environment failure, not a regression.

## 2.7.5, feature 3 of 4: Live input, layout and its own threshold (`v2.7.5-input-layout-threshold`)

- **Device and Channels on one row** in the Live input card (Device takes the free width and ends in an ellipsis with the full name in its title; Channels has a fixed width that holds "Channel 1/Channel 2 (stereo)"); Input gain is the row below, "Duck only" stays at the bottom right. Under 52 rem the labels sit above the menus so Device keeps room. The mark colour of the old marker used an undefined variable (`--fg`, always white); the new one uses `--text`.
- **Library header:** Expand all (was a down chevron) now has an expand icon (Lucide maximize-2, arrows out), the mirror of Collapse all (minimize-2, unchanged); same 16 px, stroke 2, 32 px hit area. The two buttons are actions (every folder open / closed), not a toggle, so their names stay "Expand all" / "Collapse all" and they carry no aria-expanded.
- **Live input threshold:** `input_threshold_db` (CFG, state.json, `/api/input` `threshold_db`, `/api/state` `input.threshold_db` + `threshold_default` / `threshold_min` / `threshold_max`), -60..0 dB in whole dB (clamped, non-numbers refused with 400, one bad value changes nothing). Separate from Play on Top's `duck_threshold_db`, which the Live input no longer reads (ratio, attack, release, hold and the release ramp are still shared; "Duck now" is unchanged). An install without the setting starts at the Play on Top threshold it was using (default -30 dB) and saves it, so behaviour is identical until it is changed. The mark on the meter is a slider (`role=slider`, 24 px hit area, drag along both bars, arrows 1 dB, Shift 5 dB, Home / End, double-click = reset), with the caption "Duck above -35 dB" / "Ducking", a slider + number + Reset row in the open card and a "Duck above" field in Settings > Audio; all follow each other and a change made elsewhere without a reload. "Signal present" is unchanged (above -60 dBFS before the gain).
- Tests: `tests/engine/test_live_input_engine.py` (class `InputThreshold`, 9 tests), `tests/api/test_live_input.py` (4 new / changed), `tests/test_input_layout_ui.py` (layout, Library icons, marker; 3 skins x 2 themes), `tests/test_library_header_ui.py` (icon path). Golden files: see the commit "Input layout-threshold: golden pages".

## 2.7.5, feature 3 of 4: Live input, stereo pairs and the armed state (`v2.7.5-input-stereo`)

- **Stereo pair and single channels:** the Channels menu (card and Settings, searchable menu, groups Stereo pair / Single channel, tick, placed inside the viewport). `input_channels` (list of 1 or 2 numbers) is saved next to the old `input_channel`, which is still written and read when the new key is absent. The ring now carries 1 or 2 channels per frame (`cpl/helpers/ring.py`, channels in the header, epoch-checked reads), the helper captures the chosen columns, the detector takes the louder channel (shared threshold, ratio, attack, release, hold, ramp; the gain on both), the meter has one bar per channel, Solo plays a pair as stereo and a single channel to both ears. A device with fewer channels than the saved choice falls back to the first valid one with a note. Changing the choice shows "Switching…" and ramps the ducking off while the capture restarts.
- **Armed state in the Cue container** (only while a device is chosen): status line (armed, no cue), "No cue" plus "Input off" line, a pill in the header when a cue is loaded, an amber line when armed without input; one switch (a real button, `aria-pressed`) that is the Armed setting itself.
- **Companion module 2.7.10:** the *Input armed toggle* button (green INPUT UNARMED, red INPUT ARMED), the feedback *Input armed* (red default), the action *Input arm / disarm*, a *Live input* preset category, unit tests (`npm test`).
- Golden files: see the commit "Input stereo: golden pages". New tests: `tests/engine/test_live_input_engine.py` (stereo, choices, saved channels, switching), `tests/api/test_live_input.py`, `tests/test_input_stereo_ui.py`, `companion-module/test/armed-button.test.mjs`.

## 2.7.5, feature 3 of 4: Live input, review fixes (`v2.7.5-input-rc2`)

- **Release without a click:** when the input is lost, Armed is switched off or Duck now is switched off, the input's ducking ends with a 50 ms linear-in-dB ramp (`LiveInput._start_ramp`), stretched for a deep dip so that a 10 ms step stays within 3 dB, never beyond 100 ms; the normal release curve is used when it is faster. Replaces rc1's instant volume step (and, for Armed off, the slow release). Tests: gain steps of at most 3 dB, complete within 100 ms, for each of the four ways (`Ramp` in `tests/engine/test_live_input_engine.py`).
- **Duck now is a manual override:** it works with or without an input device or ring, and with Armed on or off; the 409 / `no input` refusal is gone; the loss of the input releases only the input-driven ducking and Duck now stays on (until pressed again, `/input/ducknow/off`, or a player restart). The card shows DUCK NOW in its header, the variable `input_duck_now` follows the real state (module 2.7.9: the action text and help only, the commands are the same).
- **One hold setting:** rc1's `input_hold_ms` was a second hold time that Play on Top does not have (Play on Top's hold is only the on/off switch `duck_hold`, "stay ducked"). It is removed; an old key is ignored and dropped. The input uses the same switch, and the one-second hold after the speech is a fixed constant (`HOLD_S`), not a setting. Test: changing `duck_hold` changes the input ducking.
- **Detector staleness:** the 50 ms tick calls `LI.watchdog()`; if the 10 ms detector has not run for 250 ms the input ducking is ramped off, the chip says "Detector stalled", and a late detector step skips the audio of the gap; it recovers by itself on the next on-time step. Duck now is not touched. Tests with the fake clock.
- **Card placement:** the card was inside the Cue block under Ducking; it is now a block of its own (`#inpc`, layout block `inpc`) directly under the Cue and Preview blocks, part of Edit layout (older saved layouts get it appended at the bottom). Collapsed by default, with the chip, the meter, Armed, Duck now and Solo visible in the collapsed header. Hidden on a phone-width page as before.
- Golden files: see the commit "Input rc2: golden pages".

## 2.7.5, feature 3 of 4: Live input, Duck only (`v2.7.5-live-input`, rc1 content)

The player listens to one input channel and ducks the playlist audio while someone talks. **Duck only**: the input is analysed, never mixed into the Live output, so Live is untouched. Play only and Both, drift compensation and Bluetooth are not in this release. Companion module **2.7.8** (needs this player; major.minor 2.7).

### Added
- **Capture helper** `python player.py --input <json>` (`cpl/helpers/input_worker.py`): owns the capture device (pygame/SDL capture), writes ONE channel as mono 48 kHz int16 into a shared ring (`cpl/helpers/ring.py`, a memory-mapped file `_input/ring.bin`, 5.5 s, header = frames written + an epoch that changes when the device is (re)opened). Reports `{state, reason, channels, device}` as JSON lines. Retries to open the device every 2 s for ever; stops when the player closes its stdin. Only started when an input device is chosen.
- **Detector** `cpl/liveinput.py`: a reader of the ring with its own pointer, run by a 10 ms task in the player process (not in the 50 ms tick, nothing CPU-heavy). Per 10 ms block: RMS, then the Play on Top gain computation (`cpl.dsp.input_target_db` = `duck_curve`) and the Play on Top attack/release smoothing (`cpl.dsp.duck_smooth`, now also used by `_duck_loop`, same maths), with the same threshold, ratio, attack, release and "Stay ducked". The factor is `Deck.duck_in` (new), multiplied with Play on Top's `Deck.duck` in every place the deck volume is computed (`apply`, `level`, `set_live_volume`, `monitor_decks`), so the two never overwrite each other. Why in the player process: see the module docstring.
- **Safety:** ring not moving for 0.5 s, helper says error / no device, helper dead: all input ducking incl. Duck now ends at once (no release ramp), Duck now is cleared, chip "No input" with the reason, Armed kept, the helper is restarted (2 s) and the device is retried; recovery is automatic.
- **Solo** (`POST /api/input/solo`, `inmon` op of the preview worker): a second reader of the same ring with its own pointer, plays on channel 4 of the PREVIEW mixer only (read-only mapping, no way back to the player), follows the preview volume and Mute. Refused (400) without a Preview output. Not saved.
- **Armed** (`input_armed`, saved, default off), **Duck now** (not saved; follows threshold and ratio: holds the reduction of a signal 12 dB over the threshold; refused with `no input` / 409 while there is no input), input device / channel (1-64) / gain (-12..+24 dB, default 0) saved in `state.json`; `input_hold_ms` (default 1000, config.json) is the hold time of "Stay ducked" after the speech stops.
- **Web page:** the Live input card under Ducking in the Cue panel (collapsed by default, hidden on a phone-width page; chip, level meter with the threshold mark, Armed, Duck now, Solo, device and channel menus, gain, "Duck only"), the Reduction meter shows Play on Top plus input reduction, and rows in Settings > Audio (armed, device with the searchable menu, channel, gain; (i) help). Changes save as they are made; a refusal puts the fields back.
- **Commands / variables:** `/input/armed/<on|off|toggle>`, `/input/ducknow/<on|off|toggle>`; variables `input_armed`, `input_duck_now`, `input_signal`, `input_ducking`; `GET/POST /api/input`, `POST /api/input/solo`, `POST /api/input/ducknow`; `inputs` and `input` in `/api/devices`; `input` in `/api/state`; `in_gr` and `input` in the meters. Help guide entry, tour text, README.
- Test hook (inert unless set): `CP_TEST_INPUT=<folder>` replaces the capture device by a synthetic source read from `<folder>/feed.json`; `mock_inputs.json` in the `CP_TEST_DEVICES` folder lists the input devices.

### Changed on purpose (golden files, `python tests/test_pages_equal.py --update`)
- `api_state.json`: the new `input` block and the four new variables (`input_armed`, `input_duck_now`, `input_signal`, `input_ducking`), with the defaults of a player that has no input device (reason "No input device chosen").
- `api_variables.json`: the four new variables and their descriptions. Nothing else.
- `root.html`: the card, its CSS and JS. `help.html`: the new Help entry. `stage.html`, `variables.html`, `api_playlists.json`, `api_library.json` are unchanged.
- Gate 10 (`tests/test_gates.py`) now also lets the helpers import `cpl.helpers.ring` (stdlib + numpy only); `tests/gates/import_allowlist.json` has the new modules.

### Tests
- `tests/engine/test_live_input_engine.py` (fake clock; the test plays the capture helper by writing the ring): silence, bursts above and below the threshold, attack / release / hold numbers, a click shorter than the attack, Armed off, Duck now, loss of input, Solo isolation (identical numbers with Solo off and on), reuse of the Play on Top settings, settings validation and persistence, variables, commands.
- `tests/api/test_live_input.py` (a real instance, the real helper, a synthetic source): chip states, ducking depth, Armed, Duck now, stall / stream error / device gone / helper killed and recovery, a channel the device does not have, validation, restart persistence, a saved device that is missing at start, no device chosen, Solo reaching the preview mixer, and (marker `audio`) the Live output captured before, during and after a loss of input.
- `tests/test_input_card_ui.py` (Playwright, desktop only, 3 skins x 2 themes): chip states, meter and threshold mark, Armed, Duck now, Solo, menus, Settings rows, keyboard, accessible names, focus rings.

## 2.7.5, feature 2 of 4, follow-up `v2.7.5-preview-fixes` (`v2.7.5-preview-rc2`)

### Fix 1: output menus stay inside the viewport
- The cause was `innerWidth` / `innerHeight`, which include the scrollbars, so a menu near the right edge ran under them (and the clamp left only 4 px). `cboPlace()` now works in the visible viewport (`documentElement.clientWidth / Height`), keeps 8 px from every edge, lines the menu's right edge up with the button's near the right edge, opens upward near the bottom, limits its width to the viewport and its list height to the room on its side (the search box stays on top, the list scrolls inside), and ends with a clamp so that whatever the button does the box is inside the margins. The menu follows a resize, a scroll and the visual viewport (`cboFollow`), is re-placed when the list changes length (device refresh, typing in the search box) and closes when its button has scrolled out of view. `tests/test_menu_viewport.py`: 360 / 390 / 768 / 1280 / 1920 wide and 1280 x 500, 100 and 150 %, 3 skins, both themes, 4 scroll / button positions; 254 failures on the old code.

### Fix 2: the one-line bar appears sooner
- It shows when more than half of the full panel has scrolled out of the top of the view and goes when less than half is out: an `IntersectionObserver` with thresholds 0, 48 %, 52 %, 100 % (about 4 % of hysteresis); it is fixed, so no layout moves. `tests/test_strip_threshold.py` (steps, flicker, layout shift, z-order, 100 / 125 / 150 %, phone, every pin / shrink combination).

### Fix 3: click the playing title in the one-line bar
- `#ms_name` calls the same `liveGo()` as the full panel's title (opens the playlist, scrolls, flashes), has the link role, is focusable (Enter and Space), has an accessible name, a pointer and hover underline; rows have `scroll-margin-top` so the item does not end up under the bar. Nothing else is triggered. `tests/test_strip_title.py`, desktop bar and phone strip.

### Checks
- **`test_reduction_meter` race:** the original test (no switch-off of the page's meter feed) failed in 5 of 30 runs on this branch and in 2 of 30 runs on `v2.7.5-settings-rc4` (also the first runs on `release/2.7.5` passed 8 of 8 by luck: same race), always the same two checks "fill and value are the page's red" / "-6 dB fills 20 %" when the 14 Hz meter feed overwrote the forced value just before the read. 5 against 2 is not a significant difference (Fisher p about 0.4) and the mechanism is the test's own, so the race is older than this branch; the code is fine and the test now switches the feed off for that check (logs in `docs/screenshots/2.7.5-preview-fixes/race-reduction-meter-*.txt`).
- Focus rings and hover on the highlighted rows (`tests/test_row_states.py`): the light themes' accent was 2.85:1 on a tinted row; the ring colour `--ring` is darker in the light themes, and a hovered row control gets a visible border.
- **Idle meters:** with the Preview pair hidden the meter block is back to rc1's layout (the button group sets the width): 4 px narrower than rc1 (the speaker button is tighter), the card, the clock and the waveform do not move (clock and waveform 4 px more room) at 360 to 1920 px in all skins; the 6 to 8 px of rc1 vs preview-rc2 Fix 5 came from the fixed columns and are gone. (A page overflow at 360 px in Studio and Stage is older: it is there in rc1.)

### Fixes 4 and 5

### Fix 4: the playing-item highlight
- The bright **solid yellow card** was the "show me where it is" flash (`li.t.flash`, `.lt.flash`, `.fd.flash`: `#ffe600` with every child forced to `#111`), which stays for 4 s after you click the Live or Cue name. It is now a 16 % tint of the accent over the normal row, a dashed accent outline and a thick accent bar; nothing on the row is recoloured. Where the flash was used: playlist rows, library track rows, library folder rows (the only place; the trim dialog and the other lists never used it). States: playing = red tint + solid red outline, cued/focus = accent tint + solid accent outline, previewing = teal bar, REF = the green chip, jump = dashed accent outline + accent bar (on a playing or cued row the bar is added to their own outline).
- Text-safe colours (`--okt`, `--livet`, per theme) for the REF chip, the elapsed / length readout and the delete icon; the playing name keeps the normal text colour; greyed text and grips on a tinted row use a stronger grey. `tests/test_row_contrast.py` measures every text and icon on the normal, playing, cued, REF, flashed, playing + flashed and library-flashed rows against the real rendered background in 3 skins x light / dark x desktop / phone (it found 78 failures before: REF chip 2.3:1, elapsed readout 2.4:1, playing name 3.5:1, grips and index numbers 3.7:1, delete icon 3.2:1). Before / after screenshots in `docs/screenshots/2.7.5-preview-fixes/`.

### Fix 5: the dB scale
- The shared scale is exactly centred between the Live pair and the PRV pair: three fixed grid columns (Live column as wide as the M / S / speaker group with the bars centred, the scale, a Preview column given the same side margins as the Live bars) make the two gaps equal by construction (31 / 31 px in Console and Studio, 27 / 27 in Stage; before: 29 and 52). With the PRV pair hidden the scale is beside the Live pair at the same gap (2 to 4 px more than before). Labels are centred on the column's centre line, with a true minus sign (U+2212, `meter_label`) and the infinity sign scaled (1.9 em) and moved by `fitInf()` (canvas metrics) so it has the height and the vertical centre of the digits in any fallback font. Label heights (`bottom: x%`) and meter sizes are unchanged. `tests/test_scale_centred.py`: Chromium 100 / 125 / 150 %, Firefox and WebKit 100 / 150 %, 3 skins, both themes; equal gaps, centred labels, label heights as in rc1, each label on its dB level, the -20 dBFS tone on the -20 line, nothing moves when the PRV pair appears, no scale in the one-line bar.

## 2.7.5, feature 2 of 4: Preview meters and the pinned Live panel (`v2.7.5-preview-meters`, `v2.7.5-preview-rc1`)

Web page and player only: no Companion variable, action or feedback changed (the meter variables keep their names, rate and values; the module stays at 2.7.7).

### Added
- **Preview meters beside Live, only while previewing:** a thinner PRV pair (teal chip) to the right of the shared dB scale, with its own **Mute** (mutes the preview output only) and a speaker button; the Live pair and the scale do not move; the pair goes away when the preview stops. The meters left the Preview panel. Shown while a preview plays, is paused or loading, or while Solo live uses the preview output.
- **Preview Mute:** new worker op `mute` (`cpl/helpers/preview_worker.py`, the volume is kept), `Preview.set_mute`, `{"cmd":"mute","on":bool}` on `POST /api/preview/ctl` (400 for a non-boolean or no preview output), `muted` (and the worker's `mute`) in the `preview` block of `/api/state`. It also silences the soloed live audio on that output, keeps across a change of the preview device, and never touches the live decks, ducking, the Live meters, Live Mute or Solo (`tests/api/test_preview_mute.py`). In a browser-only preview it mutes the page's audio.
- **Output buttons:** the Live output left the transport row for a **speaker button** after M and S under the Live meters (`#dev_out`); Preview has one beside its Mute (`#pv_out`). Both open the existing searchable output menu; menus now have group headers (*Wired* for devices, *Plays on* for the preview target; the menu is prepared for more output groups, with no group header while a group is empty; Bluetooth output is not part of 2.7.5).
- **Preview panel:** its Output selector moved up to the right of the volume slider (headphone icon and name, no "Output" label, no separate row), the waveform runs the full width.
- **Pinned Live panel:** a pin button (filled upright = pinned, the default; outlined tilted = not), a **one-line panel** that appears at the top once the full panel has scrolled out of view (pin, LIVE, title, pause, stop, progress, time, LIVE and PRV meters; two rows on a phone), and three Settings > Look switches (*Pin the Live panel*, *Shrink to one line when scrolled*, *Remember the pin in this browser*), per browser.
- **Phone:** Playlists come right after the Cue panel, and the Reduction meter stays visible while Ducking is collapsed.

### Changed
- Tests that depend on the moved controls were updated: `test_live_output`, `test_meter_scale`, `test_preview_output`, `test_devices`, `test_devices_ui`, `test_output_menu_ui`. New: `tests/test_preview_meters_ui.py`, `tests/test_preview_meters_matrix.py` (3 skins x light/dark x desktop/phone, screenshots in `docs/screenshots/2.7.5-preview-meters/`), `tests/api/test_preview_mute.py`.

## 2.7.5 (feature 1 of 4: Settings rework, `v2.7.5-settings-rc1`, follow-up `-rc2`)

### rc4
- **Chips, root cause found:** the pill beside a button in a flex row (`.btns`, File check / Check all) was stretched to the button's height (46 px in the Stage skin) with its text at the top of the box, which is the "high and left, cramped" look. rc3's flex centring fixes it; `tests/test_chips_matrix.py` proves it (Chromium, Firefox, WebKit x pixel ratio 1 / 1.5 / 2 x zoom 100 / 125 / 150 % x 3 skins x 2 themes, plus DejaVu Sans, Liberation Sans and the generic sans-serif; 4320 measurements, worst line-box offset 0.80 px, worst drawn-ink offset 1.6 px = two device pixels at 125 % zoom; the same script on the pre-rc3 CSS finds 144 failures up to 11.9 px). Before / after screenshots in `docs/screenshots/2.7.5-settings-fixes/`.
- **Variables page** rebuilt its rows only once, so after a prefix change it kept showing the old names until reloaded; it now rebuilds when the prefix or the list of variables changes. Another browser page (Settings open) follows a prefix change on its next poll (`pfxSync`).
- **Prefix change while Companion cannot be reached:** the result chip says "saved, Companion not reached" (red) instead of claiming the variables were sent; the sender recovers by itself when the host resolves. Tests for a prefix change during playback (switch at once, nothing under the old names, no gap over 1.3 s), with an unreachable host, and across a restart.

### rc3 (branch `v2.7.5-settings-fixes`)
- **Page lock:** while any modal dialog or the tour is open the page behind it cannot scroll (wheel, touch, keys, rubber-banding) and its exact scroll position comes back on close; one helper with a counter (`pageLock` / `pageUnlock`), no sideways shift (`tests/test_page_lock.py`).
- **Output menu:** outlines and focus rings are no longer clipped (the highlighted row is outlined inside, the list and the search box have room for their rings; `tests/test_output_menu_ui.py`, screenshots in `docs/screenshots/2.7.5-settings-fixes/`).
- **Variable prefix** (Settings > Companion): the prefix of every variable sent to Companion is now editable (default `mp_`, config key `var_prefix`, existing configs unchanged). Checked on leaving the field (1 to 16 letters, digits, underscores, starting with a letter; trailing underscore kept as typed; live example), a bad one shows the red warning and the old one stays, a changed one asks for confirmation first, then every variable is sent again under the new names and a chip shows the result. `POST /api/settings/prefix` (409 without `confirm: true`), `variable_prefix` in `/api/state` (not in `snapshot()`). The Variables page, the Send test text and the Help guide use the current prefix. **Companion module 2.7.7** follows it: it declares its variables and the presets that show them with the player's prefix and again when it changes; fallback: its own configuration field, then `mp_` (for a player older than rc3).
- **Chips** in Settings: text centred both ways (flex centring, equal padding, minimum height; long results wrap and stay centred).
- **Settings > Audio > Transitions** order is now Default, Crossfade time, Fade-in at A, Fade-out at B.

### Version note (proposal, to be confirmed)
The module checks major.minor only, so its patch number may run ahead of the player's during a 2.x line (module 2.7.6 with player 2.7.5). Proposed rule: the module's patch is its own counter (only up, never reused for different contents; the next module change takes the next number above the highest published, even when the player's patch is lower or equal); a player patch release needs no new module; a new minor restarts both at x.y.0; every release names the module file and its SHA-256. See CLAUDE.md, Companion module.

### rc2
- **Host names are no longer resolved on save.** Only a syntactically bad or incomplete address (`192.168.1.`, empty, spaces or illegal characters) or a bad port is refused (400, red field and warning; the last good address stays in use). A well-formed name that does not resolve (offline, an mDNS name, Companion not up yet) is saved and becomes the address in use; the page shows an amber note ("Couldn't find this host right now"). `POST /api/settings` and `GET /api/settings` return `host_found` (true / false / null).
- **New sender `OscOut`** (`cpl/legacy.py`, replaces `SimpleUDPClient` as `osc_out`): no lookup when it is made or on the event loop (a name is resolved in a background thread, kept 60 s, a failed lookup is never kept and is retried after 2 s; an IP address needs none), so a name that does not resolve cannot stop the player from starting, stall the 50 ms tick or crash `push()`. `push()` marks a variable as sent only after it was sent, logs one line per minute while it cannot send, one line when it works again, and the missing variables go out as soon as the name resolves.
- **Send test** does a fresh lookup first and reports the failure itself: `{ok:false, error:"Host not found", sent_to, host_found}`; the page shows red "Couldn't send", "Host not found. Still using `host : port`".
- **`mp_test` path (documented):** the Companion module polls HTTP and cannot receive OSC, so the module variable `mp_test` is filled from `test_message` in `/api/state`. That value is only reported for 120 s after a test (then `""`), together with `test_sent_at` (epoch seconds), so Companion cannot keep showing an old time as if it were a new test. The OSC message to a Companion custom variable is separate and unchanged.
- **Companion module 2.7.6:** `mp_test` follows `test_sent_at` (it takes a value only when the send time is new; an unchanged send time keeps it, a missing one leaves it empty). Module package: `companion-module/companionplayer-2.7.6.tgz` (built with `npm run package`; the module has no lint or test script, its checks are `tests/test_module_version.py`).
- **`push()` and threads:** `push()` runs on the event loop and on worker threads (`S.notify`); `OscOut.send_message` works on local copies of its address and client, and the "can't send" flag is a dict item (not a `global`: the state gate forbids that), which is atomic under the GIL and only decides two log lines. Tested with eight threads and a name that flaps.
- **Ducking capture test (`tests/api/test_audio_capture.py`):** one failure in a full run ("the top track lasted 2.75 s of rendered audio, expected about 3 s") was the guard of that test, not the ducking: the player ends the 3 s voice-over by its wall clock while SDL's disk driver renders about 92 to 97 % of real time (less under CPU load), so the file holds 2.75 to 2.95 s of it. In 25 runs (20 alone, 5 in the full suite) the measured depth was 17.54 dB every time (expected 17.47, tolerance 1.0) and the top track 58 to 59 windows; the failure was not reproduced. The guard now needs 40 windows (2 s), which leaves 28 for the depth average and does not change the depth check or its tolerance; the test prints the window count and the file / wall time of every run.
- **Phone, every skin and theme:** `tests/test_settings_ui.py` now opens Appearance and Companion at 390 px with touch in Console / Studio / Stage x light / dark, checks no overflow, WCAG text contrast (4.5:1) of summaries, labels, chips, the red warning, the amber note and the result boxes, and saves screenshots (`docs/screenshots/2.7.5-settings-phone/`). Fixed: chip text and the red field text were too faint (light themes 2.4 to 3.8:1), the selected Light / Dark / System button on the light console theme.

### rc1

Settings is reorganised. No setting was removed and `config.json` / `state.json` load unchanged.

### Changed
- **Settings layout:** four tabs on a computer (Look, Audio, Companion, System); on a phone or touch panel one column of collapsible sections (closed, one open at a time) with a one-line live summary each and a search box. Everything saves as you change it: the Save button is gone.
- **Look:** Style, Theme, Show waveforms (a switch), Time warnings, New folder icon, Layout (Edit layout visible; Reset, Export and Import in a More menu). "This browser only" is a chip on Appearance and Layout.
- **Time warnings:** an expandable row (closed it shows the colours); any number of warnings (the limit of eight is gone: `warn_clean` accepts one or more, `WARN_MAX` removed); labels First warning, Warning 2 ... Final warning; sorted by time. The Live countdown and `/stage` already follow a list of any length.
- **Audio:** Preview plays on (with one line about the chosen option), Player output, Mirror live to a second device (switch; the device menu appears under it), Transitions (Default, Crossfade time, Fade-out at B, Fade-in at A, unit inside the field). The Refresh devices button is gone: output lists refresh each time they open.
- **Companion:** Address and OSC port are checked when you leave the field. An incomplete address (e.g. `192.168.1.`) is refused with a warning, the last good address stays in use and the Sending to chip keeps showing it (`POST /api/settings` also refuses it, status 400; a half-typed IP address used to be accepted as a host name). `GET /api/settings` has `target` and `var_prefix`.
- **System:** Rescan, File check (a result chip instead of text), Help guide, Tour, an ffmpeg chip (the format list moved to the Help guide), Restart player, version. "Saved to config.json" and the other how-it-saves texts are gone; each remaining explanation is one sentence behind an (i).

### Added
- **Send test:** `POST /api/settings/companion/test` sends `mp_test` = `HH:MM:SS` through the same OSC sender, address and port as the live variables (never the value being edited) and returns `{ok, sent_to, at}` or `{ok:false, error}` (Host not found, Network unreachable, ...). Resend now does not send it. `/api/state` has `test_message`; it is not in `snapshot()`, so nothing else reaches Companion.
- **Companion module 2.7.5:** variable `mp_test` ("Test message"), set from the player's `test_message`; module version moves to the player's 2.7 line.
- Tests: `tests/test_settings_ui.py` (Playwright, run by hand), `tests/engine/test_companion_test_send.py`, new cases in `tests/api/test_settings.py`.

## 2.7.4

Library and Trim. Web page and player only: the Companion module stays at 2.7.0 (same major.minor, `version_match` stays `ok`); no variable or command changed, and none of the new state goes to Companion.

### Added
- **Library:** favorite folders (star; a Favorites group above All folders, both alphabetical), hide folders (eye-off; only the library list changes, tracks stay in playlists, search and playback), a **Hidden (n)** toggle with unhide, **Collapse all / Expand all**, and a search message *N tracks found in hidden folders · click to show* with a reveal and *Hide these again*. Favorites and hidden are saved on the player (`playlists.json`, `folder_flags`; follow rename / move, dropped on delete; `GET` / `POST /api/library/folder/flags`, `flags` in `GET /api/library`) and shared by every browser; collapsed state and the Hidden toggle are per device. Hidden folders are left out of the trigger point's track picker.
- **Trim, fade in at A:** `start: "fade"` (Cut is the default and is not stored) and `fade_in_ms` (0.1-10 s, clamped to B - A; kept while the edge is Cut; a track with no A may have one) in the track's trim, default from the new config key `trim_fadein_ms` (0 = none; Settings > Transitions > Default fade-in at A). Applied only by `_start` and only on a start at the In point (never a seek, a resume part-way in or a paused start); a crossfade into the track wins; a track played on top fades up to its set level (the background still ducks at full depth meanwhile; documented). Trigger voice-overs are library files with no trim, so they get none. Same equal-power curve as every fade; no per-tick work. `/api/playlists` tracks have `fade_in_ms_eff`, `/api/state` has `live_fade_in_ms` and `trim_fadein_ms`, `POST .../trim` takes and returns `fade_in_ms` and `start`; moves and renames carry them with the trim. Green wedge at A on the waveform.
- **Trim dialog:** Trim | Smart Loop tab strip (Smart Loop is disabled, *coming soon*; not built in this release); **Precision** toggle (sliders button, per device) with time fields (`m:ss.s`, `h:mm:ss.s` over an hour) with arrows (hold to repeat, Shift = 10x, Up / Down), typing, and the 0.01 / 0.1 / 1 s step strip; the "s" sits inside the fade fields.
- **Loop A-B (preview only):** repeats Play A-B from A at every B, with the fade-in and fade-out each lap. On the player's preview output it is one new op of the preview worker (`{"cmd":"loop","a","b","fin","fout"}` via `POST /api/preview/ctl`, about 40 lines): one buffer of [A, B) with sin / cos fades, played with `loops=-1`, so the wrap is sample-accurate. On This browser (and Both) the page seeks back to A at B, with a small gap. It never touches the live decks; Stop, Loop off, closing the dialog, a seek or a new play ends it; it is off at every open.
- **Trim dialog on a phone:** full-screen sheet with sticky header (title, path, close) and footer (Cancel, Save and a trash button, *Remove trim*, same action as on a desktop, no confirmation), tabs, waveform with round grips (24 px touch tolerance), one Nudge step control, cards for A and B (`- time +`, Set at playhead, Reset, Precision, fade row with `- n s +`, Use default), the Preview section with an **Output** menu, the two notes; targets at least 44 px.

### rc2
- rc2: Library header stays on one row; Hidden button is icon and count only; header buttons are plain icons (Expand all and Collapse all icons changed); storage text shortens on phones. Playing row: loudness pill back in its normal column; progress line no longer runs under the left stripe; the trim, trigger and crossfade badges move to the second line next to the elapsed text (the least important are hidden when it is too short, and listed in the row's title); compact icons in the stage skin at narrower widths.

### Changed
- **Playlist header:** the line reads `Track N of M` (capital T); the mode pill (Stop at end, Loop, Shuffle, Next playlist) shows only while the playlist is collapsed (expanded, the Playlist behavior menu already says it); expanding does not move the bar.
- **Track rows:** the played check and the green in-RAM dot are gone (the blue decoding ring and the hollow not-loaded ring stay; played tracks are still dimmed). The playing row keeps all seven buttons on one line in the same place as the other rows (loudness and `elapsed / length` moved under the name); the quick-flag stripe is visible on the playing and cued rows and the progress line sits under it, inside the corners. From 34 rem rows do not wrap (the name shrinks instead); in the stage skin the buttons tighten on a narrow row.
- **On phones the Preview Output now defaults to "This browser"** when no choice has been made yet (before, a phone used the player's preview output whenever one existed). A choice already made is kept. The player's output stays in the list.
- **On phone widths library rows wrap** their buttons under the name (they were wider than the column in the studio and stage skins and widened the whole page).
- Number fields: the Settings "Default fade-in at A" field keeps its width.
- Golden pages regenerated (library header and folder rows, trim dialog, `flags`, version).

### Known issues
- **Phone layout is a later pass.** At 320-360 px the page itself is still a few pixels wider than the screen outside the trim dialog (library header, the Cue panel's Go group, some playlist columns); track rows on a phone are not reworked; the playing row's badges sit after the elapsed time there.
- Loop A-B on This browser has a small gap at the wrap (the player's preview output has none).
- Ducking runs at full depth while a track on top fades in.

### Tests
- New: `tests/api/test_library_flags.py`, `tests/engine/test_fade_in.py`, `tests/api/test_preview_loop.py` (worker loop capture, loop op validation), two audio-capture checks in `tests/api/test_audio_capture.py` (fade-in curve; a Cut start is bit-identical to the file), fade-in cases in `tests/api/test_trim_fade.py`; stand-alone Playwright scripts `tests/test_library_flags_ui.py`, `tests/test_playlist_header_ui.py`, `tests/test_trim_phone_ui.py`; `tests/test_trim_dialog.py`, `tests/test_plist_progress_ui.py` and `tests/test_ram_ui.py` extended or updated.

## 2.7.3

RAM indicator and playlist progress (web page only). The Companion module stays at 2.7.0: no Companion variable changed, and none of the new state goes to Companion.

### Added
- **RAM indicator:** a small header pill left of Cache (ring / tick / Full with N/M), a marker before each track name (filled green = in RAM, spinning ring = loading, hollow ring = not loaded), "N of M in RAM" per playlist, and a "Loading... N s" state on the Cue Go button while the cued track is decoded (display only). Data: `ram` in `/api/state`, `ram`, `ram_in`, `ram_total` in `/api/playlists` (`warm.ram_info()` / `ram_states()`, one pass, cached 1 s, read-only: `cache.ram_snapshot()` never touches the LRU order).
- **Playlist progress:** header text (track N of M, played, left, end time), a mode chip and a segmented bar (one segment per track, proportional to the A-to-B window; continuous above 40 tracks); played rows dimmed with a check, the playing row shows elapsed / length and a thin line. Loop shows the time left in the current lap, Shuffle the time left in the round, Next playlist the name of the next one. Data: `dur_eff` per track and `shuffle_left` per Shuffle playlist in `/api/playlists`; the sums are made in the page.
- Help page sections "RAM indicator" and "Playlist progress"; two tour steps.

### Changed
- Phone width: the header wraps; the RAM indicator, Cache and RAM get their own row under the title.
- rc2: RAM indicator collapsed to a small pill left of Cache; header order Cache, RAM; RAM text shows units on both numbers.
- Golden pages: the timing-dependent `ram` / `ram_in` values are masked (`tests/harness/golden.py`).

### Housekeeping
- `dist/companionplayer-2.7.1.zip` removed from the tree; `dist/` is ignored. CLAUDE.md records the promotion rule for `main`.

### Notes
- The `v2.7.1` tag points at pre-split code (2.7.0). The real 2.7.1 is `7d5f42c` (`v2.7.1-rc2`). Use `v2.7.2` or later. (The tag is not moved.)

## 2.7.2

Polish release (web page only), built on `release/2.7.1` (the `cpl/` split). The Companion module stays at 2.7.0 (same major.minor, `version_match` stays `ok`); no API field, variable name or command changed. 2.7.1 added the deploy scripts only.

### Changed
- **"Measuring" is now "Analyzing":** the library row hint, the preview information chips ("LUFS analyzing…", "peak analyzing…", "analyzing…"), the file information popover and the waveform placeholder ("Analyzing waveform…") get a small pulsing dot (still, with reduced-motion). The API status value `measuring` is unchanged.
- **Mute and Solo buttons:** a fixed 6 px corner radius in every skin (Studio and Stage made them circles). The Live meter now reads bars, "L R · dBFS", then M and S, centred under the two bars; the card is about 3 px shorter.
- **Reduction meter (Ducking):** a full-width 22 px amber bar with a 0 to -30 dB ruler and a large monospace readout (amber while ducking, dim at -0.0 dB). The value feed is unchanged.
- rc3: Reduction meter back on the Input Gain row as a slim red meter; "Stay ducked until it ends" moved to the Ducking heading.
- rc3: the Cue panel's Trim button uses the same bracket icon as the playlist rows (the "A–B" text is gone).
- rc4: the Cue panel's per-track crossfade field shows its "s" unit inside the field's box (same size; the Go column is unchanged).
- **Preview output menu:** same markup and style as the Live Output menu (headphone icon, "Output", full width on its own row, full name in the tooltip); Pause, Stop, seek and time sit on the row below.
- **Meter scale:** Live and Preview use one tick list and one formatter: `0 -5 -10 -20 -30 -40 -50 -60 -∞` (in `cpl/legacy.py`: `METER_TICKS`, `meter_label`; placeholder `@@SCL@@`; `METER_TICKS_SMALL` and `@@SCL_BIG@@` / `@@SCL_SMALL@@` are gone). Taper unchanged.

### Tests
- New Playwright tests: `tests/test_mute_solo.py`, `test_reduction_meter.py`, `test_preview_output.py`, `test_meter_scale.py` (they start their own player and are not part of `tests/run.py`).

### Superseded
- `v2.7.2-rc1` was built on the wrong base (pre-split main) and is superseded by `v2.7.2-rc2`.

## 2.7.1 (release candidate 2)

Internal release: the code is split into the `cpl/` package. **No change in behaviour**: every moved function was proved identical to the 2.7.0 code with a normalised-AST comparison (`tests/tools/verify_move.py`), the pages and API outputs are byte-identical apart from the version number (golden hashes), and the whole test suite passes. Built from the commits since 2.7.0 on the `split` branch (merged into `release/2.7.1`) and `docs/known-failures.md`.

### Verified for this candidate (macOS test machine)
- Full suite twice in a row: 475 passed, 1 skipped (the memory readout is not implemented on macOS), plus 38 trigger tests with a fake clock, the golden page hashes, the static gates, the launcher, module-version and cold-start scripts. Without ffmpeg (`"ffmpeg_path": "/nope/ffmpeg"`): 474 passed, 2 skipped (the deep format check skips; the page-equality script compares ffmpeg-derived format information, so it only holds with ffmpeg).
- Cold start on a clean folder; on a folder with playlists (trim, crossfade time, end action, trigger point) and `resume.json` after a hard kill; and a folder written by 2.7.0 started with 2.7.1 (settings identical, the track resumes).
- The first milliseconds of a track on the live output, captured with the disk audio driver (117 runs per build, `tests/tools/onset_capture.py`): intact in every measured run on 2.7.0 (115) and on 2.7.1 (116); the few runs that did not start under 4 parallel jobs (2 on 2.7.0, 1 on 2.7.1) ran fine when repeated serially on both. The Solo monitor's late start is the same on both (see below).
- **Not yet checked: the NUC (Linux, Dante output) and Windows.** Do the manual checks of `docs/split-plan.md` section 6 there before calling it final.

### Deploying this release
- **Copy `player.py`, the new `cpl/` folder and `static/` together**, replacing the old ones completely. The player exits with a clear message when `cpl/` or `static/` is missing or incomplete. `deploy/deploy.sh` and `deploy/deploy.ps1` copy all three (the Windows script also copies `run-player.bat`).
- **Windows: use the new `run-player.bat`.** It installs the requirements only when `requirements.txt` changed since the last successful install (a stamp file `.venv\requirements.installed`), so a normal start no longer waits for pip; when pip cannot update (for example with no internet) it carries on if the core packages are already installed instead of stopping; and it checks for `cpl\` and `static\` next to `player.py`. The macOS `run-player.command` is executable and checks the same folders.
- The **Companion module stays 2.7.0** (`companionplayer-2.7.0.tgz`): player 2.7.1 and module 2.7.0 share major.minor, so the module's version check says `ok` (covered by `tests/test_module_version.py`).
- Settings, playlists, library, `state.json` and `resume.json` are read as before; nothing needs converting.

### Changed (internal)
- **`player.py` is a 31-line launcher** (it was 7,788 lines before 2.7.0 moved the web pages to `static/`, and 5,490 in 2.7.0). The program is in `cpl/` (5,825 lines in 26 files): `clock` (the one time source), `util`, `dsp`, `config`, `state` (the shared state and three hook lists), 15 modules (`persist, cache, devices, durations, infostore, ffmpeg, playlists, library, triggers_data, loudness, formats, warm, fileinfo, upload, boot`), `helpers/` (the four child-process entry points) and `legacy.py` (2,740 lines: the part not split yet, see below).
- The helper processes (`--probe`, `--decode`, `--dl`, `--preview`) start from `cpl/helpers/` and import no web or OSC code.
- The player's tests moved with it: 475 automated tests plus the static gates (import graph, shared state, hooks, launchers, module version), including new tests for resume after a kill, fades and crossfades with a fake clock, auto-advance, ducking numbers, tick order, rename/move of a track with its settings, MP3/FLAC upload, the file-information popover, and a test that captures the real rendered output (`SDL_AUDIODRIVER=disk`) to check crossfade shape, loop points and ducking depth.

### Fixed
- **`run-player.bat` was empty in the repository** since the deployment-scripts commit; a Windows deploy of that commit would have overwritten a working launcher with an empty file. Replaced by the new launcher described above (the one added on `main` in `b6d4fcc`), and `tests/test_launchers.py` now fails if a launcher or deploy script is empty, if the `.bat` does not use CRLF, or if `run-player.command` is not executable.
- `run-player.command` was not marked executable in git.

### Known, not changed (found by the new tests; see `docs/known-failures.md`)
- The Solo monitor and the Mirror output start playing a new live track 90 ms to about 0.6 s late, so their first samples are missing there; the live output is intact (measured on 2.7.0 and the split build: identical).
- The `--preview` helper (headphones / Solo / Mirror) sometimes ends with a crash (SIGSEGV) or a traceback from its status thread when the player closes it a moment after a command (2 to 8 of 300 closes in a stress loop that does exactly that; the same code ran in 2.7.0). Only the helper process is affected, at its exit; the player starts a new one when it needs it.
- A track whose file is deleted after it was decoded is flagged "missing" but still plays from memory until it is evicted or the player restarts.

### Not in this release
- The rest of the Python split (**transport, tick, meters, preview, state-out, commands, web handlers, download and `main()`** are still in `cpl/legacy.py`): deferred; the plan, its status and what it needs first are in `docs/split-plan.md`.
- Serving the UI pieces as separate URLs with caching headers; Companion module support for a track's own crossfade time.

## 2.7.0

Built from the git history since the tag `pre-split` (25 commits) and `docs/known-failures.md`.

### Deploying this release
- **Copy `player.py` and the new `static/` folder together** (the web pages are files now; the player exits with a clear message if `static/` is missing). `run-player.bat` checks for it too.
- Install the Companion module `companionplayer-2.7.0.tgz` (in `companion-module/`) with this player. A module and player with different major.minor are not tested together; the module then logs a version warning.

### New
- **Product version.** One constant, `APP_VERSION`, shown as a line at the bottom of Settings (`CompanionPlayer 2.7.0`), as `version` in `/api/state`, and as the Companion variable `mp_player_version` (also on the variables page).
- **Companion module 2.7.0:** compares the player's major.minor with its own; on a difference it writes one warning to the Companion log and sets the module variable `version_match` (`ok`, `mismatch`, `unknown` for a player that reports no version). Nothing else in the module changed.
- **Keyboard shortcuts for the A/B waveform** are documented in the Help page (Left/Right nudge, Shift 1 s, Alt 0.01 s, Up/Down choose marker, Delete removes a trigger).
- **Development aids** (no effect on a show): `CP_DEV_UI=1` re-reads `static/` on every page load; `CP_TEST_DEVICES` test hook; golden-page regression test (`tests/test_pages_equal.py`), CRLF test, trim-dialog Playwright test; test baselines `tests/reports/baseline-pre-split/` and `baseline-post-fixes/`.

### Changed
- **The web UI lives in `static/`** (`index.html`, `style.css`, `app.js`, `icons.js`, `tour.js`, `help.html`, `stage.html`, `variables.html`) instead of strings inside `player.py` (7,788 to about 5,500 lines). The page the browser receives is byte-for-byte the same as before the move.
- **Trim dialog:** the −/+ buttons beside the fade length are gone; the field keeps its native spinner arrows (larger on touch screens), the Up/Down keys and typing, and Up/Down now keeps repeating. The long hint under the waveform is removed (the shortcuts are in Help). Number and time fields (fade, A/B, trigger times, cue crossfade) are sized so the maximum value is no longer clipped, in all skins, on phones and on touch layouts.
- **Stop-all clears ducking at once:** after `/stop` or `/stopall` the duck depth (`duck_gr`, the meter) drops to 0 immediately instead of fading out over the release time. Nothing is playing then, so nothing audible changes.
- `static/` files with CRLF line endings are read as LF, so a Windows checkout still serves the identical page.
- Playlist names are limited to 80 characters when created (as they already were when renamed).

### Fixed
All 38 failures found by the first full test run (`docs/known-failures.md`):
- **Audio:** after stopping all while a Play on Top was ducking, the leftover duck depth could turn down the background track of the next Play on Top (even with threshold 0 dB). 
- Commands with characters such as `²` (accepted by `isdigit()` but not by `int()`) in a path no longer cause HTTP 500 (11 tests).
- `inf`, `-inf`, `nan`, `1e999` in crossfade time, trim In/Out/fade, level-match LUFS, volume, seek, duck steps, preview volume, the transition settings and OSC `ms` are refused or ignored instead of raising an error or being stored (4 tests plus other places).
- A non-numeric or decimal playlist/track number in `/api/playlists/<p>/...` gives 404 instead of 500 (10 tests).
- Malformed bodies of `/api/playlists/<p>/add` (files `null`, a number, a bad `index`) and an upload without a multipart body give 400 (4 tests).
- `/api/preview/ctl` with a non-numeric or non-finite `seek` or `vol` gives 400 (6 tests).
- The descriptions of the variables `focus_t0` to `focus_t31` were missing the track number.
- Playlist names of any length were accepted on create.

### Not in this release
- The **Python split** (`cpl/` modules, the launcher): `player.py` is still one file for all code, with `static/` beside it.
- Serving the UI pieces as **separate URLs** with caching headers; `/` is still one assembled page.
- **Companion module support for a track's own crossfade time** (`/<p>/<t>/xftime`, `xfade` in `/api/playlists`).
- **Companion variables for the resource monitor** (RAM, cache); it is shown only in the web page, and the memory readout is not implemented on macOS.
- **macOS** launcher, startup entry and memory readout.
- The UI scale audit proposal (`docs/AUDIT-ui-scale.md`) is not implemented.
- No new audio-capture or long-run stress tests; the Playwright tests cover the trim dialog, layout sharing, devices, live output and the move button only.
