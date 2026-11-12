"""Trigger points: API validation and firing."""
import time
import pytest


def trg(api, p=0, t=2):
    return api.get(f"/api/playlists/{p}/triggers", track=t).json["triggers"]


@pytest.mark.sev(2)
@pytest.mark.covers("http.POST /api/playlists/{p}/triggers", "http.GET /api/playlists/{p}/triggers")
def test_trigger_add_update_delete_set(std):
    api = std
    r = api.post("/api/playlists/0/triggers", {"track": 2, "action": "add", "at": 2.5, "file": "short_1s.wav"})
    assert r.status == 200 and r.json["triggers"][0]["at"] == 2.5 and r.json["triggers"][0]["enabled"] is True and r.json["triggers"][0]["once"] is False
    a = r.json["triggers"][0]["id"]
    api.post("/api/playlists/0/triggers", {"track": 2, "action": "add", "at": 1, "file": "short_2s.wav", "once": True})
    lst = trg(api)
    assert [x["at"] for x in lst] == [1.0, 2.5], "sorted by time"
    assert lst[0]["once"] is True and lst[0]["name"] == "short_2s" and lst[0]["missing"] is False
    r = api.post("/api/playlists/0/triggers", {"track": 2, "action": "update", "id": a, "enabled": False, "at": 3})
    assert r.status == 200
    x = [t for t in trg(api) if t["id"] == a][0]
    assert x["enabled"] is False and x["at"] == 3.0 and x["file"] == "short_1s.wav"
    assert api.get("/api/playlists/0/triggers").json["tracks"]["2"]
    assert api.get("/api/triggers").json["ok"] is True
    r = api.post("/api/playlists/0/triggers", {"track": 2, "action": "delete", "id": a})
    assert r.status == 200 and len(trg(api)) == 1
    r = api.post("/api/playlists/0/triggers", {"track": 2, "action": "set", "triggers": [{"at": 0.5, "file": "tone_a.wav"}, {"at": 0.2, "file": "tone_b.wav"}]})
    assert [x["at"] for x in r.json["triggers"]] == [0.2, 0.5]
    assert api.post("/api/playlists/0/triggers", {"track": 2, "action": "set", "triggers": []}).json["triggers"] == []
    assert api.get("/api/playlists/0/triggers").json["tracks"] == {}


@pytest.mark.sev(2)
@pytest.mark.covers("http.POST /api/playlists/{p}/triggers")
@pytest.mark.parametrize("bad", [{"action": "add", "at": -1, "file": "short_1s.wav"}, {"action": "add", "at": 99, "file": "short_1s.wav"},
                                 {"action": "add", "at": 90000, "file": "short_1s.wav"}, {"action": "add", "at": "abc", "file": "short_1s.wav"},
                                 {"action": "add", "at": "nan", "file": "short_1s.wav"}, {"action": "add", "at": 1, "file": "nope.wav"},
                                 {"action": "add", "at": 1, "file": "../player.py"}, {"action": "add", "at": 1}, {"action": "add", "file": "short_1s.wav"},
                                 {"action": "update", "id": "zzz", "at": 1}, {"action": "delete", "id": "zzz"}, {"action": "bogus"}, {},
                                 {"action": "set", "triggers": "x"}, {"action": "set", "triggers": [5]}, {"action": "set", "triggers": [{"at": 1}]},
                                 {"track": 9, "action": "add", "at": 1, "file": "short_1s.wav"}])
def test_trigger_rejects_bad_input(std, bad):
    api = std
    body = {"track": 2, **bad}
    r = api.post("/api/playlists/0/triggers", body)
    assert r.status == 400 and r.json["ok"] is False and r.json["error"], (bad, r.status, r.text[:120])
    assert trg(api) == []


@pytest.mark.sev(2)
@pytest.mark.covers("http.POST /api/playlists/{p}/triggers")
def test_trigger_count_limit(std):
    api = std
    n = 0
    for k in range(60):
        r = api.post("/api/playlists/0/triggers", {"track": 2, "action": "add", "at": 0.1 * (k % 30), "file": "short_1s.wav"})
        if r.status != 200:
            break
        n += 1
    assert r.status == 400 and 8 <= n < 60, f"accepted {n} triggers, last status {r.status}"


@pytest.mark.sev(2)
@pytest.mark.covers("http.GET /api/playlists/{p}/triggers")
def test_trigger_get_errors(std):
    api = std
    assert api.get("/api/playlists/9/triggers").status == 404
    assert api.get("/api/playlists/0/triggers", track="x").status == 400
    assert api.get("/api/playlists/0/triggers", track="99").status == 400


@pytest.mark.sev(1)
@pytest.mark.covers("http.POST /api/triggers/arm", "http.POST /api/triggers/skip", "http.GET /api/triggers")
def test_trigger_fires_on_top_at_its_time_and_can_be_disarmed_or_skipped(std):
    api = std
    api.post("/api/playlists/0/triggers", {"track": 2, "action": "add", "at": 1.0, "file": "short_2s.wav"})
    api.cmd("0/2")
    api.wait_playing("0/2")
    s = api.wait_for(lambda s: s["next_trigger"], 3, desc="next_trigger to be reported")
    assert s["triggers_armed"] is True
    api.wait_for(lambda s: s["on_top"] == "1", 4, desc="the trigger to play its track on top")
    api.wait_for(lambda s: s["on_top"] == "0", 4, desc="it to end")
    api.cmd("stop")
    # disarmed: nothing fires
    assert api.post("/api/triggers/arm", {"armed": False}).json["triggers_armed"] is False
    api.cmd("0/2")
    api.wait_playing("0/2")
    time.sleep(2.0)
    assert api.state()["on_top"] == "0"
    api.cmd("stop")
    assert api.post("/api/triggers/arm", {}).json["triggers_armed"] is True, "no body toggles"
    # skipped: the next trigger is skipped for this pass
    api.cmd("0/2")
    api.wait_playing("0/2")
    api.wait_for(lambda s: s["next_trigger"], 3, desc="next_trigger to be reported")
    r = api.post("/api/triggers/skip")
    assert r.status == 200 and r.json["skipped"], r.text[:150]
    time.sleep(2.0)
    assert api.state()["on_top"] == "0"
    api.cmd("stop")
    api.wait_state("stopped")
    assert api.post("/api/triggers/skip").status == 409, "nothing to skip while stopped"


@pytest.mark.sev(2)
@pytest.mark.covers("http.POST /api/triggers/arm")
def test_trigger_arm_bad_values(api):
    r = api.post("/api/triggers/arm", {"armed": "maybe"})
    assert r.status < 500
    assert api.post("/api/triggers/arm", {"armed": True}).json["triggers_armed"] is True
