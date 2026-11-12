"""Level meters and the published variables."""
import sys, time
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import gen_controls                                           # noqa: E402

PLAYER = Path(__file__).resolve().parent.parent.parent / "player.py"


@pytest.mark.sev(3)
@pytest.mark.covers("var.*")
def test_every_documented_variable_is_published(api, std):
    info, keys = gen_controls.var_info(gen_controls.read_sources(PLAYER))      # player.py + cpl/**
    pub = {v["name"] for v in api.get("/api/variables").json["vars"]}
    missing = sorted(k for k in set(info) | set(keys) if k not in pub)
    assert not missing, f"documented in player.py but not published: {missing}"
    undocumented = sorted(k for k in pub if k not in info and k != "focus_count" and not k.startswith(("pl", "focus_t")))
    assert not undocumented, f"published without a description in VAR_INFO: {undocumented}"


@pytest.mark.sev(2)
@pytest.mark.covers("var.*", "http.GET /api/meters")
def test_meters_follow_the_playing_audio(std):
    api = std
    api.wait_for(lambda s: api.get("/api/meters").json["live"]["l_db"] <= -80, 8, desc="the meter to be silent before the test")
    m = api.get("/api/meters").json
    assert m["live"]["l_db"] <= -80 and m["live"]["l"] == 0
    s = api.state()
    assert s["live_db_l"] == "-inf" and s["live_fader_l"] == "0" and set(s["live_meter_l"]) == {"░"}
    api.cmd("0/0")                                            # 440 Hz at -12 dBFS peak, stereo
    api.wait_playing("0/0")
    time.sleep(0.6)
    m = api.get("/api/meters").json
    assert -20 < m["live"]["l_db"] < -8 and -20 < m["live"]["r_db"] < -8, m["live"]
    assert 60 < m["live"]["l"] < 82, m["live"]
    s = api.state()
    assert s["live_db_l"] != "-inf" and -20 < float(s["live_db_l"]) < -8 and int(s["live_fader_l"]) > 50 and int(s["live_level_l"]) > 50
    assert "█" in s["live_meter_l"] or "▓" in s["live_meter_l"] or s["live_meter_l"] != "░" * 8
    api.cmd("volume/50")
    time.sleep(0.6)
    db50 = api.get("/api/meters").json["live"]["l_db"]
    assert -26 < db50 < -14, f"-6 dB expected from the master volume, meter shows {db50}"
    api.cmd("volume/0")
    api.wait_for(lambda s: api.get("/api/meters").json["live"]["l_db"] < -60, 5, desc="the meter to fall after muting (it decays, it does not jump)")
    api.cmd("stop")
    api.wait_state("stopped")
    api.wait_for(lambda s: api.get("/api/meters").json["live"]["l_db"] <= -80, 6, desc="the meter to fall to silence after stop")


@pytest.mark.sev(2)
@pytest.mark.covers("var.*")
def test_mono_file_meters_both_sides_equally(std):
    api = std
    api.cmd("1/2")                                            # mono, -20 dBFS
    api.wait_playing("1/2")
    time.sleep(0.6)
    m = api.get("/api/meters").json["live"]
    assert abs(m["l_db"] - m["r_db"]) < 0.6 and -30 < m["l_db"] < -15, m


@pytest.mark.sev(3)
@pytest.mark.covers("var.*")
def test_variable_values_follow_playback(std):
    api = std
    api.cmd("0/1")
    api.wait_playing("0/1")
    v = {x["name"]: x["value"] for x in api.get("/api/variables").json["vars"]}
    assert v["state"] == "playing" and v["live_id"] == "0/1" and v["live_name"] == "tone_b" and v["focus_is_live"] in ("0", "1")
    assert v["remaining"] in ("00:03", "00:02") and v["loading"] == "-" and v["status"] == "ready"
    assert v["preview_state"] == "off" and v["preview_name"] == "-" and v["on_top"] == "0" and v["duck_gr"] == "0"
    api.cmd("0/2/focus")
    v = {x["name"]: x["value"] for x in api.get("/api/variables").json["vars"]}
    assert v["focus_name"] == "tone_c" and v["focus_playlist"] == "A" and v["focus_playlist_num"] == "0" and v["focus_is_live"] == "0"
