# Trim a track (A and B points)

Start and end points, fades at A and B, Precision, Loop A-B preview.

### A and B points (trim a track)
Press the bracket icon on a track row, or the same bracket icon on the Cue panel's button row, to open the trim window. It shows the
waveform; drag the green **A** (start) and red **B** (end) markers, or type times like `1:23.5`, or play the preview and press **Set A** / **Set B** at the moment you hear the spot. Everything outside the
two markers is dimmed and never plays: the track starts at A and ends at B, so the remaining time, the waveform and the
play modes all use the trimmed length. **At B** chooses between a **fade out** and a hard **cut**. The fade length is per track
(`for 1.5 s`: type it or use the field's arrows / Up / Down keys, 0.1 to 10 s, never longer than B minus A; stored as `fade_ms` in the track's trim); a track without its own
value uses the default, **Settings > Audio > Transitions > Fade-out at B** (config key `trim_fade_ms`, default 1500 ms), and
**Use default** drops the override. **At A** chooses **Cut** (the default: the track starts at full level, exactly as before) or **Fade in**, with its own length in the same way
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
