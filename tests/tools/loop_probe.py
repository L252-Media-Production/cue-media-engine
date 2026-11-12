#!/usr/bin/env python3
"""Event-loop stall and OSC-gap probe (a tool, not part of run.py: it uses real time on purpose, it MEASURES the real loop).

    python tests/tools/loop_probe.py --rev v2.7.5 --mode stall [--secs 60] [--load 8]
    python tests/tools/loop_probe.py --rev HEAD   --mode gap   [--runs 50]  [--load 8]

--rev  a git rev (extracted with git archive into a temp folder) or HEAD for the working tree.
stall  starts a disposable instance whose launcher adds a 10 ms task to the player's event loop (the same loop as the HTTP handlers, tick() and the
       health refresh) that records how late each wake-up was, plays a 120 s file, polls /api/state at 4 Hz (like the Companion module) and the
       page's 1 Hz poll, and reports the longest lag, the count above 50 ms / 100 ms, and the lags of any stall above 100 ms.
gap    the body of test_prefix_change_while_a_track_plays_switches_cleanly repeated N times in one instance (prefix alternates): the longest gap
       between two `remaining` sends under the new prefix.
--load N  runs N busy processes for the whole measurement.
"""
import argparse, json, multiprocessing, os, subprocess, sys, tempfile, threading, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE.parent))
from harness import client                      # noqa: E402
from harness.instance import Instance           # noqa: E402

LAUNCHER = '''
import asyncio, json, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import cpl.legacy as app
_main = app.main
async def _mon():
    lags, last_dump = [], time.monotonic()
    while True:
        t = time.monotonic()
        await asyncio.sleep(0.01)
        lag = time.monotonic() - t - 0.01
        lags.append((round(time.time(), 3), round(lag * 1000, 1)))
        if time.monotonic() - last_dump > 1.0:
            last_dump = time.monotonic()
            (HERE / "lag.json").write_text(json.dumps(lags))
async def _main2():
    asyncio.get_running_loop().create_task(_mon())
    await _main()
app.main = _main2
if __name__ == "__main__":
    app.run()
'''


class ProbeInstance(Instance):
    def _spawn(self, env):
        (self.workdir / "probe_player.py").write_text(LAUNCHER)
        return subprocess.Popen([sys.executable, "-u", "-I", str(self.workdir / "probe_player.py")], cwd=str(self.workdir), env=env,
                                stdout=self.log, stderr=subprocess.STDOUT, start_new_session=True)


def burn():
    while True:
        pass


def tree(rev):
    if rev == "HEAD":
        return ROOT
    d = Path(tempfile.mkdtemp(prefix="probe-tree-"))
    tar = subprocess.run(["git", "-C", str(ROOT), "archive", rev, "player.py", "cpl", "static", "requirements.txt"], capture_output=True, check=True).stdout
    subprocess.run(["tar", "-x", "-C", str(d)], input=tar, check=True)
    return d


def setup(api, files):
    api.cmd("stopall")
    api.post("/api/playlists", {"name": "A"})
    assert api.post("/api/playlists/0/add", {"files": files}).status == 200
    api.cmd("0/0/focus")


def stall(api, inst, secs):
    setup(api, ["long_120s.wav"])
    api.cmd("0/0")
    api.wait_playing()
    t0 = time.time()
    n = 0
    while time.time() - t0 < secs:
        api.state()                                            # 4 Hz
        if n % 4 == 0:
            api.get("/api/playlists")                          # page-like extras once a second
            api.get("/api/settings/health")
        n += 1
        time.sleep(0.25)
    time.sleep(1.5)
    lags = json.loads((inst.workdir / "lag.json").read_text())
    lags = [l for l in lags if l[0] >= t0]
    ms = sorted(l[1] for l in lags)
    big = [l for l in lags if l[1] > 100]
    return {"samples": len(lags), "max_ms": ms[-1], "p99_ms": ms[int(len(ms) * .99)], "over_50": sum(1 for x in ms if x > 50), "over_100": len(big),
            "stalls_over_100": big[:10], "state_polls": n}


def gap(api, inst, runs):
    out, errs = [], 0
    setup(api, ["tone_a.wav", "tone_b.wav", "tone_c.wav"])
    for i in range(runs):
        pre = "zq_" if i % 2 == 0 else "zr_"
        api.cmd("stopall")
        api.cmd("0/0")
        api.wait_playing()
        time.sleep(1.5)
        t_change = time.time()
        r = api.post("/api/settings/prefix", {"prefix": pre, "confirm": True})
        if r.status != 200:
            errs += 1
            continue
        time.sleep(3.0)
        new = [m for m in inst.sink.since(t_change - 0.001) if m[1].startswith("/custom-variable/" + pre)]
        ts = sorted(m[0] for m in new if m[1] == f"/custom-variable/{pre}remaining/value")
        gaps = [b - a for a, b in zip(ts, ts[1:])]
        out.append(max(gaps) if gaps and len(ts) >= 3 else 99.0)
        if gaps and max(gaps) >= 1.3:
            print("SLOW", [(round(m[0] - t_change, 3), m[2]) for m in new if m[1] == f"/custom-variable/{pre}remaining/value"], file=sys.stderr)
    return {"runs": len(out), "errors": errs, "max_gap": max(out), "over_1.3": sum(1 for g in out if g >= 1.3), "over_1.2": sum(1 for g in out if g >= 1.2),
            "sorted_top5": [round(g, 3) for g in sorted(out)[-5:]], "median": round(sorted(out)[len(out) // 2], 3)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rev", default="HEAD")
    ap.add_argument("--mode", choices=("stall", "gap"), required=True)
    ap.add_argument("--secs", type=int, default=60)
    ap.add_argument("--runs", type=int, default=50)
    ap.add_argument("--load", type=int, default=0)
    a = ap.parse_args()
    procs = [multiprocessing.Process(target=burn, daemon=True) for _ in range(a.load)]
    inst = ProbeInstance(project_dir=tree(a.rev), wav_only=True).start()
    try:
        api = client.Api(inst.base_url, inst.osc_port, inst.sink)
        for p in procs:
            p.start()
        res = stall(api, inst, a.secs) if a.mode == "stall" else gap(api, inst, a.runs)
        print(json.dumps({"rev": a.rev, "mode": a.mode, "load": a.load, **res}))
    finally:
        for p in procs:
            p.kill()
        inst.stop()


if __name__ == "__main__":
    main()
