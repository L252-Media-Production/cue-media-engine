# OSC and HTTP commands

Every command the player accepts on UDP 9000 and over HTTP.

## Commands (OSC to this machine, UDP 9000)
IDs start at 0: `/0/1` = second track of the first playlist.

| Address | Action |
|---|---|
| `/0/1` | Make track live, using `default_transition` (cut or crossfade) |
| `/0/1/cut` | Make live instantly, replacing whatever is playing |
| `/0/play` | Play playlist 0 from its first track (a random one when its behavior is Shuffle), like Go on that track |
| `/0/1/xfade` | Crossfade from current output to this track |
| `/0/1/toggle` | Toggle that track live / off |
| `/0/1/focus` or `/0/1/cue` | Move the cue (the "up next" track) there without playing |
| `/clear` | Clear the cue: nothing is up next, and `/take` `/xfade` `/cut` `/toggle` do nothing until you pick a cue again (click a row, `/0/1/cue`, or `/next` `/prev`). Variables `mp_focus_id` / `mp_focus_name` show `-` meanwhile |
| `/next` `/prev` | Move the cue within playlist (wraps), never plays |
| `/nextlist` `/prevlist` | Move the cue to another playlist |
| `/take` | Make the cued track live (default transition) |
| `/cut` `/xfade` | Make the cued track live with that transition |
| `/toggle` | Toggle the cued track live / off |
| `/mode/stop` `/mode/playlist` `/mode/shuffle` `/mode/continue` | Set what happens when a track ends, for the **focused** playlist (see Play modes) |
| `/0/mode/shuffle` | Same, for a specific playlist (here playlist 0) |
| `/0/1/xftime/1.5` `/0/1/xftime/clear` | Set or clear this track's own crossfade time (seconds, used when it is crossfaded into) |
| `/0/1/loop` `/0/1/loop/1` `/0/1/loop/0` `/loop` | Toggle or set looping forever of one track (or the focused track) |
| `/0/1/end/default` `/once` `/loop` `/stop` | What that track does at its end; `/0/1/end` with no value steps to the next setting (default, once, loop, stop) |
| `/0/1/in/12.5` `/0/1/out/200` `/0/1/end/cut` `/0/1/end/fade` `/0/1/trim/clear` | Set the A or B point (seconds), what happens at B, or remove the trim |
| `/mode/next` or `/0/mode/next` | Cycle that playlist through the modes (one Companion button) |
| `/preview/0/1` | Play that track on the preview output only (see Preview output) |
| `/preview/focus` | Toggle: preview the focused track, or stop if that track is already being previewed |
| `/preview/stop` `/preview/pause` `/preview/resume` `/preview/playpause` | Control the preview |
| `/preview/volume/60` `/preview/volume/up` `/preview/volume/down/10` | Volume of the preview output, 0-100 (with Solo live on, the level you hear) |
| `/pause` `/resume` `/playpause` | Pause / resume (also freezes the countdown and any fade) |
| `/fadeout` | Fade everything out, then stop |
| `/volume/<0-100>` `/volume/up[/n]` `/volume/down[/n]` `/volume/mute` | Master volume of the live output (steps of 5 unless `/n` is given; mute toggles and remembers the level). Variable `mp_live_volume` |
| `/input/armed/<on\|off\|toggle>` | The Live input's Armed switch (see Live input) |
| `/input/ducknow/<on\|off\|toggle>` | Duck now: a manual override that holds the playlist audio down until switched off (works with no input) |
| `/stop` | Stop instantly |
| `/rescan` | Re-read `media/library/` (after adding/removing files offline) |
| `/device/0` `/device/1` ... | Switch output to that entry in the device list (see the web page or `/api/devices`) |
| `/device/next` | Cycle to the next output (system default is part of the cycle) |
| `/device/default` | Switch back to the system default output |

**Fade length override:** add one integer argument in milliseconds, e.g. `/fadeout` with value `5000`,
`/xfade` with `1500`. Over HTTP use `?ms=5000`. Without it, `crossfade_ms` / `fadeout_ms` from config are used.

### A crossfade time for one track
Besides the master crossfade time (**Settings > Audio > Crossfade time**, `crossfade_ms`), each track can have its **own** crossfade time, used whenever that track is crossfaded **into**: Go in crossfade mode, `/xfade`, `/<p>/<t>/xfade`, and a plain `/<p>/<t>` when the default transition is crossfade. Set it in the small box under the cut / crossfade toggle beside Go in the Cue panel (seconds, 0-30; it is dimmed, but still editable, while Go is set to cut; the box acts on the cued track, and empty means "use the master time", which is shown as the placeholder). A track with its own time shows an **XF 1.5s** badge on its row. An explicit time on the command (`?ms=`) still wins over both. Auto-advance still cuts. The time is saved with the playlist as `xfades: {track_id: ms}` in `playlists.json` and follows renames and moves to another playlist like the trim and end action. Over OSC/HTTP: `/<p>/<t>/xftime/<seconds>` sets it and `/<p>/<t>/xftime/clear` removes it; `/api/playlists` returns `xfade` (milliseconds or null) for each track.

HTTP equivalents: `GET http://<host>:8080/api/next`, `/api/0/1/xfade`, `/api/fadeout?ms=5000`, ...
