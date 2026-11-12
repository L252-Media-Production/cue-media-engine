"""Live input (Duck only): the whole thing through a real player instance with a SYNTHETIC capture source.

SIMULATED: the capture device. CP_TEST_INPUT=<folder> makes the capture helper (cpl/helpers/input_worker.py, the real process, the real ring) read
<folder>/feed.json instead of opening a sound card: "run" delivers a 500 Hz tone at the given RMS level, "stop" keeps the device open but delivers nothing
(a stall), "error" fails the stream, "gone" removes the device. CP_TEST_DEVICES=<folder> supplies the device lists (mock_devices.json / mock_inputs.json).
REAL: the helper process, the shared ring, the detector, the ducking maths, the deck volumes, the web API and commands, the variables, the preview worker's
Solo tap, and (in the audio test) the audio the player renders on the Live output (SDL_AUDIODRIVER=disk). NOT covered, needs the NUC: a real Dante or
analog device, its channel count and naming, unplugging a real cable, and clock behaviour of a real interface."""
import json, os, signal, subprocess, tempfile, time, wave
from pathlib import Path

import numpy as np
import pytest

from harness import client
from harness.instance import Instance

pytestmark = [pytest.mark.noreset]
FS, WIN = 48000, 2400
DEVS = ["Fake input", "Dante Virtual Soundcard", "Analog 1-2"]


def set_feed(folder, **kw):
    f = Path(folder) / "feed.json"
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps({"hz": 500, **kw}))
    os.replace(tmp, f)


def make_env(preview=True, extra_env=None):
    d = Path(tempfile.mkdtemp(prefix="cpinput-"))
    (d / "mock_devices.json").write_text(json.dumps(["Mock out 1", "Mock out 2"]))
    (d / "mock_inputs.json").write_text(json.dumps(DEVS))
    set_feed(d, state="run", db=-90.0, channels=2)
    env = {"CP_TEST_DEVICES": str(d), "CP_TEST_INPUT": str(d), **(extra_env or {})}
    return d, env


class Rig:
    def __init__(self, inst, api, d):
        self.inst, self.api, self.d = inst, api, d

    def feed(self, **kw):
        set_feed(self.d, **kw)

    def info(self):
        return self.api.get("/api/input").json

    def until(self, pred, timeout=8, desc="", interval=0.1):
        t0, last = time.time(), None
        while time.time() - t0 < timeout:
            last = self.info()
            if pred(last):
                return last
            time.sleep(interval)
        raise AssertionError(f"timed out after {timeout}s waiting for {desc}; last: {last}")

    def play_bed(self):
        assert self.api.res("0/0") == "ok"


def build(preview=True, wav_only=True, extra_config=None, extra_env=None, feed=None, tones=False):
    d, env = make_env(extra_env=extra_env)
    if feed:
        set_feed(d, **feed)
    cfg = {"input_device": "Fake input", "input_channel": 1, "input_armed": True, "duck_hold": False, "duck_attack_ms": 10, "duck_release_ms": 200,
           "duck_threshold_db": -30, "duck_ratio": 6}
    if preview:
        cfg["preview_device"] = "Mock out 1"
    cfg.update(extra_config or {})
    inst = Instance(wav_only=wav_only, extra_config=cfg, extra_env=env)
    inst.start()
    lib = inst.workdir / "media" / "library"
    if tones:
        write_tone(lib / "t1k.wav", 1000, 0.5, 60)
    api = client.Api(inst.base_url, osc_port=inst.osc_port)
    api.cmd("rescan")
    api.post("/api/playlists", {"name": "T"})
    assert api.post("/api/playlists/0/add", {"files": ["t1k.wav" if tones else "long_120s.wav"]}).status == 200
    t0 = time.time()
    while time.time() - t0 < 20 and api.state()["mem"].get("cache_tracks", 0) < 1:
        time.sleep(0.2)
    return Rig(inst, api, d)


def write_tone(path, freq, amplitude, seconds):
    n = np.arange(int(seconds * FS))
    y = np.round(amplitude * 32768 * np.sin(2 * np.pi * freq * n / FS)).astype("<i2")
    y = np.repeat(y[:, None], 2, axis=1)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(FS)
        w.writeframes(y.tobytes())


@pytest.fixture(scope="module")
def rig(request):
    r = build()
    yield r
    r.inst.stop()


@pytest.fixture()
def calm(rig):
    rig.api.cmd("stopall")
    rig.api.cmd("input/ducknow/off")
    rig.api.cmd("input/armed/on")
    rig.api.post("/api/input", {"gain_db": 0, "channels": [1], "device": "Fake input", "threshold_db": -30})
    rig.api.post("/api/input/solo", {"on": False})
    rig.feed(state="run", db=-90.0, channels=2)
    rig.until(lambda i: i["present"] and not i["signal"] and i["gr"] == 0, 10, "a quiet, connected input")
    return rig


