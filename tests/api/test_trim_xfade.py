"""Trim (In / Out / end edge), per-track crossfade time, the default transition and what the crossfade does to the decks."""
import time
import pytest


def trim(api, p=0, t=0):
    return api.playlists()[p]["tracks"][t]["trim"]


@pytest.mark.sev(2)
@pytest.mark.covers("cmd.track.in", "cmd.track.out", "cmd.track.end_edge", "cmd.track.trim_clear")
def test_trim_commands_set_and_clear(std):
    api = std
    assert trim(api) is None
    assert api.res("0/0/in/0.5") == "ok" and trim(api) == {"in": 0.5}
    assert api.res("0/0/out/2.5") == "ok" and trim(api) == {"in": 0.5, "out": 2.5}
    assert api.res("0/0/end/cut") == "ok" and trim(api) == {"in": 0.5, "out": 2.5, "end": "cut"}
    assert api.res("0/0/end/fade") == "ok" and trim(api) == {"in": 0.5, "out": 2.5}, "fade is the default and is not stored"
    assert api.res("0/0/in/clear") == "ok" and trim(api) == {"out": 2.5}
    assert api.res("0/0/out/off") == "ok" and trim(api) is None
    api.cmd("0/0/in/1"); api.cmd("0/0/out/2"); api.cmd("0/0/end/cut")
    assert api.res("0/0/trim/clear") == "ok" and trim(api) is None
    assert api.res("0/0/trim/reset") == "ok"
    assert api.playlists()[0]["tracks"][1]["trim"] is None, "other tracks are untouched"


@pytest.mark.sev(2)
@pytest.mark.covers("cmd.track.in", "cmd.track.out")
@pytest.mark.parametrize("bad", ["0/0/in/abc", "0/0/in/", "0/0/in", "0/0/end/sideways", "0/0/trim", "0/0/trim/now", "0/9/in/1", "9/0/out/1", "0/0/out/1,5"])
def test_trim_commands_reject_bad_values(std, bad):
    api = std
    api.cmd("0/0/in/0.5")
    assert api.res(bad) == "invalid"
    assert trim(api) == {"in": 0.5}


@pytest.mark.sev(2)
@pytest.mark.covers("cmd.track.in", "cmd.track.out")
def test_trim_region_must_be_half_a_second_and_is_clipped_to_the_file(std):
    api = std
    api.cmd("0/0/in/1")
    assert api.res("0/0/out/1.4") == "invalid", "Out less than 0.5 s after In"
    assert api.res("0/0/out/1.5") == "ok" and trim(api) == {"in": 1.0, "out": 1.5}
    api.cmd("0/0/trim/clear")
    assert api.res("0/0/out/999") == "ok" and trim(api) is None, "Out beyond the end is the end"
    assert api.res("0/0/in/-4") == "ok" and trim(api) is None, "a negative In is the start"
    api.cmd("0/0/in/2.9")
    assert trim(api)["in"] == 2.9
    assert api.res("0/0/in/nan") == "ok"
    for v in ("inf", "-inf", "1e999"):
        api.cmd("0/0/trim/clear")
        api.res(f"0/0/in/{v}")
        t = trim(api)
        assert t is None or all(0 <= x <= 3.01 for k, x in t.items() if k in ("in", "out")), (v, t)


@pytest.mark.sev(2)
@pytest.mark.covers("http.POST /api/playlists/{p}/trim")
def test_trim_endpoint(std):
    api = std
    r = api.post("/api/playlists/0/trim", {"track": 1, "in": 0.5, "out": 2})
    assert r.status == 200 and r.json["trim"] == {"in": 0.5, "out": 2.0}
    r = api.post("/api/playlists/0/trim", {"track": 1, "in": None})
    assert r.status == 200 and r.json["trim"] == {"out": 2.0}
    r = api.post("/api/playlists/0/trim", {"track": 1, "end": "cut"})
    assert r.json["trim"] == {"out": 2.0, "end": "cut"}
    assert api.post("/api/playlists/0/trim", {"track": 1, "clear": True}).json["trim"] is None
    for bad in ({"track": 1, "in": 2, "out": 2.2}, {"track": 1, "end": "sideways"}, {"track": 9, "in": 1}, {"track": "x"}, {}, {"in": 1}):
        assert api.post("/api/playlists/0/trim", bad).status == 400, bad
    assert api.post("/api/playlists/9/trim", {"track": 0, "in": 1}).status == 400


