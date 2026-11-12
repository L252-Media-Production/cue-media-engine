<p align="center"><picture><source media="(prefers-color-scheme: dark)" srcset="assets/branding/cueme-lockup-dark.png"><img src="assets/branding/cueme-lockup-light.png" width="420" alt="Cue Media Engine (CueME)"></picture></p>

# Cue Media Engine (CueME)

Library + playlist audio player that Bitfocus Companion can control over OSC and HTTP. Runs on macOS and Linux (incl. Raspberry Pi).

Cue Media Engine is an independent project and is not affiliated with or endorsed by Bitfocus; Bitfocus Companion is a trademark of Bitfocus AS.

Code: MIT (see LICENSE). Name and logo: see TRADEMARKS.md.

> **Note:** The `v2.7.1` tag points at pre-split code (2.7.0). The real 2.7.1 is `7d5f42c` (`v2.7.1-rc2`). Use `v2.7.2` or later.

## Security
The web page and the HTTP and OSC control have **no authentication**: anyone who can reach the port can play, stop and change settings. Run the player on a trusted network, behind a firewall, or behind a reverse proxy that adds authentication, and never expose port 8080 (web / HTTP) or 9000 (OSC) to the internet.

## Run
First time only:
```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```
Every time after that (from this folder):
```
.venv/bin/python player.py
```
Open http://localhost:8080. At startup the available audio output devices are printed.

## Library and playlists
- **Library** (left of the web page): every audio file is stored **once**, in `media/library/`. Upload with
  the orange upload button beside the library search box (choose Files or Folder) or by dragging files and folders together anywhere onto the library. A folder becomes a new library folder, keeping any folders inside it; wav, mp3, ogg and flac files are uploaded as they are; with ffmpeg installed, many more formats are accepted too (see **ffmpeg (optional)** below). Hidden files are skipped. Drop a folder onto an existing library folder to put it inside that folder. Files being uploaded appear as rows at the top of the library with a progress bar (a failed one stays until you click it). Each file in a playlist shows a small badge with the number of playlists using it; click the badge to jump to the track in each of those playlists in turn (the reverse of the coloured flag on a playlist row, which jumps to the track in the library). The cross on a folder deletes it; if it is not empty you are asked to confirm, and everything in it is deleted and removed from the playlists.
  Uploading a file whose contents are already in the library reuses the existing file instead of storing a copy.
- **Playlists** (right): lists of references to library files, so the same track can sit in several playlists.
  Create playlists in the web page (the Create button, or drop tracks or a folder on the dashed box beside it; a green confirmation appears at the bottom right, and clicking it scrolls to the new playlist). Playlists are what Companion sees: `/0/1` = second track of the first playlist.
- **Add tracks to a playlist:** drag a track from the library onto a playlist (between two rows to choose the
  position), or use the "Add to…" menu on the library row. Dropping audio files from your computer onto a playlist
  uploads them to the library and adds them to that playlist.
- **Reorder:** drag a track by its ⠿ handle, or use ▲ ▼. To send a track to another playlist, drag it onto that playlist.
- **Remove** (in a playlist) takes the track out of that playlist only. The file stays in the library.
- **Delete** (in the library) permanently deletes the file, after a confirmation that lists the playlists it will
  be removed from. It is not moved to a trash folder, so the space is freed immediately.
- **Delete playlist** removes the playlist only; its tracks stay in the library.
- A playing track keeps playing when it is moved, removed or deleted, and the focus cursor stays on the same track.
- **Offline changes:** files you copy into `media/library/` while the player is stopped (sub-folders are fine)
  appear in the library on the next start, and a notice lists what was found or is gone. While the player is running,
  use **⚙ Settings > System > Rescan** (or send `/rescan`). If a playlist points at a file that no longer exists, the track is shown
  in red and kept in place, so the IDs of the other tracks don't shift. Remove it from the playlist when you're ready.
- Companion IDs (`/0/1`) follow playlist order. Reordering or removing tracks changes which track an ID points at,
  so check your buttons after reorganising. Adding a track at the end never changes existing IDs.

## Look: styles and light / dark

Open **⚙ Settings > Look > Appearance** (or use the Theme button in the header).