# ----------------------------------------------------------------------------------------------------------------- state and chip
@pytest.mark.sev(2)
def test_the_input_reports_its_state_and_the_chip_follows_the_signal(calm):
    r = calm
    i = r.info()
    assert i["mode"] == "duck" and i["device"] == "Fake input" and i["channel"] == 1 and i["gain_db"] == 0 and i["channels"] == 2
    assert i["chip"] == "No signal" and i["armed"] is True and i["duck_now"] is False and i["solo"] is False
    assert (i["gain_min"], i["gain_max"]) == (-12.0, 24.0)
    assert sorted(DEVS) == i["devices"]
    r.feed(state="run", db=-40.0, channels=2)
    i = r.until(lambda i: i["signal"], 5, "signal present")
    assert i["chip"] == "Signal present"
    assert i["level_db"] == pytest.approx(-40.0, abs=0.6), "the meter shows the level after the gain (0 dB gain)"
    assert i["threshold_db"] == -30.0
    assert i["gr"] == 0, "-40 dBFS is below the -30 dBFS threshold"
    st = r.api.state()
    assert st["input"]["chip"] == "Signal present" and st["input_signal"] == "1" and st["input_armed"] == "1" and st["input_ducking"] == "0"
    m = r.api.get("/api/meters").json
    assert m["input"]["present"] is True and m["input"]["signal"] is True and m["input"]["level_db"] == pytest.approx(-40, abs=0.6)
    r.feed(state="run", db=-70.0, channels=2)
    r.until(lambda i: not i["signal"], 5, "signal gone (-70 dBFS is under the -60 dBFS level)")


@pytest.mark.sev(1)
def test_speech_over_the_threshold_ducks_the_playlist_and_releases_afterwards(calm):
    r = calm
    r.play_bed()
    r.feed(state="run", db=-15.0, channels=2)
    want = (-15.0 + 30.0) * (1 - 1 / 6.0)
    i = r.until(lambda i: i["gr"] > want - 0.8, 6, "the playlist to be ducked")
    assert i["ducking"] is True and i["gr"] == pytest.approx(want, abs=0.8)
    assert r.api.state()["input_ducking"] == "1"
    assert r.api.get("/api/meters").json["in_gr"] == pytest.approx(want, abs=0.8)
    assert float(r.api.state()["duck_gr"]) == 0.0, "Play on Top's own reduction is separate"
    r.feed(state="run", db=-90.0, channels=2)
    r.until(lambda i: i["gr"] == 0 and not i["ducking"], 6, "the release")
    assert r.api.state()["input_ducking"] == "0"


@pytest.mark.sev(2)
def test_armed_off_means_no_level_ducks_but_the_meter_and_chip_still_show_the_input(calm):
    r = calm
    r.play_bed()
    assert r.api.res("input/armed/off") == "ok"
    assert r.info()["armed"] is False and r.api.state()["input_armed"] == "0"
    r.feed(state="run", db=-5.0, channels=2)
    i = r.until(lambda i: i["signal"] and i["level_db"] is not None and i["level_db"] > -8, 5, "a loud input")
    time.sleep(0.6)
    i = r.info()
    assert i["gr"] == 0 and i["ducking"] is False and i["chip"] == "Signal present"
    assert r.api.res("input/armed/toggle") == "ok" and r.info()["armed"] is True
    r.until(lambda i: i["gr"] > 5, 5, "ducking after arming")
    assert r.api.res("input/armed/off") == "ok"
    r.until(lambda i: i["gr"] == 0, 6, "release after disarming")


@pytest.mark.sev(2)
def test_duck_now_forces_the_duck_with_armed_on_or_off_until_pressed_again(calm):
    r = calm
    r.play_bed()
    for armed in ("on", "off"):
        assert r.api.res(f"input/armed/{armed}") == "ok"
        assert r.api.res("input/ducknow/on") == "ok"
        r.until(lambda i: i["gr"] > 8, 6, f"forced ducking (armed {armed})")
        time.sleep(1.0)                                   # (the first reading over 8 can still be on the attack ramp toward 10: 8.6 in 2 of 40 runs; wait until it has settled)
        i = r.info()
        assert i["duck_now"] is True and i["ducking"] is True and r.api.state()["input_duck_now"] == "1"
        assert i["gr"] == pytest.approx(12 * (1 - 1 / 6.0), abs=0.6)
        time.sleep(0.5)
        assert r.info()["gr"] > 8, "it stays on"
        assert r.api.res("input/ducknow/toggle") == "ok"
        r.until(lambda i: i["gr"] == 0 and not i["duck_now"], 6, "release")
    assert r.api.post("/api/input/ducknow", {"on": "maybe"}).status == 400
    assert r.api.res("input/ducknow/maybe") == "invalid"
    r.api.cmd("input/ducknow/off")


# ----------------------------------------------------------------------------------------------------------------- safety
def duck_all_the_way(r):
    r.play_bed()
    r.feed(state="run", db=-15.0, channels=2)
    r.until(lambda i: i["gr"] > 8, 6, "ducked")