@pytest.mark.sev(1)
@pytest.mark.covers("cmd.track.in", "cmd.track.out")
def test_a_trimmed_track_starts_at_in_and_ends_at_out(std):
    api = std
    api.cmd("0/0/in/1")
    api.cmd("0/0/out/2.4")
    api.cmd("0/0")
    s = api.wait_playing("0/0")
    assert s["live_in"] == 1.0 and abs(s["live_out"] - 2.4) < 0.01 and abs(s["live_dur"] - 3.0) < 0.1
    assert 0.95 <= s["live_pos"] < 1.5, f"must start at the In point, started at {s['live_pos']}"
    assert s["remaining"] in ("00:02", "00:01")
    t0 = time.time()
    api.wait_state("stopped", 4)
    assert time.time() - t0 < 2.6, "the track must end at the Out point, not at the end of the file"


@pytest.mark.sev(1)
def test_trim_end_cut_stops_hard_and_fade_fades(std):
    api = std
    api.cmd("0/0/in/0.2")
    api.cmd("0/0/out/2")
    api.cmd("0/0/end/cut")
    api.cmd("0/0")
    api.wait_playing("0/0")
    time.sleep(1.5)
    d = api.get("/api/monitor").json["decks"]
    assert d and d[0]["vol"] > 0.9, "a cut keeps full level up to the Out point"
    api.wait_state("stopped", 3)


@pytest.mark.sev(2)
@pytest.mark.covers("cmd.seek")
def test_seek_stays_inside_the_trim_region(std):
    api = std
    api.cmd("1/2/in/10")
    api.cmd("1/2/out/20")
    api.cmd("1/2")
    s = api.wait_playing("1/2")
    assert s["live_pos"] >= 9.9
    api.cmd("seek/2")
    assert api.state()["live_pos"] >= 9.9, "seek before In is held at In"
    api.cmd("seek/90")
    assert api.state()["live_pos"] <= 20.1, "seek after Out is held at Out"


@pytest.mark.sev(2)
@pytest.mark.covers("cmd.track.xftime")
def test_per_track_crossfade_time(std):
    api = std
    xf = lambda k: api.playlists()[0]["tracks"][k]["xfade"]
    assert xf(1) is None
    assert api.res("0/1/xftime/2") == "ok" and xf(1) == 2000
    assert api.res("0/1/xftime/0.25") == "ok" and xf(1) == 250
    assert api.res("0/1/xfadetime/30") == "ok" and xf(1) == 30000
    assert api.res("0/1/xftime/0") == "ok" and xf(1) == 0
    for clear in ("clear", "reset", "off", "master"):
        api.cmd("0/1/xftime/3")
        assert api.res(f"0/1/xftime/{clear}") == "ok" and xf(1) is None
    for bad in ("31", "-1", "abc", "", "nan"):
        api.cmd("0/1/xftime/4")
        assert api.res("0/1/xftime/" + bad) == "invalid", bad
        assert xf(1) == 4000
    assert api.res("0/1/xftime") == "invalid" and api.res("0/9/xftime/1") == "invalid"
    assert xf(0) is None and xf(2) is None


@pytest.mark.sev(3)
@pytest.mark.covers("cmd.track.xftime")
@pytest.mark.parametrize("v", ["inf", "-inf", "1e999"])
def test_xftime_infinite_value_is_refused_not_a_server_error(std, v):
    r = std.request("GET", f"/api/0/1/xftime/{v}")
    assert r.status == 200, f"HTTP {r.status}: {r.text[:80]}"
    assert r.json["result"] == "invalid"


