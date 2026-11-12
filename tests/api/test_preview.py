"""Preview output, Solo live, mirror (a dummy audio device stands in for the real ones)."""
import time
import pytest


@pytest.mark.sev(2)
@pytest.mark.covers("cmd.preview", "http.GET /api/preview")
def test_preview_commands_without_a_device_say_so(api, std):
    for c in ("preview/0/0", "preview/focus", "preview/stop", "preview/pause", "preview/resume", "preview/playpause", "preview/volume/50", "solo", "solo/1"):
        assert api.res(c) == "no preview output", c
    assert api.state()["preview_state"] == "off" and api.state()["preview_solo"] == "0"
    r = api.post("/api/preview/play", {"p": 0, "t": 0})
    assert r.status == 400
    assert api.post("/api/preview/ctl", {"cmd": "stop"}).status == 400


@pytest.mark.sev(2)
@pytest.mark.covers("cmd.preview", "http.POST /api/preview/play", "http.POST /api/preview/ctl", "http.GET /api/preview", "http.POST /api/preview/device")
def test_preview_play_pause_stop_and_seek(std, preview):
    api = std
    assert api.res("preview/1/2") == "ok"
    s = api.wait_for(lambda s: s["preview_state"] == "playing", 8, desc="preview playing")
    assert s["preview_playing"] == "1" and s["preview_name"] == "long_120s"
    assert api.state()["live_id"] == "-", "preview must not touch the live output"
    assert api.res("preview/pause") == "ok"
    api.wait_for(lambda s: s["preview_state"] == "paused", 5, desc="paused")
    assert api.res("preview/playpause") == "ok"
    api.wait_for(lambda s: s["preview_state"] == "playing", 5, desc="resumed")
    assert api.res("preview/playpause") == "ok"
    api.wait_for(lambda s: s["preview_state"] == "paused", 5, desc="paused again")
    assert api.res("preview/resume") == "ok"
    assert api.post("/api/preview/ctl", {"cmd": "seek", "pos": 50}).status == 200
    api.wait_for(lambda s: s["preview"].get("pos", 0) > 49, 5, desc="preview position")
    assert api.get("/api/preview").json["state"] in ("playing", "paused")
    assert api.res("preview/stop") == "ok"
    api.wait_for(lambda s: s["preview_state"] == "stopped", 5, desc="stopped")
    assert api.post("/api/preview/play", {"id": "tone_a.wav"}).status == 200
    api.wait_for(lambda s: s["preview_state"] == "playing", 5, desc="playing by id")
    assert api.post("/api/preview/play", {"p": 0, "t": 1}).status == 200
    api.wait_for(lambda s: s["preview_name"] == "tone_b", 5, desc="playing by p/t")
    api.cmd("preview/stop")


@pytest.mark.sev(2)
@pytest.mark.covers("cmd.preview", "http.POST /api/preview/play", "http.POST /api/preview/ctl")
def test_preview_bad_input(std, preview):
    api = std
    for c in ("preview/9/9", "preview/bogus", "preview/0/x"):
        assert api.res(c) in ("invalid", "unknown"), c
    assert api.post("/api/preview/play", {"id": "nope.wav"}).status == 404
    assert api.post("/api/preview/play", {"p": 9, "t": 9}).status == 404
    assert api.post("/api/preview/play", {}).status == 404
    assert api.post("/api/preview/ctl", {"cmd": "explode"}).status == 400
    assert api.post("/api/preview/ctl", {}).status == 400
    assert api.post("/api/preview/device", {"name": "No Such"}).status == 400


@pytest.mark.sev(3)
@pytest.mark.covers("http.POST /api/preview/ctl")
@pytest.mark.parametrize("body", [{"cmd": "seek", "pos": "abc"}, {"cmd": "seek", "pos": None}, {"cmd": "seek", "pos": [1]}, {"cmd": "vol", "v": "abc"},
                                  {"cmd": "vol", "v": None}, {"cmd": "vol", "v": [1]}, {"cmd": "seek", "pos": "inf"}, {"cmd": "vol", "v": "nan"}])
