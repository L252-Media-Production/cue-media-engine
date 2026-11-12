"""2.7.4 Loop A-B: the preview worker's `loop` op (cpl/helpers/preview_worker.py), captured with SDL's disk audio driver.

The worker is started on its own (python player.py --preview "" from a copy of the app) and fed JSON lines like the player does. The test file is a constant
sample value (DC 0.5), so every sample of the capture is 0.5 x the gain applied: fades and gaps show up directly.
  * the loop wraps at B sample-accurately: consecutive laps are exactly 48000 frames apart (the lap boundary is the zero of the fade-out / fade-in), with no gap;
  * each lap has the equal-power fade-in at A (sin) and fade-out at B (cos), and full level in between;
  * the reported position stays inside [A, B), stop ends it, a new play replaces it.
Sample VALUES from the disk driver are exact; timing is only good to about 100 ms (see test_audio_capture.py), so only sample spacing and values are checked.
Skipped where the disk driver is not available.  Marker: audio."""
import json, os, subprocess, sys, tempfile, threading, time, wave
from pathlib import Path

import numpy as np
import pytest

from harness.appcopy import copy_app
from harness.instance import PROJECT
from test_audio_capture import FS, disk_driver_available

pytestmark = [pytest.mark.audio, pytest.mark.noreset]


@pytest.fixture(scope="module")
def disk_ok():
    if not disk_driver_available():
        pytest.skip("SDL's disk audio driver is not available in this pygame/SDL build")


class Worker:
    def __init__(self, folder):
        self.dir = Path(folder)
        self.app = copy_app(self.dir / "app", PROJECT)
        self.raw = self.dir / "out.raw"
        wav = self.dir / "dc.wav"
        with wave.open(str(wav), "wb") as w:
            w.setnchannels(2); w.setsampwidth(2); w.setframerate(FS)
            w.writeframes(np.full((10 * FS, 2), 16384, dtype="<i2").tobytes())
        self.wav = wav
        self.status, self.lines = {}, []
        self.proc = subprocess.Popen([sys.executable, "-I", str(self.app), "--preview", ""], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     env=dict(os.environ, SDL_AUDIODRIVER="disk", SDL_DISKAUDIOFILE=str(self.raw), PYGAME_HIDE_SUPPORT_PROMPT="1"))
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        for line in self.proc.stdout:
            try:
                self.status = json.loads(line)
                self.lines.append(self.status)
            except Exception:
                pass

    def send(self, **c):
        self.proc.stdin.write((json.dumps(c) + "\n").encode())
        self.proc.stdin.flush()

    def wait(self, state, timeout=10):
        t = time.time() + timeout
        while time.time() < t:
            if self.status.get("state") == state:
                return True
            time.sleep(0.05)
        return False

    def close(self):
        try:
            self.send(cmd="quit")
            self.proc.wait(timeout=5)
        except Exception:
            self.proc.kill()


@pytest.fixture
def worker(disk_ok):
    w = Worker(tempfile.mkdtemp(prefix="cploop-"))
    yield w
    w.close()


