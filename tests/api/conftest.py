"""Fixtures for the API/command tests. Run through tests/run.py (it makes the report folder), or directly:
    pytest tests/api [--base-url URL --allow-remote --confirm-target HOST:PORT --osc-port N]"""
import sys, tempfile, time
from pathlib import Path

import pytest

TESTS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TESTS))
from harness import client, libgen, report, safety          # noqa: E402
from harness.instance import Instance, PROJECT              # noqa: E402

REPORT = [None]


def pytest_addoption(parser):
    g = parser.getgroup("companionplayer")
    g.addoption("--base-url", default=None, help="test an already running instance instead of starting one")
    g.addoption("--allow-remote", action="store_true", help="allow a target that is not a local harness instance (needs --confirm-target)")
    g.addoption("--confirm-target", default=None, help="HOST:PORT of the target, typed out, to confirm --allow-remote")
    g.addoption("--osc-port", type=int, default=None, help="OSC input port of an external target (OSC tests are skipped without it)")
    g.addoption("--report-dir", default=None)
    g.addoption("--keep-instance", action="store_true", help="keep the temp folder of the managed instance")
    g.addoption("--project", default=str(PROJECT), help="folder holding the player.py to copy")


def pytest_configure(config):
    config.addinivalue_line("markers", "sev(n): severity if this test fails: 1 no audio/crash/stuck/wrong track on air, 2 wrong behaviour, 3 UI/usability, 4 cosmetic")
    config.addinivalue_line("markers", "covers(*ids): control ids (tests/controls.csv) this test exercises")
    config.addinivalue_line("markers", "noreset: do not reset the shared instance before this test (it starts its own)")
    config.addinivalue_line("markers", "audio: renders the real output with SDL_AUDIODRIVER=disk and analyses the samples (skipped where the driver is unavailable)")
    out = config.getoption("--report-dir")
    if not out:
        import platform
        out = TESTS / "reports" / f"{sys.platform}-{platform.machine().lower()}-{time.strftime('%Y%m%d-%H%M%S')}"
    REPORT[0] = report.ReportPlugin(out, config.getoption("--project"))
    config.pluginmanager.register(REPORT[0], "cp-report")


@pytest.fixture(scope="session")
def target(request):
    o = request.config.getoption
    inst = None
    if o("--base-url"):
        base = o("--base-url").rstrip("/")
        try:
            info = safety.check_target(base, o("--allow-remote"), o("--confirm-target"))
        except safety.Refused as e:
            pytest.exit(f"REFUSED: {e}", returncode=3)
        api = client.Api(base, osc_port=o("--osc-port"))
    else:
        inst = Instance(keep=o("--keep-instance"), project_dir=o("--project"))
        inst.start()
        info = safety.check_target(inst.base_url)
        api = client.Api(inst.base_url, osc_port=inst.osc_port)
    info = dict(info)
    t = {"api": api, "instance": inst, "info": info, "managed": inst is not None, "sink": inst.sink if inst else None}
    REPORT[0].target = {k: info.get(k) for k in ("netloc", "harness_owned", "loopback", "looks_like_production", "config_file")}
    REPORT[0].target["managed"] = inst is not None
    # make sure the library holds the test files (a managed instance already has them; an external one gets them uploaded)
    with tempfile.TemporaryDirectory() as td:
        manifest = inst.manifest if inst else libgen.generate(td)
        have = {f["id"] for f in api.library()["files"]}
        actual = {}
        for fid, secs in manifest.items():
            if fid in have or inst:
                actual[fid] = secs
                continue
            p = Path(td) / fid
            if p.exists():
                r = _upload(api, p, str(Path(fid).parent) if "/" in fid else "")
                got = r.json["files"][0]["id"] if r.status == 200 and r.json.get("files") else fid
                actual[got] = secs                                # an upload cleans odd characters out of the name
        t["manifest"] = actual
    try:
        api.wait_for(lambda s: s["status"] == "ready", 60, interval=0.5, desc="the player to be ready")
        REPORT[0].remote_env["instance"] = {"ffmpeg": {k: v for k, v in api.get("/api/ffmpeg").json.items() if k in ("ok", "version", "ffprobe")},
                                            "devices": api.get("/api/devices").json.get("devices"), "state_health": api.state().get("health")}
    except Exception:
        pass
    yield t
    if inst:
        REPORT[0].remote_env["instance_log_tail"] = inst.log_text()[-1500:]
        try:
            out = REPORT[0].outdir
            out.mkdir(parents=True, exist_ok=True)
            (out / "instance.log").write_text(inst.log_text(), encoding="utf-8")
        except Exception:
            pass
        inst.stop()


