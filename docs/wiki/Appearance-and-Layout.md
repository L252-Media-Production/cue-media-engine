# Appearance and layout

Styles, themes, the page layout, folder colours, waveforms, time warnings, the pinned Live panel and layout sharing.

## Look: styles and light / dark

Open **⚙ Settings > Look > Appearance** (or use the Theme button in the header).

- **Style**: *Console* (dense, amber), *Studio* (clean, soft cards) or *Stage* (large, touch friendly).
- **Theme**: *System* (follows the device's light/dark setting and changes live), *Light* or *Dark*.
- **Page width** (desktop and tablet): how wide the page may grow on a large screen. *Standard* is the usual centred column (1320 pixels), *Wide* allows 1800, *Full width* uses the whole window, *Custom* takes 800 to 3840 pixels (a number outside that is brought into the range). It applies as you pick it; **Reset to Standard** goes back. Phones are not affected and do not show the row.

These choices are remembered per browser, so a touch panel can run Stage while your laptop runs Console. Nothing about it is stored on the player.

Drag and drop: drag a library row (⠿) onto a playlist to add it, before or after any track (a line shows where it will land).
Drag a playlist row to reorder it or drop it on another playlist. Drop audio files from your computer straight onto a playlist to upload and add them.

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
  waveform you can click or drag like a seek bar. Seeking live jumps the on-air audio. OSC/HTTP: `/seek/<seconds>`.

- **Time warnings** (⚙ Settings > Look > Time warnings, a row you can open; any number of warnings): the big live countdown changes colour as the track runs out. Each warning is a time (mm:ss) with a colour, e.g. `01:00` orange and `00:30` red. It is always on. **Add a warning** adds another (up to 8, a longer time than the rest becomes the *First warning*; they are named First, Second, ... and Final warning, longest time first), and ✕ removes one (at least one stays). At any moment the countdown takes the colour of the shortest warning time it has reached. The settings are kept by the player in `state.json` (key `time_warning`), so every browser and the [stage page](#stage-page) share them; change them in one browser and the others follow within a second. A browser that still has the old per-browser copy (`cp_warn`) uploads it once if the player has none yet. Endpoints: `GET /api/settings/warning` and `POST /api/settings/warning` with `{"warnings": [{"t": seconds, "c": "#rrggbb"}, ...]}`; the same list is in `/api/state` under `warning` (which also still carries the older `t1/c1/t2/c2` first and final warning).


A plain-language guide for operators is built in: **⚙ Settings > System > Maintenance > Help guide** (or `http://<host>:8080/help`).

**Restart player** (⚙ Settings > System > Maintenance) restarts the program from the web page: it saves the position, re-runs itself in the same process (so systemd keeps supervising it and no sudo is needed), and the page reloads when it is back. Audio stops for a few seconds and a playing track resumes where it was. It does not reboot the machine.

## Live card: M and S, and what Go does
Under the Live meters (below the **LIVE** caption) are three small buttons with slightly rounded corners in every skin: **M** mutes the live output (solid red while muted; the same as `/volume/mute`), **S** is Solo live (solid yellow while on) and a **speaker button** that opens the Live output menu (a search box, a *Wired* group, a tick on the current device; the menu is prepared for more output groups; Bluetooth output is not supported yet). The Live transport row has pause, fade out and stop, the volume and (when enabled) the Mirror menu.

**Preview meters.** The Preview level meters no longer sit in the Preview panel: while a preview is playing, paused or loading (or Solo live is using the preview output) a thinner **PRV** pair appears to the right of the Live pair and shares its dB scale (the Live pair and the scale do not move), in a teal chip, with its own **M** (mutes the preview output only: the preview track and any soloed live audio on it; it keeps the preview volume; the live decks, ducking and the Live meters are never touched; `{"cmd":"mute","on":true}` on `POST /api/preview/ctl`, `muted` in the `preview` block of `/api/state`) and a speaker button (the same menu as the Preview panel's *Preview plays on* selector). The Mute buttons share one row. When the preview stops the pair goes away. The Preview panel has its output selector (headphone icon and the device name, no label) to the right of the volume slider (below the slider on a phone) and a full-width waveform. The meter variables sent to Companion are unchanged.

**Pin the Live panel.** The pin button (top left of the Live panel; filled and upright when pinned, outlined and tilted when not; pinned by default) keeps the Live panel in view: once the full panel has scrolled out of view a **one-line** panel stays at the top (pin, LIVE, title, pause, stop, progress, time, LIVE meters and the PRV chip while previewing; on a phone two short rows with a progress line and no stop button). Settings > Look has *Pin the Live panel*, *Shrink to one line when scrolled* (off: the whole panel stays at the top) and *Remember the pin in this browser*; they are per browser (`cp_pin`, `cp_pinmini`, `cp_pinkeep` in localStorage). The pinned panel is not a modal and does not lock the page. On a phone the order is Live, Cue, Playlists (then the Library), and the Reduction meter stays visible while Ducking is collapsed.
In the Cue panel a single toggle button sits beside the big **Go** button. It shows the current setting and flips when you click it: **Cut** (the *Take* icon: Go **cuts** to the cued track) or **Fade** (the *crossfade* icon, highlighted: Go **crossfades**, using `crossfade_ms`). It is remembered as `go_transition` (`"cut"` or `"crossfade"`, default `"cut"`) in `state.json`, returned in `/api/state` and as the variable `mp_go_transition`, and shared by every open page; set it with `/go_transition/cut`, `/go_transition/crossfade` or `/go_transition/toggle`. It only changes the web page's Go button: `default_transition`, `/take`, `/xfade`, `/0/1` and Companion's actions are unchanged.

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

- **Export and import (share a layout):** **Settings > Look > Layout > More > Export layout**, or **Export layout** in the editor bar, asks for a short name (default `layout`) and downloads `cue-media-engine-layout-<name>.json`. Tick *Include appearance (skin, theme, waveforms)* to add those settings. If no custom layout is saved, the standard layout as it is on your screen is exported (the dialog says so). **Import layout** (same two places) opens a dialog where you choose a file, drop it, or paste the text (for sharing through chat). It checks the data, shows a small preview with the layout name and the hidden blocks, and changes nothing until you press **Apply**; *Also apply appearance* is off by default. Rules: valid JSON, under 64 KB, `app` must be `cue-media-engine-layout` (the older `companionplayer-layout` is accepted too), a `version` above 1 is refused as "made by a newer version", unknown fields are ignored, and the layout always goes through the same repair step as a saved layout, so only the repaired result is stored (never the raw file). Names are shown as plain text.
- **Undo import:** the previous layout (and appearance, if it was replaced) is kept in memory and in `cp_layout_prev`; **Undo import** is in the confirmation message and in the dialog. **Reset layout** works as before.
- **Narrow screens:** you can export and import on any width; on a screen narrower than 850 px the import is stored and applies when the page is on a wider screen. Editing stays wide-only.