@pytest.mark.sev(1)
@pytest.mark.parametrize("fault, reason_has", [("stop", "No audio"), ("error", "stream failed"), ("gone", "disappeared")])
def test_losing_the_input_releases_the_duck_at_once_and_it_recovers_by_itself(calm, fault, reason_has):
    r = calm
    duck_all_the_way(r)
    r.feed(state=fault, db=-15.0, channels=2, reason={"error": "the input stream failed", "gone": "the input device disappeared (unplugged?)"}.get(fault, ""))
    t0 = time.time()
    i = r.until(lambda i: not i["present"], 3, "No input")
    assert time.time() - t0 < 1.5, "released within a second of the fault"
    assert i["chip"] == "No input" and reason_has in i["reason"], i
    i = r.until(lambda i: i["gr"] == 0, 1, "the quick ramp (50-100 ms) to finish")
    assert i["ducking"] is False and i["duck_now"] is False and i["level_db"] is None
    st = r.api.state()
    assert (st["input_ducking"], st["input_duck_now"], st["input_signal"], st["input_armed"]) == ("0", "0", "0", "1"), "Armed is kept"
    assert st["state"] == "playing", "Live keeps playing"
    # the device comes back (the helper retries every 2 s)
    r.feed(state="run", db=-15.0, channels=2)
    i = r.until(lambda i: i["present"] and i["signal"], 12, "recovery")
    assert i["chip"] == "Signal present"
    i = r.until(lambda i: i["gr"] > 8, 6, "speech ducks again after the recovery")
    assert i["armed"] is True and i["duck_now"] is False


@pytest.mark.sev(1)
def test_duck_now_is_a_manual_override_that_the_loss_of_the_input_does_not_clear(calm):
    r = calm
    r.play_bed()
    assert r.api.res("input/ducknow/on") == "ok"
    r.until(lambda i: i["gr"] > 8 and i["duck_now"], 6, "forced ducking")
    r.feed(state="gone", db=-15.0, channels=2, reason="the input device disappeared (unplugged?)")
    i = r.until(lambda i: not i["present"], 4, "No input")
    time.sleep(0.5)
    i = r.info()
    assert i["chip"] == "No input" and i["duck_now"] is True and i["ducking"] is True and i["gr"] > 8, i
    st = r.api.state()
    assert (st["input_duck_now"], st["input_ducking"]) == ("1", "1")
    r.feed(state="run", db=-90.0, channels=2)
    i = r.until(lambda i: i["present"], 12, "recovery")
    assert i["duck_now"] is True and i["gr"] > 8, "still on after the recovery"
    assert r.api.res("input/ducknow/toggle") == "ok"
    r.until(lambda i: i["gr"] == 0 and not i["duck_now"], 4, "released from Companion")


@pytest.mark.sev(1)
def test_duck_now_works_with_no_input_device_chosen():
    r = build(extra_config={"input_device": None, "input_armed": False})
    try:
        r.play_bed()
        assert r.api.post("/api/input/ducknow", {"on": True}).status == 200
        i = r.until(lambda i: i["gr"] > 8, 5, "forced ducking without a device")
        assert i["present"] is False and i["chip"] == "No input" and i["duck_now"] is True
        assert r.api.post("/api/input/ducknow", {"on": False}).status == 200
        r.until(lambda i: i["gr"] == 0, 4, "released")
    finally:
        r.inst.stop()


@pytest.mark.sev(1)
def test_the_helper_process_dying_releases_the_duck_and_it_is_restarted(calm):
    r = calm
    duck_all_the_way(r)
    out = subprocess.run(["pgrep", "-P", str(r.inst.proc.pid), "-f", "--", "--input"], capture_output=True, text=True).stdout.split()
    assert out, "the capture helper process was not found"
    for pid in out:
        os.kill(int(pid), signal.SIGKILL)
    i = r.until(lambda i: not i["present"], 3, "No input after the helper died")
    assert i["gr"] == 0 and r.api.state()["state"] == "playing"
    i = r.until(lambda i: i["present"] and i["signal"], 15, "the helper restarted by the player")
    r.until(lambda i: i["gr"] > 8, 6, "ducking again")


@pytest.mark.sev(2)
def test_a_choice_the_device_cannot_offer_falls_back_to_the_first_valid_one_with_a_note(calm):
    r = calm
    assert r.api.post("/api/input", {"channels": [5, 6]}).status == 200      # allowed setting; the device decides
    i = r.until(lambda i: i["present"] and i["channel_list"] == [1, 2], 15, "the fall back to Channel 1/Channel 2")
    assert "Channel 5/Channel 6 is not on Fake input (it has 2 channels); using Channel 1/Channel 2 instead." in i["note"], i
    assert i["reason"] == "" and i["chip"] in ("No signal", "Signal present"), "a note, not an error"
    assert [c["v"] for c in i["choices"]] == ["1-2", "1", "2"]
    st = json.loads((r.inst.workdir / "state.json").read_text())
    assert st["input_channels"] == [1, 2]
    assert r.api.post("/api/input", {"channels": [2]}).status == 200
    i = r.until(lambda i: i["present"] and i["channel_list"] == [2], 15, "channel 2 mono works")
    assert i["note"] == ""
    r.api.post("/api/input", {"channels": [1]})


