"""2.7.5 rc1 (Preview meters): the Mute under the Preview meters mutes the preview output ONLY: never the live decks, the live meters, the ducking, Live Mute or Solo."""
import time

import pytest


def pv(api):
    return api.state()["preview"]


@pytest.mark.sev(2)
@pytest.mark.covers("http.POST /api/preview/ctl")
def test_mute_needs_a_device_and_a_boolean(api, std):
    assert api.post("/api/preview/ctl", {"cmd": "mute", "on": True}).status == 400, "no preview output set"


@pytest.mark.sev(2)
@pytest.mark.covers("http.POST /api/preview/ctl")
def test_mute_flag_and_worker_follow_each_other_and_the_volume_is_kept(std, preview):
    api = std
    assert api.post("/api/preview/ctl", {"cmd": "mute", "on": "yes"}).status == 400
    assert api.post("/api/preview/ctl", {"cmd": "mute"}).status == 400
    api.cmd("preview/volume/70")
    assert api.res("preview/1/2") == "ok"
    api.wait_for(lambda s: s["preview_state"] == "playing", 8, desc="preview playing")
    assert pv(api)["muted"] is False
    assert api.post("/api/preview/ctl", {"cmd": "mute", "on": True}).status == 200
    api.wait_for(lambda s: s["preview"].get("mute") is True and s["preview"]["muted"] is True, 5, desc="worker muted")
    assert api.state()["preview_volume"] == "70", "Mute is not the volume: the slider keeps its value"
    assert api.post("/api/preview/ctl", {"cmd": "mute", "on": False}).status == 200
    api.wait_for(lambda s: s["preview"].get("mute") is False and s["preview"]["muted"] is False, 5, desc="worker unmuted")
    assert api.state()["preview_volume"] == "70"
    api.res("preview/stop")


@pytest.mark.sev(1)
@pytest.mark.covers("http.POST /api/preview/ctl")
def test_preview_mute_changes_nothing_about_live(std, preview):
    api = std
    api.cmd("volume/80")
    api.cmd("0/0"); api.wait_playing("0/0")
    api.res("preview/1/2"); api.wait_for(lambda s: s["preview_state"] == "playing", 8, desc="preview playing")
    time.sleep(0.8)
    keys = ("live_volume", "live_id", "state", "on_top", "duck_threshold", "duck_ratio", "duck_attack", "duck_release", "duck_hold", "preview_solo")
    before = {k: api.state()[k] for k in keys}
    m0 = api.get("/api/meters").json["live"]
    assert m0["l_db"] > -40, m0
    assert api.post("/api/preview/ctl", {"cmd": "mute", "on": True}).status == 200
    api.wait_for(lambda s: s["preview"].get("mute") is True, 5, desc="muted")
    time.sleep(0.8)
    after = {k: api.state()[k] for k in keys}
    m1 = api.get("/api/meters").json["live"]
    assert after == before, (before, after)
    assert abs(m1["l_db"] - m0["l_db"]) < 6 and m1["l_db"] > -40, (m0, m1)
    assert float(api.state()["duck_gr"]) == pytest.approx(0.0, abs=0.1)
    # Live Mute behaves as before and does not touch the preview mute
    api.cmd("volume/mute"); time.sleep(0.3)
    assert api.state()["live_volume"] == "0" and pv(api)["muted"] is True
    api.cmd("volume/mute"); time.sleep(0.3)
    assert api.state()["live_volume"] == "80"
    api.post("/api/preview/ctl", {"cmd": "mute", "on": False})
    api.wait_for(lambda s: s["preview"].get("mute") is False, 5, desc="unmuted")
    api.cmd("stop"); api.res("preview/stop")


@pytest.mark.sev(2)
@pytest.mark.covers("http.POST /api/preview/ctl", "cmd.solo")
def test_mute_silences_the_soloed_live_audio_on_the_preview_output_and_solo_stays_on(std, preview):
    api = std
    api.cmd("0/0"); api.wait_playing("0/0")
    api.cmd("solo/1")
    api.wait_for(lambda s: s["preview"].get("mon", 0) >= 1 and s["preview"].get("mv", 0) > 0.05, 8, desc="live audio on the preview output")
    api.post("/api/preview/ctl", {"cmd": "mute", "on": True})
    api.wait_for(lambda s: s["preview"].get("mv", 1) == 0, 5, desc="the monitor channels silent")
    assert api.state()["preview_solo"] == "1", "Solo is still on"
    assert api.state()["state"] == "playing" and api.state()["live_volume"] == "100"
    api.post("/api/preview/ctl", {"cmd": "mute", "on": False})
    api.wait_for(lambda s: s["preview"].get("mv", 0) > 0.05, 5, desc="the monitor audible again")
    api.cmd("solo/0"); api.cmd("stop")


@pytest.mark.sev(2)
@pytest.mark.covers("http.POST /api/preview/ctl", "http.POST /api/preview/device")
def test_mute_survives_a_change_of_the_preview_device(std, preview, api):
    devs = api.get("/api/devices").json["devices"]
    api.post("/api/preview/ctl", {"cmd": "mute", "on": True})
    assert api.post("/api/preview/device", {"name": devs[0]}).status == 200      # the worker is restarted
    api.res("preview/1/2")
    api.wait_for(lambda s: s["preview_state"] == "playing", 8, desc="playing on the restarted worker")
    api.wait_for(lambda s: s["preview"].get("mute") is True, 5, desc="the new worker is muted too")
    api.post("/api/preview/ctl", {"cmd": "mute", "on": False})
    api.res("preview/stop")
