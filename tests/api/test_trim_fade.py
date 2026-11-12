"""Per-track fade-out length at B (trim "fade_ms"), with the global trim_fade_ms as the default."""
import sys
import time
import urllib.error
import pytest


def trim(api, p=0, t=0):
    return api.playlists()[p]["tracks"][t]["trim"]


def eff(api, p=0, t=0):
    return api.playlists()[p]["tracks"][t]["fade_ms_eff"]


def set_fade(api, **kw):
    return api.post("/api/playlists/0/trim", {"track": 0, **kw})


@pytest.mark.sev(2)
def test_fade_is_stored_per_track_and_falls_back_to_the_default(std):
    api = std
    r = set_fade(api, out=2.0, fade_ms=800)
    assert r.json["trim"] == {"out": 2.0, "fade_ms": 800} and r.json["fade_ms"] == 800
    assert eff(api) == 800 and eff(api, 0, 1) == 1500, "other tracks keep the default"
    api.post("/api/settings/transition", {"trim_fade_s": 2.5})
    assert eff(api) == 800 and eff(api, 0, 1) == 2500, "the default follows Settings; an override does not"
    assert set_fade(api, fade_ms=None).json["trim"] == {"out": 2.0}, "null removes the override"
    assert eff(api) == 2500
    assert api.get("/api/settings/transition").json["trim_fade_ms"] == 2500


@pytest.mark.sev(2)
def test_fade_is_clamped_to_the_played_part_and_validated(std):
    api = std
    r = set_fade(api, **{"in": 0.5, "out": 1.5, "fade_ms": 5000})
    assert r.status == 200 and r.json["trim"]["fade_ms"] == 1000, "B minus A is 1 s"
    for bad in (50, 10001, "x", -5):
        assert set_fade(api, out=2.0, fade_ms=bad).status == 400, bad
    assert set_fade(api, out=2.0, fade_ms=100).json["trim"]["fade_ms"] == 100
    assert set_fade(api, clear=True).json["trim"] is None, "removing the trim removes the fade length too"
    assert set_fade(api, **{"in": 0.5, "fade_ms": 900}).json["trim"] == {"in": 0.5}, "no B, no fade length"


@pytest.mark.sev(2)
def test_cut_keeps_the_value_but_plays_without_a_fade(std):
    api = std
    set_fade(api, out=2.0, fade_ms=700, end="cut")
    assert trim(api) == {"out": 2.0, "end": "cut", "fade_ms": 700}
    api.cmd("0/0")
    assert api.wait_playing("0/0")["live_fade_ms"] == 0
    api.cmd("stopall")
    set_fade(api, end="fade")
    api.cmd("0/0")
    assert api.wait_playing("0/0")["live_fade_ms"] == 700


@pytest.mark.sev(1)
def test_live_deck_uses_the_effective_value_and_keeps_it_through_seek(std):
    api = std
    set_fade(api, out=2.5)
    api.cmd("0/0")
    assert api.wait_playing("0/0")["live_fade_ms"] == 1500, "no override: the default"
    api.cmd("stopall")
    api.post("/api/settings/transition", {"trim_fade_s": 0.6})
    api.cmd("0/0")
    assert api.wait_playing("0/0")["live_fade_ms"] == 600, "default changed in Settings"
    api.cmd("stopall")
    set_fade(api, fade_ms=1200)
    api.cmd("0/0")
    assert api.wait_playing("0/0")["live_fade_ms"] == 1200
    api.cmd("seek/0.5")
    time.sleep(0.3)
    assert api.state()["live_fade_ms"] == 1200
    api.cmd("0/1")
    assert api.wait_playing("0/1")["live_fade_ms"] == 0, "an untrimmed track has no end fade"


@pytest.mark.sev(2)
def test_the_fade_really_starts_that_long_before_b(std):
    api = std
    set_fade(api, out=2.0, fade_ms=1000)
    api.cmd("0/0")
    api.wait_playing("0/0")
    time.sleep(0.4)
    v = api.get("/api/monitor").json["decks"][0]["vol"]
    assert v > 0.95, "full level before the fade"
    time.sleep(1.1)                                   # about 1.5 s in: halfway through the 1 s fade that began at 1.0 s
    v = api.get("/api/monitor").json["decks"][0]["vol"]
    assert 0.05 < v < 0.95, f"mid-fade level expected, got {v}"
    api.wait_state("stopped", 3)


@pytest.mark.sev(2)
def test_settings_range(std):
    api = std
    for bad in (0.05, 11, "x"):
        assert api.post("/api/settings/transition", {"trim_fade_s": bad}).status == 400, bad
    assert api.post("/api/settings/transition", {"trim_fade_s": 0.1}).status == 200
    assert api.get("/api/settings/transition").json["trim_fade_ms"] == 100
    assert api.get("/api/state").json["trim_fade_ms"] == 100


@pytest.mark.sev(2)
def test_fade_goes_with_the_track(std):
    api = std
    set_fade(api, out=2.0, fade_ms=900)
    assert api.post("/api/move", {"from": [0, 0], "to": [1, 0]}).status == 200
    assert api.playlists()[1]["tracks"][0]["trim"] == {"out": 2.0, "fade_ms": 900}
    assert eff(api, 1, 0) == 900


