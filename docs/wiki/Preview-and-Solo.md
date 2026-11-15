# Preview, Solo and Mirror

Listening privately: the preview in the web page, the preview output, Solo live and the Mirror output.

## Preview in the web page

Preview can play **in the browser** instead of on the Pi: the track streams to the page and comes out of the speakers or
headphones of whatever device has the page open (laptop, phone). Choose it in **⚙ Settings > Audio > Preview plays on**
(*This browser*, *Player output*, or *Both*); the same menu sits at the top of the Preview card, styled like the Live **Output** menu (headphone icon, small "Output" label, full width on its own row, the full device name in its tooltip), with Pause, Stop, the seek bar and the time on the row below. The choice is remembered per browser, so the audio engineer's laptop can preview locally
while the player's own preview output stays available. With no preview device configured, *This browser* is used automatically. On a phone the preview also defaults to *This browser* when no choice has been made yet, even if the player has a preview output; the player's output stays in the list.

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

## Solo live (monitor)
While Solo live is on, the **Vol** slider of the Preview panel is relabelled **Solo vol** and sets how loud the live audio is on the preview output (it applies at once, on the player's preview output and in the browser). The preview meter shows what you hear: the live level at the preview volume. From Companion or OSC use `/preview/volume/<0-100>`, `/preview/volume/up[/n]` and `/preview/volume/down[/n]` (steps of 5 unless `/n` is given); the variable `mp_preview_volume` shows the level (0-100).

The **S** button under the Live meter (Solo live; it turns yellow while on) (or `/solo`, `/solo/1`, `/solo/0`) plays the live audio on the preview output, so you can listen on headphones. The preview track is muted but keeps playing, and comes back when you turn solo off. It needs a Pi preview output (Settings > Preview). It follows what is really live: crossfades, Play on Top, pause, seek and the live volume. The preview volume sets the monitor level. The room output is not affected. Variable `mp_preview_solo` is `1` while it is on. Solo is not remembered over a restart.

**Solo live in the browser.** When **Settings > Audio > Preview plays on** is *This browser* (or *Both*), the button works without a preview output: the page plays its own copy of the live tracks, kept in step with the live position and following the live volume, fades, Play on Top ducking and level match. The main output is not touched; the page only asks the player what is on air (`/api/monitor`). With *Both*, it also turns solo on for the preview output. Notes: it is a copy, not a tap of the real output, so it can sit a fraction of a second ahead or behind and it does not follow the room output device; each live track is streamed to the page, so over Wi-Fi a WAV needs about 10 MB a minute per track; the browser solo is per page, so `/solo` from Companion and `mp_preview_solo` only reflect the preview output; and the browser's own preview is muted while it is on.

## Mirror output
The mirror is **off by default**. Switch it on in **Settings > Audio > Mirror live to a second device**; a **Mirror** menu then appears beside Output (web page) where you choose the device. It plays a copy of the live audio on a second device: the production machine's headphone jack, or a second Dante USB adapter. It uses the same helper process as Preview, with the live monitor always on, so it follows the live track's position, fades, Play on Top ducking, level match and live volume. Preview and Solo live are independent of it. The choice is saved in `state.json` (or set `"mirror_enabled"` and `"mirror_device"` in `config.json`, matching a name from the startup device list). If the device is missing at startup the mirror stays off. `GET /api/devices` shows `mirror`, `mirror_error` and `mirror_playing` (and `notices` for saved outputs that are missing); `POST /api/mirror/device {"name": ...}` changes the device and `POST /api/mirror/enable {"on": true}` switches it on or off.
Two separate adapters run on their own clocks and can drift slightly apart, and the copy is a few tens of milliseconds behind the main output. It suits headphone monitoring or a backup feed, not two speakers in the same room.

## Preview in the playlist
Previewing a playlist track opens the preview controls (play/pause, stop, output, seek, volume, waveform and a slim level meter) in an expanded area under that row; the Preview panel at the top shrinks to a one-line note with a Show button. Previews started from the library or the trim editor still use the top panel. Frontend only: the preview API is unchanged.
