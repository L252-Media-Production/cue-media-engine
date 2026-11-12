"""Gap 10 (docs/split-plan.md 5.4), EXPERIMENTAL: what the player really renders, captured with SDL's disk audio driver and analysed with numpy.

SDL_AUDIODRIVER=disk makes the mixer write every buffer it renders to a raw file (SDL_DISKAUDIOFILE) instead of a sound card. It runs the mixer at the
format the player asks for (48 kHz, 16-bit, stereo, buffer 1024) and paces itself in real time: SDL waits one buffer length per write, so the file
grows at about 97 % of real time (186,000 of 192,000 bytes/s measured: the wait is rounded to whole milliseconds). Sample VALUES are exact (see
test_disk_driver_matches_what_the_player_mixer_renders), timestamps are only good to about 100 ms, so every check below works on the samples
themselves: tone amplitudes per 50 ms window (a single-bin DFT, no leakage because every window holds whole cycles), residuals against a fitted sine,
runs of zeros.

These tests start their own instance (SDL_AUDIODRIVER=disk, own library with sine tones of known level) and are skipped where the disk driver is
not available. Marker: audio.  Run only these:  python tests/run.py -m audio"""
import os, subprocess, sys, tempfile, time, wave
from pathlib import Path

import numpy as np
import pytest

from harness import client
from harness.instance import Instance

pytestmark = [pytest.mark.audio, pytest.mark.noreset]
FS, WIN = 48000, 2400                                   # 50 ms windows


def disk_driver_available():
    code = ("import os,sys;os.environ['PYGAME_HIDE_SUPPORT_PROMPT']='1';import pygame,time;pygame.mixer.pre_init(48000,-16,2,1024);"
            "pygame.mixer.init(allowedchanges=0);time.sleep(0.3);sys.exit(0 if pygame.mixer.get_init()==(48000,-16,2) else 3)")
    out = Path(tempfile.mkdtemp(prefix="cpdisk-")) / "probe.raw"
    try:
        r = subprocess.run([sys.executable, "-I", "-c", code], env=dict(os.environ, SDL_AUDIODRIVER="disk", SDL_DISKAUDIOFILE=str(out)),
                           capture_output=True, timeout=30)
        return r.returncode == 0 and out.exists() and out.stat().st_size > 0
    except Exception:
        return False


@pytest.fixture(scope="module")
def disk_ok():
    if not disk_driver_available():
        pytest.skip("SDL's disk audio driver is not available in this pygame/SDL build, so the real output cannot be captured")


def load_raw(path, start_sample=0):
    a = np.fromfile(path, dtype="<i2")
    a = a[: len(a) // 2 * 2].reshape(-1, 2)
    return a[start_sample:, 0].astype(np.float64) / 32768.0, a[start_sample:, 1].astype(np.float64) / 32768.0


def amp(y, freq, n_windows=None):
    """Amplitude of a `freq` tone per 50 ms window (single-bin DFT)."""
    nw = len(y) // WIN if n_windows is None else n_windows
    t = np.arange(WIN) / FS
    c, s = np.cos(2 * np.pi * freq * t), np.sin(2 * np.pi * freq * t)
    w = y[:nw * WIN].reshape(nw, WIN)
    return 2.0 / WIN * np.hypot(w @ c, w @ s)


def write_tone(path, freq, amplitude, seconds, stereo=True):
    n = np.arange(int(seconds * FS))
    y = np.round(amplitude * 32768 * np.sin(2 * np.pi * freq * n / FS)).astype("<i2")
    if stereo:
        y = np.repeat(y[:, None], 2, axis=1)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2 if stereo else 1); w.setsampwidth(2); w.setframerate(FS)
        w.writeframes(y.tobytes())


