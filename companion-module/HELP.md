# Cue Media Engine

Controls a Cue Media Engine (CueME) player over its HTTP API.

**Configuration**
- **IP address / Port**: where the player's web UI runs (default port 8080).
- **Variable prefix (fallback)**: the player tells the module which prefix it sends its variables under (set in the player at Settings > Companion > Variable prefix; default `mp_`), and the module follows it. This field is only used when the player does not report one (a player older than 2.7.5 rc3). Use a different prefix per player, e.g. `foh_` and `stage_`, if you run several. Connection labels already separate them too: `$(foh:foh_live_name)`.
- **Poll interval**: how often state is read (ms).

**Playlist and track end actions** (needs a player with end actions, i.e. the Playlist behavior / Play button release)
- Action *Play playlist* starts a playlist (or the cued one) from its first track; *Track end action* and *Live: End action of the live track* set or cycle next / loop once / loop forever / stop. *Loop on/off* actions now mean loop forever.
- Feedbacks *Track end action is* and *Live track end action is*; extra variables `live_end` (NEXT / ONCE / LOOP / STOP) and `live_pass` ("1 of 2" while a loop-once track plays).
- Presets: *End action of the live track*, *Play the cued playlist*, and in every playlist section a PLAY button and an END ACTION button per track.

- **Live input (module 2.7.8, player 2.7.5 with the Live input):** actions *Live input: Armed* and *Live input: Duck now*, feedbacks for armed / duck now / signal / ducking, the presets *INPUT ARMED*, *DUCK NOW*, *INPUT signal/ducking* (Ducking section) and the variables `input_armed`, `input_duck_now`, `input_signal`, `input_ducking` (1 / 0). Duck now is a manual override: it works with no input and stays on when the input is lost, until it is switched off (player rc2 and newer; rc1 refused it without input).

- **Input armed toggle (module 2.7.10, text size 14):** a preset in the *Live input* category. Unarmed is a green button with white INPUT / UNARMED, armed is red with white INPUT / ARMED; press to toggle (the same Armed setting as the switch on the web page, in Settings and in the Cue container, within one poll). The variable `input_armed` is 1 (armed) or 0 (unarmed).

- **Player health (module 2.8.0, player 2.8.0):** variables `health_state` and `health_text`, the feedback *Player health* (Degraded, Problem, or either) and the preset *Health* (category Health): amber when the player is degraded, red on a problem. With an older player the variables are empty and the feedback does not fire.

**Version check**: the module and the player have the same major.minor version (this module 2.8 goes with player 2.8.x). When they differ, a warning is written to the Companion log and the variable `version_match` (`$(connection:mp_version_match)`) shows `mismatch`; `unknown` means the player is too old to report a version. `mp_player_version` shows the player's version.

Variables, playlists and track buttons are created automatically. Playlist presets refresh when you add, remove or rename tracks.

**Level meters (player with the console-fader meters)**
- `live_fader_l/r`, `preview_fader_l/r`: 0-100 position on the player's console-fader taper (0 dBFS = 100, -10 = 76, -20 = 60, -40 = 33, -60 = 10, -inf = 0). The monitor presets' gauges use these, with the amber stop at -17 dBFS (64.8) and the red stop at -6 dBFS (85.6).
- `live_db_l/r`, `preview_db_l/r`: the level in dBFS as text with one decimal (`-inf` when silent).
- `live_meter_l/r`, `preview_meter_l/r`: text bars, now following the same taper.
- **Legacy:** `live_level_l/r` and `preview_level_l/r` are kept unchanged (0-100 on the old linear -60..0 dBFS scale) so existing buttons keep working. Use the fader variables for new buttons.

**Go button mode**
- Variable `go_transition` (`cut` or `crossfade`), feedback *Web page Go button mode is*, action *Web page Go button: cut or crossfade* and the preset *Go button mode*. This only sets what the Go button on the player's web page does; the *Cue: Take* and *Cue: Crossfade* actions are unchanged.

**Preview volume**
- Action *Preview volume* (set, up or down, in %) and the variable `preview_volume` (0-100). While Solo live is on this is the level you hear on the preview output. Presets: *Preview volume*, *up*, *down* (amber while solo is on) and a rotary for Stream Deck+.
