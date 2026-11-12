"""Play on Top ducking settings (HTTP and commands) and their effect on the background deck."""
import time
import pytest

KEYS = {"threshold": ("duck_threshold", "-30.0"), "ratio": ("duck_ratio", "6"), "attack": ("duck_attack", "10"), "release": ("duck_release", "500"),
        "level": ("top_level", "100")}


def duck(api):
    return api.get("/api/settings/top").json


@pytest.mark.sev(2)
@pytest.mark.covers("http.GET /api/settings/top", "http.POST /api/settings/top")
def test_duck_settings_http_roundtrip(api):
    assert duck(api) == {"fade_ms": 1500, "track_pct": 100, "threshold_db": -30.0, "ratio": 6.0, "attack_ms": 10, "release_ms": 500, "hold": True}
    r = api.post("/api/settings/top", {"track_pct": 80, "threshold_db": -41.26, "ratio": 8.44, "attack_ms": 20.4, "release_ms": 900, "hold": False, "fade_ms": 2500})
    assert r.status == 200
    d = duck(api)
    assert d == {"fade_ms": 2500, "track_pct": 80, "threshold_db": -41.3, "ratio": 8.4, "attack_ms": 20, "release_ms": 900, "hold": False}, d
    s = api.state()
    assert (s["top_level"], s["duck_threshold"], s["duck_ratio"], s["duck_attack"], s["duck_release"], s["duck_hold"]) == ("80", "-41.3", "8.4", "20", "900", "0")


@pytest.mark.sev(2)
@pytest.mark.covers("http.POST /api/settings/top")
@pytest.mark.parametrize("bad", [{"threshold_db": 5}, {"threshold_db": -61}, {"ratio": 0.5}, {"ratio": 21}, {"attack_ms": 0}, {"attack_ms": 201},
                                 {"release_ms": 5}, {"release_ms": 3001}, {"track_pct": -1}, {"track_pct": 101}, {"ratio": "abc"}, {"ratio": None},
                                 {"ratio": "nan"}, {"threshold_db": [1]}, {"ratio": 6, "attack_ms": 9999}])
def test_duck_settings_http_rejects_out_of_range_and_changes_nothing(api, bad):
    before = duck(api)
    r = api.post("/api/settings/top", bad)
    assert r.status == 400 and r.json["ok"] is False and r.json["error"], r.text
    assert duck(api) == before, "a refused request must not change any value"


@pytest.mark.sev(2)
@pytest.mark.covers("http.POST /api/settings/top")
def test_duck_settings_ignores_unknown_keys_and_clamps_fade(api):
    assert api.post("/api/settings/top", {"bogus": 1, "ratio": 7, "fade_ms": 99999999}).status == 200
    d = duck(api)
    assert d["ratio"] == 7.0 and d["fade_ms"] == 30000
    assert api.post("/api/settings/top", {"fade_ms": -50}).status == 200 and duck(api)["fade_ms"] == 0
    assert api.post("/api/settings/top", {}).status == 200


@pytest.mark.sev(2)
@pytest.mark.covers("cmd.duck")
@pytest.mark.parametrize("what", ["threshold", "ratio", "attack", "release", "level"])
def test_duck_commands_set_inc_dec_and_clamp(api, what):
    var, default = KEYS[what]
    lo_hi = {"threshold": ("-60.0", "0.0"), "ratio": ("1", "20"), "attack": ("1", "200"), "release": ("10", "3000"), "level": ("0", "100")}[what]
    mid = {"threshold": "-40", "ratio": "8", "attack": "50", "release": "800", "level": "70"}[what]
    assert api.res(f"duck/{what}/{mid}") == "ok"
    v0 = api.state()[var]
    assert float(v0) == float(mid)
    api.cmd(f"duck/{what}/inc")
    v1 = float(api.state()[var])
    assert v1 > float(v0)
    api.cmd(f"duck/{what}/dec")
    api.cmd(f"duck/{what}/dec")
    assert float(api.state()[var]) < float(v0)
    api.cmd(f"duck/{what}/{mid}")
    api.cmd(f"duck/{what}/up/2")
    api.cmd(f"duck/{what}/down/4")
    assert float(api.state()[var]) < float(mid) and api.res(f"duck/{what}/inc/1") == "ok"
    for _ in range(3):
        api.cmd(f"duck/{what}/inc/100000")
    assert float(api.state()[var]) == float(lo_hi[1]), "inc stops at the upper limit"
    api.cmd(f"duck/{what}/dec/100000")
    assert float(api.state()[var]) == float(lo_hi[0]), "dec stops at the lower limit"
    assert api.res(f"duck/{what}/{lo_hi[1]}") == "ok"
    assert api.res(f"duck/{what}/{float(lo_hi[1]) + 1000}") == "invalid"