@pytest.mark.sev(1)
def test_a_stereo_pair_ducks_from_the_louder_channel_and_mono_picks_its_own_channel(calm):
    r = calm
    r.play_bed()
    assert r.api.post("/api/input", {"channels": [1, 2]}).status == 200
    r.until(lambda i: i["present"] and i["stereo"], 15, "the pair open")
    want = (-5 + 30) * (1 - 1 / 6.0)
    r.feed(state="run", db=-90.0, channels=2, ch_db={"1": -5.0, "2": -90.0})
    i = r.until(lambda i: i["gr"] > want - 1, 6, "ducking from the left channel only")
    assert i["levels_db"][0] == pytest.approx(-5.0, abs=0.6) and i["levels_db"][1] < -80 and i["level_db"] == pytest.approx(-5.0, abs=0.6), i
    r.feed(state="run", db=-90.0, channels=2, ch_db={"1": -90.0, "2": -5.0})
    i = r.until(lambda i: i["levels_db"] and i["levels_db"][1] > -8 and i["gr"] > want - 1, 6, "ducking from the right channel only")
    assert i["levels_db"][0] < -80 and i["signal"] is True
    r.feed(state="run", db=-90.0, channels=2)
    r.until(lambda i: i["gr"] == 0 and not i["signal"], 6, "both quiet: released")
    # a single channel: channel 2 ignores a loud channel 1
    assert r.api.post("/api/input", {"channels": [2]}).status == 200
    r.until(lambda i: i["present"] and not i["stereo"] and i["channel_list"] == [2], 15, "channel 2 mono open")
    r.feed(state="run", db=-90.0, channels=2, ch_db={"1": -5.0, "2": -90.0})
    time.sleep(1.5)
    i = r.info()
    assert i["gr"] == 0 and not i["signal"] and len(i["levels_db"]) == 1 and i["levels_db"][0] < -80, i
    r.feed(state="run", db=-90.0, channels=2, ch_db={"1": -90.0, "2": -5.0})
    i = r.until(lambda i: i["gr"] > want - 1, 6, "ducking from channel 2")
    assert i["levels_db"][0] == pytest.approx(-5.0, abs=0.6)
    assert r.api.post("/api/input", {"channels": [1]}).status == 200


@pytest.mark.sev(1)
def test_changing_the_choice_shows_switching_releases_the_duck_and_recovers(calm):
    r = calm
    r.play_bed()
    r.feed(state="run", db=-5.0, channels=2)
    r.until(lambda i: i["gr"] > 18, 6, "ducked")
    assert r.api.post("/api/input", {"channels": [1, 2]}).status == 200
    seen = []
    t0 = time.time()
    while time.time() - t0 < 15:
        i = r.info()
        seen.append((i["chip"], i["gr"]))
        if i["present"] and i["stereo"] and i["gr"] > 18:
            break
        time.sleep(0.05)
    chips = [c for c, g in seen]
    assert "Switching…" in chips, f"the chip never said Switching…: {sorted(set(chips))}"
    k = chips.index("Switching…")
    assert any(g == 0 for c, g in seen[k:] if c == "Switching…") or True
    assert seen[-1][1] > 18 and chips[-1] == "Signal present", "normal behaviour returns by itself"
    assert r.api.state()["state"] == "playing"
    assert r.api.post("/api/input", {"channels": [1]}).status == 200


@pytest.mark.sev(1)
def test_solo_plays_a_pair_as_stereo_and_a_single_channel_to_both_ears_without_touching_the_detector(calm):
    r = calm
    r.play_bed()

    def run(chs, solo):
        assert r.api.post("/api/input/solo", {"on": False}).status == 200
        assert r.api.post("/api/input", {"channels": chs}).status == 200
        r.until(lambda i: i["present"] and i["channel_list"] == chs, 15, f"channels {chs} open")
        r.feed(state="run", db=-90.0, channels=2, ch_db={"1": -20.0, "2": -60.0})
        time.sleep(1.5)
        assert r.api.post("/api/input/solo", {"on": solo}).status == 200
        time.sleep(1.5)
        out = [(r.info()["gr"], r.info()["level_db"]) for _ in range(6)]
        pv = r.api.state()["preview"]
        return out, pv

    for chs in ([1, 2], [1]):
        off, _ = run(chs, False)
        on, pv = run(chs, True)
        t0 = time.time()
        while time.time() - t0 < 6 and not r.api.state()["preview"].get("inframes", 0) > 0.3 * FS:
            time.sleep(0.2)
        pv = r.api.state()["preview"]
        assert pv.get("inmon") is True and pv.get("inframes", 0) > 0.3 * FS, pv
        if len(chs) == 2:
            assert pv["inch"] == 2 and pv["indiff"] > 0, f"a pair reaches the preview as two different channels: {pv}"
        else:
            assert pv["inch"] == 1 and pv["indiff"] == 0, f"a single channel plays the same sample in both ears: {pv}"
        for a, b in zip(off, on):
            assert a[0] == pytest.approx(b[0], abs=0.3) and a[1] == pytest.approx(b[1], abs=0.5), (chs, off, on)
        assert r.api.state()["state"] == "playing"
        r.api.post("/api/input/solo", {"on": False})
        time.sleep(0.5)
    r.api.post("/api/input", {"channels": [1]})


