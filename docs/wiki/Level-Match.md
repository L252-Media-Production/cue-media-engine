# Level match

Per-playlist loudness matching.

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
