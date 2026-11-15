# File information

The **i** popover on library and playlist rows.

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

- Without ffmpeg the popover still shows the size, the length (from the existing length cache), the WAV header facts of a `.wav`, and LUFS from the built-in measurement when scipy is installed; the rest says "needs ffmpeg".
