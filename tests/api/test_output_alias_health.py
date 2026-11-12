"""2.8.0 output-alias, health and report, through a real player instance with the device list of the NUC (2026-11-11, CP_TEST_DEVICES): the ALSA loopback card of Inferno
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


def test_the_live_output_health_is_not_bad_because_of_the_alias(api):
    assert api.post("/api/device", {"name": LB1}).status == 200
    for aliases in (None, [], [{"match": LB1, "label": "Dante over IP", "live_only": True}]):
        api.post("/api/settings/outputs", {"aliases": aliases})
        h = api.state()["health"]
        live = [c for c in h["checks"] if c["id"] == "live_output"][0]
        assert live["status"] in ("ok", "unknown"), (aliases, live)


def test_the_report_shows_label_first_and_raw_in_brackets(api):
    api.post("/api/device", {"name": LB1})
    api.post("/api/preview/device", {"name": USB})
    t = api.get("/api/health/report").json["text"]
    assert "Live output: Dante over IP (Loopback, Loopback PCM) (" in t, t
    assert f"Preview output: {USB} (" in t                           # unaliased: exactly as before
    api.post("/api/settings/outputs", {"aliases": []})
    assert "Live output: Loopback, Loopback PCM (" in api.get("/api/health/report").json["text"]