- **Style**: *Console* (dense, amber), *Studio* (clean, soft cards) or *Stage* (large, touch friendly).
- **Theme**: *System* (follows the device's light/dark setting and changes live), *Light* or *Dark*.

The choice is remembered per browser, so a touch panel can run Stage while your laptop runs Console. Nothing about it is stored on the player.

Drag and drop: drag a library row (⠿) onto a playlist to add it, before or after any track (a line shows where it will land).
Drag a playlist row to reorder it or drop it on another playlist. Drop audio files from your computer straight onto a playlist to upload and add them.

## Resume after a restart

If the player restarts while a track is live (service restart, reboot, power cut), it carries on with that track from where
it left off, and stays paused if it was paused. The position is saved to `resume.json` every 5 seconds while playing and
exactly at a normal stop (`systemctl stop/restart`). Nothing is saved while the player is stopped, so a deliberate Stop or
Fade out is never undone by a restart.

- It only resumes if the player was last seen playing within `resume_max_age_s` seconds (default 1800), so a restart the
  next morning does not start music in an empty room. A track that had practically finished is not resumed.
- After a crash or power cut you lose at most `resume_save_s` seconds of position.
- Set `"resume_on_start": false` to turn it off.
- The write is a tiny file every few seconds only while audio is playing, so it is gentle on the Pi's SD card.

### Renaming and reordering playlists

In the web page, each playlist header has a **✎** rename button (or double-click the name; Enter saves, Esc cancels), a **⠿** handle to drag it to a new position,
and a chevron to **collapse** it to just its header (remembered per browser). Playing and focused tracks follow their playlist, and each playlist keeps its
own end-of-track mode.

**Companion buttons use the playlist number** (`/2/0` means the third playlist), so moving a playlist changes which buttons
trigger it. Reorder before programming buttons, or re-check them afterwards. Renaming does not affect any button.

## Folders and renaming in the library

The library follows the real folders under `media/library/`. Make folders in the web page (**＋ Folder** at the top of the
Library, or ＋ on a folder for a sub-folder) or in the file manager, and press **Rescan library** to pick up changes made
outside the page.

- **Move a track:** drag its ⠿ handle onto a folder (a "top level" row appears at the bottom of the list while dragging), or press ✎ and choose a folder.
- **Rename:** ✎ on a track or folder. The window opens right next to the button you pressed, with the name selected, so you can type and press Enter. A track keeps its file type. Playlists, the sound cache and a track that is playing
  follow the new name, so nothing in your playlists breaks.
- **Upload into a folder:** drop audio files from your computer onto a folder row.
- **Delete a folder:** only empty folders can be deleted (✕ is greyed out otherwise).
- Folders whose name starts with `.` or `_` are ignored by the library, so the page will not create them. Use them for files you want kept out of the library.
- Playlists refer to tracks by their path, so moving or renaming a file *outside* the page (in the file manager) shows up as a missing track until you re-add it.
- Searching shows a flat list of matches with their folder.

### Favorite and hidden folders, Collapse all (2.7.4)
- **Collapse all / Expand all** are the two plain icon buttons in the Library header (Expand all: chevron down; Collapse all: two arrows pointing inward). The header stays on one row at every width; on a phone the storage text is shortened. They skip hidden folders. Which folders are open or closed is remembered **per browser**.
- **Favorites:** the star on a folder row (filled yellow = favorite; titles *Favorite* / *Unfavorite*). Favorite folders move to a **Favorites** group at the top of the tree (alphabetical), above **All folders** (alphabetical). With no favorites there is no Favorites heading.
- **Hide:** the eye-off button hides a folder (and everything inside it) from the library **tree** only. Its tracks stay in playlists and keep playing, and the search still finds them (see below). Hidden folders are also left out of the track picker of a trigger point.
- **Hidden:** a crossed-out eye with the number of hidden folders (no text; title and label *Hidden folders: N*). It appears in the Library header only while something is hidden. Switch it on to see hidden folders, dimmed and striped, with a *hidden* badge and a blue crossed-out eye (*Hidden. Click to unhide*). Whether it is on is remembered per browser, and it switches itself off when the last folder is unhidden.
- **Search and hidden folders:** matches in visible folders show as before. If some matches are in hidden folders, a message row says *N tracks found in hidden folders · click to show* (also under *No tracks found* when nothing visible matches). Clicking it shows only the matching hidden folders, dimmed, each with the unhide eye, and a *Hide these again* row; it does not switch the Hidden toggle, and clearing the search puts them away again.
- **Favorites and hidden are shared by every browser** (they are saved on the player, in `playlists.json` as `folder_flags`, and follow a rename or move of the folder; a deleted folder drops out). `GET /api/library` has a `flags` object (`{path: {fav: true, hidden: true}}`) and `GET` / `POST /api/library/folder/flags` (`{path, fav?, hidden?}`) reads and sets them. They are for the web page only: nothing goes to Companion.

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

The setting is saved with the playlist as `end_actions: {track_id: "once"|"loop"|"stop"}` in `playlists.json` (default is absent),
keyed by the file within that playlist, so it follows renames, re-ordering and moves to another playlist (like trims).
The old `loops` list is read as `loop` and migrated on load (a copy of the old file is kept as `playlists.pre-endactions.json`), and
the old "Loop the track" mode is converted the same way. Over OSC/HTTP: `/<p>/<t>/end/default|once|loop|stop` sets it, `/<p>/<t>/end`
with no value steps to the next setting, `/<p>/<t>/loop` still toggles loop forever (`/loop/1`, `/loop/0`; `/loop` for the focused track).
`/mode/track` toggles loop for the focused track. `/api/playlists` returns `end` for each track plus `loop` (true only for `loop`);
`/api/state` adds `live_end`, `live_pass` and `live_passes`, and `live_rem` is the time left of the current pass.

### A and B points (trim a track)
Press the bracket icon on a track row, or the same bracket icon on the Cue panel's button row, to open the trim window. It shows the
waveform; drag the green **A** (start) and red **B** (end) markers, or type times like `1:23.5`, or play the preview and press **Set A** / **Set B** at the moment you hear the spot. Everything outside the
two markers is dimmed and never plays: the track starts at A and ends at B, so the remaining time, the waveform and the
play modes all use the trimmed length. **At B** chooses between a **fade out** and a hard **cut**. The fade length is per track
(`for 1.5 s`: type it or use the field's arrows / Up / Down keys, 0.1 to 10 s, never longer than B minus A; stored as `fade_ms` in the track's trim); a track without its own
value uses the default, **Settings > Audio > Transitions > Fade-out at B** (config key `trim_fade_ms`, default 1500 ms), and
**Use default** drops the override. **At A** (2.7.4) chooses **Cut** (the default: the track starts at full level, exactly as before) or **Fade in**, with its own length in the same way
(`for 1.5 s`, 0.1 to 10 s, never longer than B minus A; stored as `start: "fade"` and `fade_in_ms` in the track's trim; the length is remembered while the edge is Cut). A track without its own length uses
**Settings > Audio > Transitions > Fade-in at A** (config key `trim_fadein_ms`, 0 = none, so choosing Fade in on a track with no default gives 1.5 s to start from). The fade-in has the same equal-power curve as every fade and shows as a green wedge after A.
It is applied only when the track starts at its In point (a seek or a resume part-way in never fades), a crossfade into the track wins (the crossfade is the fade-in), and a track played on top fades up to its set level (the background ducks at full depth meanwhile). The fade shows as a red wedge before B, and the Preview buttons use the length on screen
even before you Save. Hovering the waveform shows the time and the time left; **Playhead** shows the play position. A looping track repeats between A and B. The **Preview** buttons play through the
normal preview (browser, preview output or both): *Play A → B* plays it exactly as it will go on air, including the
fade or cut; *Last 6 s* checks the ending; *Whole track* ignores the points so you can find them. **Loop A-B** (the repeat button next to the preview buttons) makes *Play A-B* repeat from A each time it reaches B, with the fade-in at A and the fade-out at B on every lap, so you can judge whether the section loops cleanly. It is **preview only**: it never loops the live program and never touches the live decks. On the player's preview output the helper process loops the section itself (one buffer, no gap at the wrap; command `{"cmd":"loop","a","b","fin","fout"}` of `POST /api/preview/ctl`); on *This browser* (and *Both*) the page jumps back to A, which leaves a small gap. Stop, switching Loop off, closing the window or a seek ends it; Loop is off every time the window opens.
**Precision** (the sliders button beside Set A / Set B, blue when on, remembered per browser; on by default): shows a time field for A and for B (`m:ss.s`, `h:mm:ss.s` over an hour) with up / down arrows (hold to repeat, Shift = 10×; Up / Down in the field too), and the step strip 0.01 / 0.1 / 1 s (default 0.1; with 0.01 the field shows hundredths). You can type a time; it is clamped like the keyboard nudges. With Precision off the fields and the strip are hidden and Set and Reset have the row.
On a **phone** the window is a full-screen sheet: header with the file path and a close button, the waveform with big round grips, one *Nudge step* control, a card each for A and B (`− time +`, *Set A at playhead*, *Reset*, Precision, and the fade row with `− 1.5 s +`), the Preview section with an **Output** menu (default *This browser* when no choice was made yet), and Cancel / Save at the bottom with a trash button *Remove trim*. The Trim | Smart Loop tab strip is shown; Smart Loop is not available yet (greyed, marked *coming soon*). A trimmed track shows
its range next to its name, the Cue panel shows a chip when the cued track is trimmed, and the live waveform shows the
cut-off parts dimmed. The points belong to the file within that playlist, so the same file can be trimmed differently in
another playlist (`trims` in `playlists.json`). The file itself is never changed.
Over OSC/HTTP (A is `in`, B is `out`): `/<p>/<t>/in/<seconds>`, `/<p>/<t>/out/<seconds>`, `/<p>/<t>/end/fade` or
`/end/cut`, `/<p>/<t>/in/clear`, `/<p>/<t>/out/clear` and `/<p>/<t>/trim/clear`.

## RAM indicator
A track has to be decoded into RAM before it can play. A track that is already in RAM starts instantly; one that is not waits for a decode (about 5 seconds for a 15-minute MP3 on the production machine). The page shows where you stand:

- **Header indicator** (a small pill directly left of `Cache`; on a phone it sits in the row under the title with `Cache` and `RAM`): a spinning ring, `N/M` and a small bar while the playlists are being decoded (N tracks in RAM, M tracks used by the playlists); a green tick and `N/M` when every track is in RAM; an amber alert circle and `Full` when the cache is at 95 % of its budget (`cache_mb`) and some track is not in RAM, so the least recently used tracks are being dropped (the Cache numbers turn amber too). It goes to loading at once but back to the tick only after 2 s of being ready, and it is hidden when no playlist has tracks. If the cache is not full but some tracks are not loaded (the warm-up stops at 80 % of the budget) it shows the tick with the counts. Hover for the tooltip. Header order: indicator, `Cache 4.1 GB / 12.0 GB`, `RAM 23% (7.1 GB / 31 GB)`.
- **Marker before a track name (2.7.4):** only a track that needs attention is marked: a spinning blue ring = decoding now, a grey hollow ring = not loaded, starts after a short wait. No marker = in RAM, starts instantly (the green dot of 2.7.3 is gone). The playlist header says `3 of 4 in RAM`.
- **Go button:** if the cued track is not in RAM when you press Go, the button shows a spinner and `Loading… 4 s` (counting up) until the track starts. This is display only: Go waits for the decode exactly as before.

The numbers are in `/api/state` (`ram`: `used_mb`, `budget_mb`, `tracks_total`, `tracks_in_ram`, `loading`, `full`, `rev`) and `/api/playlists` (`ram`, `ram_in`, `ram_total`). They are for the web page only: nothing about them goes to Companion. They are computed from the cache with lookups, cached for one second, and reading them never changes which track the cache drops first.

## Playlist progress
Each playlist header shows where you are in the list: `Track 3 of 6 · 12:34 played · 18:20 left · ends 21:47`, a chip for the playlist behavior (Stop at end, Loop, Shuffle, Next playlist; shown only while the playlist is collapsed, because the Playlist behavior menu shows it when expanded) and a bar with one segment per track. Segment widths follow each track's real length: the **A to B window** when the track is trimmed, so the time left is what will actually play. Played tracks are dark green, the current one is outlined and filled up to the position, upcoming ones are empty. A playlist with more than 40 tracks shows one continuous bar. In the rows, played tracks are dimmed (no check mark since 2.7.4) and the playing row shows its loudness and `elapsed / length` under the name and a thin progress line along the bottom; its seven buttons stay on one line like every other row, and the quick-flag stripe stays visible. A playlist that is not the playing one (or nothing live) shows only its totals.

- **Stop at end / Next playlist:** time left runs to the end of the list (or to a track whose end action is Stop). Next playlist also shows the name of the playlist that follows.
- **Loop playlist:** time left is counted for the current lap.
- **Shuffle:** a track counts as played when it has been played in the current round; time left is what remains of the round.
- A track that loops forever shows "looping this track" instead of a time left. A track set to play once counts twice.

The sums are made in the page from `/api/playlists` (`dur_eff`, the seconds of one pass; `shuffle_left`, the ids still to come in a Shuffle round) and the live position; the engine does no extra work.

## Page layout, folder colours and waveforms
- **Naming:** the "focus" of earlier versions is now called the **Cue** (the track that is up next; click a row to cue it). The playlist **Play** button is now the green **Go**, and the orange **PVW** button on a track previews it privately. Companion variable and command names are unchanged (`mp_focus_*`, `/focus`); `/cue` also works in place of `/focus`.
- The page runs top to bottom: **Live** (full width, with a large time-remaining countdown), **Cue** (a strip with Prev / Next; the track that is up next), then **Preview**, then the library and playlists.
- **Folder colours and icons**: click the dot (or icon) left of a folder name in the library and pick a colour (or the ✕ for none) and, if you like, an icon instead of the circle. The icons are a selection of [Lucide](https://lucide.dev) icons (ISC licence) drawn inline, so nothing is loaded from the internet. The colour is used for the icon. Every
  playlist row has a coloured flag on its left edge showing the colour of the folder the file lives in (grey if none).
  **Click a flag** to open that folder in the library and flash it bright yellow for 4 seconds. The cued row is
  outlined in the accent colour and the live row in the live colour. Colours and icons are saved in `playlists.json`. **Settings > Look > New folder icon** sets the icon that folders created from now on get (new folders, folders made by moving a file into a new path, upload folders and the Downloads folder); `default_folder_icon` in `config.json`. Folders that already exist are not changed.
- **PVW**: the preview button in the library and playlists reads **PVW** (it turns into a pause button while previewing).
- **Drop into an empty page**: when there are no playlists, drag a library track (or audio files) onto the empty
  area and an "Untitled playlist" is created with it.
- **Waveforms**: switch on **⚙ Settings > Look > Show waveforms** (per browser, works in every style). Live and Preview then show a
- **Time warnings** (⚙ Settings > Look > Time warnings, a row you can open; any number of warnings): the big live countdown changes colour as the track runs out. Each warning is a time (mm:ss) with a colour, e.g. `01:00` orange and `00:30` red. It is always on. **Add a warning** adds another (up to 8, a longer time than the rest becomes the *First warning*; they are named First, Second, ... and Final warning, longest time first), and ✕ removes one (at least one stays). At any moment the countdown takes the colour of the shortest warning time it has reached. The settings are kept by the player in `state.json` (key `time_warning`), so every browser and the [stage page](#stage-page) share them; change them in one browser and the others follow within a second. A browser that still has the old per-browser copy (`cp_warn`) uploads it once if the player has none yet. Endpoints: `GET /api/settings/warning` and `POST /api/settings/warning` with `{"warnings": [{"t": seconds, "c": "#rrggbb"}, ...]}`; the same list is in `/api/state` under `warning` (which also still carries the older `t1/c1/t2/c2` first and final warning).
  waveform you can click or drag like a seek bar. Seeking live jumps the on-air audio. OSC/HTTP: `/seek/<seconds>`.

A plain-language guide for operators is built in: **⚙ Settings > System > Maintenance > Help guide** (or `http://<host>:8080/help`).

**Restart player** (⚙ Settings > System > Maintenance) restarts the program from the web page: it saves the position, re-runs itself in the same process (so systemd keeps supervising it and no sudo is needed), and the page reloads when it is back. Audio stops for a few seconds and a playing track resumes where it was. It does not reboot the machine.

## Stage page

A display-only page for stage screens: the live track's time remaining as big text. Use it in a browser, or as a web element / iframe in another program (for example a FreeShow stage layout, on another machine). No login, no external files, and no frame-blocking headers are sent.

| URL | Shows |
|---|---|
| `http://<player>:8080/stage` or `/stage/a` | the time only |
| `/stage/b` | the track name above the time (small, one line, cut with an ellipsis if long) |
| `/stage/c` | name and a thin progress bar along the bottom |

Options in the address (they also apply on top of a shortcut, e.g. `/stage/b?bar=1`, `/stage/c?name=0`):

- `name=1` shows the live track name; `bar=1` shows the progress bar (elapsed within the playable A-B range, so a trimmed track fills correctly).
- `bg=black` (default) or `bg=transparent`. A transparent frame needs an embedding page that does not declare a dark `color-scheme` (browsers paint such frames solid); use `black` if unsure.

Behaviour:

- **Format:** `mm:ss`, and `h:mm:ss` only from one hour up (`59:59`, then `1:00:00`). The Live card of the main page still shows `mm:ss` with minutes beyond 59 (`65:30`). Seconds are rounded up, like the Live card.
- **Size:** monospaced tabular digits that scale to fill the element, wide or square.
- **States:** paused dims the time and shows `PAUSED`; nothing playing, or no answer from the player for about 3 seconds, shows a dim `--:--`; it reconnects by itself.
- **Smooth:** it asks `GET /api/state` four times a second and counts down locally in between (`live_rem`, the exact seconds left, plus `live_pos`, `live_in`, `live_out` for the bar), so the seconds never skip.
- **Colours:** the warning colours from **Settings > Look > Time warnings**, with the same rule as the Live countdown (the colour of the shortest warning time that has been reached); the bar follows. Above the longest warning time it stays white.

## Stop All
The bold red **STOP ALL** button at the top of the page (or `/stopall` over OSC/HTTP) stops the live audio, stops the preview and clears the cue in one press. There is no confirmation, so use it deliberately.

## Trigger points
A track in a playlist can have **trigger points**: when the live track reaches one, the player does a **Play on Top** of a library track you chose, by itself (same ducking and top-track level as the button; it is the same code path). Typical use: a voice-over at 0:10 of a long music bed.

- **Set up:** open the trim window (the bracket icon on a row, or the same icon in the Cue panel). Under **Trigger points**, move the play position and press **Add trigger at playhead**, then pick the target in the searchable list. Each trigger has an editable time (`m:ss.s`), **First pass only** (a looping or loop-once track does not fire it again), an On/Off switch, **Test** (plays the target on the preview output) and delete. Flags on the waveform (purple, numbered) can be dragged; with the waveform focused, Left/Right nudge the selected marker by 0.1 s (Shift 1 s, Alt 0.01 s), Up/Down choose a marker, Delete removes a trigger. **Save** stores the triggers together with the trim; **Cancel** discards them. A flag badge with the count on a playlist row opens the window at this section.
- **On air:** the Live panel shows *Next trigger in 00:42 → name* with **Skip** (skips that one trigger, once), small flags on the live waveform (grey once they have fired in this pass), and a short notice when a trigger fires, is skipped or fails. The **Auto triggers** switch beside the Live heading turns all triggers off (red **AUTO TRIGGERS OFF**); it is kept in `config.json` as `triggers_armed` (default `true`).
- **Rules:** a trigger fires when the file position crosses its time, once per pass. Seeking past it does not fire it (seeking back arms it again); pause holds; a trigger before the In point or at/after the Out point never fires; a track that is no longer live (a crossfade moved on) does not fire; if a Play on Top is already playing the trigger is skipped with a notice; with Auto triggers off nothing fires. The target is decoded ahead of time; if it is not ready when the time comes it plays as soon as it is (the delay is logged).
- **Missing target:** if the target leaves the library the trigger is kept, marked missing, and nothing plays.
- **Data:** `playlists[p]["triggers"] = {file_id: [{id, at, file, once, enabled}]}`, next to `trims`; it follows renames (both the track and the target), reordering and moves to another playlist.
- **API** (web page only, not Companion): `GET/POST /api/playlists/<p>/triggers` (`track`, `action` = `add|update|delete|set`, `id`, `at`, `file`, `once`, `enabled`, `triggers`), `GET /api/triggers`, `POST /api/triggers/arm {"armed": true|false}`, `POST /api/triggers/skip`. `/api/state` has `triggers_armed`, `next_trigger`, `live_triggers`, `trigger_notice`; `/api/playlists` has `triggers` per track. There are no Companion variables, actions or commands for triggers.
- **Tests:** `SDL_AUDIODRIVER=dummy python3 -I tests/test_triggers.py` (fake clock, no audio device needed).

## Play on Top
The **Play on Top** button on the Cue strip (or `/top` over OSC/HTTP, or `/<playlist>/<track>/top`) lowers whatever is live and plays the cued track over it. When that track ends, the background comes back up to full level and carries on from where it was. It is meant for pre-recorded announcements over background music.
- The background is turned down by a **sidechain ducker**, like a compressor on the music with the announcement as its sidechain. The announcement is measured every 10 ms up front; while it is louder than the **Threshold**, the background is reduced by (dB over the threshold) × (1 − 1/**Ratio**), going down in **Attack** ms and coming back in **Release** ms. The announcement itself starts straight away at its set level (no fade-in).
- The **Reduction** meter at the bottom of the Ducking section is a slim red meter (8 px) on the Input Gain row, in the right-hand column, with the label and value in the same type as the other settings: 0 dB at the left, −30 dB at the right, a tick every 10 dB, and the value (`-6.1 dB`) red while ducking and dim at `-0.0 dB`. "Stay ducked until it ends" is in the Ducking heading line. The scale ends at 30 dB: that covers every normal setting; the engine can in theory go deeper (up to 60 dB with the most extreme settings), and then the bar simply stays full while the readout keeps counting.
- The controls are in the **Ducking** section of the Cue panel (one global set, saved to `config.json`): `duck_threshold_db` (default −30), `duck_ratio` (6), `duck_attack_ms` (10), `duck_release_ms` (500), the **Input Gain** (the level of the announcement, `top_track_pct`, 100) and **Stay ducked until it ends** `duck_hold` (on). With it on, the music goes down at the first loud moment and stays down, at the typical depth, until the announcement ends, so it never bounces back in pauses; with it off, the music follows the speech. The section is collapsed by default (click **Ducking** to open it; the page remembers); its header shows the current settings, or the reduction while it is ducking. A **Reduction** bar shows how far the background is turned down right now. The old Background level setting is no longer used (except when numpy is missing, when the background just dips to it).
- Over OSC/HTTP: `/duck/threshold/-30`, `/duck/ratio/6`, `/duck/attack/10`, `/duck/release/500`, `/duck/hold/1` (`/duck/hold` toggles) and `/duck/level/100` set a value. For rotary knobs, `/duck/<name>/inc` and `/duck/<name>/dec` step it up or down and stop at the limits; add a step to change it, e.g. `/duck/ratio/inc/0.5`. Default steps: threshold 1 dB, ratio 0.5, attack 1 ms, release 10 ms, level 1 %. Variables `mp_duck_threshold`, `mp_duck_ratio`, `mp_duck_attack`, `mp_duck_release`, `mp_duck_hold` and `mp_top_level` show the current values (they follow changes made on the page too), and `mp_duck_gr` is the reduction in dB right now.
- Pick the threshold relative to the announcement's level: a voice at about −12 dBFS with a −30 dB threshold, 6:1, is turned down 15 dB. Level match changes the announcement's level too, and the threshold follows it.
- The live volume fader moves both together, and Level match still applies to each track underneath.
- While it plays, the Live card shows **ON TOP** and the big countdown is the announcement's. Variable `mp_on_top` is `1` meanwhile.
- The cue does not move. If nothing is playing, it just plays the cued track normally. Starting a second one on top replaces the first and keeps the same background.
- If the background track ends while it is covered, the playlist moves on to its next track when the announcement finishes (according to that playlist's "When a track ends" setting). Stop and Fade out affect everything. A restart resumes the background track, not the announcement.

## Live input (Duck only)
The player can listen to **one input channel** and turn the playlist audio down while someone talks (a presenter's microphone arriving on a Dante channel, or on a separate analog interface), then bring it back. 2.7.5 ships **Duck only**: the input is only analysed, **never mixed into the Live output**, so Live is untouched. (Playing the input as a playlist item, "Play only" and "Both", is a later release.)

- **Where:** the **Live input** card, a block of its own under the Cue and Preview blocks (it is part of Edit layout; collapsed by default, remembered, the chip, meter, Duck now and Solo stay visible when collapsed; hidden on a phone-width page), and **Settings > Audio** (Live input armed, Input device, Input channels, Input gain, Duck above). Changes save as they are made. The card: chip (**Signal present** = above −60 dBFS within the last half second, before the gain; **No signal**; **No input** with a plain reason), a level meter (after the gain) with a mark at the **Live input threshold** (a slider and the only control for it on the card: drag it, click or press on the bar, use the arrow keys (1 dB, Shift 5 dB, Home / End), double-click it for −30 dB; the readout under the meter says "Duck above −35 dB", "Ducking" while the level is over it; the number is also in Settings > Audio), **Duck now**, **Solo**, the Device and Channels menus on one row (as small as the Duck now and Solo chips; searchable, the current device ticked), the input gain slider on the row below (−12 to +24 dB, default 0) and the text "Duck only". **Arming is done in the Cue container** (its switch, or the pill in its header); the card only shows "armed" / "not armed" as text (the card's own Armed switch is still in the page for a phone-width window, where the card is hidden; Settings > Audio keeps its Armed switch too). The Cue container's **Input Gain** (the level of the track played on top) has an (i) button that says so, so it is not mistaken for the Live input's gain.
- **How it ducks:** it reuses Play on Top: the same threshold, ratio, attack, release and **Stay ducked** settings (changing them changes both), the same gain computation (`cpl.dsp.duck_curve`, `duck_smooth`) and the same **Reduction** meter (the sum of both). The level of each 10 ms block, after the input gain, above the threshold dips the playlist audio by (dB over) × (1 − 1/ratio) after the attack time; it comes back over the release time. With **Stay ducked** on (the shared Play on Top switch) the dip is held at its typical depth for one second (fixed, not a setting) after the speech stops. There is no separate hold setting; an `input_hold_ms` key from rc1 is ignored. The factor is `Deck.duck_in`, separate from Play on Top's `Deck.duck`: the two multiply and never overwrite each other. The input only ducks the playlist audio (every live deck, including one that starts meanwhile).
- **Armed** (saved, **off** at the first start): when off no input level can duck, but the meter and the chip still show the input. **Duck now** (not saved) is a **manual override**: it holds the reduction a signal 12 dB over the threshold would ask for (so it follows threshold and ratio) until pressed again, with Armed on or off, with or without an input device. Losing the input does not clear it; a player restart or `/input/ducknow/off` does. **Solo** (not saved, off at every start) plays the input on the **Preview output** only: it needs a Preview output, follows the Preview volume and Mute, and changes nothing in the detector, the ducking or Live.
- **Safety:** if the capture stream stops delivering audio for half a second, errors, the device disappears or the helper dies, **the speech ducking ends with a **50 ms linear-in-dB ramp** (longer for a dip deeper than 15 dB so one 10 ms step stays within 3 dB, never more than 100 ms; the normal release curve is used when it is faster), Duck now is untouched, the chip says **No input** with the reason, **Armed is kept**. Armed off and Duck now off use the same ramp. If the 10 ms detector task itself does not run for 250 ms (a blocked event loop), the 50 ms tick treats the input as lost (chip **Detector stalled**) and the detector recovers by itself. The helper keeps trying to reopen the device every 2 s, so it recovers by itself. The player never waits for it.
- **Isolation:** capture runs in its own process (`python player.py --input`, `cpl/helpers/input_worker.py`), the only writer of a shared ring (`cpl/helpers/ring.py`: one mono channel, 48 kHz int16, 5.5 s, a memory-mapped file in `_input/`). The **detector** (`cpl/liveinput.py`) and the **Solo tap** (inside the preview worker) are two readers of that ring, each with its **own read pointer** and a read-only mapping. The detector runs in the player process as a small 10 ms task (a few hundred samples copied, one RMS per block, a few float operations; nothing is added to the 50 ms tick): next to the shared ducking settings, with one source of truth and no settings protocol, while the helper stays a dumb pipe that is safe to lose.
- **Clock drift is ignored in 2.7.5.** Duck only never plays the input into Live, so a separate analog interface cannot drift against the output. It must be revisited (resampling or drift correction) when Play only or Both ships.
- **Companion / HTTP:** `/input/armed/<on|off|toggle>` and `/input/ducknow/<on|off|toggle>` . Variables `mp_input_armed`, `mp_input_duck_now`, `mp_input_signal`, `mp_input_ducking` (1 / 0). `GET /api/input` (state, device list); `POST /api/input` `{device, channel, gain_db, armed}` (400 with a reason for an unknown device, a channel outside 1-64 or a gain outside −12..+24; nothing changes on a refusal); `POST /api/input/solo` `{on}`; `POST /api/input/ducknow` `{on}`. `/api/state` has an `input` block, the meter stream (`/api/live`, `/api/meters`) has `in_gr` and `input` `{present, signal, level_db}`.
- **Settings keys** (`state.json`, written as you change them): `input_device`, `input_channel`, `input_gain_db`, `input_armed`. A saved device that is not present at start shows **No input** ("not found") and is picked up when it appears; a bad saved value falls back to its default.
- **Channels and stereo pairs (input-stereo):** the **Channels** menu (card and Settings > Audio, the searchable menu with a tick) lists, for a device with N channels, the **Stereo pair** group (Channel 1/Channel 2, Channel 2/Channel 3, ...; an odd last channel has no pair) and then the **Single channel** group (Channel 1 (mono), ...); a 2-channel device shows exactly Channel 1/Channel 2 (stereo), Channel 1 (mono), Channel 2 (mono). The device's own channel names are used when it reports them (SDL does not, so today it is "Channel n"). Saved as `input_channels` (`[n]` or `[n, n+1]`) in `state.json`; `input_channel` is still written (the first channel) and read when `input_channels` is absent, so a channel saved by an older version is the same single channel and a fresh setup stays channel 1. The helper captures the selected 1 or 2 channels into the ring (a header field holds the channels per frame); the detector uses the **louder channel** of a pair (the same per-channel level measure as for one channel, then the maximum; threshold, ratio, attack, release, hold and the release ramp are the shared ones, the input gain applies to both). The card's meter has one bar per channel with one shared threshold mark; "Signal present" is true when either channel is above -60 dBFS. State: `channel_list`, `stereo`, `choices`, `levels_db` (per channel) next to `level_db` (the maximum). Solo plays a pair as stereo and a single channel to both ears. Changing the choice or the device restarts the capture: chip **Switching…**, the ducking released with the quick ramp, recovery by itself. If the device has fewer channels than the saved choice, the first valid choice is used and a plain note says so (not an error).
- **Armed in the Cue container:** while an input device is chosen, the Cue container shows the armed state instead of "No cue" (armed, no cue), under "No cue" (off), as a pill in its header (a cue is loaded), or as an amber line (armed, no input). The switch is a button with `aria-pressed` and the name "Input armed. Switch off to disarm" / "Input armed. Switch on to arm"; it is the Armed setting itself. Hidden at phone width, where the container stays as it was.

## Level match (per playlist)
Each playlist has a **Level match** setting in its header. It turns louder tracks **down** so the playlist plays at one level; it **never boosts** a quiet track, so it cannot cause clipping.
- **Cue card:** the cued track's playlist name sits under its title. Click the title (or press Enter on it) or the playlist name to jump to that track in its playlist, the same as on the Live card: the playlist expands if it is collapsed, scrolls to the track and flashes it for 4 seconds. With nothing cued the title is plain text.
- **Live card:** the live track's playlist name sits under its title (click to jump to it), with the end-action button, a "pass 1 of 2" hint for a loop-once track and the same dB bubble as the playlist row. Click the bubble to adjust the playlist's level match (close it with its ✕, Esc, a click or tap outside, or the bubble again); with Fixed LUFS, + and − move the target 1 LUFS (raising it brings the track up, still never boosting above the original).
- **Off** (default).
- **Match a track**: pick a reference track from the playlist (marked **REF**). Every track louder than it is turned down to its level; quieter ones are left alone.
- **Fixed LUFS**: every track louder than the target (for example `-18`) is turned down to it. `-23` is the broadcast standard, around `-16` to `-14` is typical for streaming.

Each row shows the change as a badge (`-3.2 dB`, `0 dB`, `REF`). `…` (with a pulsing dot) means it is still being analyzed and `–` means the track is too short (under 0.4 s) or silent, so it plays at its normal level. The same file in two playlists gets its own offset in each, depending on that playlist's setting.
- **Analyzing:** loudness is measured once per file (ITU-R BS.1770 / EBU R128 integrated LUFS, the same as ffmpeg's `ebur128`) in a low-priority helper process, one file at a time, and only for tracks in playlists that have Level match on. Results are cached in `loudness.json` with each file's size and modified time. It uses **ffmpeg** when it is installed (faster on long tracks and it never holds the decoded track in memory) and the built-in **scipy** measurement otherwise or if ffmpeg fails on a file; both agree within 0.1 dB. If neither is available the status light turns red with that reason.
- **Where it applies:** live playback only, including crossfades and resume. **Preview is never level matched.** The live meters show the matched level, and `mp_live_gain_db` holds the amount applied to the live track.
- **Commands:** `/0/norm/off`, `/0/norm/track` (or `/0/norm/track/<track number>` to choose the reference), `/0/norm/lufs/-18`, `/0/norm/ref/<track number>`.

## File information

The small **i** (a circle with an i) on every library row, and on playlist tracks, opens a popover with the properties of that file, with no waveform. It opens beside the button and behaves like the Live card's level-match popover: its **✕**, **Esc**, a click or tap outside (pointer-down, so it works on touch), or pressing the same **i** again closes it, and only one of the two popovers is open at a time. It is not rebuilt by the page's once-a-second refresh or by the library list re-drawing, and it fills in by itself while measurements finish. Cards wrap to two per row on a phone.

Hover (or tap) a value for its meaning:

| Value | In plain words |
|---|---|
| Format, Codec | The kind of file (WAV, MP3, FLAC, OGG) and how the sound is packed in it. PCM means not compressed. |
| Duration, File size | How long it plays, and the disk space it takes. |
| Bitrate | How much data is used for each second of sound. For MP3 and similar files, higher usually means better quality. |
| Sample rate | How many times a second the sound is measured. The player works at 48,000 Hz and converts other rates when a file loads. |
| Channels, Bit depth | Mono is one channel, stereo is two. Bit depth is how finely each measurement is stored (16-bit CD quality, 24-bit studio quality). |
| LUFS | How loud the file sounds on average over its whole length. Closer to zero is louder (-14 is louder than -23). Level match uses this. |
| True Peak (dBTP) | The loudest point in the file. Above -1 dBTP can distort. |
| Loudness Range (LU) | How much the loudness moves up and down. Small is steady, large has quiet and loud parts. |
| Max Volume (dB) | The loudest single moment of the sound. 0 dB is the loudest a file can go. |
| RMS (dB) | The average level of the sound over the whole file. Lower means quieter overall. |
| Probe Score | How sure the file detector is about the format. It is not a quality score (an ordinary MP3 often scores about 50). |

How it works:

- `GET /api/library/info?id=<library id>` returns all of these as JSON (`null` where not available) with a `status` for each group (`probe`, `loud`, `peak`, `vol`: `ok`, `measuring`, `needs ffmpeg`, `failed` or `unavailable`), a `done` flag, the file-check message if the file has a yellow or red sign, and `error` for a file that cannot be read. An unknown id is a 404, and a listed file that has vanished from the disk is a 404 with "missing from the disk".
- Format, codec, duration, bitrate, sample rate, channels, bit depth and probe score come from ffprobe. LUFS, True Peak and Loudness Range come from one ffmpeg `ebur128` pass, the same pass the level-match worker uses (so a file measured for level matching also has them here, and the other way round). Max Volume and RMS come from one `volumedetect` pass, run only when the popover is opened.
- Everything runs through the same one-at-a-time, low-priority, core-limited ffmpeg runner as the other ffmpeg jobs, and the page asks again once a second while the popover is open and something is still being analyzed (the chips show a pulsing dot and "analyzing…"; the API status value stays `measuring`).
- Results are kept in `fileinfo.json` (per library id, with the file's size and modified time, so a changed file is measured again).
- Without ffmpeg the popover still shows the size, the length (from the existing length cache), the WAV header facts of a `.wav`, and LUFS from the built-in measurement when scipy is installed; the rest says "needs ffmpeg".

## Status light, health panel, watchdog and push (2.8.0)
- The dot beside "Cue Media Engine" is the status light and a button. **Orange ring** (pulsing) while the player starts and checks the library, **green circle** when it is ready, **amber triangle** when it is degraded (something needs attention, the audio still works), **red diamond** when something is wrong. The shape is part of the signal, so it does not rest on colour alone; the title and the accessible name say `Health: degraded. Disk space low`. Click it for the health panel: seven checks (Live output, Preview output, Audio engine, Companion, Media drive space, Track cache, Player uptime), each with an icon, a short title and, when it is not OK, one sentence saying what is wrong. Overall state: `starting` while the player starts, `problem` if any check is bad, `degraded` if any is a warning, else `ready`; a check that is `unknown` never changes it. The older red reasons (the audio output is not open or fell back to the system default, the library folder is missing, a track failed to load for two minutes, level matching without ffmpeg or scipy) still make it red. **Copy report** (`GET /api/health/report`) builds a plain-text report for a chat (version, state, checks, audio driver as SDL names it (`alsa`, `coreaudio`, `pipewire` ... read once a device is open, else `not detected`), Live and Preview device names and whether each is in the current device list, watchdog restarts, whether push is on, `Process memory: N MB` (resident size; VmRSS on Linux, getrusage on macOS) and `Open files: N` (entries of `/proc/self/fd`, Linux only, else `not available`) for watching a soak run, uptime, date) with no Companion address, no webhook address and no file paths. `/api/state` has the small `health` object: `status` / `detail` (the old light, unchanged) and `state`, `summary`, `checks` (`id`, `status`, `title`, `text`), plus `push_error` after a failed push.
- **Checks.** *Live output*: the configured output is in the device list and open (bad otherwise). *Preview output*: only when a Preview device is configured and missing, and only while Settings > System > Health and alerts > "Amber for a missing Preview output" is on (default on): warning. *Audio engine*: bad while the watchdog has seen the output stall. *Companion*: the module's polls of `/api/state` are recognised by the header `X-CompanionPlayer-Client` (module 2.8.0) or the user agent `node` (older modules); a browser, curl and the tests are not counted. Before the first poll since the player started it is `unknown`; after that, silence for more than 30 s is a warning, and so is an OSC address that does not resolve (Settings shows "Host not found"). *Media drive space*: warning below 10 % free or 5 GB, bad below 1 GB (the text reads `2.0 GB free (2 %)`, with `less than 1 %` for a small non-zero share and no percentage when the total is unknown), read in a thread and kept 30 s. *Track cache*: warning when the cache is full (95 % used and a playlist track is not in RAM) or a track failed to load; `unknown` when no playlist has tracks. *Uptime*: information only.
- **No device enumeration while audio plays (2.8.0 follow-up).** `cpl/devwatch.py`: while any deck exists the health report makes no SDL device-list call and opens no device. The Live output is judged by a plain read of `/proc/asound/cards` (Linux): the configured SDL name is matched tolerantly to a card (the card id or its description appears in the name); once matched, the check turns bad only if that card's id (the bracketed name in `/proc/asound/cards`, e.g. `Module`) disappears; the card number is not used, because it changes after a replug. If two cards matched equally at some time (a second identical adapter) and the first one then goes while the other stays, the check reports unknown (one INFO line in the log) instead of guessing. A name that cannot be matched stays `unknown` and only the watchdog's stall signal counts (never a false bad); one INFO line says which card matched. Without `/proc/asound` (macOS) the probe is skipped. When nothing plays the SDL list is refreshed in a worker thread at most every 10 s and never waited for (a hung call leaves the last good list). Copy report uses the last good list. A missing Live output (the player left on the system default or SDL's dummy output) is reported bad and is not treated as a stall: the watchdog makes no restart while the Live output check is bad.
- **Watchdog.** `cpl/watchdog.py`: while something is playing, a silent half-second sound is looped on a reserved mixer channel (channel 0, never given to a track); each time SDL's audio callback finishes it, a counter goes up. If the counter does not move for 10 s while a track is playing and not paused (or a fade is running), the audio engine is closed and reopened exactly as a device change does, and the live track carries on from where it was (`Watchdog: audio engine restarted (output stalled for 10 s)` in the log). It never touches the service or the process. At most 3 restarts in 10 minutes, then it stops restarting and the Audio engine check stays bad. Settings > System > Health and alerts > Watchdog (on by default). Test hook: start the player with `CP_TEST_WATCHDOG=1` and `POST /api/test/stall` stops the counter as if the output had stalled; `CP_TEST_DISK_FREE_GB=2` fakes the free space (the drive's real total is kept; `CP_TEST_DISK_TOTAL_GB=100`, or `2,100`, sets the total as well).
- **Push on state change** (off by default). Settings > System > Health and alerts: Send to Webhook, the address (http or https only), the events (a problem starts, it recovers, degraded lasts more than 5 minutes, the watchdog restarts the engine), Hold messages until nothing is playing, and Send a test message. An HTTP POST with a JSON body `{text, content, player, event, state, time}` (`text` and `content` are the same sentence, for Slack-style and Discord-style webhooks; `time` is ISO 8601 with offset), a 5 s timeout, up to 2 retries with backoff (1 s, 3 s), on one background thread. A state must hold 5 s before it is sent. The address is never written to the log, the report or `/api/state` (the page shows only its host). Examples: `L252 production machine: PROBLEM — the live output (Dante USB) is not available. 14:32`, `L252 production machine: Audio engine restarted by the watchdog (output stalled for 10 s). 14:35`, `L252 production machine: Recovered — everything is ready. 14:36`. The player name is Settings > System > Health and alerts > Player name (up to 40 characters; also `player_name` in state.json), else the host name. The Audio engine row and the report say "Restarted N times since start"; the log has one `Watchdog: running, N restarts since start` line per hour while playing. Once a poll with the `X-CompanionPlayer-Client` header has been seen, only the header identifies Companion (a user agent `node` no longer does). Endpoints: `GET` / `POST /api/settings/health`, `POST /api/settings/health/push-test`.
- Companion variable `mp_status` still holds `starting` / `ready` / `error`. The module 2.8.0 adds `mp_health_state` (`starting`, `ready`, `degraded`, `problem`; empty with an older player) and `mp_health_text`, the feedback *Player health* and the preset *Health*.
- Track lengths are saved in `durations.json` next to `player.py`, with each file's size and modified time. On start-up
  only new or changed files are measured, so a restart with an unchanged library is ready in a moment. The file is safe
  to delete; lengths are then measured again (MP3/OGG/FLAC in a low-priority helper process, one at a time).

## Download from a link

The **download** button beside the library's search box saves the audio of a web link (YouTube and many other sites) into the
library, in a folder called **Downloads**, so it is easy to find. Paste the link, choose **FLAC** (the default: lossless, converted to 48 kHz 16-bit stereo like the rest of the library), **MP3** or **WAV**, and press
**Download**. A progress bar shows the download and conversion. Press **Minimise** to get back to the player: a small box in the bottom corner shows the progress, then "Saved N tracks" when it is done. Click it to jump to the new track in the library (the same highlight as the flag on a playlist row); the cross dismisses it.

- A link to a playlist saves **only its first track** unless you tick **Whole playlist** (then up to 100 tracks, in a folder named after the playlist inside Downloads).
- One download runs at a time. Identical audio that is already in the library is not added twice.
- It uses **yt-dlp**, the maintained fork of youtube-dl with the same embedding interface; if only youtube-dl is installed the player uses that instead, but YouTube often breaks it. `pip install -r requirements.txt` installs yt-dlp and a JavaScript runtime (deno) that YouTube needs.
- It needs **ffmpeg** (on Debian: `sudo apt install ffmpeg`) and internet access from the player. Keep yt-dlp up to date (`.venv/bin/pip install -U "yt-dlp[default,deno]"`, then restart the player), because sites change often and old versions stop working.
- `config.json`: `download_folder` (default `"Downloads"`) and `download_format` (`"flac"` by default, `"mp3"` or `"wav"`; the page's choice overrides it).
- Use it only for content you have the right to download.

## Preview in the web page

Preview can play **in the browser** instead of on the Pi: the track streams to the page and comes out of the speakers or
headphones of whatever device has the page open (laptop, phone). Choose it in **⚙ Settings > Audio > Preview plays on**
(*This browser*, *Player output*, or *Both*); the same menu sits at the top of the Preview card, styled like the Live **Output** menu (headphone icon, small "Output" label, full width on its own row, the full device name in its tooltip), with Pause, Stop, the seek bar and the time on the row below. The choice is remembered per browser, so the audio engineer's laptop can preview locally
while the player's own preview output stays available. With no preview device configured, *This browser* is used automatically. On a phone the preview also defaults to *This browser* when no choice has been made yet (2.7.4), even if the player has a preview output; the player's output stays in the list.

**Both** plays the track on the player's preview output and in the browser at the same time. The player's output is the master and the
browser follows it, staying within about half a second. Pause, resume, seek and stop go to both. The browser copy is not sample-locked,
so it can sit slightly ahead or behind; the level meters and waveform show the player's output. *Solo live* only ever plays on the player's output.

- Press the ▶ button on a library row or a playlist track to preview it. While it plays the button shows ⏸: press it to pause, and again to resume. The Stop button in the preview strip stops it.
- The strip at the top has pause, stop, seek, volume, time and its own level meters (measured in the browser).
- The **File information** strip above the waveform shows the previewed file: one line (length, format, bitrate, sample rate, channels, LUFS, peak; the peak is amber above -1 dB) with **More** for every value as cards (format, codec, duration, bitrate, sample rate, channels, LUFS, true peak, loudness range, max volume, RMS) and **Hide**; the choice is remembered in the browser. It uses the same `/api/library/info` data and cache as the **i** popover, fetches once per previewed file (polling only while values are still being measured), and says nothing when nothing is previewed. Under a playlist row it is one compact line with an **All details…** link. Without ffmpeg it shows only what can be read.
- It is local to that page: Companion's `/preview/...` commands and the `mp_preview_*` variables still refer to the Pi output only.
- Browsers need a click before they will play sound, and an iPhone's silent switch mutes it.

## Preview output
Listen to a track on a second output, without it touching the main output. The usual setup on a Raspberry Pi is
the main output on the Dante / USB interface and the preview on the Pi's 3.5 mm headphone jack.
- Pick it in **⚙ Settings > Audio > Player output**. The list is the same one as the main Output dropdown (the headphone jack
  appears with a name like "bcm2835 Headphones" or "Headphones"). Choose **Off** to turn preview off. It is saved
  straight away. Pick a different device from the main output.
- Once a preview output is set, every track in the library and in the playlists gets a **Preview** button. A bar at the
  top shows the previewing track with Pause/Resume, Stop, a seek slider and a preview volume.
- Preview is independent of the main output: playing, crossfading, fading or stopping the main audio never changes
  the preview, and the other way round. One track is previewed at a time; starting another replaces it.
- Companion (optional): `/preview/0/1`, `/preview/focus` (toggle on the focused track: use it with Next / Prev to audition quickly), `/preview/stop`, `/preview/playpause`.
  Variables `mp_preview_state` (`off` / `stopped` / `loading` / `playing` / `paused` / `error`), `mp_preview_playing` (1 / 0), `mp_preview_remaining` and `mp_preview_name`.
- It runs as a small helper process that is started with the player and exits with it. A track is decoded in full when
  previewed, so a long MP3 or FLAC may take a few seconds to start on a Pi. If the device can't be opened, the bar
  shows the error. Pick the device again in Settings to retry.
- `config.json` can also set `"preview_device"` (exact device name) and `"preview_volume"` (0 to 1); the choice made in the
  web page is remembered in `state.json` and overrides them.

## Storage limits
The Library header on the web page shows one line, for example "Library 1.6 GB of 60.0 GB cap (3%) · 51 file(s)" (without a cap:
"Library 1.6 GB · 51 file(s)"), with a slim usage bar under it. Hover over it to read the free disk space and how much room is left for
uploads ("Disk 348.4 GB free of 468.4 GB · room for uploads: 58.4 GB (library cap)"). The line turns orange at 80% and red at 95%, over the
cap, or when less than 50 MB is left for uploads; a red chip beside it says "Library is over its cap" or "Low room for uploads" so the
problem is visible without hovering. Uploads that would not fit are refused with a message. In `config.json`:
```json
{
  "storage_limit": "10GB",
  "storage_reserve": "1GB"
}
```
- `storage_limit`: cap on the total library size. Use an exact size (`"10GB"`, `"500MB"`) or a percentage of the
  whole disk (`"25%"`). A bare number means GB. `null` (default) means no cap.
- `storage_reserve`: free space that is always kept on the disk (default `"1GB"`). Uploads are refused if they
  would eat into it, even when the cap would allow them. Also accepts a size or a percentage.
- Sizes use 1 GB = 1024 MB. The percentage is of the disk's total capacity.
- Lowering the cap below what the library already uses never deletes anything; it just blocks new uploads
  until you delete files.

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

## config.json (all optional)
Place it in the same folder as `player.py` and restart the player after editing by hand. (The Companion address
and port can instead be changed from ⚙ Settings on the web page, which updates this file for you.)
```json
{
  "default_transition": "cut",
  "crossfade_ms": 3000,
  "fadeout_ms": 2000,
  "toggle_off_fade_ms": 0,
  "storage_limit": null,
  "storage_reserve": "1GB",
  "play_mode": "stop",
  "preview_device": null,
  "mirror_enabled": false,
  "mirror_device": null,
  "meter_rate_hz": 4,
  "live_volume": 1.0,
  "resume_on_start": true,
  "resume_save_s": 5,
  "resume_max_age_s": 1800,
  "trim_fade_ms": 1500,
  "trim_fadein_ms": 0,
  "audio_device": null,
  "cache_mb": 768,
  "osc_in_port": 9000,
  "http_port": 8080,
  "companion_host": "127.0.0.1",
  "companion_osc_port": 12321,
  "var_prefix": "mp_",
  "ffmpeg_path": "",
  "ffmpeg_cores": 2,
  "ffmpeg_nice": 10,
  "import_convert": true,
  "import_normalise": true
}
```
`audio_device` must match a name from the startup device list exactly. You normally don't need to set it:
pick the output from the dropdown on the web page and the choice is remembered in `state.json`
(it overrides `config.json`). Switching outputs while a track is live carries it over to the new device from the same point (paused stays paused), with only a brief gap while the device opens. If the saved device is
missing at startup (e.g. Dante not connected yet) the player falls back to the system default.

## ffmpeg (optional)
Everything works without it. When `ffmpeg` and `ffprobe` are installed (`sudo apt install ffmpeg`; no restart needed, the player looks again every minute) the player also uses it for:
- **More file types on upload:** m4a, aac, aiff, caf, wma, opus, oga, mp2, ac3, wv and the audio of video files (mp4, mov, mkv, webm, avi, 3gp...). They are converted to FLAC (48 kHz, 16-bit, stereo) in the library; the original is not kept. Without ffmpeg these are refused with a message saying so. Turn off with `"import_convert": false`.
- **Normalise at upload:** wav and flac files that are not 48 kHz, are over 16-bit, or have more than two channels are converted to 48 kHz / 16-bit / stereo, so they load fast and play at the right speed. If the conversion fails, the original is kept. Turn off with `"import_normalise": false`.
- **Waveforms:** drawn from a quick 8 kHz decode (also for tracks that are not in memory yet). If ffmpeg is missing or fails, the built-in decoder is used.
- **File checks:** every library file is looked at once in the background (results kept in `formats.json`). A yellow sign on a library row means a warning (more than two channels, very short); a red sign means the file cannot be read or has no audio. Hover for the reason; hover over a name to see its format (codec, rate, channels, bit depth). **Settings > Check all files** decodes every file completely to find damaged ones.
- **Level match:** loudness measured by ffmpeg's `ebur128` filter (see Level match).

ffmpeg is deliberately held back so it can never disturb playback: one job at a time, at low priority (`ffmpeg_nice`, default 10) and, on Linux, restricted to the last `ffmpeg_cores` CPU cores (default 2; ignored when the machine has no more cores than that). `ffmpeg_path` points at a specific ffmpeg if it is not on the PATH. `GET /api/ffmpeg` shows what was found and `GET /api/formats` the check status.

## Dante
- **Mac:** Dante Virtual Soundcard (or a Dante PCIe/USB interface) shows up as a normal output device.
  Choose it in the web page's Output dropdown. Subscribe its channels to your Dante receivers in Dante Controller.
- **Raspberry Pi:** Dante Virtual Soundcard does not run on Pi/Linux. Use a Dante USB adapter that
  presents itself as a standard USB audio device, or send analog/USB out of the Pi into a Dante interface.
- **Channels:** the player outputs stereo, so it feeds channels 1-2 of the selected device. Use Dante Controller
  routing to patch those two channels wherever they need to go.
- Match the sample rate: the player runs at 48 kHz, the Dante default.

### Searchable output menus
The Output, Mirror, Settings > Audio > Player output and Preview "Plays on" menus, and the track picker of a trigger point, share one searchable
dropdown. Click it or press Enter; the search box is focused. Typing filters as you type (case-insensitive, spaces and punctuation
ignored: `dvs 1` finds every `DVS Transmit ...` pair that has a 1 in it). Up/Down, Page Up/Down, Home and End move, Enter chooses, Esc closes,
and **System default** / **Off** stay at the top. The list is read again from the player each time it opens; the page's once-a-second
refresh never closes it or clears the search. Rows are at least 44 px high on touch screens, and the popover flips upward when there is no room below.
The native `<select>` elements keep their ids (`dev`, `mdev`, `set_pv`, `pvsel`, `set_pvt`) and values; they are hidden and the dropdown button is
`<id>_cb` (`dev_cb`, ...).

### Troubleshooting: output device missing
- The device has to be running before the player can see it. With Dante Virtual Soundcard on Windows, start DVS first.
  DVS lists its channels as stereo pairs named `DVS Transmit N-N` (for example `DVS Transmit  1-2 (Dante Virtual Soundcard)`;
  SDL keeps odd spacing in these names and the player passes them back unchanged).
- Check that Windows lists the device under Sound settings.
- Open an output menu (there is no Refresh button): the lists refresh when Settings or an output menu is opened, so a device that
  starts later appears without reloading the page. Devices are listed in natural order (`Out 2` before `Out 10`); two devices
  with the same name get a ` (2)` suffix in the menu (the name itself is what is stored, so the first one is used).
- If the saved output is not found at start-up, the log says so, the page shows a note under the Output menu, and the system
  default is used. The saved name stays in `state.json` until you pick another output.

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
0 dBFS is the top (nothing is boosted, so ducking thresholds, level match and the gain-reduction meter are unaffected). The scale
is piecewise linear, as a percentage of the meter height from the bottom: 0 dBFS = 100, -5 = 88, -10 = 76, -20 = 60, -30 = 46,
-40 = 33, -50 = 21, -60 = 10, and -90 (labelled -∞) = 0. Both meters carry the same labels, `0 -5 -10 -20 -30 -40 -50 -60 -∞` (0 unsigned, a minus before every other number), at the same heights: one list (`METER_TICKS`) and one formatter (`meter_label`) in `cpl/legacy.py`. The colour zones are green, amber from -17 dBFS (65%) and red from
-6 dBFS (86%). The table lives once in `cpl/legacy.py` (`METER_STOPS`); the page's scale labels, colour zones and JS copy are generated
from it. The meters stretch to the full height of the Live and Preview panels. Bars fall back at 30 dB per second.

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
- Developers: the web page listens to the server-sent-event stream `GET /api/live` (meters about 14 times a second, the
  preview output's state 4 times a second). `GET /api/meters` still returns one reading,
  `{"live": {"l","r","l_db","r_db"}, "preview": {...}, "enabled": true}` with `l`/`r` as 0-100 on the taper above and `l_db`/`r_db` in dBFS.

### Variables page
Open **⚙ Settings > Companion > View** (or go to `http://<player>:8080/variables`) to see every variable the
player sends, with its live value and what it means. Use **Copy all names** to get the full list for creating the
custom variables in Companion. This shows what the player is sending; it can't confirm that Companion received them.

### Settings page (⚙ Settings, top right of the web page)
Four tabs on a computer (**Look**, **Audio**, **Companion**, **System**); on a phone or touch panel one column of closed sections, each with a one-line summary of its value and a search box, one open at a time. **Everything saves as you change it** (there is no Save button), and a short (i) beside a setting holds one sentence of explanation.
- **Look** (Style, Theme, Show waveforms, Time warnings, New folder icon: this browser only, except Time warnings and the folder icon, which the player keeps; Layout: Edit layout, and a More menu with Reset, Export and Import).
- **Audio:** Preview plays on (This browser / Player output / Both) and the player output device, Mirror live to a second device (its device menu appears under the switch), Transitions (Default, Crossfade time, Fade-in at A, Fade-out at B). Output lists refresh each time they open.
- **Companion:** Address and OSC port (where the variables go). The address is checked when you leave the field: an incomplete one such as `192.168.1.` shows a warning and the last good address stays in use (the **Sending to** chip shows the one in use). Valid values are applied at once and written to `config.json` (all your other settings in that file are kept); a well-formed host name that can't be found right now (offline, Companion not up yet) is still saved: an amber note says so and the player keeps trying; it is not looked up when saved. **Variable prefix** (default `mp_`; config key `var_prefix`, an existing config.json is read as before) is put in front of the name of every variable the player sends (`mp_live_name`, `mp_remaining`, ... in this README mean *prefix + name*). Letters, digits and underscores, starting with a letter, 1 to 16; checked when you leave the field, with a live example (`Example: mp_remaining`); a trailing underscore is your choice and is not added for you. Changing it asks for a confirmation (buttons and triggers using the old names must be updated; the old variables stay in Companion until the module is reloaded), then saves it and sends every variable again under the new names. `POST /api/settings/prefix` `{prefix, confirm:true}` (409 without `confirm`), `variable_prefix` in `/api/state`, `GET /api/variables` has `prefix`. The Companion module (2.7.7) follows the player's prefix. **Send test** sends `<prefix>test` (`mp_test` by default) = the current time (`HH:MM:SS`) to the address in use with the same sender as the live variables, and reports *Test sent* or *Couldn't send* with the reason. OSC gives no reply, so it only confirms the player sent it: check that `mp_test` shows up in Companion (create the custom variable `mp_test` first; the Companion module 2.7.5 also has a module variable `mp_test` that shows the last test). **View** opens the variables page, **Resend now** pushes every variable again (it does not send `mp_test`). API: `POST /api/settings/companion/test` returns `{ok, sent_to, at}` or `{ok:false, error}`; `/api/state` has `test_message` and `test_sent_at` (reported for two minutes after the test, then empty; the Companion module has no OSC input, so its `mp_test` variable reads this).
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

## Folder layout
```
cue-media-engine/
├── player.py           the launcher (starts cpl/)
├── cpl/                the program (Python modules); copy it together with player.py
├── static/             the web page files (index.html, style.css, app.js ...) and help/stage/variables pages (deploy together with player.py)
├── run-player.bat      Windows launcher (run-player.command on a Mac)
├── config.json         optional settings
├── playlists.json      playlists and their order (created automatically)
├── state.json          remembered output device
└── media/library/      all audio files
```
**Updating the player:** copy `player.py`, `cpl/` and `static/` together (replace the old ones completely; the player refuses to start if `cpl/` or `static/` is missing or incomplete). On Windows also copy the new `run-player.bat`. Your playlists, library and settings are picked up on the next
start. To move the player to another machine, copy the whole folder.

**Upgrading from the one-folder-per-playlist layout:** the first start moves every file into `media/library/`
(identical files are merged into one), rewrites the playlists to reference the library, and keeps a safety copy of
the old data as `playlists.pre-library.json`.

## Notes
- **No glitches when a track loads.** A track is decoded into RAM before it plays. Decoding MP3, OGG or FLAC
  inside the player freezes its audio for seconds, so that work is done by a helper process instead and the
  music that is playing is never interrupted. The tracks from the focused one onward in its playlist are decoded
  ahead of time (in the background, at low priority), so normally every cue starts instantly.
- If you trigger a track that isn't ready yet (for example straight after starting the player, or one in a
  playlist you haven't focused), whatever is playing carries on, the page shows "Preparing …" and `mp_loading`
  holds the track name, and the new track cuts or crossfades in as soon as it is ready (a few seconds for a long
  MP3 or FLAC). Pressing Stop or Fade out cancels it, and triggering another track replaces it.
- `cache_mb` (default 768) is the RAM used for decoded tracks, least recently used first out. Decoded audio is
  about 11 MB per minute (stereo), so 768 MB holds roughly an hour. Lower it on a Raspberry Pi with little RAM; the
  warm-up then covers fewer tracks. Plain WAV files load fastest.
- Formats: wav, mp3, ogg, flac.
- Crossfades use equal-power curves so loudness stays steady.

## Raspberry Pi
```
sudo apt install python3-venv
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python player.py
```
Pick the output with the web page's Output dropdown (HDMI, 3.5 mm jack or a USB interface). If SDL can't find
sound on a headless Pi, try `SDL_AUDIODRIVER=alsa python player.py`. If Companion runs on the same Pi, leave
`companion_host` at 127.0.0.1. On a Pi with a small SD card, set `storage_limit` so the library can't fill it.

Run at boot: `/etc/systemd/system/cue-media-engine.service`
```
[Unit]
Description=Cue Media Engine
After=network-online.target sound.target

[Service]
User=cueme
WorkingDirectory=/opt/cue-media-engine
ExecStart=/opt/cue-media-engine/.venv/bin/python player.py
Restart=always

[Install]
WantedBy=multi-user.target
```
Then `sudo systemctl enable --now cue-media-engine`. Adjust `User` and paths to match your setup.

## Customising the layout
**Settings > Look > Edit layout** turns the page into a free-form grid for this browser. The five blocks (Live, Cue, Preview, Library, Playlists) sit on a twelve-column grid that is drawn while you edit; each block has a position and a size in grid cells.
- **Move:** drag a block by the handle in its orange bar. It snaps to the grid. **Esc** cancels a drag.
- **Resize:** drag the orange handles on its right edge, bottom edge or bottom-right corner. The buttons in the bar set it to 1/4, 1/2, 3/4 or full width, and the up-down arrow fits its height to its content. A block that is taller than its box scrolls inside it. The smallest block is three columns wide and three rows tall.
- **Collisions:** blocks never overlap. A block that is in the way is pushed down, and after every change the blocks float up to close vertical gaps (gaps beside a block are allowed).
- **Hide:** the eye hides a block (it is dimmed while you edit). Hidden blocks leave no gap when you are not editing.
- **Arrows:** move a block one cell, as an alternative to dragging.
- **Buttons are disabled while editing**, so nothing can go on air by accident. **Done** saves, **Reset layout** returns to the standard layout.
- The first time you edit, the grid starts from the standard layout as it is on your screen, so nothing jumps. If you change nothing, the standard layout stays.
- **Storage:** the layout is kept in the browser's local storage (`cp_layout`), so it is per browser and per device and is lost when site data is cleared. It applies to screens wider than 850 px; narrower screens keep the standard single-column layout.
- **Repair:** on every page load the saved layout is checked and repaired: unknown or missing blocks, blocks outside the grid, sizes that are too small or too large, overlaps, bad numbers and damaged data are all corrected (a missing block is added at the bottom), and layouts saved by earlier versions (rows and widths) are converted. The repaired layout is stored again. Data that cannot be repaired falls back to the standard layout.
- **Export and import (share a layout):** **Settings > Look > Layout > More > Export layout**, or **Export layout** in the editor bar, asks for a short name (default `layout`) and downloads `cue-media-engine-layout-<name>.json`. Tick *Include appearance (skin, theme, waveforms)* to add those settings. If no custom layout is saved, the standard layout as it is on your screen is exported (the dialog says so). **Import layout** (same two places) opens a dialog where you choose a file, drop it, or paste the text (for sharing through chat). It checks the data, shows a small preview with the layout name and the hidden blocks, and changes nothing until you press **Apply**; *Also apply appearance* is off by default. Rules: valid JSON, under 64 KB, `app` must be `cue-media-engine-layout` (the older `companionplayer-layout` is accepted too), a `version` above 1 is refused as "made by a newer version", unknown fields are ignored, and the layout always goes through the same repair step as a saved layout, so only the repaired result is stored (never the raw file). Names are shown as plain text.
- **Undo import:** the previous layout (and appearance, if it was replaced) is kept in memory and in `cp_layout_prev`; **Undo import** is in the confirmation message and in the dialog. **Reset layout** works as before.
- **Narrow screens:** you can export and import on any width; on a screen narrower than 850 px the import is stored and applies when the page is on a wider screen. Editing stays wide-only.
- **File format:** `{"app":"cue-media-engine-layout","version":1,"name":"...","exported":"<ISO date>","layout":{"v":3,"b":{"cl":{"x":0,"y":0,"w":12,"h":7},...},"hide":[]},"appearance":{"skin":"console","theme":"dark","waveforms":true}}` (`appearance` only when ticked).

## Mirror output
The mirror is **off by default**. Switch it on in **Settings > Audio > Mirror live to a second device**; a **Mirror** menu then appears beside Output (web page) where you choose the device. It plays a copy of the live audio on a second device: the production machine's headphone jack, or a second Dante USB adapter. It uses the same helper process as Preview, with the live monitor always on, so it follows the live track's position, fades, Play on Top ducking, level match and live volume. Preview and Solo live are independent of it. The choice is saved in `state.json` (or set `"mirror_enabled"` and `"mirror_device"` in `config.json`, matching a name from the startup device list). If the device is missing at startup the mirror stays off. `GET /api/devices` shows `mirror`, `mirror_error` and `mirror_playing` (and `notices` for saved outputs that are missing); `POST /api/mirror/device {"name": ...}` changes the device and `POST /api/mirror/enable {"on": true}` switches it on or off.
Two separate adapters run on their own clocks and can drift slightly apart, and the copy is a few tens of milliseconds behind the main output. It suits headphone monitoring or a backup feed, not two speakers in the same room.

## Output names (output aliases)
An output can have a label, a group heading, a hidden flag and a live-only flag without changing which device is used: the saved Live, Preview and Mirror outputs stay the exact SDL device names, so matching, the health check and the Companion `output` variable (raw name) are not affected. The table is `output_aliases` in `state.json`, edited through `GET` / `POST /api/settings/outputs` (`{"aliases": [{"match": "<exact device name>", "label": "...", "group": "...", "hidden": false, "live_only": false}]}`; `{"aliases": null}` brings back the default; at most 32 entries, texts up to 80 characters, no `match` twice; a bad table is refused whole and the old one stays). There is no editor in the page yet. While nothing was ever saved, a built-in rule for the ALSA loopback card of Dante over IP (Inferno) applies: `Loopback, Loopback PCM` reads **Dante over IP** under **Network audio** and is offered for Live only (Preview and Mirror are refused with "Only one program can use Dante over IP. Use it for Live."), and `Loopback, Loopback PCM (2)` is hidden. A saved table replaces that rule completely. A hidden output is listed only while it is the chosen one, or when **Settings > Audio > Show hidden outputs** is on (dimmed, marked hidden). `/api/devices` keeps `devices` as before and adds `output_info` (one object per device: `name`, `label`, `hidden`, `group`, `live_only`) and `output_aliases`. The health panel and Copy report show an aliased output as `Dante over IP (Loopback, Loopback PCM)`. The Companion command `/device/next` skips hidden outputs; `/device/<n>` still counts the full list.

## Live card: M and S, and what Go does
Under the Live meters (below the **LIVE** caption) are three small buttons with slightly rounded corners in every skin: **M** mutes the live output (solid red while muted; the same as `/volume/mute`), **S** is Solo live (solid yellow while on) and a **speaker button** that opens the Live output menu (a search box, a *Wired* group, a tick on the current device; the menu is prepared for more output groups; Bluetooth output is not part of 2.7.5). The Live transport row has pause, fade out and stop, the volume and (when enabled) the Mirror menu.

**Preview meters (2.7.5 rc1).** The Preview level meters no longer sit in the Preview panel: while a preview is playing, paused or loading (or Solo live is using the preview output) a thinner **PRV** pair appears to the right of the Live pair and shares its dB scale (the Live pair and the scale do not move), in a teal chip, with its own **M** (mutes the preview output only: the preview track and any soloed live audio on it; it keeps the preview volume; the live decks, ducking and the Live meters are never touched; `{"cmd":"mute","on":true}` on `POST /api/preview/ctl`, `muted` in the `preview` block of `/api/state`) and a speaker button (the same menu as the Preview panel's *Preview plays on* selector). The Mute buttons share one row. When the preview stops the pair goes away. The Preview panel has its output selector (headphone icon and the device name, no label) to the right of the volume slider (below the slider on a phone) and a full-width waveform. The meter variables sent to Companion are unchanged.

**Pin the Live panel (2.7.5 rc1).** The pin button (top left of the Live panel; filled and upright when pinned, outlined and tilted when not; pinned by default) keeps the Live panel in view: once the full panel has scrolled out of view a **one-line** panel stays at the top (pin, LIVE, title, pause, stop, progress, time, LIVE meters and the PRV chip while previewing; on a phone two short rows with a progress line and no stop button). Settings > Look has *Pin the Live panel*, *Shrink to one line when scrolled* (off: the whole panel stays at the top) and *Remember the pin in this browser*; they are per browser (`cp_pin`, `cp_pinmini`, `cp_pinkeep` in localStorage). The pinned panel is not a modal and does not lock the page. On a phone the order is Live, Cue, Playlists (then the Library), and the Reduction meter stays visible while Ducking is collapsed.
In the Cue panel a single toggle button sits beside the big **Go** button. It shows the current setting and flips when you click it: **Cut** (the *Take* icon: Go **cuts** to the cued track) or **Fade** (the *crossfade* icon, highlighted: Go **crossfades**, using `crossfade_ms`). It is remembered as `go_transition` (`"cut"` or `"crossfade"`, default `"cut"`) in `state.json`, returned in `/api/state` and as the variable `mp_go_transition`, and shared by every open page; set it with `/go_transition/cut`, `/go_transition/crossfade` or `/go_transition/toggle`. It only changes the web page's Go button: `default_transition`, `/take`, `/xfade`, `/0/1` and Companion's actions are unchanged.

## Solo live (monitor)
While Solo live is on, the **Vol** slider of the Preview panel is relabelled **Solo vol** and sets how loud the live audio is on the preview output (it applies at once, on the player's preview output and in the browser). The preview meter shows what you hear: the live level at the preview volume. From Companion or OSC use `/preview/volume/<0-100>`, `/preview/volume/up[/n]` and `/preview/volume/down[/n]` (steps of 5 unless `/n` is given); the variable `mp_preview_volume` shows the level (0-100).

The **S** button under the Live meter (Solo live; it turns yellow while on) (or `/solo`, `/solo/1`, `/solo/0`) plays the live audio on the preview output, so you can listen on headphones. The preview track is muted but keeps playing, and comes back when you turn solo off. It needs a Pi preview output (Settings > Preview). It follows what is really live: crossfades, Play on Top, pause, seek and the live volume. The preview volume sets the monitor level. The room output is not affected. Variable `mp_preview_solo` is `1` while it is on. Solo is not remembered over a restart.

**Solo live in the browser.** When **Settings > Audio > Preview plays on** is *This browser* (or *Both*), the button works without a preview output: the page plays its own copy of the live tracks, kept in step with the live position and following the live volume, fades, Play on Top ducking and level match. The main output is not touched; the page only asks the player what is on air (`/api/monitor`). With *Both*, it also turns solo on for the preview output. Notes: it is a copy, not a tap of the real output, so it can sit a fraction of a second ahead or behind and it does not follow the room output device; each live track is streamed to the page, so over Wi-Fi a WAV needs about 10 MB a minute per track; the browser solo is per page, so `/solo` from Companion and `mp_preview_solo` only reflect the preview output; and the browser's own preview is muted while it is on.

## Playlist and track name variables
Besides the live and cue variables, the player sends the names in every playlist: `mp_pl<N>_name` (playlist name), `mp_pl<N>_count` (number of tracks) and `mp_pl<N>_t<K>` (name of track K), where N and K are the same numbers used in `/<playlist>/<track>` commands. `mp_focus_playlist_num` is the number of the focused playlist, so a Companion button can build the name it needs, for example `$(custom:mp_pl$(custom:mp_focus_playlist_num)_t0)` for the first track of whichever playlist is focused. When a track or playlist is removed its variable is set to `-`. They are listed on the **View variables** page.

### Focused playlist window
`mp_focus_t0` to `mp_focus_t31` always hold the track names of the **focused** playlist, in order, and `mp_focus_count` its number of tracks. Unused slots are `-`. Create these 33 variables in Companion once and a page of buttons (`$(custom:mp_focus_t3)`) follows whichever playlist is focused, with no nested variables.


## Preview in the playlist
Previewing a playlist track opens the preview controls (play/pause, stop, output, seek, volume, waveform and a slim level meter) in an expanded area under that row; the Preview panel at the top shrinks to a one-line note with a Show button. Previews started from the library or the trim editor still use the top panel. Frontend only: the preview API is unchanged.

## Licence

The source code is MIT licensed (see `LICENSE`). The name "Cue Media Engine", "CueME" and the logo are not covered by that licence (see `TRADEMARKS.md`). Third-party notices (the Lucide icons, ISC and MIT) are in `NOTICE`.