@pytest.mark.sev(2)
@pytest.mark.covers("cmd.duck")
def test_duck_hold_command(api):
    assert api.state()["duck_hold"] == "1"
    assert api.res("duck/hold") == "ok" and api.state()["duck_hold"] == "0", "no value toggles"
    assert api.res("duck/hold") == "ok" and api.state()["duck_hold"] == "1"
    assert api.res("duck/hold/0") == "ok" and api.state()["duck_hold"] == "0"
    assert api.res("duck/hold/1") == "ok" and api.state()["duck_hold"] == "1"
    assert api.res("duck/hold/off") == "ok" and api.state()["duck_hold"] == "0"
    assert api.res("duck/hold/on") == "ok" and api.state()["duck_hold"] == "1"


@pytest.mark.sev(2)
@pytest.mark.covers("cmd.duck")
@pytest.mark.parametrize("bad", ["duck", "duck/bogus/1", "duck/threshold", "duck/threshold/abc", "duck/threshold/10", "duck/ratio/inc/abc",
                                 "duck/ratio/0", "duck/attack/nan", "duck/release/-5", "duck/level/101", "duck/threshold/inf"])
def test_duck_commands_reject_bad_values_and_change_nothing(api, bad):
    before = duck(api)
    assert api.res(bad) == "invalid", bad
    assert duck(api) == before


def play_over(api, bg="0/2", top="1/1"):
    api.cmd(bg)
    api.wait_playing(bg)
    api.cmd(f"{top}/top")
    api.wait_for(lambda s: s["on_top"] == "1", 5, desc="top track on")


def deck_levels(api):
    return sorted(d["vol"] for d in api.get("/api/monitor").json["decks"])


@pytest.mark.sev(1)
@pytest.mark.covers("cmd.track.top", "http.POST /api/settings/top")
def test_background_is_turned_down_while_the_top_track_plays_and_comes_back(std):
    api = std
    play_over(api)                                       # tone_c (4 s) under short_2s
    time.sleep(0.5)
    low = deck_levels(api)
    assert len(low) == 2 and low[0] < 0.5, f"the background must be ducked well below full, got {low}"
    assert float(api.state()["duck_gr"]) > 5
    assert api.get("/api/meters").json["gr"] > 5
    api.wait_for(lambda s: s["on_top"] == "0", 4, desc="the top track to end")
    t0 = time.time()
    api.wait_for(lambda s: (deck_levels(api) or [0])[-1] > 0.9, 4, desc="the background to come back up (release 500 ms)")
    assert time.time() - t0 < 3.0, "the release is slower than 3 x the release time"
    assert float(api.state()["duck_gr"]) < 2


@pytest.mark.sev(2)
@pytest.mark.covers("cmd.duck", "http.POST /api/settings/top")
def test_ducking_settings_change_the_depth(std):
    api = std
    api.post("/api/settings/top", {"threshold_db": 0})            # the top track is never louder than 0 dB: no ducking
    play_over(api)
    time.sleep(0.6)
    assert deck_levels(api)[0] > 0.9, "threshold 0 dB: no reduction expected"
    api.cmd("stopall")
    api.wait_state("stopped")
    api.post("/api/settings/top", {"threshold_db": -60, "ratio": 20})
    play_over(api)
    time.sleep(0.6)
    assert deck_levels(api)[0] < 0.2, "a low threshold and a high ratio must duck deeply"


