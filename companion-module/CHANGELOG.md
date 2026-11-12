# Changelog

## Rename (version unchanged)
- The module is now named *Cue Media Engine* (short name CueME). Manifest id `cue-media-engine`, the old id `companionplayer` is in `legacyIds`. Names, descriptions and the config label changed; actions, feedbacks, presets, variables and the polling are unchanged. The `X-CompanionPlayer-Client` header is kept (the player recognises it).

## 2.8.0
- Player health (needs player 2.8.0; with an older player the new variables stay empty and the feedback never fires): variables `health_state` (`starting`, `ready`, `degraded`, `problem`) and `health_text` (a short reason such as "Disk space low", empty when ready), under the player's variable prefix; the boolean feedback *Player health* (reacts to Degraded, Problem, or Degraded or problem; default style amber with dark text, the preset uses red with white text for a problem); and the preset *Health* (category Health, text size 14) that shows HEALTH and the reason and turns amber or red.
- Every request now carries the header `X-CompanionPlayer-Client: companion-module`, so the player can tell the module's polls from a browser's (its Companion check says "not answering" after 30 s of silence).
- Version: module 2.8.0 goes with player 2.8.0 (major.minor must match; the module's patch number is its own counter and 2.8.0 is the first of the 2.8 line). `npm test` runs `test/health.test.mjs` (variables, feedback in each state, preset, a player without `health`, the header).

## 2.7.12
- *Input armed toggle* preset: the button text is size 14 again (the string `'14'`, like the other presets) in both looks, the default (unarmed, green) and the armed feedback style (red), from one constant. Tested on a real Companion button. 2.7.11 had 26. Texts, colours, the press action, the feedback logic, ids and variable names are unchanged.

## 2.7.11
- *Input armed toggle* preset: the button text is size 26 (a number; Companion's own list has 24 and 30, the module API accepts any number) in both looks, the default (unarmed, green, INPUT / UNARMED) and the feedback style (armed, red, INPUT / ARMED), so INPUT / UNARMED does not wrap. The size was 14 before. Texts, colours, the press action, the feedback logic, ids and variable names are unchanged. Unit test: size 26 in both looks.
- Needs the same player as 2.7.10. Whether the text fits on a real button can only be seen on one (the unit test cannot show it).

## 2.7.10
- *Input armed toggle* button (Live input presets): green with white INPUT / UNARMED when the Live input is not armed, red with white INPUT / ARMED when it is. Press = toggle. The armed look stays red when the device is missing (armed is kept). With no state from the player yet the button shows the unarmed look.
- Feedback *Live input is armed* is now *Input armed* with the red look as its default style (it followed the state before, with a green default). The action `input_armed` is now named *Input arm / disarm* with the choices Toggle, Arm, Disarm (the values `toggle`, `on`, `off` and the id are unchanged). The Live input presets moved to their own category *Live input*. No action, feedback or variable id was renamed.
- `npm test` (node --test) runs unit tests of the button (`test/armed-button.test.mjs`).
- Needs player `v2.7.5-input-stereo` or newer for the stereo-pair state; the button itself works with any player that has the Live input.

## 2.7.9
- Live input rc2: *Duck now* is a manual override. It works with or without an input device, whatever Armed is, and the loss of the input does not switch it off; `input_duck_now` is `1` for as long as it is on. The player no longer answers "no input" to it. The *Duck now is on* feedback and the *DUCK NOW* preset need nothing else. Needs the player at `v2.7.5-input-rc2` or newer; with rc1, Duck now is refused while there is no input.

## 2.7.8
- Live input (Duck only), needs player 2.7.5 (`v2.7.5-input-rc1` or newer): new actions *Live input: Armed* and *Live input: Duck now* (toggle / on / off, they send `/input/armed/<v>` and `/input/ducknow/<v>`), feedbacks *Live input is armed*, *Duck now is on*, *has signal* and *is ducking the playlist audio*, and presets *INPUT ARMED*, *DUCK NOW* and *INPUT signal/ducking* in the Ducking section.
- New variables from the player (declared automatically from `/api/variables`, under the player's variable prefix): `input_armed`, `input_duck_now`, `input_signal`, `input_ducking` (1 / 0). With an older player they do not exist and the actions answer "invalid".
- The module's number is its own counter (2.7.8: the next above the highest published, 2.7.7); the player stays at 2.7.5. It needs only the matching major.minor, 2.7.

## 2.7.7
- The variable prefix now comes from the player (`variable_prefix` in `/api/state`, set in the player's Settings > Companion). The module declares all its variables, and the presets that show them, with that prefix and declares them again when it changes. With the default prefix (`mp_`) nothing changes. When the player does not report a prefix (older than 2.7.5 rc3) the module uses the prefix in its own configuration, then `mp_`; the configuration field is now labelled as that fallback. Needs the player 2.7.5 rc3 or newer for the automatic prefix. Nothing else changed.

## 2.7.6
- `mp_test` no longer relies on the message text alone: the module reads `test_message` and `test_sent_at` from the player and only takes a value when `test_sent_at` is new (details under 2.7.5). Needs the player 2.7.5 rc2 or newer for `test_sent_at`; with rc1 `mp_test` stays empty. Nothing else changed.

## 2.7.5
- New module variable `mp_test` ("Test message", empty by default). It shows the value of the last *Send test* made from the player's Settings > Companion (the time, `HH:MM:SS`). The module cannot receive OSC (it polls HTTP), so it reads `test_message` and `test_sent_at` from the player's `/api/state`. `mp_test` takes a value only when `test_sent_at` is new; while it stays the same the value is kept, and when the player reports nothing (no test yet, a restart, or two minutes after the test, when the player clears it) `mp_test` is empty. An old time therefore never shows as a fresh test. No action or feedback is involved; no other variable, action or feedback changed. Version now matches the player's 2.7 line.

## 2.7.0
- Version check: the player now reports its version (variable `player_version`, also `version` in its state). The module compares the player's major.minor with its own and, when they differ, writes one warning to the Companion log and sets the new module variable `version_match` to `mismatch` (`ok` when equal, `unknown` when the player reports no version, e.g. a player older than 2.7). Nothing else changed. Use with player 2.7.x.

## 2.6.1
- New action *Preview volume* (set / up / down) using the player's `/preview/volume/...` command, and presets *Preview volume* (shows the new `preview_volume` variable), *up*, *down* and a rotary. While Solo live is on the preview volume is the level you hear. Nothing changed or removed.
- Needs a player with the Solo volume change; with an older player the action does nothing.

## 2.6.0
- New variables from the player (they appear automatically): `live_fader_l/r`, `preview_fader_l/r` (0-100 on the console-fader meter taper), `live_db_l/r`, `preview_db_l/r` (dBFS text), `go_transition`.
- Changed presets: the live and preview monitor gauges use the fader variables, with colour stops computed from -17 dBFS (amber) and -6 dBFS (red) through the taper (64.8 and 85.6, were 72 and 90 on the old linear scale). The text-meter button follows the new bars. New presets: *Meter in dBFS*, *Go button mode*.
- New action *Web page Go button: cut or crossfade* and feedback *Web page Go button mode is*. *Cue: Take*, *Cue: Crossfade* and every other action are unchanged.
- Legacy variables `live_level_l/r` and `preview_level_l/r` are kept (documented as legacy in HELP.md). Nothing was removed.
- Needs a player with the console-fader meters; with an older player the fader and dB variables stay empty and the gauges show nothing.

## 2.5.0
- Playlist and track end actions: actions *Play playlist*, *Track end action*, *Live: End action of the live track*; feedbacks *Track end action is*, *Live track end action is* and the loop-once / stop choices of the slot feedback; module variables `live_end` and `live_pass`; presets for the live end action, the cued playlist's Play button, and per-playlist PLAY and per-track END ACTION buttons. The loop actions now mean loop forever.

## 2.4.1 and earlier
- See the packages in the Module folder; no changelog was kept before 2.5.0.