@pytest.mark.sev(2)
def test_fade_survives_a_restart(std, managed):
    if sys.platform == "win32":
        pytest.skip("os.execv on Windows starts a new process")
    api = std
    set_fade(api, out=2.0, fade_ms=900)
    api.cmd("0/1/out/2")                               # a trim written without fade_ms (the old shape) next to it
    assert api.post("/api/restart").status == 200
    time.sleep(1.0)
    for _ in range(100):
        try:
            if api.state()["status"] == "ready":
                break
        except (urllib.error.URLError, OSError, AssertionError, ValueError):
            pass
        time.sleep(0.3)
    assert trim(api, 0, 0) == {"out": 2.0, "fade_ms": 900}
    assert trim(api, 0, 1) == {"out": 2.0} and eff(api, 0, 1) == 1500, "an old trim loads unchanged and uses the default"


# ---- 2.7.4: fade-in at A (trim "start": "fade" + "fade_in_ms"), default config key trim_fadein_ms (0 = none)
def eff_in(api, p=0, t=0):
    return api.playlists()[p]["tracks"][t]["fade_in_ms_eff"]


@pytest.mark.sev(2)
def test_fade_in_is_stored_per_track_and_falls_back_to_the_default(std):
    api = std
    r = set_fade(api, start="fade", fade_in_ms=1500)
    assert r.status == 200 and r.json["trim"] == {"start": "fade", "fade_in_ms": 1500} and r.json["fade_in_ms"] == 1500, "an entry holding only the fade-in survives (A is then the start of the file)"
    assert eff_in(api) == 1500 and eff_in(api, 0, 1) == 0, "other tracks: no default, no fade"
    api.post("/api/settings/transition", {"trim_fadein_s": 2.5})
    assert eff_in(api) == 1500 and eff_in(api, 0, 1) == 2500, "the default follows Settings; an own value does not"
    assert api.get("/api/settings/transition").json["trim_fadein_ms"] == 2500 and api.get("/api/state").json["trim_fadein_ms"] == 2500
    assert set_fade(api, fade_in_ms=None).json["trim"] == {"start": "fade"}, "null removes the own value (Use default)"
    assert eff_in(api) == 2500
    api.post("/api/settings/transition", {"trim_fadein_s": 0})
    assert eff_in(api) == 0


@pytest.mark.sev(2)
def test_fade_in_cut_keeps_the_value_and_the_default_edge_is_not_stored(std):
    api = std
    set_fade(api, start="fade", fade_in_ms=700)
    assert set_fade(api, start="cut").json["trim"] == {"fade_in_ms": 700}, "Cut is the default and is not stored; the length is remembered"
    assert set_fade(api, start="fade").json["trim"] == {"start": "fade", "fade_in_ms": 700}
    assert set_fade(api, start=None, fade_in_ms=None).json["trim"] is None, "nothing left: the entry goes"
    assert set_fade(api, start="fade", fade_in_ms=900).status == 200
    assert set_fade(api, clear=True).json["trim"] is None, "removing the trim removes the fade-in too"


@pytest.mark.sev(2)
def test_fade_in_is_clamped_and_validated(std):
    api = std
    r = set_fade(api, **{"in": 0.5, "out": 1.5, "start": "fade", "fade_in_ms": 5000})
    assert r.status == 200 and r.json["trim"]["fade_in_ms"] == 1000, "B minus A is 1 s"
    for bad in (50, 10001, "x", -5):
        assert set_fade(api, start="fade", fade_in_ms=bad).status == 400, bad
    assert set_fade(api, start="sideways").status == 400
    assert set_fade(api, **{"in": 1.0}, fade_in_ms=10000, start="fade").json["trim"]["fade_in_ms"] <= 9000, "no B: clamped to what is left of the file"
    for bad in (0.05, 11, "x"):
        assert api.post("/api/settings/transition", {"trim_fadein_s": bad}).status == 400, bad
    assert api.post("/api/settings/transition", {"trim_fadein_s": 0.1}).status == 200


@pytest.mark.sev(2)
def test_fade_in_goes_with_the_track_on_move_and_rename(std):
    api = std
    set_fade(api, start="fade", fade_in_ms=900)
    assert api.post("/api/move", {"from": [0, 0], "to": [1, 0]}).status == 200
    assert api.playlists()[1]["tracks"][0]["trim"] == {"start": "fade", "fade_in_ms": 900}
    assert eff_in(api, 1, 0) == 900


@pytest.mark.sev(1)
def test_live_deck_applies_the_fade_in_at_a_hard_start_only(std):
    api = std
    set_fade(api, fade_in_ms=1200)
    api.cmd("0/0")
    assert api.wait_playing("0/0")["live_fade_in_ms"] == 0, "Cut: the value is remembered but not applied"
    api.cmd("stopall")
    set_fade(api, start="fade")
    api.cmd("0/0")
    assert api.wait_playing("0/0")["live_fade_in_ms"] == 1200
    time.sleep(1.4)                                   # the 1.2 s fade-in is over
    assert api.get("/api/monitor").json["decks"][0]["vol"] > 0.99
    api.cmd("seek/0.5")
    time.sleep(0.2)
    assert api.state()["live_fade_in_ms"] == 1200, "the deck keeps what it started with"
    assert api.get("/api/monitor").json["decks"][0]["vol"] > 0.99, "a seek starts no new fade"
    api.cmd("stopall")
    api.cmd("0/1")
    assert api.wait_playing("0/1")["live_fade_in_ms"] == 0, "an untrimmed track has no fade-in"
