# Stage page

A display-only page with the live track's time remaining.

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
