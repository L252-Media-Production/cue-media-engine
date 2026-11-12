#!/usr/bin/env python3
"""Diagnostic: does the start of a track survive on the live output (and on the Solo monitor)?   Changes nothing in the application.

    python tests/tools/onset_capture.py --app PATH_TO_A_SOURCE_TREE --label v2.7.0 [--repeat 3] [--jobs 4] [--out result.json]
    python tests/tools/onset_capture.py --prove-driver                      # only the disk-driver proof (pacing, bit-exactness)

PATH_TO_A_SOURCE_TREE is a folder holding player.py (+ cpl/ and static/ for builds after split step P1), e.g. `git archive v2.7.0 | tar -x -C dir`
or the working tree. Each case runs in a fresh, isolated instance (own folder, ports, library, SDL_AUDIODRIVER=disk) started from a COPY.

What it does
  * Source files (48 kHz, 16-bit, stereo): a full-level 1 kHz cosine burst of 10 ms (480 samples) that starts at sample 0 and is followed by silence,
    and a second file with 100 ms of silence before the same burst.  Short WAVs (cached cases), and long FLAC / WAV files (60 s / 120 s) for the
    "not cached" cases, where the decode takes long enough to go through the loading path (_start_when_ready) every time.
  * Modes: (a) a normal Play with nothing else playing, (b) Play on Top over a playing but SILENT background track, (c) Play on Top over a playing
    background track (a quiet 220 Hz sine); each with the target cached (played once before, or warmed) and not cached.
  * SDL's disk audio driver writes everything the mixer renders to a raw file (SDL_DISKAUDIOFILE).  The Solo monitor (the preview worker process,
    CP_ONSET_MON_FILE below) is captured too, to its own file, so the live output and what the engineer hears can be compared in the same run.
  * For each burst it reports: sample index of the first sample above 50 % of the burst's own peak, the peak (re. the source peak), the number of
    samples missing (source span of the >50 % samples minus the captured span, 480 for an intact burst), and the approximate delay from the HTTP
    command to the burst (kept in the JSON as delay_ms_approx only: it can come out negative, the clock of the disk driver is not tied to the wall clock to better than ~100 ms).  Resolution of "missing": a few samples (the first sample above 50 % depends on the phase of the tone if the burst is cut).

The disk driver is real-time paced (SDL waits one buffer length per write); --prove-driver shows the pacing and that a known signal comes out bit for bit.
"""
import argparse, concurrent.futures, json, os, shutil, signal, socket, subprocess, sys, tempfile, time, urllib.request, wave
from pathlib import Path

import numpy as np

FS, BURST, AMP = 48000, 480, 24000
MARKS_MS = list(range(0, 201, 20)) + [250, 300, 350, 400, 450, 500, 600, 700, 800, 1000]            # a click train: which of the first clicks survive tells where playback really began
BG_AMP = 4000                                                      # the quiet background sine of mode c (burst + background stays below full scale)
EXPECT = {"s0": [0], "s100": [100], "m0": MARKS_MS, "f0": [0], "f100": [100], "fm": MARKS_MS, "w0": [0], "wm": MARKS_MS}
HERE = Path(__file__).resolve().parent
TESTS = HERE.parent

SHIM = '''import asyncio, os, runpy, sys
_orig = asyncio.create_subprocess_exec
async def _exec(*a, **kw):                    # only the preview/monitor worker gets its own capture file; nothing else is touched
    if "--preview" in a and os.environ.get("CP_ONSET_MON_FILE"):
        env = dict(kw.get("env") or os.environ)
        env["SDL_DISKAUDIOFILE"] = os.environ["CP_ONSET_MON_FILE"]
        kw["env"] = env
    return await _orig(*a, **kw)
asyncio.create_subprocess_exec = _exec
here = os.path.dirname(os.path.abspath(__file__))
sys.argv = ["player.py"]
runpy.run_path(os.path.join(here, "player.py"), run_name="__main__")
'''


# ------------------------------------------------------------------ source material
def cosine_burst():
    n = np.arange(BURST)
    return np.round(AMP * np.cos(2 * np.pi * 1000 * n / FS)).astype(np.int16)         # sample 0 = full level


def write_wav(path, mono):
    st = np.repeat(mono[:, None], 2, axis=1).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(FS)
        w.writeframes(st.tobytes())


def make_signal(marks_ms, seconds):
    x = np.zeros(int(seconds * FS), dtype=np.int16)
    for ms in marks_ms:
        st = int(ms * FS / 1000)
        x[st:st + BURST] = cosine_burst()
    return x