def test_preview_ctl_bad_numbers_are_client_errors(std, preview, body):
    r = std.post("/api/preview/ctl", body)
    assert r.status < 500, f"{body} -> HTTP {r.status}"


@pytest.mark.sev(3)
@pytest.mark.covers("cmd.preview")
def test_preview_volume_commands(api, preview):
    pv = lambda: int(api.state()["preview_volume"])
    assert api.res("preview/volume/40") == "ok" and pv() == 40
    api.cmd("preview/volume/up"); assert pv() == 45
    api.cmd("preview/volume/up/10"); assert pv() == 55
    api.cmd("preview/volume/down/20"); assert pv() == 35
    api.cmd("preview/volume/down/100"); assert pv() == 0
    api.cmd("preview/volume/500"); assert pv() == 100
    assert api.res("preview/volume/abc") == "invalid" and pv() == 100
    api.cmd("preview/volume/100")


@pytest.mark.sev(2)
@pytest.mark.covers("cmd.solo", "cmd.preview")
def test_solo_live_toggle(std, preview):
    api = std
    api.cmd("0/0")
    api.wait_playing("0/0")
    assert api.res("solo") == "ok" and api.state()["preview_solo"] == "1"
    assert api.res("solo") == "ok" and api.state()["preview_solo"] == "0"
    assert api.res("solo/1") == "ok" and api.state()["preview_solo"] == "1"
    assert api.res("solo/0") == "ok" and api.state()["preview_solo"] == "0"
    assert api.res("solo/on") == "ok" and api.state()["preview_solo"] == "1"
    api.cmd("solo/0")


@pytest.mark.sev(2)
@pytest.mark.covers("cmd.preview")
def test_preview_focus_toggles_the_cued_track(std, preview):
    api = std
    api.cmd("0/1/focus")
    assert api.res("preview/focus") == "ok"
    api.wait_for(lambda s: s["preview_state"] == "playing" and s["preview_name"] == "tone_b", 6, desc="preview of the cue")
    assert api.res("preview/focus") == "ok"
    api.wait_for(lambda s: s["preview_state"] != "playing", 6, desc="toggled off")
    api.cmd("clear")
    assert api.res("preview/focus") == "ok" and api.state()["preview_state"] != "playing", "no cue: nothing to preview"


@pytest.mark.sev(2)
@pytest.mark.covers("http.POST /api/mirror/device", "http.POST /api/mirror/enable")
def test_mirror_enable_and_device(api):
    devs = api.get("/api/devices").json["devices"]
    assert api.post("/api/mirror/device", {"name": "No Such"}).status == 400
    if not devs:
        pytest.skip("no output device listed")
    try:
        assert api.post("/api/mirror/device", {"name": devs[0]}).status == 200
        r = api.post("/api/mirror/enable", {"on": True})
        assert r.status == 200 and r.json["enabled"] is True
        d = api.get("/api/devices").json
        assert d["mirror_enabled"] is True and d["mirror"] == devs[0]
        api.cmd("0/0")
        assert api.state()["state"] in ("stopped", "loading", "playing")
    finally:
        assert api.post("/api/mirror/enable", {"on": False}).json["enabled"] is False
        api.post("/api/mirror/device", {"name": None})


@pytest.mark.sev(4)
@pytest.mark.covers("cmd.solo")
def test_monitor_alias_of_solo_works_over_http_like_over_osc(api, preview):
    """/monitor is an alias of /solo in the command grammar, but over HTTP /api/monitor is the endpoint that lists the audible decks."""
    r = api.get("/api/monitor/1")
    assert r.status == 200 and r.json.get("result") == "ok", "GET /api/monitor/1 should run the alias (only /api/monitor itself is the endpoint)"
    r = api.request("GET", "/api/monitor")
    assert "decks" in r.json
    api.cmd("solo/0")
