"""2.8.0 output-alias through a real player instance with the device list of the NUC (2026-11-11, CP_TEST_DEVICES): the ALSA loopback card of Inferno
(Dante over IP) is listed twice, "Loopback, Loopback PCM" and "... (2)". The first is shown as "Dante over IP", the second is hidden, the saved outputs stay the
raw SDL names, and the health result for the Live output never turns bad because of an alias. SIMULATED: the device list (and a dummy audio driver);
NOT covered, needs the NUC: whether a real second open of the busy loopback device fails (see the report)."""
import json, tempfile
from pathlib import Path

import pytest

from harness import client
from harness.instance import Instance

pytestmark = [pytest.mark.noreset]
NUC = ["Dante USB I/O Module, USB Audio", "HDA Intel PCH, ALC233 Analog", "HDA Intel PCH, ALC233 Digital", "HDA Intel PCH, HDMI 0", "HDA Intel PCH, HDMI 1",
       "HDA Intel PCH, HDMI 2", "Loopback, Loopback PCM", "Loopback, Loopback PCM (2)"]
LB1, LB2, USB = NUC[6], NUC[7], NUC[0]
REFUSAL = "Only one program can use Dante over IP. Use it for Live."


@pytest.fixture(scope="module")
def rig():
    d = Path(tempfile.mkdtemp(prefix="cpalias-"))
    (d / "mock_devices.json").write_text(json.dumps(NUC))
    inst = Instance(wav_only=True, extra_env={"CP_TEST_DEVICES": str(d)})
    inst.start()
    api = client.Api(inst.base_url, osc_port=inst.osc_port)
    yield inst, api
    inst.stop()


@pytest.fixture()
def api(rig):
    inst, a = rig
    a.post("/api/settings/outputs", {"aliases": None})
    a.post("/api/device", {"name": None})
    a.post("/api/preview/device", {"name": None})
    a.post("/api/mirror/device", {"name": None})
    return a


def saved(inst):
    return json.loads((inst.workdir / "state.json").read_text())


def info(api):
    return {e["name"]: e for e in api.get("/api/devices").json["output_info"]}


def test_nothing_saved_the_default_applies_and_the_list_is_unchanged(api):
    d = api.get("/api/devices").json
    assert d["devices"] == NUC                                    # the names and their order exactly as before
    i = info(api)
    assert list(i) == NUC
    assert i[LB1]["label"] == "Dante over IP" and i[LB1]["group"] == "Network audio" and i[LB1]["live_only"] and not i[LB1]["hidden"]
    assert i[LB2]["hidden"] and i[LB2]["label"] == LB2
    assert all(i[n] == {"name": n, "label": n, "hidden": False, "group": "", "live_only": False} for n in NUC[:6])
    s = api.get("/api/settings/outputs").json
    assert s["using_default"] is True and [a["match"] for a in s["aliases"]] == [LB1, LB2]


def test_live_can_use_the_aliased_output_and_the_saved_name_stays_raw(rig, api):
    inst, _ = rig
    assert api.post("/api/device", {"name": LB1}).status == 200
    assert api.get("/api/devices").json["current"] == LB1
    assert saved(inst)["audio_device"] == LB1
    # switching aliases off and on never changes what is saved
    assert api.post("/api/settings/outputs", {"aliases": []}).status == 200
    assert saved(inst)["audio_device"] == LB1 and api.get("/api/devices").json["current"] == LB1
    assert info(api)[LB1]["label"] == LB1
    assert api.post("/api/settings/outputs", {"aliases": None}).status == 200
    assert saved(inst)["audio_device"] == LB1 and info(api)[LB1]["label"] == "Dante over IP"


def test_the_companion_output_variable_is_the_raw_name(api):
    api.post("/api/device", {"name": LB1})
    out = {x["name"]: x["value"] for x in api.get("/api/variables").json["vars"]}["output"]
    assert out == LB1
    api.post("/api/settings/outputs", {"aliases": []})
    assert {x["name"]: x["value"] for x in api.get("/api/variables").json["vars"]}["output"] == LB1


def test_a_saved_table_replaces_the_default(rig, api):
    inst, _ = rig
    r = api.post("/api/settings/outputs", {"aliases": [{"match": USB, "label": "Main PA", "group": "Dante", "hidden": False}]})
    assert r.status == 200 and r.json["using_default"] is False
    i = info(api)
    assert i[USB]["label"] == "Main PA" and i[USB]["group"] == "Dante"
    assert i[LB1]["label"] == LB1 and not i[LB2]["hidden"] and not i[LB1]["live_only"]
    assert saved(inst)["output_aliases"][0]["match"] == USB
    # a restart reads the table back
    inst.restart()
    assert info(api)[USB]["label"] == "Main PA"
    api.post("/api/settings/outputs", {"aliases": None})
    assert saved(inst)["output_aliases"] is None


def test_a_bad_table_is_refused_whole_and_the_old_one_stays(api):
    good = [{"match": USB, "label": "Main PA"}]
    assert api.post("/api/settings/outputs", {"aliases": good}).status == 200
    for bad in ("text", [5], [{"label": "no match"}], [{"match": "a", "hidden": "yes"}], [{"match": "a"}, {"match": "a"}],
                [{"match": "x" * 81}], [{"match": str(i)} for i in range(33)], [good[0], {"match": LB1, "label": 7}]):
        r = api.post("/api/settings/outputs", {"aliases": bad})
        assert r.status == 400 and r.json["ok"] is False and r.json["error"], bad
        assert [a["match"] for a in api.get("/api/settings/outputs").json["aliases"]] == [USB]
    assert api.post("/api/settings/outputs", {}).status == 400
    assert info(api)[USB]["label"] == "Main PA"


def test_an_alias_for_a_device_that_is_not_present_does_nothing_and_is_kept(api):
    api.post("/api/settings/outputs", {"aliases": [{"match": "Not here", "label": "Ghost", "hidden": True, "live_only": True}]})
    assert api.get("/api/devices").json["devices"] == NUC
    assert all(not e["hidden"] and e["label"] == e["name"] for e in info(api).values())
    assert api.get("/api/settings/outputs").json["aliases"][0]["match"] == "Not here"


def test_live_only_is_refused_for_preview_and_mirror_but_not_live(api):
    for route in ("/api/preview/device", "/api/mirror/device"):
        r = api.post(route, {"name": LB1})
        assert r.status == 400 and r.json["error"] == REFUSAL, route
    d = api.get("/api/devices").json
    assert d["preview"] is None and d["mirror"] is None             # nothing was saved
    assert api.post("/api/preview/device", {"name": USB}).status == 200
    assert api.post("/api/mirror/device", {"name": LB2}).status == 200      # the hidden one is only hidden, not refused (the far end is not marked live-only)
    assert api.post("/api/device", {"name": LB1}).status == 200
    # an unknown name is still the old plain error
    assert api.post("/api/preview/device", {"name": "nope"}).json["error"] == "unknown device"
    # with the flag off the same output is accepted
    api.post("/api/settings/outputs", {"aliases": []})
    assert api.post("/api/preview/device", {"name": LB1}).status == 200


def test_device_next_never_lands_on_the_hidden_output(api):
    api.post("/api/device", {"name": NUC[5]})
    assert api.res("device/next") == "ok"
    assert api.get("/api/devices").json["current"] == LB1
    assert api.res("device/next") == "ok"
    assert api.get("/api/devices").json["current"] is None          # the system default, not the hidden "(2)"
    assert api.res("device/5") == "ok"                               # a number still means the position in the full list
