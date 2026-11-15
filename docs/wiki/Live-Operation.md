# Live operation

What to know while a show is running: resume after a restart, the RAM indicator, playlist progress and Stop All.

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

## RAM indicator
A track has to be decoded into RAM before it can play. A track that is already in RAM starts instantly; one that is not waits for a decode (about 5 seconds for a 15-minute MP3 on the production machine). The page shows where you stand:

- **Header indicator** (a small pill directly left of `Cache`; on a phone it sits in the row under the title with `Cache` and `RAM`): a spinning ring, `N/M` and a small bar while the playlists are being decoded (N tracks in RAM, M tracks used by the playlists); a green tick and `N/M` when every track is in RAM; an amber alert circle and `Full` when the cache is at 95 % of its budget (`cache_mb`) and some track is not in RAM, so the least recently used tracks are being dropped (the Cache numbers turn amber too). It goes to loading at once but back to the tick only after 2 s of being ready, and it is hidden when no playlist has tracks. If the cache is not full but some tracks are not loaded (the warm-up stops at 80 % of the budget) it shows the tick with the counts. Hover for the tooltip. Header order: indicator, `Cache 4.1 GB / 12.0 GB`, `RAM 23% (7.1 GB / 31 GB)`.
- **Marker before a track name:** only a track that needs attention is marked: a spinning blue ring = decoding now, a grey hollow ring = not loaded, starts after a short wait. No marker = in RAM, starts instantly . The playlist header says `3 of 4 in RAM`.
- **Go button:** if the cued track is not in RAM when you press Go, the button shows a spinner and `Loading… 4 s` (counting up) until the track starts. This is display only: Go waits for the decode exactly as before.

## Playlist progress
Each playlist header shows where you are in the list: `Track 3 of 6 · 12:34 played · 18:20 left · ends 21:47`, a chip for the playlist behavior (Stop at end, Loop, Shuffle, Next playlist; shown only while the playlist is collapsed, because the Playlist behavior menu shows it when expanded) and a bar with one segment per track. Segment widths follow each track's real length: the **A to B window** when the track is trimmed, so the time left is what will actually play. Played tracks are dark green, the current one is outlined and filled up to the position, upcoming ones are empty. A playlist with more than 40 tracks shows one continuous bar. In the rows, played tracks are dimmed  and the playing row shows its loudness and `elapsed / length` under the name and a thin progress line along the bottom; its seven buttons stay on one line like every other row, and the quick-flag stripe stays visible. A playlist that is not the playing one (or nothing live) shows only its totals.

- **Stop at end / Next playlist:** time left runs to the end of the list (or to a track whose end action is Stop). Next playlist also shows the name of the playlist that follows.
- **Loop playlist:** time left is counted for the current lap.
- **Shuffle:** a track counts as played when it has been played in the current round; time left is what remains of the round.
- A track that loops forever shows "looping this track" instead of a time left. A track set to play once counts twice.

## Stop All
The bold red **STOP ALL** button at the top of the page (or `/stopall` over OSC/HTTP) stops the live audio, stops the preview and clears the cue in one press. There is no confirmation, so use it deliberately.