@pytest.mark.sev(2)
@pytest.mark.covers("cmd.duck", "http.POST /api/settings/top")
def test_top_level_sets_the_level_of_the_top_track(std):
    api = std
    api.cmd("duck/level/50")
    api.post("/api/settings/top", {"threshold_db": 0})
    play_over(api)
    time.sleep(0.4)
    assert abs(deck_levels(api)[-1] - 1.0) < 0.05, deck_levels(api)
    tops = [d for d in api.get("/api/monitor").json["decks"] if "short_2s" in d["fid"]]
    assert tops and abs(tops[0]["vol"] - 0.5) < 0.06, tops


@pytest.mark.sev(2)
@pytest.mark.covers("cmd.track.top", "cmd.stopall")
def test_stopall_while_ducked_does_not_leak_the_duck_into_the_next_play_on_top(std):
    """The depth the ducking had when playback was stopped is released over several seconds in the background. A background track started
    meanwhile, with a Play on Top that asks for no ducking at all, must not be turned down by that leftover."""
    api = std
    api.post("/api/settings/top", {"threshold_db": -60, "ratio": 20})
    play_over(api)
    time.sleep(0.6)
    assert float(api.state()["duck_gr"]) > 30
    api.cmd("stopall")
    assert float(api.state()["duck_gr"]) == 0, "stop all clears the duck depth at once (it is not released over the release time)"
    api.post("/api/settings/top", {"threshold_db": 0, "ratio": 6})      # now a top track that never needs ducking
    time.sleep(0.4)
    api.cmd("0/2")
    api.wait_playing("0/2")
    api.cmd("1/1/top")
    api.wait_for(lambda s: s["on_top"] == "1", 5, desc="top")
    low = []
    for _ in range(8):
        time.sleep(0.1)
        bg = [d["vol"] for d in api.get("/api/monitor").json["decks"] if "tone_c" in d["fid"]]
        low += bg
    assert low and min(low) > 0.9, f"the background dipped to {min(low) if low else None} although the threshold is 0 dB"


@pytest.mark.sev(2)
@pytest.mark.covers("cmd.track.top", "cmd.fadeout")
def test_fadeout_while_ducked_keeps_ducking_while_the_top_track_is_still_there(std):
    """A fade-out is not a stop-all: the top track and the ducked background fade together and the duck depth is untouched until they are gone."""
    api = std
    api.post("/api/settings/top", {"threshold_db": -60, "ratio": 20})
    play_over(api)
    time.sleep(0.5)
    before = float(api.state()["duck_gr"])
    assert before > 30
    api.cmd("fadeout", ms=1500)
    time.sleep(0.2)
    assert float(api.state()["duck_gr"]) > 0.8 * before, "the duck depth must carry on during a fade-out"
    api.wait_state("stopped", 6)


@pytest.mark.sev(2)
@pytest.mark.covers("cmd.track.top", "cmd.stopall")
def test_duck_is_released_over_the_release_time_after_the_top_track_ends_on_its_own(std):
    """Unchanged normal behaviour: when the top track ends, the depth falls back to 0 over about the release time (500 ms), not at once."""
    api = std
    api.post("/api/settings/top", {"threshold_db": -60, "ratio": 20})
    play_over(api)
    time.sleep(0.5)
    api.wait_for(lambda s: s["on_top"] == "0", 4, desc="the top track to end")
    api.wait_for(lambda s: float(s["duck_gr"]) < 0.5, 4, desc="the duck to be released")


@pytest.mark.sev(2)
@pytest.mark.covers("cmd.stopall", "cmd.stop")
@pytest.mark.parametrize("word", ["stopall", "stop"])
def test_stop_all_clears_the_duck_depth_at_once(std, word):
    api = std
    api.post("/api/settings/top", {"threshold_db": -60, "ratio": 20})
    play_over(api)
    time.sleep(0.5)
    assert float(api.state()["duck_gr"]) > 30
    api.cmd(word)
    time.sleep(0.15)
    assert float(api.state()["duck_gr"]) < 1, "stop-all must not keep a duck depth that is released later"