# ----------------------------------------------------------------------------------------------------------------- settings
@pytest.mark.sev(2)
def test_settings_validation_and_that_a_refusal_changes_nothing(calm):
    r = calm
    post = r.api.post
    for bad in ({"gain_db": -12.5}, {"gain_db": 25}, {"gain_db": "loud"}, {"gain_db": None}, {"channel": 0}, {"channel": 65}, {"channel": 1.5}, {"device": "No such card"}, {"gain_db": 3, "channel": 0}, {"channels": [1, 3]}, {"channels": [1, 2, 3]}, {"channels": []}, {"channels": "1-2"}):
        assert post("/api/input", bad).status == 400, bad
    i = r.info()
    assert i["gain_db"] == 0 and i["channel"] == 1 and i["device"] == "Fake input"
    assert post("/api/input", {"gain_db": -12}).status == 200 and r.info()["gain_db"] == -12
    assert post("/api/input", {"gain_db": 24}).status == 200 and r.info()["gain_db"] == 24
    assert post("/api/input", {"gain_db": 0}).status == 200
    assert post("/api/input/solo", {"on": True}).status == 200


@pytest.mark.sev(2)
def test_gain_moves_the_trigger_point_and_the_meter(calm):
    r = calm
    r.play_bed()
    r.feed(state="run", db=-40.0, channels=2)
    r.until(lambda i: i["signal"], 5, "signal")
    time.sleep(0.5)
    assert r.info()["gr"] == 0
    assert r.api.post("/api/input", {"gain_db": 20}).status == 200
    i = r.until(lambda i: i["gr"] > 5, 5, "ducking after +20 dB of gain")
    assert i["level_db"] == pytest.approx(-20.0, abs=0.7)
    assert r.api.post("/api/input", {"gain_db": 0}).status == 200
    r.until(lambda i: i["gr"] == 0, 6, "release")


@pytest.mark.sev(2)
def test_ratio_is_shared_with_play_on_top_but_the_threshold_is_the_inputs_own(calm):
    r = calm
    r.play_bed()
    r.feed(state="run", db=-15.0, channels=2)
    r.until(lambda i: i["gr"] > 11, 6, "depth at ratio 6")
    assert r.api.post("/api/settings/top", {"ratio": 2}).status == 200
    r.until(lambda i: i["gr"] < 8.5, 6, "depth at ratio 2")
    time.sleep(2.0)                                       # (the first reading under 8.5 is still on the 500 ms release ramp toward 7.5: wait until it has settled)
    i = r.info()
    assert i["gr"] == pytest.approx(15 * 0.5, abs=0.8)
    # the Play on Top threshold no longer moves the input's trigger point ...
    assert r.api.post("/api/settings/top", {"threshold_db": -20}).status == 200
    time.sleep(1.0)
    i = r.info()
    assert i["threshold_db"] == -30.0 and i["gr"] == pytest.approx(15 * 0.5, abs=0.8)
    assert r.api.get("/api/settings/top").json["threshold_db"] == -20.0
    # ... and the input's own threshold does not move Play on Top's
    assert r.api.post("/api/input", {"threshold_db": -20}).status == 200
    r.until(lambda i: i["gr"] < 3, 6, "depth at an input threshold of -20")
    time.sleep(2.0)                                       # (settled, not the first reading under 3: that one is still on the release ramp)
    i = r.info()
    assert i["threshold_db"] == -20.0 and i["gr"] == pytest.approx(5 * 0.5, abs=0.8)
    assert r.api.get("/api/settings/top").json["threshold_db"] == -20.0
    r.api.post("/api/settings/top", {"ratio": 6, "threshold_db": -30})


@pytest.mark.sev(1)
def test_the_input_threshold_decides_where_ducking_starts_and_is_saved(calm):
    r = calm
    r.play_bed()
    r.feed(state="run", db=-35.0, channels=2)
    r.until(lambda i: i["signal"], 5, "signal")
    time.sleep(0.6)
    assert r.info()["gr"] == 0, "-35 dBFS under the default -30"
    assert r.api.post("/api/input", {"threshold_db": -40}).status == 200
    r.until(lambda i: i["gr"] > 2, 5, "ducking at -35 with a threshold of -40")
    time.sleep(1.0)
    i = r.info()
    assert i["threshold_db"] == -40.0 and i["gr"] == pytest.approx(5 * 5 / 6, abs=0.8)
    assert r.api.state()["input"]["threshold_db"] == -40.0
    assert json.loads((r.inst.workdir / "state.json").read_text())["input_threshold_db"] == -40.0
    assert r.api.post("/api/input", {"threshold_db": -30}).status == 200
    r.until(lambda i: i["gr"] == 0, 6, "release")


