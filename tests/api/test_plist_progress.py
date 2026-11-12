"""Playlist progress data (2.7.3 Phase 3): /api/playlists tracks have dur_eff (seconds of one pass: the A-to-B window, the whole file without a trim,
null while the length is unknown); shuffle playlists have shuffle_left (ids still to come in the round, read-only). Web page only."""
import pytest

from harness import client
from harness.instance import Instance

pytestmark = pytest.mark.noreset


@pytest.fixture()
def pinst(request):
    inst = Instance(project_dir=request.config.getoption("--project"), wav_only=True)
    inst.start()
    api = client.Api(inst.base_url, osc_port=inst.osc_port)
    api.post("/api/playlists", {"name": "P"})
    api.post("/api/playlists/0/add", {"files": ["tone_a.wav", "tone_b.wav", "tone_c.wav", "short_1s.wav"]})     # 3, 3, 4, 1 s
    yield inst, api
    inst.stop()


def effs(api, p=0):
    return [t["dur_eff"] for t in api.get("/api/playlists").json[p]["tracks"]]


def test_dur_eff_is_the_window_a_to_b(pinst):
    inst, api = pinst
    api.wait_for(lambda s: None not in effs(api), 20, desc="durations known")
    assert effs(api) == [3.0, 3.0, 4.0, 1.0]
    api.post("/api/playlists/0/trim", {"track": 0, "in": 0.5, "out": 2.5})
    api.post("/api/playlists/0/trim", {"track": 2, "in": 1.0})                  # only A
    api.post("/api/playlists/0/trim", {"track": 1, "out": 1.5})                 # only B
    assert effs(api) == [2.0, 1.5, 3.0, 1.0]
    api.post("/api/playlists/0/trim", {"track": 0, "clear": True})
    assert effs(api)[0] == 3.0, "removing the trim gives the whole file back"


def test_shuffle_left_only_in_shuffle_and_read_only(pinst):
    inst, api = pinst
    assert api.get("/api/playlists").json[0]["shuffle_left"] is None
    api.cmd("0/mode/shuffle")
    pl = api.get("/api/playlists").json[0]
    assert pl["shuffle_left"] == []                                              # no round started yet
    api.cmd("0/play")                                                            # starts a round: one track is taken out of the bag
    api.wait_for(lambda s: s["live_id"] != "-", 10, desc="playing")
    left = api.get("/api/playlists").json[0]["shuffle_left"]
    assert len(left) == 3 and len(set(left)) == 3 and set(left) <= {"tone_a.wav", "tone_b.wav", "tone_c.wav", "short_1s.wav"}
    assert api.get("/api/playlists").json[0]["shuffle_left"] == left, "reading does not draw from the bag"
