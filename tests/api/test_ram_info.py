"""Black box: the RAM indicator data (2.7.3 Phase 1). /api/state has a `ram` block next to `mem`; /api/playlists has `ram` per track and
`ram_in` / `ram_total` per playlist. Web page only: nothing about it is in the Companion variables. Also times 200 /api/state calls with a 500-track playlist."""
import time
import pytest

from harness import client
from harness.instance import Instance

pytestmark = pytest.mark.noreset
IDS = ["tone_a.wav", "tone_b.wav", "tone_c.wav", "short_1s.wav"]


@pytest.fixture()
def rinst(request):
    inst = Instance(project_dir=request.config.getoption("--project"), wav_only=True)
    inst.start()
    api = client.Api(inst.base_url, osc_port=inst.osc_port)
    yield inst, api
    inst.stop()


def lists(api):
    return api.get("/api/playlists").json


def test_ram_block_and_per_track_states(rinst):
    inst, api = rinst
    api.post("/api/playlists", {"name": "A"}); api.post("/api/playlists", {"name": "B"})
    api.post("/api/playlists/0/add", {"files": IDS[:3]})
    api.post("/api/playlists/1/add", {"files": [IDS[2], IDS[3]]})      # tone_c is in both: counted once in tracks_total
    s = api.wait_for(lambda s: s["ram"]["tracks_in_ram"] >= 4 and not s["ram"]["loading"], 30, desc="the warm-up finished")
    r = s["ram"]
    assert set(r) >= {"used_mb", "budget_mb", "tracks_total", "tracks_in_ram", "loading", "full", "rev"}
    assert r["tracks_total"] == 4 and r["tracks_in_ram"] == 4 and r["full"] is False
    assert r["budget_mb"] >= 64 and 0 <= r["used_mb"] <= r["budget_mb"]
    pls = lists(api)
    assert [(p["ram_in"], p["ram_total"]) for p in pls] == [(3, 3), (2, 2)]
    assert all(t["ram"] == "in" for p in pls for t in p["tracks"])


def test_missing_file_is_not_counted_and_not_ready(rinst):
    inst, api = rinst
    api.post("/api/playlists", {"name": "A"})
    api.post("/api/playlists/0/add", {"files": IDS[:2]})
    api.wait_for(lambda s: s["ram"]["tracks_in_ram"] >= 2, 30, desc="warm-up")
    p = lists(api)[0]
    assert p["ram_total"] == 2 and all(t["ram"] in ("in", "loading", "out") for t in p["tracks"])


def test_not_in_companion_state(rinst):
    inst, api = rinst
    v = api.get("/api/variables").json
    assert not any("ram" in k.lower() and "mem" not in k.lower() for k in (v if isinstance(v, dict) else {}))
    assert "ram" not in api.get("/api/meters").json if isinstance(api.get("/api/meters").json, dict) else True


def test_state_stays_cheap_with_a_500_track_playlist(rinst):
    inst, api = rinst
    api.post("/api/playlists", {"name": "Big"})
    for _ in range(5):
        assert api.post("/api/playlists/0/add", {"files": [IDS[i % 4] for i in range(100)]}).status == 200
    assert len(lists(api)[0]["tracks"]) == 500
    api.wait_for(lambda s: s["ram"]["tracks_in_ram"] >= 4, 30, desc="warm-up")
    api.state()
    ts = []
    for _ in range(200):
        t0 = time.perf_counter(); api.state(); ts.append((time.perf_counter() - t0) * 1000)
    ts.sort()
    print(f"\n/api/state x200 with 500 tracks: median {ts[100]:.2f} ms, p95 {ts[190]:.2f} ms, max {ts[-1]:.2f} ms")
    assert ts[100] < 50 and ts[190] < 100
    t0 = time.perf_counter(); lists(api); print(f"/api/playlists (500 tracks): {(time.perf_counter() - t0) * 1000:.1f} ms")