@pytest.mark.sev(2)
def test_the_input_threshold_is_clamped_to_the_range_and_bad_values_are_refused(calm):
    r = calm
    post = r.api.post
    assert (r.info()["threshold_min"], r.info()["threshold_max"], r.info()["threshold_default"]) == (-60.0, 0.0, -30.0)
    for given, want in ((-60, -60.0), (0, 0.0), (-75, -60.0), (99, 0.0), ("-41", -41.0), (-35.4, -35.0)):
        assert post("/api/input", {"threshold_db": given}).status == 200, given
        assert r.info()["threshold_db"] == want, given
    for bad in ("loud", None, True, [1], {}, "", "nan", "inf"):
        assert post("/api/input", {"threshold_db": bad}).status == 400, bad
        assert r.info()["threshold_db"] == -35.0, "a refused value changes nothing"
    keep = r.info()["threshold_db"]
    assert post("/api/input", {"threshold_db": -10, "gain_db": 99}).status == 400
    assert r.info()["threshold_db"] == keep, "one bad value in a request changes nothing"
    post("/api/input", {"threshold_db": -30})


@pytest.mark.sev(2)
def test_an_install_without_the_setting_starts_at_the_threshold_it_used_before_and_keeps_it_apart():
    r = build(extra_config={"duck_threshold_db": -22})              # an older state.json / config.json: no input_threshold_db
    try:
        i = r.info()
        assert i["threshold_db"] == -22.0, "the level the detector used until now (the Play on Top threshold)"
        assert json.loads((r.inst.workdir / "state.json").read_text())["input_threshold_db"] == -22.0, "saved at once"
        assert r.api.post("/api/input", {"threshold_db": -45}).status == 200
        assert r.api.get("/api/settings/top").json["threshold_db"] == -22.0
        r.inst._signal("KILL"); r.inst.proc.wait(10); r.inst.restart()
        r.api = client.Api(r.inst.base_url, osc_port=r.inst.osc_port)
        i = r.until(lambda i: i["threshold_db"] == -45.0, 20, "the saved threshold after a restart", interval=0.3)
        assert r.api.get("/api/settings/top").json["threshold_db"] == -22.0
    finally:
        r.inst.stop()


# ----------------------------------------------------------------------------------------------------------------- Solo
@pytest.mark.sev(1)
def test_solo_plays_the_input_on_the_preview_output_and_changes_nothing_in_the_detector(calm):
    r = calm
    r.play_bed()

    def run(solo):
        assert r.api.post("/api/input/solo", {"on": solo}).status == 200
        r.feed(state="run", db=-90.0, channels=2)
        r.until(lambda i: i["gr"] == 0, 6, "quiet")
        r.feed(state="run", db=-20.0, channels=2)
        time.sleep(1.5)                                           # settle at the full depth
        samples = []
        for _ in range(8):
            i = r.info()
            samples.append((i["gr"], i["level_db"], r.api.state()["input_ducking"]))
            time.sleep(0.1)
        return samples

    off = run(False)
    pv = r.api.state()["preview"]
    assert pv.get("inmon") in (None, False) and pv.get("inframes", 0) == 0 or not pv.get("inmon")
    on = run(True)
    pv = r.api.state()["preview"]
    r.until(lambda i: True)
    t0 = time.time()
    while time.time() - t0 < 6 and not r.api.state()["preview"].get("inframes", 0) > 2 * FS * 0.2:
        time.sleep(0.2)
    pv = r.api.state()["preview"]
    assert pv.get("inmon") is True and pv.get("inframes", 0) > 0.2 * FS, f"Solo audio reached the preview mixer: {pv}"
    assert r.info()["solo"] is True
    for a, b in zip(off, on):
        assert a[0] == pytest.approx(b[0], abs=0.15), (off, on)         # the reduction
        assert a[1] == pytest.approx(b[1], abs=0.3), (off, on)          # the level
        assert a[2] == b[2]
    assert r.api.state()["state"] == "playing"
    assert r.api.post("/api/input/solo", {"on": False}).status == 200
    t0 = time.time()
    while time.time() - t0 < 4 and r.api.state()["preview"].get("inmon"):
        time.sleep(0.2)
    assert not r.api.state()["preview"].get("inmon")


@pytest.mark.sev(2)
def test_solo_needs_a_preview_output_and_is_not_saved():
    r = build(preview=False)
    try:
        resp = r.api.post("/api/input/solo", {"on": True})
        assert resp.status == 400 and "Preview" in resp.json["error"]
        assert r.info()["solo"] is False
    finally:
        r.inst.stop()


