# Companion variables and settings

How the player feeds Bitfocus Companion, the meter variables, playlist-name variables and troubleshooting.

## Feedback into Companion
The player sends OSC to Companion's OSC listener (Settings > Protocols, default port 12321),
setting these **custom variables**. Create each one in Companion (Variables > Custom Variables):

`mp_focus_name`, `mp_focus_id`, `mp_focus_playlist`, `mp_focus_playlist_num`, `mp_focus_is_live`,
`mp_live_name`, `mp_live_id`, `mp_remaining` (mm:ss), `mp_state` (`playing` / `paused` / `fading` / `loading` / `stopped`),
`mp_loading` (name of a track being prepared, or `-`),
`mp_live_fader_l/r`, `mp_live_db_l/r`, `mp_live_meter_l/r`, `mp_preview_fader_l/r`, `mp_preview_db_l/r`, `mp_preview_meter_l/r` and the legacy `mp_live_level_l/r`, `mp_preview_level_l/r` (level meters, see below),
`mp_preview_state`, `mp_preview_playing` (1 while a preview plays, else 0), `mp_preview_remaining`, `mp_preview_name` (the preview output),
`mp_play_mode` (end-of-track mode of the focused playlist: `stop` / `loop_playlist` / `next_playlist` / `shuffle`),
`mp_input_armed`, `mp_input_duck_now`, `mp_input_signal`, `mp_input_ducking` (the Live input, 1 / 0),
`mp_output` (name of the current output device), `mp_player_version` (the player's version, e.g. `2.7.0`),
`mp_storage_free` (free disk space, e.g. `29.9 GB`), `mp_storage_library` (library size, e.g. `2.1 GB / 10 GB` when a cap is set)

Use them in button text, e.g. `$(custom:mp_live_name)  $(custom:mp_remaining)`.
Companion connection: Generic OSC, target = this machine, port 9000. If Companion runs on another computer, set its
address in **⚙ Settings** on the web page (see below).
The player resends every variable every 5 seconds, so Companion catches up after a restart or after you create a variable.

**One button for pause and resume:** send `/playpause`. Put `$(custom:mp_state)` on the button text (or use it in a
feedback) to show `playing` / `paused` / `stopped`.

### Level meters
The web page shows stereo level meters for the live output and for the preview, on a **console-fader taper** from -inf to 0 dBFS.


The same levels go to Companion as variables, for **live** and **preview** (shown for live, the same with `mp_preview_`):
- `mp_live_fader_l`, `mp_live_fader_r`: 0-100 position on the taper (use these for gauges).
- `mp_live_db_l`, `mp_live_db_r`: the level in dBFS as text with one decimal, `-inf` when silent.
- `mp_live_meter_l`, `mp_live_meter_r`: a text bar such as `█████░░░`, which follows the taper.
- `mp_live_level_l`, `mp_live_level_r`: **legacy**, 0-100 on the old linear -60..0 dBFS scale, unchanged for existing buttons.
- Put `$(custom:mp_live_meter_l)` and `$(custom:mp_live_meter_r)` on two lines of a button for a stereo bar. Companion has no
  true bar graphic for variables, so this is the closest it gets.
- Companion is sent at most `meter_rate_hz` updates per second (default 4) and only when the value changed; nothing is
  sent while the audio is silent. Set `"meter_rate_hz": 0` to stop sending meters (the web meters are unaffected). On a
  busy or small Companion machine keep it low.
- The levels are the peaks of the audio files at the playback position, including fades and crossfades, so they show what is
  being sent to the output rather than reading the output device itself. Preview meters follow the preview volume.
- Meters need `numpy` (in `requirements.txt`; run `pip install -r requirements.txt` after updating). Without it everything
  else works and the meters stay at zero.


### Variables page
Open **⚙ Settings > Companion > View** (or go to `http://<player>:8080/variables`) to see every variable the
player sends, with its live value and what it means. Use **Copy all names** to get the full list for creating the
custom variables in Companion. This shows what the player is sending; it can't confirm that Companion received them.

### Settings page (⚙ Settings, top right of the web page)
Four tabs on a computer (**Look**, **Audio**, **Companion**, **System**); on a phone or touch panel one column of closed sections, each with a one-line summary of its value and a search box, one open at a time. **Everything saves as you change it** (there is no Save button), and a short (i) beside a setting holds one sentence of explanation.
- **Look** (Style, Theme, Show waveforms, Time warnings, New folder icon: this browser only, except Time warnings and the folder icon, which the player keeps; Layout: Edit layout, and a More menu with Reset, Export and Import).
- **Audio:** Preview plays on (This browser / Player output / Both) and the player output device, Mirror live to a second device (its device menu appears under the switch), Transitions (Default, Crossfade time, Fade-in at A, Fade-out at B). Output lists refresh each time they open.
- **Companion:** Address and OSC port (where the variables go). The address is checked when you leave the field: an incomplete one such as `192.168.1.` shows a warning and the last good address stays in use (the **Sending to** chip shows the one in use). Valid values are applied at once and written to `config.json` (all your other settings in that file are kept); a well-formed host name that can't be found right now (offline, Companion not up yet) is still saved: an amber note says so and the player keeps trying; it is not looked up when saved. **Variable prefix** (default `mp_`; config key `var_prefix`, an existing config.json is read as before) is put in front of the name of every variable the player sends (`mp_live_name`, `mp_remaining`, ... in this README mean *prefix + name*). Letters, digits and underscores, starting with a letter, 1 to 16; checked when you leave the field, with a live example (`Example: mp_remaining`); a trailing underscore is your choice and is not added for you. Changing it asks for a confirmation (buttons and triggers using the old names must be updated; the old variables stay in Companion until the module is reloaded), then saves it and sends every variable again under the new names. `POST /api/settings/prefix` `{prefix, confirm:true}` (409 without `confirm`), `variable_prefix` in `/api/state`, `GET /api/variables` has `prefix`. The Companion module follows the player's prefix. **Send test** sends `<prefix>test` (`mp_test` by default) = the current time (`HH:MM:SS`) to the address in use with the same sender as the live variables, and reports *Test sent* or *Couldn't send* with the reason. OSC gives no reply, so it only confirms the player sent it: check that `mp_test` shows up in Companion (create the custom variable `mp_test` first; the Companion module 2.7.5 also has a module variable `mp_test` that shows the last test). **View** opens the variables page, **Resend now** pushes every variable again (it does not send `mp_test`). API: `POST /api/settings/companion/test` returns `{ok, sent_to, at}` or `{ok:false, error}`; `/api/state` has `test_message` and `test_sent_at` (reported for two minutes after the test, then empty; the Companion module has no OSC input, so its `mp_test` variable reads this).
- **System:** Rescan the library, File check (result chip), Help guide, Tour, the ffmpeg chip, Restart player and the version.

### If a variable in a button stays empty
The player's log shows where it sends: `variables out -> host:port`.
1. **Same computer?** The address defaults to `127.0.0.1`, which only works when Companion runs on the same
   machine as the player. If Companion is on another computer (for example a Raspberry Pi), open ⚙ Settings and
   enter that machine's IP address.
2. **OSC listener port.** In Companion open Settings > Protocols > OSC and make sure it is listening
   (a non-zero port). The number must match the OSC port in ⚙ Settings (default 12321).
3. **Variable names** must match exactly, including the prefix: `mp_live_name`, not `live_name`.
   Create them under Variables > Custom Variables first.
4. **Firewall:** the machine running Companion must allow incoming UDP on that port.
5. Click **Resend now** in ⚙ Settings > Companion after fixing any of these.

## Playlist and track name variables
Besides the live and cue variables, the player sends the names in every playlist: `mp_pl<N>_name` (playlist name), `mp_pl<N>_count` (number of tracks) and `mp_pl<N>_t<K>` (name of track K), where N and K are the same numbers used in `/<playlist>/<track>` commands. `mp_focus_playlist_num` is the number of the focused playlist, so a Companion button can build the name it needs, for example `$(custom:mp_pl$(custom:mp_focus_playlist_num)_t0)` for the first track of whichever playlist is focused. When a track or playlist is removed its variable is set to `-`. They are listed on the **View variables** page.

### Focused playlist window
`mp_focus_t0` to `mp_focus_t31` always hold the track names of the **focused** playlist, in order, and `mp_focus_count` its number of tracks. Unused slots are `-`. Create these 33 variables in Companion once and a page of buttons (`$(custom:mp_focus_t3)`) follows whichever playlist is focused, with no nested variables.
