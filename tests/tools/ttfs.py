#!/usr/bin/env python3
"""Time to first sound of a never-cached track (a measurement tool, not a test).

    python tests/tools/ttfs.py --rev v2.7.0 --mode working --target long --runs 5 --libcache <folder>
    python tests/tools/ttfs.py --rev split-P4 --mode idle --target short --runs 5 --libcache <folder>

Each run is a COLD start of a fresh copy of the build (`git archive REV`): a new folder, a new process, an empty sound cache, the dummy
audio driver. The library has playlist A = 20 MP3 tracks of 4 minutes (the warm-up queue) and playlist B = a 15-minute MP3 (B/0, "long")
and a 3-second WAV (B/1, "short"). The focus is A/0, so the warm-up works through A first and never reaches B before the measured Go.
  --mode working   the warm-up runs as in production; Go is sent --delay seconds (default 1.0) after the player answers
  --mode idle      the warm-up is switched off by a launcher shim (it replaces `_warm_loop` by a function that returns), the same shim for
                   both builds; Go is sent at the same moment
Measured: from just before `GET /api/1/<t>` is sent until /api/state first shows state "playing" with live_id "1/<t>" (polled every ~5 ms
over one connection). The dummy audio driver has no output latency, so this is the player's own load + start time. Also printed: how many
tracks were decoded at the moment of Go and how many `--decode` helper processes were running.
Needs ffmpeg (with libmp3lame) once, to build the library into --libcache (reused).
"""
import argparse, http.client, json, os, shutil, signal, statistics, subprocess, sys, tempfile, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE.parent))
from harness.instance import free_port   # noqa: E402

SHIM = '''import sys, os, asyncio, importlib, importlib.util
here = os.path.dirname(os.path.abspath(__file__))
sys.argv = ["player.py"]
if os.path.isdir(os.path.join(here, "cpl")):
    sys.path.insert(0, here)
    m = importlib.import_module("cpl.legacy")
    run = m.run
else:
    spec = importlib.util.spec_from_file_location("player_shim", os.path.join(here, "player.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    run = lambda: asyncio.run(m.main())
if os.environ.get("TTFS_WARM") == "idle":
    async def _idle():
        return None
    m._warm_loop = _idle
run()
'''
A_IDS = ["A/track%02d.mp3" % i for i in range(1, 21)]


def build_library(cache):
    cache = Path(cache)
    ok = cache / ".done"
    if ok.exists():
        return cache
    ff = shutil.which("ffmpeg")
    if not ff:
        sys.exit("ttfs: ffmpeg is needed once to build the library")
    (cache / "A").mkdir(parents=True, exist_ok=True)
    (cache / "B").mkdir(parents=True, exist_ok=True)

    def mp3(path, secs, hz):
        subprocess.run([ff, "-v", "error", "-y", "-f", "lavfi", "-i", f"anoisesrc=d={secs}:c=pink:a=0.2:r=44100", "-f", "lavfi", "-i", f"sine=f={hz}:d={secs}:r=44100",
                        "-filter_complex", "amix=inputs=2:duration=first,aformat=channel_layouts=stereo", "-c:a", "libmp3lame", "-b:a", "192k", str(path)], check=True)
    mp3(cache / "A" / "track01.mp3", 240, 300)
    for i in range(2, 21):
        shutil.copy2(cache / "A" / "track01.mp3", cache / "A" / ("track%02d.mp3" % i))
    mp3(cache / "B" / "long15.mp3", 900, 440)
    subprocess.run([ff, "-v", "error", "-y", "-f", "lavfi", "-i", "sine=f=660:d=3:r=44100", "-ac", "2", str(cache / "B" / "short3.wav")], check=True)
    ok.write_text("ok")
    return cache


def extract(rev, dest):
    names = ["player.py", "static"] + (["cpl"] if subprocess.run(["git", "-C", str(ROOT), "cat-file", "-e", f"{rev}:cpl"], capture_output=True).returncode == 0 else [])
    tar = subprocess.run(["git", "-C", str(ROOT), "archive", rev] + names, capture_output=True, check=True).stdout
    subprocess.run(["tar", "-x", "-C", str(dest)], input=tar, check=True)