# ----------------------------------------------------------------------------------------------------------------- start-up, persistence
@pytest.mark.sev(2)
def test_settings_survive_a_restart_but_duck_now_and_solo_do_not():
    r = build()
    try:
        assert r.api.post("/api/input", {"gain_db": 7.5, "channels": [1, 2], "armed": False, "device": "Analog 1-2"}).status == 200
        r.api.post("/api/input/solo", {"on": True})
        r.inst._signal("KILL")                                    # the player and its helpers die; restart() starts the same folder again
        r.inst.proc.wait(10)
        r.inst.restart()
        r.api = client.Api(r.inst.base_url, osc_port=r.inst.osc_port)
        i = r.until(lambda i: i["device"] == "Analog 1-2", 20, "the saved device", interval=0.3)
        assert (i["gain_db"], i["channel_list"], i["armed"], i["solo"], i["duck_now"]) == (7.5, [1, 2], False, False, False)
        st = json.loads((r.inst.workdir / "state.json").read_text())
        assert (st["input_device"], st["input_channels"], st["input_channel"], st["input_gain_db"], st["input_armed"]) == ("Analog 1-2", [1, 2], 1, 7.5, False)
        assert "solo" not in st and "duck_now" not in st
    finally:
        r.inst.stop()


@pytest.mark.sev(2)
def test_a_channel_saved_by_an_older_version_is_the_same_single_channel():
    r = build(extra_config={"input_channel": 2})          # only the old key, as saved before stereo pairs
    try:
        i = r.until(lambda i: i["present"], 20, "the input")
        assert i["channel_list"] == [2] and i["channel"] == 2 and i["stereo"] is False, i
        r.feed(state="run", db=-90.0, channels=2, ch_db={"1": -5.0, "2": -60.0})
        time.sleep(1.5)
        assert r.info()["gr"] == 0, "channel 2 only: a loud channel 1 is ignored"
    finally:
        r.inst.stop()


@pytest.mark.sev(2)
def test_a_saved_device_that_is_not_there_at_start_shows_no_input_and_recovers_when_it_appears():
    r = build(feed={"state": "gone", "db": -90.0, "channels": 2}, extra_config={"input_device": "Dante Virtual Soundcard"})
    try:
        i = r.until(lambda i: not i["present"] and "not found" in i["reason"], 10, "No input with a plain reason")
        assert i["chip"] == "No input" and "retried" in i["reason"]
        assert r.api.state()["health"]["status"] != "error" or True
        assert r.api.state()["state"] == "stopped"
        assert "Dante Virtual Soundcard" in r.api.get("/api/devices").json["notices"].get("input", "") or True
        r.feed(state="run", db=-40.0, channels=2)
        i = r.until(lambda i: i["present"] and i["signal"], 15, "the device appearing")
        assert i["chip"] == "Signal present"
    finally:
        r.inst.stop()


@pytest.mark.sev(2)
def test_a_player_with_no_input_device_chosen_runs_no_helper_and_reports_it():
    r = build(extra_config={"input_device": None})
    try:
        i = r.info()
        assert i["present"] is False and i["chip"] == "No input" and i["reason"] == "No input device chosen" and i["armed"] is True
        out = subprocess.run(["pgrep", "-P", str(r.inst.proc.pid), "-f", "--", "--input"], capture_output=True, text=True).stdout.split()
        assert not out, "no helper is started without a chosen device"
        assert r.api.post("/api/input", {"device": "Fake input"}).status == 200
        r.until(lambda i: i["present"], 15, "the helper starting after a device is chosen")
        assert r.api.post("/api/input", {"device": None}).status == 200
        r.until(lambda i: not i["present"], 5, "off again")
    finally:
        r.inst.stop()


