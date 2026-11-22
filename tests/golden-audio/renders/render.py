#!/usr/bin/env python3
"""Reference renders: short WAVs of what the REAL player mixer outputs for four simple mixes (docs/AUDIO-SPEC.md).

    python tests/golden-audio/renders/render.py --write      # render and overwrite the WAVs and renders.json
    python tests/golden-audio/renders/render.py --check      # render again, compare the 50 ms tone envelopes with renders.json (tolerance below)
    python tests/golden-audio/renders/render.py --repeat     # render twice and say whether the two runs are bit-identical (they are not, see README)

Method = tests/api/test_audio_capture.py: a disposable player instance with SDL_AUDIODRIVER=disk, which writes every buffer the mixer renders to a raw file.
The scenarios are driven through the HTTP API in wall-clock time, so the disk driver's real-time pacing and the 50 ms tick make a render repeatable only to
within about 100 ms and a few percent of amplitude, NOT bit for bit. Not part of `python tests/run.py` (it takes about 40 s of real time and needs the disk
audio driver); the in-process fixtures (tests/golden-audio/fixtures) are the exact ones.

Each render is the LEFT channel (the player puts a mono file on both) as a mono 48 kHz 16-bit WAV, cut from the first audible sample to a fixed length.
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
import wave
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent))                   # tests/
from harness import client                                    # noqa: E402
from harness.instance import Instance                         # noqa: E402

SPEC_VERSION = 1
FS, WIN = 48000, 2400                                         # 50 ms windows
TOL_AMP = 0.06                                                # allowed worst deviation of a window amplitude (full scale 1.0, tones are 0.5), after the best shift
MAX_SHIFT = 3                                                 # windows (150 ms): timing slack of the wall-clock scenarios
FREQS = (1000, 2000)
SCENARIOS = {
    "crossfade": {"seconds": 3.6, "about": "1 kHz tone (0.5) for 1 s, then a 2 s equal-power crossfade into a 2 kHz tone (0.5); the capture starts at the first sample and ends 0.6 s after the fade"},
    "ducked": {"seconds": 3.8, "about": "1 kHz background (0.5); after 1 s a 2 s voice-over (2 kHz, 0.5) is played on top: threshold -30 dB, ratio 6, attack 10 ms, release 500 ms, hold on; the background ducks and comes back"},
    "loop": {"seconds": 3.2, "about": "a 1 s clip (0.5 s of 1 kHz then 0.5 s of 2 kHz, both whole cycles) set to end action loop: the pattern repeats seamlessly every 1 s"},
    "trim_fade_out": {"seconds": 4.0, "about": "a 1 kHz tone of 10 s with Out point B = 3 s and a 1.5 s fade at B: full level for 1.5 s, an equal-power fade down to B, then silence"},
}


def disk_ok():
    code = ("import os,sys;os.environ['PYGAME_HIDE_SUPPORT_PROMPT']='1';import pygame,time;pygame.mixer.pre_init(48000,-16,2,1024);"
            "pygame.mixer.init(allowedchanges=0);time.sleep(0.3);sys.exit(0 if pygame.mixer.get_init()==(48000,-16,2) else 3)")
    out = Path(tempfile.mkdtemp(prefix="cpdisk-")) / "probe.raw"
    try:
        r = subprocess.run([sys.executable, "-I", "-c", code], env=dict(os.environ, SDL_AUDIODRIVER="disk", SDL_DISKAUDIOFILE=str(out)), capture_output=True, timeout=30)
        return r.returncode == 0 and out.exists() and out.stat().st_size > 0
    except Exception:
        return False


def write_wav(path, frames, mono=True):
    y = np.round(np.asarray(frames) * 32768).clip(-32768, 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(FS)
        w.writeframes(y.tobytes())


def tone(freq, amp, secs):
    n = np.arange(int(secs * FS))
    return np.sin(2 * np.pi * freq * n / FS) * amp


def amp_windows(y, freq, nw=None):
    """Amplitude of a `freq` tone in every 50 ms window (single-bin DFT; whole cycles, so no leakage)."""
    nw = len(y) // WIN if nw is None else nw
    t = np.arange(WIN) / FS
    c, s = np.cos(2 * np.pi * freq * t), np.sin(2 * np.pi * freq * t)
    w = y[:nw * WIN].reshape(nw, WIN)
    return 2.0 / WIN * np.hypot(w @ c, w @ s)


def load_raw(path, start):
    a = np.fromfile(path, dtype="<i2")
    a = a[: len(a) // 2 * 2].reshape(-1, 2)
    return a[start:, 0].astype(np.float64) / 32768.0


def capture_all():
    """Run every scenario in one disposable instance. -> {name: left-channel samples cut from the first audible sample, fixed length}."""
    tmp = Path(tempfile.mkdtemp(prefix="cprender-"))
    raw = tmp / "out.raw"
    inst = Instance(wav_only=True, extra_env={"SDL_AUDIODRIVER": "disk", "SDL_DISKAUDIOFILE": str(raw)}, extra_config={"duck_hold": True})
    inst.start()
    out = {}
    try:
        lib = inst.workdir / "media" / "library"
        for name, y in (("t1k.wav", tone(1000, 0.5, 30)), ("t2k.wav", tone(2000, 0.5, 30)), ("voice2k.wav", tone(2000, 0.5, 2)),
                        ("pattern.wav", np.concatenate([tone(1000, 0.5, 0.5), tone(2000, 0.5, 0.5)])), ("t1k10.wav", tone(1000, 0.5, 10))):
            write_wav(lib / name, y)                                   # mono files: the player plays them on both channels
        api = client.Api(inst.base_url, osc_port=inst.osc_port)
        api.cmd("rescan")
        api.post("/api/playlists", {"name": "T"})
        assert api.post("/api/playlists/0/add", {"files": ["t1k.wav", "t2k.wav", "pattern.wav", "t1k10.wav"]}).status == 200
        api.post("/api/playlists", {"name": "V"})
        assert api.post("/api/playlists/1/add", {"files": ["voice2k.wav"]}).status == 200
        t0 = time.time()
        while time.time() - t0 < 30 and api.state()["mem"].get("cache_tracks", 0) < 5:        # every track decoded: nothing loads during a scenario
            time.sleep(0.2)
        api.post("/api/settings/top", {"track_pct": 100, "threshold_db": -30, "ratio": 6, "attack_ms": 10, "release_ms": 500, "hold": True, "fade_ms": 1500})
        api.post("/api/settings/transition", {"default": "cut", "crossfade_s": 3, "trim_fade_s": 1.5})

        def run(name, steps):
            api.cmd("stopall")
            time.sleep(1.2)
            time.sleep(0.3)
            mark = raw.stat().st_size // 4
            steps()
            time.sleep(0.8)                                                      # the last buffers reach the file
            y = load_raw(raw, mark)
            k = int(np.argmax(np.abs(y) > 0.005))
            n = int(SCENARIOS[name]["seconds"] * FS)
            out[name] = y[k:k + n]
            api.cmd("stopall")

        def crossfade():
            assert api.res("0/0") == "ok"
            time.sleep(1.0)
            assert api.res("0/1/xfade", ms=2000) == "ok"
            time.sleep(2.7)

        def ducked():
            assert api.res("0/0") == "ok"
            time.sleep(1.0)
            assert api.res("1/0/top") == "ok"
            time.sleep(3.0)

        def loop():
            assert api.res("0/2/end/loop") == "ok"
            assert api.res("0/2") == "ok"
            time.sleep(3.3)

        def trim_fade_out():
            assert api.post("/api/playlists/0/trim", {"track": 3, "out": 3.0, "end": "fade", "fade_ms": 1500}).status == 200
            assert api.res("0/3") == "ok"
            time.sleep(4.2)
        for name, fn in (("crossfade", crossfade), ("ducked", ducked), ("loop", loop), ("trim_fade_out", trim_fade_out)):
            run(name, fn)
    finally:
        inst.stop()
    return out


def envelope(y):
    return {str(f): [round(float(x), 3) for x in amp_windows(y, f)] for f in FREQS}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _dist_to_range(v, vals):
    return max(0.0, float(min(vals)) - v, v - float(max(vals)))


def compare(y, ref_env):
    """Worst deviation of the 50 ms tone amplitudes from the committed envelope. Allowed timing slack: a global shift of up to +-MAX_SHIFT windows, and on top
    of it a window's value only has to lie within the range of the other side's three neighbouring windows (and the other way round): a sharp edge (a voice-over
    starting or stopping, the ducking attack) falls at a different point of a 50 ms window from one run to the next and gives an in-between value."""
    best = (9.0, 0)
    for shift in range(-MAX_SHIFT, MAX_SHIFT + 1):
        worst = 0.0
        for f in FREQS:
            ref = np.array(ref_env[str(f)])
            got = amp_windows(y, f)
            for i in range(MAX_SHIFT + 1, min(len(ref), len(got)) - MAX_SHIFT - 1):
                j = i + shift
                worst = max(worst, _dist_to_range(got[j], ref[i - 1:i + 2]), _dist_to_range(ref[i], got[j - 1:j + 2]))
        if worst < best[0]:
            best = (worst, shift)
    return best


def main(argv=None):
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--write", action="store_true")
    g.add_argument("--check", action="store_true")
    g.add_argument("--repeat", action="store_true", help="render twice and report whether the runs are bit-identical")
    args = ap.parse_args(argv)
    if not disk_ok():
        print("SDL's disk audio driver is not available here: cannot render")
        return 2
    if args.repeat:
        a, b = capture_all(), capture_all()
        for name in SCENARIOS:
            same = len(a[name]) == len(b[name]) and np.array_equal(a[name], b[name])
            n = min(len(a[name]), len(b[name]))
            print(f"{name}: bit-identical={same}; worst sample difference {float(np.max(np.abs(a[name][:n] - b[name][:n]))):.4f}; window-amplitude deviation {compare(b[name], envelope(a[name]))}")
        return 0
    got = capture_all()
    if args.write:
        meta = {"spec_version": SPEC_VERSION, "sample_rate": FS, "channels": 1, "bits": 16, "method": "SDL disk audio driver capture of the real player mixer, left channel, from the first audible sample",
                "deterministic": False,
                "tolerance_notes": ("Not bit-for-bit repeatable (the loop render happens to be): the scenarios run in wall-clock time (the HTTP call, the 50 ms tick and the disk driver's pacing at about 97 percent of real time move events by up to about 100 ms between runs, "
                                    "and fades are applied in 50 ms steps against that clock). Compare 50 ms tone amplitudes (single-bin DFT) with an absolute tolerance of " + f"{TOL_AMP:.2f}" + " (tones are 0.5 full scale) after the best shift of up to "
                                    + f"{MAX_SHIFT} windows ({MAX_SHIFT * 50} ms)" + ", a window only has to lie within the range of the other render's three neighbouring windows (sharp edges give in-between values). "
                                    "sha256 is of the committed file (integrity of the reference), not of a re-render."),
                "tolerance": {"window_ms": 50, "amplitude_abs": TOL_AMP, "max_shift_windows": MAX_SHIFT}, "renders": {}}
        for name, y in got.items():
            f = HERE / f"{name}.wav"
            write_wav(f, y)
            meta["renders"][name] = {"file": f.name, "about": SCENARIOS[name]["about"], "sample_rate": FS, "channels": 1, "frames": int(len(y)), "length_s": round(len(y) / FS, 3),
                                     "sha256": sha(f), "envelope_50ms": envelope(y)}
        (HERE / "renders.json").write_text(json.dumps(meta, indent=1) + "\n")
        print("wrote", ", ".join(f"{n}.wav" for n in got), "and renders.json")
        return 0
    meta = json.loads((HERE / "renders.json").read_text())
    bad = 0
    for name, y in got.items():
        ref = meta["renders"][name]
        worst, shift = compare(y, ref["envelope_50ms"])
        ok = worst <= TOL_AMP
        bad += not ok
        print(f"{'ok  ' if ok else 'FAIL'} {name}: worst window deviation {worst:.3f} (allowed {TOL_AMP}), shift {shift} windows")
        if sha(HERE / ref["file"]) != ref["sha256"]:
            print(f"FAIL {name}: the committed {ref['file']} does not match its sha256 in renders.json")
            bad += 1
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
