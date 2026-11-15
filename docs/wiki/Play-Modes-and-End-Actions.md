# Play modes and end actions

What happens when a track ends: the playlist behavior and the per-track end action.

## Play modes
Every playlist has its own **Playlist behavior** selector in its header on the web page (or use `/mode/...` over
OSC/HTTP). It decides what follows a track of that playlist that plays to its end. The page labels are Stop, Loop Playlist,
Next Playlist and Shuffle; the internal values and OSC/HTTP names are unchanged:
- **Stop** (default): the track ends and the player goes quiet.
- **Loop Playlist** (`loop_playlist`, also `playlist`): the next track starts, wrapping from the last track back to the first.
- **Next Playlist** (`next_playlist`, also `continue`): the remaining tracks of this
  playlist play, then the tracks of the playlists below it, in order. It stops after the last playlist (no wrap).
- **Shuffle** (`shuffle`): random order within the playlist; every track plays once before any repeats, and the
  same track never plays twice in a row.

The mode only applies to natural endings. Fade out, Stop, and Toggle off still stop everything, and tracks you
trigger yourself play as usual. Auto-advance stays inside the playlist (except in the continue mode), cuts to the next track (no crossfade) and the
focus moves with it. Modes are saved in `playlists.json` with the playlist. `"play_mode"` in `config.json` (default
`stop`) is only the starting mode for playlists that have never been set. Companion variable: `mp_play_mode` holds the
mode of the focused playlist (`stop` / `loop_playlist` / `next_playlist` / `shuffle`).

### The Play button
The green **Play** button in a playlist's header starts the playlist from its first track, like pressing Go on that track; the
playlist's behavior then applies. When the behavior is Shuffle the button shows the shuffle icon, reads **Shuffle** and starts
with a random track (the usual shuffle bag). It is disabled for an empty playlist or one whose files are all missing.
Over OSC/HTTP: `/<playlist>/play`.

### What a track does at its end
Each track row has one **end-action button** that cycles through four settings (the same button is on the Live card, for the live track):

| Icon | Setting (`end`) | Behavior |
|---|---|---|
| grey arrow down | `default` | Follows the playlist behavior. |
| repeat-1 (orange) | `once` | **Loop once**: the track plays twice in all, seamlessly (`play(loops=1)`), then the playlist behavior applies. The count restarts every time the track is started. The Live card counts down the current pass and shows "pass 1 of 2". With an A/B trim the repeat covers A to B, and an Out fade happens at the end of the last pass. |
| infinity (orange) | `loop` | **Loop forever**, seamlessly, until stopped or another track is played (the old loop switch). |
| circle-stop (red) | `stop` | When this track **ends by itself**, playback stops, whatever the playlist behavior is. Go, Next/Prev, crossfade and Stop All behave as usual. |

Notes: a track played with Play on Top never repeats (its ducking is measured for one pass), except Loop forever, as before.
After a restart, resume continues the pass that was playing and then follows the behavior (a "once" track is not repeated again).
Changing a track from once or loop to something else while it plays lets the pass that is running finish.