@pytest.mark.sev(2)
@pytest.mark.covers("http.GET /api/settings/transition", "http.POST /api/settings/transition")
def test_transition_settings(api):
    assert api.get("/api/settings/transition").json == {"default": "cut", "crossfade_ms": 3000, "trim_fade_ms": 1500, "trim_fadein_ms": 0}
    assert api.post("/api/settings/transition", {"default": "crossfade", "crossfade_s": 1.5}).status == 200
    assert api.get("/api/settings/transition").json == {"default": "crossfade", "crossfade_ms": 1500, "trim_fade_ms": 1500, "trim_fadein_ms": 0}
    assert api.post("/api/settings/transition", {"crossfade_s": 2}).status == 200
    assert api.get("/api/settings/transition").json == {"default": "crossfade", "crossfade_ms": 2000, "trim_fade_ms": 1500, "trim_fadein_ms": 0}, "a missing field keeps its value"
    for bad in ({"default": "wipe"}, {"crossfade_s": 31}, {"crossfade_s": -1}, {"crossfade_s": "abc"}, {"default": None, "crossfade_s": "x"}):
        assert api.post("/api/settings/transition", bad).status == 400, bad
    assert api.get("/api/settings/transition").json == {"default": "crossfade", "crossfade_ms": 2000, "trim_fade_ms": 1500, "trim_fadein_ms": 0}


def levels(api):
    return [d["vol"] for d in api.get("/api/monitor").json["decks"]]


@pytest.mark.sev(1)
@pytest.mark.covers("cmd.track.xfade", "cmd.xfade")
def test_crossfade_runs_two_decks_and_ends_with_one(std):
    api = std
    api.cmd("0/2")
    api.wait_playing("0/2")
    api.cmd("1/2/xfade", ms=2000)
    time.sleep(0.8)
    d = levels(api)
    assert len(d) == 2 and 0.05 < min(d) < 0.95, f"two decks in a fade: {d}"
    api.wait_for(lambda s: len(levels(api)) == 1, 4, desc="old deck to go")
    assert api.state()["live_id"] == "1/2"
    assert levels(api)[0] > 0.9


@pytest.mark.sev(1)
@pytest.mark.covers("cmd.track.xfade", "cmd.track.xftime")
def test_crossfade_time_priority_ms_over_track_over_master(std):
    api = std
    api.post("/api/settings/transition", {"default": "cut", "crossfade_s": 6})
    api.cmd("1/2/xftime/0.5")                              # the track's own time
    api.cmd("0/2")
    api.wait_playing("0/2")
    t0 = time.time()
    api.cmd("1/2/xfade")                                   # own time 0.5 s beats the master 6 s
    api.wait_for(lambda s: len(levels(api)) == 1, 3, desc="a short crossfade")
    assert time.time() - t0 < 2.0
    api.cmd("1/2/xftime/clear")
    api.cmd("0/2")
    api.wait_playing("0/2")
    time.sleep(0.3)
    api.cmd("1/2/xfade", ms=300)                           # ?ms= beats the master time
    api.wait_for(lambda s: len(levels(api)) == 1, 1.8, desc="a 300 ms crossfade")


@pytest.mark.sev(2)
@pytest.mark.covers("cmd.take", "http.POST /api/settings/transition")
def test_take_follows_the_default_transition(std):
    api = std
    api.cmd("0/2")
    api.wait_playing("0/2")
    time.sleep(0.3)
    api.post("/api/settings/transition", {"default": "crossfade", "crossfade_s": 2})
    api.cmd("1/2/focus")
    api.cmd("take")
    time.sleep(0.7)
    assert len(levels(api)) == 2, "take with the default set to crossfade must crossfade"
    api.post("/api/settings/transition", {"default": "cut"})
    api.cmd("0/2")
    api.wait_playing("0/2")
    time.sleep(2.6)
    api.cmd("1/2/focus")
    api.cmd("take")
    time.sleep(0.3)
    assert len(levels(api)) == 1, "take with the default set to cut must cut"


@pytest.mark.sev(2)
@pytest.mark.covers("cmd.go_transition")
def test_go_transition_setting(api):
    assert api.state()["go_transition"] == "cut"
    assert api.res("go_transition/crossfade") == "ok" and api.state()["go_transition"] == "crossfade"
    assert api.res("go_transition/toggle") == "ok" and api.state()["go_transition"] == "cut"
    assert api.res("go_transition") == "ok" and api.state()["go_transition"] == "crossfade", "no value toggles"
    assert api.res("go_transition/cut") == "ok" and api.state()["go_transition"] == "cut"
    assert api.res("go_transition/wipe") == "invalid" and api.state()["go_transition"] == "cut"
    assert api.get("/api/settings/transition").json["default"] == "cut", "Go and the default transition are separate"
