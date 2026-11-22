# Reference renders

Four short WAVs of what the REAL player mixer outputs (docs/AUDIO-SPEC.md). They complement the exact in-process fixtures in `../fixtures/`: those say what the gains are, these say what comes out of the mixer.

| File | Mix | Length |
|---|---|---|
| `crossfade.wav` | 1 kHz tone for 1 s, then a 2 s equal-power crossfade into a 2 kHz tone | 3.6 s |
| `ducked.wav` | 1 kHz background; a 2 s voice-over (2 kHz) played on top at 1 s: threshold -30 dB, ratio 6, attack 10 ms, release 500 ms, hold on | 3.8 s |
| `loop.wav` | a 1 s clip (0.5 s of 1 kHz, 0.5 s of 2 kHz) with end action loop: the pattern repeats seamlessly | 3.2 s |
| `trim_fade_out.wav` | 1 kHz tone with Out point B = 3 s and a 1.5 s fade at B: full level, equal-power fade, silence | 4.0 s |

Format: mono (the left channel; the player puts a mono file on both), 48 kHz, 16-bit, cut from the first audible sample. Tones have amplitude 0.5 (peak, full scale 1.0). Total size about 1.4 MB. `renders.json` has sample rate, frame count, length, the sha256 of each committed file, the scenario text and the 50 ms tone envelopes used for comparing.

## Commands (not part of `python tests/run.py`)

```
python tests/golden-audio/renders/render.py --check     # render again (about 45 s of real time), compare with renders.json
python tests/golden-audio/renders/render.py --write     # re-render and overwrite the WAVs and renders.json (only for a deliberate change of audio behaviour: bump the spec version)
python tests/golden-audio/renders/render.py --repeat    # render twice and report whether the two runs are bit-identical
```

Needs the disk audio driver of SDL (`SDL_AUDIODRIVER=disk`, in pygame's SDL on Linux, macOS and Windows) and starts a disposable player instance (the harness of `tests/harness`; the real config and library are not touched).

## Not bit-for-bit repeatable

The scenarios are driven through the HTTP API in wall-clock time, and the disk driver paces itself at about 97 % of real time, so two renders differ. Measured with `--repeat` on macOS (arm64), pygame 2.6.1:

- `loop`: bit-identical (no gain is moving; it starts at the first audible sample).
- `crossfade`, `trim_fade_out`: not identical (worst sample difference up to 0.02 for the trim, ~0.9 around the crossfade because the second tone's phase and the 50 ms fade steps shift); the 50 ms tone amplitudes differ by about 0.015 at most.
- `ducked`: not identical; the voice-over and the ducking attack land at a different point of a 50 ms window from run to run, so single windows at the edges differ by up to ~0.2 (an in-between value).

So `renders.json` stores tolerances, not a hash of a re-render (the sha256 there only protects the committed file):

- window 50 ms, amplitude of each tone by a single-bin DFT (whole cycles, no leakage);
- absolute tolerance 0.06 (tones are 0.5);
- a global timing shift of up to 3 windows (150 ms) is allowed;
- in addition a window only has to lie within the range of the other render's three neighbouring windows (and the reverse), so an edge that falls in the middle of a window passes.

Tried against the committed envelopes: a linear crossfade (0.098), a 1 s fade instead of 2 s (0.28) and a render shifted by 400 ms (0.5) fail; the same crossfade shifted by 100 ms passes (by design).

A consumer (CueME Stage) should render the same four scenarios with its own engine, cut at the first audible sample, and compare with the same rule.