def left(w):
    time.sleep(0.6)
    a = np.fromfile(w.raw, dtype="<i2")
    return a[: len(a) // 2 * 2].reshape(-1, 2)[:, 0].astype(np.float64) / 32768.0


def boundaries(x):
    """Centres of the clusters of (near) zero samples that are short: the lap boundaries (the long zero run at the end of the capture is the silence after stop)."""
    z = np.where(np.abs(x) < 1e-6)[0]
    out, i = [], 0
    while i < len(z):
        j = i
        while j + 1 < len(z) and z[j + 1] - z[j] <= 2:
            j += 1
        if z[j] - z[i] < 50:
            out.append((z[i] + z[j]) / 2)
        i = j + 1
    return out


@pytest.mark.sev(3)
def test_loop_wraps_at_b_without_a_gap_and_applies_both_fades(worker):
    w = worker
    w.send(cmd="play", path=str(w.wav), start=0)
    assert w.wait("playing")
    time.sleep(0.4)
    w.send(cmd="loop", a=2.0, b=3.0, fin=200, fout=200)
    time.sleep(3.7)                                     # about 3.5 laps of audio at the disk driver's pace
    w.send(cmd="stop")
    x = left(w)
    bs = boundaries(x)
    assert len(bs) >= 3, f"expected at least 3 lap boundaries, found {bs}"
    gaps = np.diff(bs)
    assert all(abs(g - FS) <= 2 for g in gaps), f"laps must be exactly 1 s (48000 frames) apart: {gaps}"
    lap = x[int(round(bs[0])) + 1: int(round(bs[0])) + 1 + FS]            # the first full lap, from its first sample
    assert abs(lap[int(0.1 * FS)] - 0.5 * np.sin(0.5 * np.pi / 2)) < 0.004, "fade-in at A: equal power, half way = sin(pi/4)"
    assert abs(lap[int(0.02 * FS)] - 0.5 * np.sin(0.1 * np.pi / 2)) < 0.004
    assert abs(lap[int(0.9 * FS)] - 0.5 * np.cos(0.5 * np.pi / 2)) < 0.004, "fade-out at B: cos"
    assert lap[int(0.25 * FS): int(0.75 * FS)].min() > 0.499 and lap[int(0.25 * FS): int(0.75 * FS)].max() < 0.501, "full level, no dip, no gap between the fades"
    assert abs(x[int(bs[0]) - 200]) > 0.49, "before the loop the plain playback was at full level"


@pytest.mark.sev(3)
def test_loop_position_stays_inside_a_to_b_and_stop_ends_it(worker):
    w = worker
    w.send(cmd="play", path=str(w.wav), start=0)
    assert w.wait("playing")
    w.send(cmd="loop", a=2.0, b=3.0, fin=100, fout=100)
    time.sleep(0.8)
    n0 = len(w.lines)
    time.sleep(2.4)
    pos = [s["pos"] for s in w.lines[n0:] if s.get("state") == "playing"]
    assert len(pos) > 15 and all(1.99 <= p <= 3.01 for p in pos), pos
    assert max(pos) - min(pos) > 0.6, "it keeps wrapping around, not stuck"
    w.send(cmd="stop")
    assert w.wait("stopped")
    w.send(cmd="play", path=str(w.wav), start=5.0)       # a new play replaces any loop
    assert w.wait("playing")
    time.sleep(1.2)
    assert w.status["pos"] > 5.5 and w.status["pos"] < 7.5, w.status


@pytest.mark.sev(3)
def test_seek_leaves_loop_mode(worker):
    w = worker
    w.send(cmd="play", path=str(w.wav), start=0)
    assert w.wait("playing")
    w.send(cmd="loop", a=2.0, b=3.0, fin=100, fout=100)
    time.sleep(0.8)
    w.send(cmd="seek", pos=6.0)
    time.sleep(1.2)
    assert 6.5 < w.status["pos"] < 8.0, "after a seek the file plays on normally, it does not wrap back to A"


@pytest.mark.sev(3)
@pytest.mark.covers("http.POST /api/preview/ctl")
def test_loop_op_through_the_player_is_validated_and_never_touches_the_live_decks(std, preview):
    api = std
    assert api.res("preview/1/2") == "ok"
    api.wait_for(lambda s: s["preview_state"] == "playing", 8, desc="preview playing")
    for bad in ({"a": "x", "b": 3}, {"a": 2, "b": 2.05}, {"a": -1, "b": 3}, {"a": 2, "b": 3, "fin": 20000}, {"a": 2, "b": 3, "fout": -5}, {"a": None, "b": 3}):
        assert api.post("/api/preview/ctl", {"cmd": "loop", **bad}).status == 400, bad
    r = api.post("/api/preview/ctl", {"cmd": "loop", "a": 2, "b": 5, "fin": 200, "fout": 300})
    assert r.status == 200
    time.sleep(1.5)
    s = api.state()
    assert s["live_id"] == "-" and s["preview_state"] == "playing", "the live output is untouched and the preview keeps playing"
    assert api.res("preview/stop") == "ok"
    api.wait_for(lambda s: s["preview_state"] == "stopped", 5, desc="stopped")