def _upload(api, path, folder=""):
    return api.upload(path.name, path.read_bytes(), folder=folder or None)


@pytest.fixture(scope="session")
def api(target):
    return target["api"]


@pytest.fixture(scope="session")
def manifest(target):
    return target["manifest"]


DEFAULTS_TOP = {"track_pct": 100, "threshold_db": -30, "ratio": 6, "attack_ms": 10, "release_ms": 500, "hold": True, "fade_ms": 1500}


def reset_player(api):
    api.cmd("stopall")
    for _ in range(50):
        pls = api.playlists()
        if not pls:
            break
        api.delete("/api/playlists/0")
    api.post("/api/settings/top", DEFAULTS_TOP)
    api.post("/api/settings/transition", {"default": "cut", "crossfade_s": 3, "trim_fade_s": 1.5, "trim_fadein_s": 0})
    api.cmd("volume/100")
    api.cmd("go_transition/cut")
    api.post("/api/triggers/arm", {"armed": True})
    api.post("/api/settings/warning", {"warnings": [{"t": 60, "c": "#f97316"}, {"t": 30, "c": "#ef4444"}]})
    api.cmd("solo/0")
    api.wait_for(lambda s: s["state"] == "stopped", 6, desc="stopped after reset")
    try:                                                   # a duck that was held when playback stopped is still being released: let it finish
        api.wait_for(lambda s: float(s["duck_gr"]) == 0 and s["on_top"] == "0", 10, interval=0.2, desc="ducking released")
    except AssertionError:
        pass


def make_playlist(api, name, files):
    api.post("/api/playlists", {"name": name})
    idx = len(api.playlists()) - 1
    if files:
        r = api.post(f"/api/playlists/{idx}/add", {"files": files})
        assert r.status == 200, r
    return idx


@pytest.fixture(autouse=True)
def _each(request, api):
    client.CURRENT[0] = request.node.nodeid
    if request.node.get_closest_marker("noreset"):
        yield
        return
    reset_player(api)
    yield
    client.CURRENT[0] = None


@pytest.fixture()
def std(api):
    """Playlist 0 "A" = tone_a, tone_b, tone_c (3/3/4 s); playlist 1 "B" = short_1s, short_2s, long_120s. Focus on 0/0."""
    make_playlist(api, "A", ["tone_a.wav", "tone_b.wav", "tone_c.wav"])
    make_playlist(api, "B", ["short_1s.wav", "short_2s.wav", "long_120s.wav"])
    api.cmd("0/0/focus")
    return api


@pytest.fixture()
def preview(api):
    d = api.get("/api/devices").json
    if not d.get("devices"):
        pytest.skip("no audio output device is listed, so the preview output cannot be enabled")
    r = api.post("/api/preview/device", {"name": d["devices"][0]})
    if r.status != 200:
        pytest.skip(f"cannot enable a preview device: {r.text[:100]}")
    api.wait_for(lambda s: s["preview_state"] != "off", 10, desc="preview enabled")
    yield d["devices"][0]
    api.post("/api/preview/device", {"name": None})


@pytest.fixture()
def needs_osc(api):
    if not api.osc_port:
        pytest.skip("OSC input port unknown for this target (pass --osc-port)")
    return api


@pytest.fixture()
def sink(target):
    if not target["sink"]:
        pytest.skip("OSC output can only be checked on an instance started by the harness")
    return target["sink"]


@pytest.fixture()
def managed(target):
    if not target["managed"]:
        pytest.skip("needs an instance started by the harness")
    return target["instance"]


@pytest.fixture()
def scratch(api):
    """make(name, folder="", secs=1.0, freq=500) uploads a small WAV into the library; everything made here is removed afterwards."""
    from harness import libgen
    import tempfile
    made, folders = [], []

    def make(name, folder="", secs=1.0, freq=None, playlist=None):
        import zlib
        freq = freq or 300 + zlib.crc32(name.encode()) % 600          # the player de-duplicates identical uploads, so every file gets its own tone
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / name
            libgen.write_tone(p, freq, secs, -12)
            r = api.upload(name, p.read_bytes(), folder=folder or None, playlist=playlist)
        assert r.status == 200, r
        fid = r.json["files"][0]["id"]
        made.append(fid)
        if folder:
            folders.append(folder.split("/")[0])
        return fid
    make.folders = folders
    yield make
    for fid in made:
        api.delete("/api/library", id=fid)
    for f in set(folders):
        api.delete("/api/library/folder", path=f, force="1")


@pytest.fixture(scope="session")
def weird_id(manifest):
    """The library id of the file with spaces and special characters in its name (an upload may have cleaned it)."""
    return next(k for k in manifest if k.startswith("Name with spaces"))