def make_library(lib, with_flac=True):
    lib.mkdir(parents=True, exist_ok=True)
    files = {}
    for name, marks, secs in (("s0", [0], 2), ("s100", [100], 2), ("m0", MARKS_MS, 2), ("w0", [0], 120), ("wm", MARKS_MS, 120)):
        write_wav(lib / f"{name}.wav", make_signal(marks, secs))
        files[name] = f"{name}.wav"
    write_wav(lib / "bg.wav", np.round(BG_AMP * np.sin(2 * np.pi * 220 * np.arange(20 * FS) / FS)).astype(np.int16))
    write_wav(lib / "silent.wav", np.zeros(20 * FS, dtype=np.int16))
    if with_flac and shutil.which("ffmpeg"):
        for name, marks in (("f0", [0]), ("f100", [100]), ("fm", MARKS_MS)):
            tmp = lib / f"_{name}.wav"
            write_wav(tmp, make_signal(marks, 60))
            subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(tmp), "-c:a", "flac", str(lib / f"{name}.flac")], check=True)
            tmp.unlink()
            files[name] = f"{name}.flac"
    return files


# ------------------------------------------------------------------ analysis
def load_raw(path):
    a = np.fromfile(path, dtype="<i2")
    a = a[: len(a) // 2 * 2].reshape(-1, 2)
    return a[:, 0].astype(np.int32), a[:, 1].astype(np.int32)


def detect_groups(y, start_idx, ref_peak, max_groups=40):
    """Bursts at or after sample `start_idx` -> [{first_above50, span, peak}]. A burst = samples above 35 % of ref_peak that are < 200 apart
    (the 1 kHz tone has a peak every 48 samples; clicks are >= 40 ms apart). The first / last sample above 50 % of the burst's OWN peak
    give its span (480 for an intact burst: it starts at full level, it ends at 99 % of full level)."""
    seg = np.abs(y[start_idx:])
    loud = np.nonzero(seg > 0.35 * ref_peak)[0]
    if len(loud) == 0:
        return []
    cuts = np.nonzero(np.diff(loud) > 200)[0]
    starts = np.concatenate(([0], cuts + 1))
    ends = np.concatenate((cuts, [len(loud) - 1]))
    out = []
    for a_, b_ in zip(starts, ends):
        lo, hi = int(loud[a_]), int(loud[b_])
        grp = seg[lo:hi + 1]
        peak = int(grp.max())
        above = np.nonzero(grp > 0.5 * peak)[0]
        f, l = lo + int(above[0]), lo + int(above[-1])
        out.append({"first_above50": start_idx + f, "first_any": start_idx + lo, "span": l - f + 1, "peak": peak})
        if len(out) >= max_groups:
            break
    return out


def align(groups, expect_ms):
    """Which of the expected clicks are in `groups`? The capture is assumed to run to the end of the click train, so the detected clicks
    are the LAST len(groups) of the expected ones; their spacing (exact, in mixer samples) must agree. -> (n_lost_at_head, ok)"""
    n, m = len(expect_ms), len(groups)
    if m == 0:
        return n, False
    if m > n:
        return 0, False
    j0 = n - m
    for k in range(1, m):
        want = (expect_ms[j0 + k] - expect_ms[j0 + k - 1]) * FS / 1000
        got = groups[k]["first_above50"] - groups[k - 1]["first_above50"]
        if abs(got - want) > 12:
            return j0, False
    return j0, True


def source_span():
    b = np.abs(cosine_burst().astype(np.int32))
    above = np.nonzero(b > 0.5 * b.max())[0]
    return int(above[-1] - above[0] + 1), int(above[0])             # (480, 0)


# ------------------------------------------------------------------ instance
def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Inst:
    def __init__(self, app, lib_src, monitor=True, cfg_extra=None):
        self.dir = Path(tempfile.mkdtemp(prefix="cponset-"))
        for f in ("player.py",):
            shutil.copy2(Path(app) / f, self.dir / f)
        for d in ("cpl", "static"):
            if (Path(app) / d).is_dir():
                shutil.copytree(Path(app) / d, self.dir / d, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        (self.dir / "_runner.py").write_text(SHIM)
        shutil.copytree(lib_src, self.dir / "media" / "library")
        self.port, self.osc = free_port(), free_port()
        cfg = {"http_port": self.port, "osc_in_port": self.osc, "resume_on_start": False, "companion_osc_port": free_port()}
        cfg.update(cfg_extra or {})
        self.monitor = monitor
        if monitor:
            cfg["preview_device"] = "MockOut"                    # the CP_TEST_DEVICES hook lets the worker open "any" device (the disk driver)
            (self.dir / "mock_devices.json").write_text(json.dumps(["MockOut"]))
        (self.dir / "config.json").write_text(json.dumps(cfg))
        self.main_raw, self.mon_raw = self.dir / "main.raw", self.dir / "monitor.raw"
        self.proc = None

    def start(self):
        env = dict(os.environ, SDL_AUDIODRIVER="disk", SDL_DISKAUDIOFILE=str(self.main_raw), PYGAME_HIDE_SUPPORT_PROMPT="1",
                   CP_ONSET_MON_FILE=str(self.mon_raw))
        if self.monitor:
            env["CP_TEST_DEVICES"] = str(self.dir)
        self.log = open(self.dir / "out.log", "wb")
        self.proc = subprocess.Popen([sys.executable, "-u", "-I", str(self.dir / "_runner.py")], cwd=self.dir, env=env, stdout=self.log, stderr=subprocess.STDOUT)
        t0 = time.time()
        while time.time() - t0 < 30:
            try:
                self.get("/api/state")
                break
            except Exception:
                if self.proc.poll() is not None:               # it already died: do not wait for the timeout
                    t0 -= 31
                time.sleep(0.1)
        else:
            self.log.flush()
            raise RuntimeError(f"did not start (http port {self.port}, osc port {self.osc}, process exit code {self.proc.poll()}):\n" + (self.dir / "out.log").read_text(errors="replace"))     # the FULL log
        t = time.time()
        while not (self.main_raw.exists() and self.main_raw.stat().st_size > 0):          # the device is open when the file starts to grow
            if time.time() - t > 10:
                raise RuntimeError("no audio file")
            time.sleep(0.002)
        self.t_open = time.time()            # (+- one poll): sample 0 of main.raw
        return self

    def get(self, path, timeout=10):
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}{path}", timeout=timeout) as r:
            return json.loads(r.read())

    def post(self, path, obj):
        rq = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", json.dumps(obj).encode(), {"Content-Type": "application/json"})
        with urllib.request.urlopen(rq, timeout=10) as r:
            return json.loads(r.read())

    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.proc.send_signal(signal.SIGTERM)
            try:
                self.proc.wait(5)
            except Exception:
                self.proc.kill()
        # the preview worker is a child: make sure it is gone
        subprocess.run(["pkill", "-f", str(self.dir)], capture_output=True)
        self.log.close()

    def cleanup(self):
        shutil.rmtree(self.dir, ignore_errors=True)


def add_playlist(inst, name, files):
    inst.post("/api/playlists", {"name": name})
    pl = inst.get("/api/playlists")
    n = len(pl["playlists"] if isinstance(pl, dict) else pl) - 1
    inst.post(f"/api/playlists/{n}/add", {"files": files})
    return n


def wait_cached(inst, n, timeout=20):
    t = time.time()
    while time.time() - t < timeout:
        try:
            if inst.get("/api/state")["mem"]["cache_tracks"] >= n:
                return True
        except Exception:
            pass
        time.sleep(0.1)
    return False


def run_case(app, lib, files, mode, kind, cached, monitor=True, cfg_extra=None):
    """mode a|b|c, kind s0|s100|m0|f0|f100|fm|w0|wm (s short wav, m click train, f 60 s FLAC, w 120 s WAV), cached True|False. -> dict"""
    inst = Inst(app, lib, monitor, cfg_extra).start()
    out = {"mode": mode, "file": kind, "cached": cached}
    try:
        add_playlist(inst, "bg", ["bg.wav", "silent.wav"])
        wait_cached(inst, 2)
        time.sleep(0.4)
        if monitor:
            inst.get("/api/solo/1")                               # Solo live: the preview worker starts and monitors the live decks
            time.sleep(1.5)
        tgt = files[kind]
        p = None
        if cached:                                                 # added early, warmed into the cache, then the background starts
            p = add_playlist(inst, "t", [tgt])
            out["cache_wait_ok"] = wait_cached(inst, 3)
            time.sleep(0.4)
        # background
        if mode == "b":
            inst.get("/api/0/1")                                   # silent.wav
            time.sleep(1.2)
        elif mode == "c":
            inst.get("/api/0/0")                                   # bg.wav, 220 Hz sine
            time.sleep(1.2)
        if not cached:                                             # added only now, and played at once: the file is not in the cache when the command arrives
            p = add_playlist(inst, "t", [tgt])
        # the command under test
        cmd = f"/api/{p}/0" if mode == "a" else f"/api/{p}/0/top"
        try:
            out["cache_tracks_before_cmd"] = inst.get("/api/state")["mem"]["cache_tracks"]       # 2 = the target is NOT in the cache, 3 = it is
        except Exception:
            out["cache_tracks_before_cmd"] = None
        t_call = time.time()
        res = inst.get(cmd)
        out["result"] = res.get("result")
        out["t_call_after_open_s"] = round(t_call - inst.t_open, 3)
        time.sleep(3.0)
        st = inst.get("/api/state")
        out["state_after"] = st.get("state")
        out["live_name"] = st.get("live_name")
    finally:
        inst.stop()
    src_span, _ = source_span()
    expect = EXPECT[kind]
    start_idx = max(0, int((t_call - inst.t_open) * FS * 0.969) - FS)       # one second before the command (the disk driver renders 96.9 % of real time)
    for label, raw in (("live", inst.main_raw), ("monitor", inst.mon_raw)):
        if not raw.exists() or raw.stat().st_size == 0:
            out[label] = None
            continue
        L, R = load_raw(raw)
        gs = detect_groups(L, start_idx if label == "live" else 0, AMP)
        if label == "live" and len(expect) == 1 and gs:
            gs = gs[:1]
        lost, ok = align(gs, expect)
        m = {"n_expected": len(expect), "n_found": len(gs), "lost_at_head": lost, "aligned": ok,
             "first_missing": (src_span - gs[0]["span"]) if gs else None,
             "peak_re_source": round(gs[0]["peak"] / AMP, 4) if gs else None,
             "first_above50": gs[0]["first_above50"] if gs else None}
        if gs and label == "live":
            m["delay_ms_approx"] = round((gs[0]["first_any"] / (FS * 0.969) - (t_call - inst.t_open)) * 1000, 1)
        if len(expect) > 1 and gs:
            m["spans"] = [g["span"] for g in gs]
            if len(gs) > 3:
                rest = sorted(g["peak"] for g in gs[1:])
                m["first_peak_vs_median_rest"] = round(gs[0]["peak"] / rest[len(rest) // 2], 3)
        out[label] = m
    inst.cleanup()
    return out


# ------------------------------------------------------------------ proof of the capture method
def prove_driver():
    """Pacing and bit-exactness of SDL's disk driver in this pygame, using a bare mixer (no application)."""
    code = r'''
import os, sys, time, wave, numpy as np
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
import pygame
FS, BURST, AMP = 48000, 480, 30000
pygame.mixer.pre_init(48000, -16, 2, 1024)
pygame.mixer.init(allowedchanges=0)
n = np.arange(BURST)
b = np.round(AMP * np.cos(2 * np.pi * 1000 * n / FS)).astype("<i2")
x = np.zeros(FS, dtype="<i2"); x[:BURST] = b
st = np.repeat(x[:, None], 2, axis=1)
snd = pygame.mixer.Sound(buffer=st.tobytes())
t0 = time.time(); sizes = []
time.sleep(1.0)
snd.play()
for i in range(6):
    time.sleep(0.5); sizes.append((round(time.time() - t0, 2), os.path.getsize(sys.argv[1])))
pygame.mixer.quit()
print(sizes)
'''
    raw = Path(tempfile.mkdtemp(prefix="cpdisk-")) / "d.raw"
    env = dict(os.environ, SDL_AUDIODRIVER="disk", SDL_DISKAUDIOFILE=str(raw))
    r = subprocess.run([sys.executable, "-I", "-c", code, str(raw)], env=env, capture_output=True, text=True)
    sizes = eval(r.stdout.strip().splitlines()[-1])
    rate = [(b[1] - a[1]) / (b[0] - a[0]) for a, b in zip(sizes, sizes[1:])]
    print(f"disk driver pacing: file grows {np.mean(rate):.0f} bytes/s over {sizes[-1][0]} s  (real time stereo 16-bit 48 kHz = 192000 B/s, i.e. {np.mean(rate) / 192000 * 100:.1f} % of real time)")
    L, R = load_raw(raw)
    src_span, _ = source_span()
    m = burst_metrics(L, 0, AMP, src_span)
    b = cosine_burst().astype(np.int32)
    got = L[m["first_any"]:m["first_any"] + BURST]
    print(f"known signal: burst found at sample {m['first_any']} ({m['first_any'] / FS:.3f} s after the device opened), span {m['span']} (source {src_span}), "
          f"peak {m['peak']} (source {AMP}), samples differing from the source: {int(np.count_nonzero(got != b))} of {BURST}; left == right: {bool(np.array_equal(L, R))}")
    shutil.rmtree(raw.parent, ignore_errors=True)


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--app", help="source tree with player.py (+ cpl/, static/)")
    ap.add_argument("--label", default="build")
    ap.add_argument("--repeat", type=int, default=3)
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--out")
    ap.add_argument("--no-monitor", action="store_true", help="do not start the preview worker / Solo monitor")
    ap.add_argument("--only", help="comma list of mode:file:cached (e.g. c:s0:1,b:f0:0) to run a subset")
    ap.add_argument("--cfg", action="append", default=[], help="extra config.json key=value for the instance (JSON value), e.g. --cfg top_track_pct=50")
    ap.add_argument("--prove-driver", action="store_true")
    a = ap.parse_args()
    if a.prove_driver:
        prove_driver()
        return 0
    if not a.app:
        ap.error("--app is required")
    lib_dir = Path(tempfile.mkdtemp(prefix="cponset-lib-"))
    files = make_library(lib_dir / "lib")
    cases = []
    for mode in "abc":
        for kind in ("s0", "s100", "m0", "f0", "f100", "fm", "w0", "wm"):
            if kind not in files:
                continue
            for cached in (True, False):
                if not cached and kind in ("s0", "s100", "m0"):
                    continue                                     # a 2 s WAV decodes within a millisecond: "not cached" cannot be forced
                cases.append((mode, kind, cached))
    if a.only:
        want = {tuple(x.split(":")) for x in a.only.split(",")}
        cases = [c for c in cases if (c[0], c[1], "1" if c[2] else "0") in want]
    cfg_extra = {k: json.loads(v) for k, v in (x.split("=", 1) for x in a.cfg)}
    jobs = [(c, r) for r in range(a.repeat) for c in cases]
    results = []

    def one(job):
        (mode, kind, cached), r = job
        try:
            o = run_case(a.app, lib_dir / "lib", files, mode, kind, cached, monitor=not a.no_monitor, cfg_extra=cfg_extra)
        except Exception as e:
            o = {"mode": mode, "file": kind, "cached": cached, "error": repr(e)}
        o["rep"] = r
        return o
    with concurrent.futures.ThreadPoolExecutor(a.jobs) as ex:
        for o in ex.map(one, jobs):
            results.append(o)
            print(".", end="", flush=True)
    print()
    shutil.rmtree(lib_dir, ignore_errors=True)
    doc = {"label": a.label, "app": str(a.app), "cfg_extra": cfg_extra, "cases": results}
    if a.out:
        Path(a.out).write_text(json.dumps(doc, indent=1))
    summarize(doc)
    return 0


def summarize(doc):
    rows = {}
    for o in doc["cases"]:
        rows.setdefault((o["mode"], o["file"], "cached" if o["cached"] else "uncached"), []).append(o)
    print(f"\n== {doc['label']} ==  cfg {doc.get('cfg_extra') or '{}'}   one cell per repetition")
    print("  found/exp = clicks of the train (or the single burst) found / expected; lost = clicks missing at the head; miss = samples missing from the first click found (0 = intact);")
    print("  cache = tracks in the player's cache just before the command (2 = target not cached, 3 = cached); 1st/rest = first click's peak / median peak of the others (marker files, live)")
    print(f"{'mode':4} {'file':5} {'cache':8} {'c':>9} | {'LIVE found/exp':>14} {'lost':>10} {'miss':>10} {'1st/rest':>17} | {'MONITOR found/exp':>17} {'lost':>12} {'miss':>14}")
    for key in sorted(rows):
        rs = rows[key]
        def col(lbl, f):
            return [r[lbl].get(f) if r.get(lbl) else None for r in rs if "error" not in r]
        errs = [r["error"] for r in rs if "error" in r]
        lf = col("live", "n_found"); le = (col("live", "n_expected") or [""])[0]
        mf = col("monitor", "n_found"); me = (col("monitor", "n_expected") or [""])[0]
        cb = [r.get("cache_tracks_before_cmd") for r in rs if "error" not in r]
        print(f"{key[0]:4} {key[1]:5} {key[2]:8} {str(cb):>9} | {str(lf) + '/' + str(le):>14} {str(col('live', 'lost_at_head')):>10} {str(col('live', 'first_missing')):>10} {str(col('live', 'first_peak_vs_median_rest')):>17} | "
              f"{str(mf) + '/' + str(me):>17} {str(col('monitor', 'lost_at_head')):>12} {str(col('monitor', 'first_missing')):>14}" + (f"  ERR {errs[0]}" if errs else ""))


if __name__ == "__main__":
    sys.exit(main())
