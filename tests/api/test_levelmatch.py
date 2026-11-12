"""Level match (loudness normalisation per playlist)."""
import time
import pytest
from conftest import make_playlist


def wait_measured(api, p, n, timeout=40):
    def ok(_):
        return all(t["lufs"] is not None for t in api.playlists()[p]["tracks"][:n])
    try:
        api.wait_for(ok, timeout, interval=0.5, desc="loudness measured")
    except AssertionError:
        pytest.skip("loudness was not measured in time (needs ffmpeg or scipy on the player)")


@pytest.fixture()
def lm(api):
    p = make_playlist(api, "LM", ["loud.wav", "quiet.wav"])
    api.post(f"/api/playlists/{p}/norm", {"mode": "track", "ref": 1})        # files are measured only for playlists that use level match
    wait_measured(api, p, 2)
    api.post(f"/api/playlists/{p}/norm", {"mode": "off"})
    return p


@pytest.mark.sev(2)
@pytest.mark.covers("http.POST /api/playlists/{p}/norm", "cmd.playlist.norm")
def test_norm_modes_http_and_commands(api, lm):
    p = lm
    nm = lambda: api.playlists()[p]["norm"]
    assert nm()["mode"] == "off"
    assert api.post(f"/api/playlists/{p}/norm", {"mode": "track", "ref": 1}).status == 200
    assert nm()["mode"] == "track" and nm()["ref"] == "quiet.wav"
    assert api.post(f"/api/playlists/{p}/norm", {"mode": "lufs", "lufs": -20.04}).status == 200
    assert nm()["mode"] == "lufs" and nm()["lufs"] == -20.0
    assert api.res(f"{p}/norm/off") == "ok" and nm()["mode"] == "off"
    assert api.res(f"{p}/norm/track/0") == "ok" and nm()["mode"] == "track" and nm()["ref"] == "loud.wav"
    assert api.res(f"{p}/norm/ref/1") == "ok" and nm()["ref"] == "quiet.wav"
    assert api.res(f"{p}/norm/lufs/-18") == "ok" and nm()["mode"] == "lufs" and nm()["lufs"] == -18.0
    assert api.res(f"{p}/norm/lufs/-99") == "ok" and nm()["lufs"] == -60.0, "clamped to -60"
    assert api.res(f"{p}/norm/lufs/5") == "ok" and nm()["lufs"] == 0.0, "clamped to 0"
    assert api.res(f"{p}/norm/match") == "ok" and nm()["mode"] == "track"
    for bad in (f"{p}/norm/bogus", f"{p}/norm/lufs/abc", f"{p}/norm/ref", f"{p}/norm/ref/9", "9/norm/off", f"{p}/norm"):
        assert api.res(bad) in ("invalid", "unknown"), bad
    for bad in ({"mode": "bogus"}, {"ref": 9}, {"ref": "nope.wav"}, {"lufs": "x"}):
        assert api.post(f"/api/playlists/{p}/norm", bad).status == 400, bad


@pytest.mark.sev(1)
@pytest.mark.covers("http.POST /api/playlists/{p}/norm")
def test_level_match_turns_the_loud_track_down_and_never_boosts(api, lm):
    p = lm
    api.post(f"/api/playlists/{p}/norm", {"mode": "track", "ref": 1})
    t = api.playlists()[p]["tracks"]
    assert t[1]["gain_db"] in (0, 0.0), "the reference track keeps its level"
    assert -26 < t[0]["gain_db"] < -22, f"loud (-6 dBFS) matched to quiet (-30 dBFS) should be about -24 dB, got {t[0]['gain_db']}"
    assert 20 < t[0]["lufs"] - t[1]["lufs"] < 28
    api.cmd(f"{p}/0")
    api.wait_playing(f"{p}/0")
    time.sleep(0.3)
    s = api.state()
    assert float(s["live_gain_db"]) < -20
    v = api.get("/api/monitor").json["decks"][0]["vol"]
    assert abs(v - 10 ** (t[0]["gain_db"] / 20)) < 0.01, v
    api.post(f"/api/playlists/{p}/norm", {"mode": "off"})
    time.sleep(0.3)
    assert api.get("/api/monitor").json["decks"][0]["vol"] > 0.95, "switching level match off restores the level live"
    assert api.state()["live_gain_db"] == "0"
    api.post(f"/api/playlists/{p}/norm", {"mode": "lufs", "lufs": 0})
    t = api.playlists()[p]["tracks"]
    assert t[0]["gain_db"] == 0 and t[1]["gain_db"] == 0, "a target above both tracks must not boost"


@pytest.mark.sev(2)
def test_level_match_target_loudness_is_honoured(api, lm):
    p = lm
    api.post(f"/api/playlists/{p}/norm", {"mode": "lufs", "lufs": -23})
    t = api.playlists()[p]["tracks"]
    assert abs((t[0]["lufs"] + t[0]["gain_db"]) - (-23)) < 0.2
    assert t[1]["gain_db"] == 0
