"""Health, revision counter, persistence and restart."""
import json, sys, time, urllib.error, urllib.request
import pytest


@pytest.mark.sev(2)
@pytest.mark.covers("http.GET /api/state")
def test_health_is_ready_and_memory_is_reported(api):
    s = api.state()
    assert s["status"] == "ready" and s["health"]["status"] == "ready", s["health"]
    m = s["mem"]
    assert isinstance(m, dict) and m
    if sys.platform == "darwin":
        pytest.skip("the memory readout is not implemented on macOS")
    assert any(isinstance(v, (int, float)) and v > 0 for v in m.values()), m


@pytest.mark.sev(3)
@pytest.mark.covers("http.GET /api/state")
def test_rev_changes_when_playlists_or_library_change(api):
    r0 = api.state()["rev"]
    api.post("/api/playlists", {"name": "rev"})
    r1 = api.state()["rev"]
    assert r1 != r0
    api.post("/api/playlists/0/add", {"files": ["tone_a.wav"]})
    assert api.state()["rev"] != r1
    r2 = api.state()["rev"]
    time.sleep(0.5)
    assert api.state()["rev"] == r2, "rev must be stable when nothing changes"


@pytest.mark.sev(2)
@pytest.mark.covers("http.POST /api/restart")
def test_restart_comes_back_with_playlists_and_settings(std, managed):
    if sys.platform == "win32":
        pytest.skip("os.execv on Windows starts a new process; the harness cannot supervise it")
    api = std
    api.cmd("volume/63")
    api.cmd("0/1/end/loop")
    api.cmd("go_transition/crossfade")
    api.post("/api/settings/top", {"ratio": 11})
    api.cmd("0/2")
    api.wait_playing("0/2")
    pid = managed.proc.pid
    r = api.post("/api/restart")
    assert r.status == 200 and r.json["ok"]
    deadline = time.time() + 30
    came_back = False
    time.sleep(1.0)
    while time.time() < deadline:
        try:
            s = api.state()
            if s["status"] in ("ready", "starting"):
                came_back = True
                break
        except (urllib.error.URLError, OSError, AssertionError, ValueError):
            pass
        time.sleep(0.3)
    assert came_back, "the player did not come back within 30 s"
    assert managed.proc.pid == pid and managed.proc.poll() is None, "restart keeps the same process (so systemd keeps supervising it)"
    api.wait_for(lambda s: s["status"] == "ready", 40, desc="ready after restart")
    s = api.state()
    assert s["live_volume"] == "63" and s["go_transition"] == "crossfade" and s["duck_ratio"] == "11"
    pls = api.playlists()
    assert [p["name"] for p in pls] == ["A", "B"] and pls[0]["tracks"][1]["end"] == "loop"
    assert s["state"] == "stopped", "resume_on_start is off in the harness config: nothing plays after a restart"
    api.post("/api/settings/top", {"ratio": 6})
    api.cmd("go_transition/cut")


@pytest.mark.sev(2)
def test_state_json_and_playlists_json_survive_a_hard_kill(std, managed):
    """Playlists are written atomically: killing the player right after a change must leave a readable file with that change."""
    if sys.platform == "win32":
        pytest.skip("hard-kill semantics differ on Windows")
    api = std
    api.post("/api/playlists", {"name": "Last words"})
    managed.proc.kill()
    managed.proc.wait(5)
    d = json.loads((managed.workdir / "playlists.json").read_text("utf-8"))
    assert [p["name"] for p in d["playlists"]][-1] == "Last words"
    # bring it back for the following tests
    managed.restart()
    api.wait_for(lambda s: s["status"] == "ready", 40, desc="ready after a hard kill")
    assert [p["name"] for p in api.playlists()][-1] == "Last words"