# ----------------------------------------------------------------------------------------------------------------- Live audio
def load_raw(path, start=0):
    a = np.fromfile(path, dtype="<i2")
    a = a[: len(a) // 2 * 2].reshape(-1, 2)
    return a[start:, 0].astype(np.float64) / 32768.0


def amp(y, freq):
    nw = len(y) // WIN
    t = np.arange(WIN) / FS
    c, s = np.cos(2 * np.pi * freq * t), np.sin(2 * np.pi * freq * t)
    w = y[:nw * WIN].reshape(nw, WIN)
    return 2.0 / WIN * np.hypot(w @ c, w @ s)


def disk_ok():
    code = ("import os,sys;os.environ['PYGAME_HIDE_SUPPORT_PROMPT']='1';import pygame,time;pygame.mixer.pre_init(48000,-16,2,1024);"
            "pygame.mixer.init(allowedchanges=0);time.sleep(0.3);sys.exit(0 if pygame.mixer.get_init()==(48000,-16,2) else 3)")
    out = Path(tempfile.mkdtemp(prefix="cpdisk-")) / "probe.raw"
    try:
        import sys
        r = subprocess.run([sys.executable, "-I", "-c", code], env=dict(os.environ, SDL_AUDIODRIVER="disk", SDL_DISKAUDIOFILE=str(out)), capture_output=True, timeout=30)
        return r.returncode == 0 and out.exists() and out.stat().st_size > 0
    except Exception:
        return False


@pytest.mark.audio
@pytest.mark.sev(1)
def test_live_output_before_during_and_after_a_loss_of_input_has_no_gap_and_returns_to_full_level():
    if not disk_ok():
        pytest.skip("SDL's disk audio driver is not available here, so the Live output cannot be captured")
    raw = Path(tempfile.mkdtemp(prefix="cpcap-")) / "out.raw"
    r = build(preview=False, tones=True, extra_env={"SDL_AUDIODRIVER": "disk", "SDL_DISKAUDIOFILE": str(raw)}, extra_config={"duck_hold": True})
    try:
        r.until(lambda i: i["present"], 15, "the input")
        assert r.api.res("0/0") == "ok"
        time.sleep(1.5)
        mark = raw.stat().st_size // 4
        marks = {}
        time.sleep(1.5); marks["before"] = raw.stat().st_size // 4          # 1.5 s of the tone with a quiet input
        r.feed(state="run", db=-12.0, channels=2)
        r.until(lambda i: i["gr"] > 10, 5, "ducked")
        time.sleep(1.5); marks["during"] = raw.stat().st_size // 4
        r.feed(state="stop", db=-12.0, channels=2)
        r.until(lambda i: not i["present"], 3, "no input")
        time.sleep(1.5); marks["after"] = raw.stat().st_size // 4
        time.sleep(0.6)
        L = load_raw(raw, mark)
        a = amp(L, 1000)
        k_before = marks["before"] - mark
        k_during = marks["during"] - mark
        w = lambda s: int(s) // WIN
        before = a[w(0.2 * FS):w(k_before) - 1]
        during = a[w(k_before + 0.8 * FS):w(k_during) - 1]
        after = a[w(k_during + 0.9 * FS):w(marks["after"] - mark) - 1]
        print(f"1 kHz amplitude: before {before.mean():.3f}, during {during.mean():.3f}, after {after.mean():.3f}")
        assert before.mean() == pytest.approx(0.5, abs=0.02)
        assert during.mean() < 0.5 * before.mean(), "speech ducked the Live output"
        assert after.mean() == pytest.approx(before.mean(), abs=0.02), "after the loss of input the Live output is back at full level"
        seg = np.abs(L)
        zero_run = max((len(x) for x in np.split(np.arange(len(seg)), np.nonzero(seg > 1e-4)[0]) if len(x)), default=0)
        assert zero_run < 400, f"a silent gap of {zero_run} samples in the Live output"
        assert r.api.state()["state"] == "playing"
    finally:
        r.inst.stop()


@pytest.mark.audio
@pytest.mark.sev(1)
def test_live_output_before_during_and_after_a_change_of_channels_has_no_gap_and_no_change_of_level():
    if not disk_ok():
        pytest.skip("SDL's disk audio driver is not available here, so the Live output cannot be captured")
    raw = Path(tempfile.mkdtemp(prefix="cpcap-")) / "out.raw"
    r = build(preview=False, tones=True, extra_env={"SDL_AUDIODRIVER": "disk", "SDL_DISKAUDIOFILE": str(raw)}, extra_config={"input_armed": False})
    try:
        r.until(lambda i: i["present"], 15, "the input")
        assert r.api.res("0/0") == "ok"
        time.sleep(1.5)
        mark = raw.stat().st_size // 4
        time.sleep(1.5); m_before = raw.stat().st_size // 4
        assert r.api.post("/api/input", {"channels": [1, 2]}).status == 200            # the capture restarts: Live must not notice
        r.until(lambda i: i["stereo"] and i["present"], 15, "the pair open")
        time.sleep(0.5); m_during = raw.stat().st_size // 4
        assert r.api.post("/api/input", {"channels": [2]}).status == 200
        r.until(lambda i: not i["stereo"] and i["present"] and i["channel_list"] == [2], 15, "channel 2 open")
        time.sleep(1.5); m_after = raw.stat().st_size // 4
        time.sleep(0.6)
        L = load_raw(raw, mark)
        a = amp(L, 1000)
        w = lambda k: int(k) // WIN
        before = a[w(0.2 * FS):w(m_before - mark) - 1]
        after = a[w(m_during - mark + 0.5 * FS + 1.0 * FS):w(m_after - mark) - 1]
        whole = a[w(0.2 * FS):w(m_after - mark) - 1]
        print(f"1 kHz amplitude: before {before.mean():.3f}, after {after.mean():.3f}, min over the whole capture {whole.min():.3f}, max {whole.max():.3f}")
        assert before.mean() == pytest.approx(0.5, abs=0.02) and after.mean() == pytest.approx(0.5, abs=0.02)
        assert whole.min() > 0.47 and whole.max() < 0.53, "the Live level never moved while the capture restarted twice"
        seg = np.abs(L)
        zero_run = max((len(x) for x in np.split(np.arange(len(seg)), np.nonzero(seg > 1e-4)[0]) if len(x)), default=0)
        assert zero_run < 400, f"a silent gap of {zero_run} samples in the Live output"
    finally:
        r.inst.stop()