class Rig:
    def __init__(self, inst, api, raw):
        self.inst, self.api, self.raw = inst, api, raw
        self.mark = 0

    def start_capture(self):
        time.sleep(0.3)
        self.mark = (self.raw.stat().st_size // 4)       # samples already in the file: everything after this belongs to the test

    def samples(self):
        time.sleep(0.6)                                    # let the last buffers reach the file
        return load_raw(self.raw, self.mark)


@pytest.fixture(scope="module")
def rig(request, disk_ok):
    tmp = Path(tempfile.mkdtemp(prefix="cpaudio-"))
    raw = tmp / "out.raw"
    inst = Instance(project_dir=request.config.getoption("--project"), wav_only=True, extra_env={"SDL_AUDIODRIVER": "disk", "SDL_DISKAUDIOFILE": str(raw)},
                    extra_config={"duck_hold": True})
    inst.start()
    lib = inst.workdir / "media" / "library"
    write_tone(lib / "t1k.wav", 1000, 0.5, 30)
    write_tone(lib / "t2k.wav", 2000, 0.5, 30)
    write_tone(lib / "voice2k.wav", 2000, 0.5, 3)
    write_tone(lib / "loop1k.wav", 1000, 0.5, 0.5)       # 500 whole cycles: the end joins the start without a step
    api = client.Api(inst.base_url, osc_port=inst.osc_port)
    api.cmd("rescan")
    api.post("/api/playlists", {"name": "T"})
    assert api.post("/api/playlists/0/add", {"files": ["t1k.wav", "t2k.wav", "loop1k.wav"]}).status == 200
    api.post("/api/playlists", {"name": "V"})
    assert api.post("/api/playlists/1/add", {"files": ["voice2k.wav"]}).status == 200
    t0 = time.time()
    while time.time() - t0 < 20 and api.state()["mem"].get("cache_tracks", 0) < 4:       # every track decoded: nothing loads during the tests
        time.sleep(0.2)
    api.post("/api/settings/top", {"track_pct": 100, "threshold_db": -30, "ratio": 6, "attack_ms": 10, "release_ms": 500, "hold": True, "fade_ms": 1500})
    api.post("/api/settings/transition", {"default": "cut", "crossfade_s": 3, "trim_fade_s": 1.5})
    yield Rig(inst, api, raw)
    inst.stop()


@pytest.fixture()
def quiet(rig):
    rig.api.cmd("stopall")
    time.sleep(1.2)
    rig.start_capture()
    return rig


# ----------------------------------------------------------------------------------------------------------------- the method
@pytest.mark.sev(3)
def test_disk_driver_matches_what_the_player_mixer_renders(disk_ok, tmp_path):
    """The method itself: with the player's mixer settings a known signal comes out of the file bit for bit, and the file grows in (about) real time."""
    raw = tmp_path / "d.raw"
    code = r'''
import os, sys, time, numpy as np
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
import pygame
pygame.mixer.pre_init(48000, -16, 2, 1024)
pygame.mixer.init(allowedchanges=0)
assert pygame.mixer.get_init() == (48000, -16, 2), pygame.mixer.get_init()
x = np.zeros(48000, dtype="<i2"); x[:480] = np.round(24000 * np.cos(2 * np.pi * 1000 * np.arange(480) / 48000))
snd = pygame.mixer.Sound(buffer=np.repeat(x[:, None], 2, axis=1).tobytes())
time.sleep(1.0); snd.play(); sizes = []; t0 = time.time()
for i in range(8):
    time.sleep(0.5); sizes.append((time.time() - t0, os.path.getsize(sys.argv[1])))
print(repr(sizes))
'''
    r = subprocess.run([sys.executable, "-I", "-c", code, str(raw)], env=dict(os.environ, SDL_AUDIODRIVER="disk", SDL_DISKAUDIOFILE=str(raw)), capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr[-500:]
    sizes = eval(r.stdout.strip().splitlines()[-1])
    rate = (sizes[-1][1] - sizes[0][1]) / (sizes[-1][0] - sizes[0][0])
    print(f"disk driver pacing: {rate:.0f} bytes/s = {rate / 192000 * 100:.1f} % of real time (48 kHz x 16-bit x 2 channels = 192000 B/s)")
    assert 0.90 * 192000 < rate < 1.05 * 192000, f"the disk driver is not paced in real time here: {rate:.0f} bytes/s"
    L, R = load_raw(raw)
    k = int(np.argmax(np.abs(L) > 0.1))
    want = np.round(24000 * np.cos(2 * np.pi * 1000 * np.arange(480) / 48000)) / 32768
    assert np.array_equal(L[k:k + 480], want), "the captured burst differs from the source: the capture is not bit-exact"
    assert np.array_equal(L, R) and np.count_nonzero(L[:k]) == 0 and np.count_nonzero(L[k + 480:]) == 0


# ----------------------------------------------------------------------------------------------------------------- crossfade
@pytest.mark.sev(1)
def test_crossfade_has_no_energy_dip_and_no_step_at_start_or_end(quiet):
    rig = quiet
    api = rig.api
    assert api.res("0/0") == "ok"
    time.sleep(2.0)
    assert api.res("0/1/xfade", ms=2000) == "ok"
    time.sleep(4.5)
    L, _ = rig.samples()
    a1, a2 = amp(L, 1000), amp(L, 2000)
    start = int(np.argmax(a2 > 0.01))
    assert a2[start] > 0.01, "the second tone never appeared"
    n = 40                                               # a 2 s fade is 40 windows of 50 ms
    # shape: equal power. The disk driver renders at about 97 % of real time while the fade follows the wall clock, so window k of the capture sits at
    # fade position s * (k + 0.5) / n with s a little above 1 (and the first window may begin up to a window early or late): fit s and the offset,
    # then the residual must be small. A wrong curve (linear, wrong length, a dip) does not fit for any s.
    best = (9.0, 1.0, 0)
    for sc in np.linspace(1.0, 1.08, 17):
        x = np.clip(sc * (np.arange(n) + 0.5) / n, 0, 1)
        want1, want2 = 0.5 * np.cos(x * np.pi / 2), 0.5 * np.sin(x * np.pi / 2)
        for d in (-1, 0, 1, 2):
            i0 = start + d
            if i0 < 0 or i0 + n > len(a1):
                continue
            e = np.max(np.abs(a1[i0:i0 + n] - want1)) + np.max(np.abs(a2[i0:i0 + n] - want2))
            if e < best[0]:
                best = (e, sc, d)
    err = best[0]
    seg1, seg2 = a1[start + best[2]:start + best[2] + n], a2[start + best[2]:start + best[2] + n]
    assert err < 0.06, f"the crossfade does not follow the equal-power curve (worst summed error {err:.3f} after fitting time scale {best[1]:.3f} and offset {best[2]})"
    power = (seg1 ** 2 + seg2 ** 2) / 0.25
    mid = power[4:n - 4]
    print(f"crossfade: worst summed deviation from equal power {err:.3f} (scale {best[1]:.3f}, offset {best[2]}); power range {10 * np.log10(mid.min()):.2f} .. {10 * np.log10(mid.max()):.2f} dB")
    assert np.all(np.abs(10 * np.log10(mid)) < 0.7), f"energy dip/bump in the middle: {10 * np.log10(mid.min()):.2f} .. {10 * np.log10(mid.max()):.2f} dB"
    # no step at the start and at the end of the fade
    for a, name in ((a1, "old"), (a2, "new")):
        around = np.concatenate([np.diff(a[max(0, start - 6):start + 6]), np.diff(a[start + n - 6:start + n + 6])])
        assert np.max(np.abs(around)) < 0.045, f"a step in the {name} tone at the start or end of the fade: {np.max(np.abs(around)):.3f}"
    assert a1[start + n + 2] < 0.01 and abs(a2[start + n + 2] - 0.5) < 0.02, "after the fade only the new tone remains, at full level"
    assert abs(a1[max(0, start - 2)] - 0.5) < 0.02, "before the fade only the old tone, at full level"


@pytest.mark.sev(1)
def test_a_cut_replaces_the_tone_without_a_gap(quiet):
    rig = quiet
    rig.api.res("0/0")
    time.sleep(1.5)
    rig.api.res("0/1")
    time.sleep(1.5)
    L, _ = rig.samples()
    a1, a2 = amp(L, 1000), amp(L, 2000)
    k = int(np.argmax(a2 > 0.1))
    assert a1[k - 2] > 0.45 and a1[k + 2] < 0.01 and a2[k + 2] > 0.45
    seg = np.abs(L[(k - 2) * WIN:(k + 3) * WIN])
    zero_run = max((len(r) for r in np.split(np.arange(len(seg)), np.nonzero(seg > 1e-4)[0]) if len(r)), default=0)
    assert zero_run < 400, f"a silent gap of {zero_run} samples at the cut"


# ----------------------------------------------------------------------------------------------------------------- loop
@pytest.mark.sev(1)
def test_a_looped_short_region_has_no_gap_or_discontinuity_at_the_loop_point_over_ten_passes(quiet):
    rig = quiet
    api = rig.api
    assert api.res("0/2/end/loop") == "ok"
    assert api.res("0/2") == "ok"
    time.sleep(6.2)                                      # 12 passes of 0.5 s (the disk driver renders 97 % of real time)
    api.res("stopall")
    L, _ = rig.samples()
    on = np.nonzero(np.abs(L) > 1e-3)[0]
    first = int(on[0])
    # the playing region: from the first sample to the last non-zero one
    last = int(on[-1])
    seg = L[first:last + 1]
    passes = len(seg) / (0.5 * FS)
    assert passes >= 10, f"only {passes:.1f} passes captured"
    # a fit of one continuous sine over the whole region: a gap, a repeated or a missing sample shows up as a residual of the size of the signal
    n = np.arange(len(seg))
    M = np.stack([np.sin(2 * np.pi * 1000 * n / FS), np.cos(2 * np.pi * 1000 * n / FS)], axis=1)
    coef, *_ = np.linalg.lstsq(M, seg, rcond=None)
    res = seg - M @ coef
    print(f"loop: {passes:.1f} passes, fitted amplitude {np.hypot(*coef):.4f}, worst residual {np.max(np.abs(res)):.5f}")
    assert abs(np.hypot(*coef) - 0.5) < 0.005
    assert np.max(np.abs(res)) < 0.003, f"discontinuity in the loop: worst residual {np.max(np.abs(res)):.4f} at sample {int(np.argmax(np.abs(res)))} (a pass is 24000 samples)"
    zero_run = max((len(r) for r in np.split(np.arange(len(seg)), np.nonzero(np.abs(seg) > 1e-4)[0]) if len(r)), default=0)
    assert zero_run < 10, f"a run of {zero_run} zero samples inside the loop"


# ----------------------------------------------------------------------------------------------------------------- ducking
@pytest.mark.sev(1)
def test_ducking_depth_in_db_while_a_top_track_plays_and_the_return_to_full_level(quiet):
    rig = quiet
    api = rig.api
    t_wall = time.time()
    assert api.res("0/0") == "ok"                        # background: 1 kHz at 0.5
    time.sleep(2.0)
    assert api.res("1/0/top") == "ok"                    # the 3 s voice-over: 2 kHz at 0.5
    time.sleep(8.0)
    L, _ = rig.samples()
    bg, top = amp(L, 1000), amp(L, 2000)
    base = float(np.mean(bg[2:30]))
    assert abs(base - 0.5) < 0.01
    t_start = int(np.argmax(top > 0.25))
    t_end = len(top) - 1 - int(np.argmax(top[::-1] > 0.25))
    n_top = t_end - t_start + 1
    print(f"ducking capture: top track {n_top} windows ({n_top * 0.05:.2f} s of file), file {len(L) / FS:.2f} s for {time.time() - t_wall:.2f} s of wall time")
    # The player ends the voice-over by its WALL clock (3 s), but the disk driver renders only ~97 % of real time and less under CPU load (92 % measured in a
    # full run), so the file holds 2.75 to 2.9 s of it. The depth below only needs the steady part (the duck is at depth within ~100 ms), so what matters is that
    # enough windows are there for the average (from t_start + 8 to t_end - 4) and for the fit of the release: 40 windows (2 s) leaves 28 for the average.
    assert n_top >= 40, f"the top track lasted {n_top * 0.05:.2f} s of rendered audio, expected about 3 s (at least 2 s are needed)"
    # settings: threshold -30 dB, ratio 6, the top track is a 0.5 sine (RMS -9.03 dB): reduction = (-9.03 + 30) * (1 - 1/6) = 17.5 dB
    want = (20 * np.log10(0.5 / np.sqrt(2)) + 30) * (1 - 1 / 6)
    during = bg[t_start + 8:t_end - 4]
    depth = 20 * np.log10(float(np.mean(during)) / base)
    print(f"ducking: depth {-depth:.2f} dB (expected {want:.2f}); top track {float(np.mean(top[t_start + 2:t_end - 2])):.3f}")
    assert abs(depth + want) < 1.0, f"background ducked by {-depth:.2f} dB, expected {want:.2f} dB"
    assert float(np.mean(top[t_start + 2:t_end - 2])) == pytest.approx(0.5, abs=0.02), "the top track itself must not be ducked"
    # release: a 500 ms time constant, gr(t) = want * exp(-(t - t0) / 0.5). The release starts when the player's WALL clock says the top track is over, and the
    # disk driver renders only ~97 % of real time (less under CPU load), so t0 is up to a few hundred ms away from where the top track's audio ends in the file:
    # fit the time constant instead of checking fixed times.
    seg = bg[t_end - 2:t_end + 1 + int(2.0 / 0.05)]
    gr = -20 * np.log10(np.maximum(seg, 1e-6) / base)
    t = (np.arange(len(seg)) - 2) * 0.05
    use = (gr > 1.0) & (gr < want * 0.95)               # the part of the curve that is neither the floor nor still the full depth
    assert use.sum() >= 8, "not enough of the release curve in the capture"
    slope, _ = np.polyfit(t[use], np.log(gr[use]), 1)
    tau = -1.0 / slope
    print(f"ducking release: fitted time constant {tau * 1000:.0f} ms (configured 500 ms; the file is rendered at about 97 % of real time)")
    assert 0.38 < tau < 0.65, f"the release time constant is {tau * 1000:.0f} ms, expected about 500 ms"
    back = bg[t_end + 1 + int(3.5 / 0.05):]
    assert len(back) > 5 and abs(20 * np.log10(float(np.mean(back)) / base)) < 0.3, "the background does not return to full level after the release time"


# ----------------------------------------------------------------------------------------------------------------- stop all
@pytest.mark.sev(1)
def test_silence_after_stop_all(quiet):
    rig = quiet
    api = rig.api
    api.res("0/0")
    time.sleep(2.0)
    api.res("1/0/top")                                   # something on top as well: stop all must silence both
    time.sleep(1.0)
    assert api.res("stopall") == "ok"
    time.sleep(2.0)
    L, R = rig.samples()
    on = np.nonzero((np.abs(L) > 0) | (np.abs(R) > 0))[0]
    assert len(on), "nothing was rendered at all"
    tail = len(L) - 1 - int(on[-1])
    assert tail >= int(1.2 * FS), f"audio is still rendered {(len(L) - tail) / FS:.2f} s into the capture; only {tail / FS:.2f} s of silence at the end"
    assert np.count_nonzero(L[int(on[-1]) + 1:]) == 0 and np.count_nonzero(R[int(on[-1]) + 1:]) == 0
    # and the ducking did not leave anything behind: the next background starts at full level
    api.res("0/0")
    time.sleep(1.5)
    L2, _ = rig.samples()
    a = amp(L2[len(L):], 1000)
    assert float(np.mean(a[-10:])) == pytest.approx(0.5, abs=0.01), "after stop all the next track must start at full level (no leftover duck)"


# ----------------------------------------------------------------------------------------------------------------- 2.7.4: fade in at A
@pytest.mark.sev(1)
def test_fade_in_starts_near_silence_and_reaches_full_level_at_the_set_time(quiet):
    """A track with a 1.5 s fade-in (start edge = Fade in) starts at (nearly) zero and follows the equal-power curve sin(x*pi/2) up to full level at about 1.5 s."""
    rig = quiet
    api = rig.api
    assert api.post("/api/playlists/0/trim", {"track": 0, "start": "fade", "fade_in_ms": 1500}).status == 200
    try:
        assert api.res("0/0") == "ok"
        time.sleep(3.2)
        L, _ = rig.samples()
    finally:
        api.cmd("stopall")
        api.post("/api/playlists/0/trim", {"track": 0, "clear": True})
    a = amp(L, 1000)
    start = int(np.argmax(a > 0.001))
    assert a[start] < 0.05, f"the first 50 ms window must be almost silent, got {a[start]:.3f}"
    n = 30                                                # 1.5 s = 30 windows of 50 ms
    best = (9.0, 1.0, 0)
    for sc in np.linspace(1.0, 1.08, 17):                 # the disk driver renders at about 97 % of real time (see test_crossfade...)
        x = np.clip(sc * (np.arange(n) + 0.5) / n, 0, 1)
        want = 0.5 * np.sin(x * np.pi / 2)
        for d in (-1, 0, 1, 2):
            i0 = start + d
            if i0 < 0 or i0 + n > len(a):
                continue
            e = np.max(np.abs(a[i0:i0 + n] - want))
            if e < best[0]:
                best = (e, sc, d)
    print(f"fade in: worst deviation from sin(x*pi/2) {best[0]:.3f} (scale {best[1]:.3f}, offset {best[2]}); first window {a[start]:.3f}")
    assert best[0] < 0.04, f"the fade-in does not follow the equal-power curve (worst error {best[0]:.3f})"
    assert abs(a[start + n + 3] - 0.5) < 0.02 and abs(a[start + n + 12] - 0.5) < 0.02, "after the fade the track plays at full level"
    assert a[start + 5] < 0.5 * 0.35, "still low a quarter of the way in (a cut would be at 0.5 already)"


@pytest.mark.sev(1)
def test_default_cut_start_is_sample_identical_to_the_source_file(quiet):
    """Without a fade-in (the default, and also with the length remembered but the edge on Cut) the live output is the file, bit for bit: nothing changed for 2.7.3 shows."""
    rig = quiet
    api = rig.api
    n = np.arange(24001)
    src = np.round(0.5 * 32768 * np.sin(2 * np.pi * 1000 * n / FS)) / 32768
    for trim in (None, {"fade_in_ms": 1500}):
        api.cmd("stopall")
        time.sleep(0.8)
        if trim:
            assert api.post("/api/playlists/0/trim", {"track": 0, **trim}).status == 200
        rig.start_capture()
        assert api.res("0/0") == "ok"
        time.sleep(1.6)
        L, _ = rig.samples()
        api.cmd("stopall")
        k = int(np.argmax(L != 0))
        assert np.array_equal(L[k:k + 24000], src[1:24001]), f"the live start differs from the source file (trim={trim})"
    api.post("/api/playlists/0/trim", {"track": 0, "clear": True})
