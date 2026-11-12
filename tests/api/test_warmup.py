"""Black box: after a start the warm-up decodes the playlists (docs/split-plan.md 4.6 / hooks F2). The player is started with a saved playlist and
nothing else; the number of decoded tracks in /api/state (mem.cache_tracks) must rise to cover the playlist, and so must it after a playlist edit
through the API. If the on_change hook were not registered, an edit would not warm the new track and the first Go on it would wait for a decode."""
import time
import pytest

from harness import client
from harness.instance import Instance

pytestmark = pytest.mark.noreset
IDS = ["tone_a.wav", "tone_b.wav", "tone_c.wav", "short_1s.wav", "loud.wav"]


@pytest.fixture()
def winst(request):
    inst = Instance(project_dir=request.config.getoption("--project"), wav_only=True)
    inst.start()
    api = client.Api(inst.base_url, osc_port=inst.osc_port)
    api.post("/api/playlists", {"name": "W"})
    assert api.post("/api/playlists/0/add", {"files": IDS[:4]}).status == 200
    yield inst, api
    inst.stop()


def decoded(api):
    return api.state()["mem"]["cache_tracks"]


def test_a_restart_warms_the_whole_playlist(winst):
    inst, api = winst
    api.wait_for(lambda s: s["mem"]["cache_tracks"] >= 4, 20, desc="the first warm-up")
    inst._signal("KILL")
    inst.proc.wait(10)
    inst.restart()                                                          # a cold start: the cache is empty, playlists.json has the four tracks
    t0 = time.time()
    api.wait_for(lambda s: s["mem"]["cache_tracks"] >= 4, 20, desc="every track of the playlist decoded after the start")
    assert time.time() - t0 < 20


def test_a_playlist_edit_warms_the_added_track(winst):
    inst, api = winst
    api.wait_for(lambda s: s["mem"]["cache_tracks"] >= 4, 20, desc="the first warm-up")
    assert api.post("/api/playlists/0/add", {"files": [IDS[4]]}).status == 200
    api.wait_for(lambda s: s["mem"]["cache_tracks"] >= 5, 20, desc="the added track decoded by the warm-up that the edit started")