def link_tree(src, dst):
    for p in src.rglob("*"):
        if p.is_file() and p.name != ".done":
            t = dst / p.relative_to(src)
            t.parent.mkdir(parents=True, exist_ok=True)
            try:
                os.link(p, t)
            except OSError:
                shutil.copy2(p, t)


def one_run(rev, mode, target, libcache, delay, python):
    work = Path(tempfile.mkdtemp(prefix="ttfs-")).resolve()
    proc = None
    try:
        extract(rev, work)
        (work / "shim.py").write_text(SHIM)
        link_tree(libcache, work / "media" / "library")
        port, osc, sink = free_port(), free_port(), free_port()
        (work / "config.json").write_text(json.dumps({"http_port": port, "osc_in_port": osc, "companion_host": "127.0.0.1", "companion_osc_port": sink,
                                                      "resume_on_start": False, "storage_limit": None, "storage_reserve": "100MB", "cache_mb": 768}))
        ids = A_IDS + ["B/long15.mp3", "B/short3.wav"]
        (work / "playlists.json").write_text(json.dumps({"version": 2, "known": ids, "playlists": [{"name": "A", "tracks": A_IDS}, {"name": "B", "tracks": ["B/long15.mp3", "B/short3.wav"]}]}))
        env = {**os.environ, "SDL_AUDIODRIVER": "dummy", "PYGAME_HIDE_SUPPORT_PROMPT": "1", "PYTHONUNBUFFERED": "1", "TTFS_WARM": mode}
        log = open(work / "player.log", "wb")
        proc = subprocess.Popen([python, "-u", "-I", str(work / "shim.py")], cwd=str(work), env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=60)

        def get(path):
            conn.request("GET", path)
            r = conn.getresponse()
            return json.loads(r.read())
        t0 = time.time()
        while True:
            if proc.poll() is not None:
                raise RuntimeError("the player exited:\n" + (work / "player.log").read_text()[-1500:])
            try:
                get("/api/state")
                break
            except (OSError, ValueError, http.client.HTTPException):
                conn.close()
                conn = http.client.HTTPConnection("127.0.0.1", port, timeout=60)
                time.sleep(0.05)
                if time.time() - t0 > 60:
                    raise RuntimeError("no start")
        up = time.time()
        time.sleep(max(0.0, delay))
        n0 = get("/api/state")["mem"]["cache_tracks"]
        helpers = subprocess.run(["pgrep", "-f", f"{work}/player.py --decode"], capture_output=True, text=True).stdout.split()
        want = "1/0" if target == "long" else "1/1"
        a = time.perf_counter()
        get("/api/" + want)
        while True:
            s = get("/api/state")
            if s["state"] == "playing" and s.get("live_id") == want:
                break
            if time.perf_counter() - a > 90:
                raise RuntimeError("never started")
        dt = time.perf_counter() - a
        return {"ms": round(dt * 1000), "decoded_at_go": n0, "helpers_at_go": len(helpers), "decoded_after": get("/api/state")["mem"]["cache_tracks"],
                "start_after_up_s": round(time.time() - up, 2)}
    finally:
        if proc and proc.poll() is None:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except OSError:
                pass
            proc.wait(10)
        shutil.rmtree(work, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rev", required=True, help="git revision of the build (v2.7.0, split-P4, ...)")
    ap.add_argument("--mode", choices=["working", "idle"], required=True)
    ap.add_argument("--target", choices=["long", "short"], required=True)
    ap.add_argument("--runs", type=int, default=5)
    ap.add_argument("--delay", type=float, default=1.0)
    ap.add_argument("--libcache", required=True)
    ap.add_argument("--python", default=sys.executable)
    a = ap.parse_args()
    lib = build_library(a.libcache)
    res = []
    for i in range(a.runs):
        r = one_run(a.rev, a.mode, a.target, lib, a.delay, a.python)
        res.append(r)
        print(json.dumps({"rev": a.rev, "mode": a.mode, "target": a.target, "run": i + 1, **r}), flush=True)
    ms = [r["ms"] for r in res]
    print(f"SUMMARY rev={a.rev} mode={a.mode} target={a.target} runs={len(ms)} median={statistics.median(ms):.0f} ms min={min(ms)} max={max(ms)}")


if __name__ == "__main__":
    main()
