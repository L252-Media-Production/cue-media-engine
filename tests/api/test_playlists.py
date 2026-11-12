"""Playlist CRUD, track add/remove/move, and robustness of the {p}/{t} endpoints."""
import json, time
import pytest
from conftest import make_playlist


def names(api):
    return [p["name"] for p in api.playlists()]


def ids(api, p):
    return [t["id"] for t in api.playlists()[p]["tracks"]]


@pytest.mark.sev(2)
@pytest.mark.covers("http.POST /api/playlists")
def test_create_playlist(api):
    r = api.post("/api/playlists", {"name": "  My list  "})
    assert r.status == 200 and r.json["ok"]
    assert names(api) == ["My list"]
    api.post("/api/playlists", {"name": ""})
    api.post("/api/playlists", {})
    api.post("/api/playlists", raw="not json")
    assert names(api) == ["My list", "Playlist", "Playlist", "Playlist"]
    assert api.get("/api/variables").json["vars"]
    v = {x["name"]: x["value"] for x in api.get("/api/variables").json["vars"]}
    assert v["pl0_name"] == "My list" and v["pl3_count"] == "0"


@pytest.mark.sev(3)
@pytest.mark.covers("http.POST /api/playlists")
def test_create_playlist_name_length_is_limited_like_rename(api):
    api.post("/api/playlists", {"name": "x" * 5000})
    assert len(names(api)[0]) <= 80, f"a {len(names(api)[0])} character name was accepted (rename limits it to 80)"


@pytest.mark.sev(2)
@pytest.mark.covers("http.POST /api/playlists/{p}/rename")
def test_rename_playlist(api, std):
    r = api.post("/api/playlists/1/rename", {"name": "  Show   two  "})
    assert r.status == 200 and names(api)[1] == "Show two"
    api.post("/api/playlists/1/rename", {"name": "y" * 200})
    assert len(names(api)[1]) == 80
    for body in ({"name": ""}, {"name": "   "}, {}):
        assert api.post("/api/playlists/1/rename", body).status == 400
    assert api.post("/api/playlists/9/rename", {"name": "z"}).status == 400
    assert api.post("/api/playlists/-1/rename", {"name": "z"}).status == 400
    assert names(api)[1] == "y" * 80
    assert api.get("/api/variables").json  # still serving


@pytest.mark.sev(2)
@pytest.mark.covers("http.POST /api/playlists/reorder")
def test_reorder_playlists_and_focus_follows(std):
    api = std
    api.post("/api/playlists", {"name": "C"})
    api.cmd("0/2/focus")
    assert api.post("/api/playlists/reorder", {"from": 0, "to": 2}).status == 200
    assert names(api) == ["B", "C", "A"]
    assert api.state()["focus_id"] == "2/2", "the cue must follow the playlist it was in"
    api.cmd("2/1")
    api.wait_playing("2/1")
    api.post("/api/playlists/reorder", {"from": 2, "to": 0})
    assert names(api) == ["A", "B", "C"]
    assert api.state()["live_id"] == "0/1", "the live track must follow its playlist"
    assert api.post("/api/playlists/reorder", {"from": 1, "to": 1}).status == 200
    for bad in ({"from": 0, "to": 9}, {"from": -1, "to": 0}, {"from": "a", "to": 0}, {"from": 0}, {}):
        assert api.post("/api/playlists/reorder", bad).status == 400, bad
    assert names(api) == ["A", "B", "C"]


@pytest.mark.sev(2)
@pytest.mark.covers("http.DELETE /api/playlists/{p}")
def test_delete_playlist(std):
    api = std
    assert api.delete("/api/playlists/0").status == 200
    assert names(api) == ["B"]
    assert api.state()["focus_id"] == "0/0"
    assert api.delete("/api/playlists/7").status == 200 and names(api) == ["B"]
    assert api.delete("/api/playlists/-1").status in (200, 400, 404)
    assert names(api) == ["B"]


@pytest.mark.sev(1)
@pytest.mark.covers("http.DELETE /api/playlists/{p}")
def test_deleting_the_playlist_of_the_live_track_keeps_the_audio_going(std):
    api = std
    api.cmd("1/2")
    api.wait_playing("1/2")
    api.delete("/api/playlists/1")
    time.sleep(0.4)
    s = api.state()
    assert s["state"] == "playing", s
    assert s["live_id"] == "-"
    assert api.res("stop") == "ok"
    api.wait_state("stopped")


@pytest.mark.sev(2)
@pytest.mark.covers("http.POST /api/playlists/{p}/add")
def test_add_tracks(api):
    p = make_playlist(api, "L", [])
    assert api.post(f"/api/playlists/{p}/add", {"files": ["tone_a.wav", "tone_b.wav"]}).status == 200
    assert ids(api, p) == ["tone_a.wav", "tone_b.wav"]
    api.post(f"/api/playlists/{p}/add", {"files": ["tone_c.wav"], "index": 1})
    assert ids(api, p) == ["tone_a.wav", "tone_c.wav", "tone_b.wav"]
    api.post(f"/api/playlists/{p}/add", {"files": ["tone_a.wav"], "index": 0})
    assert ids(api, p)[:2] == ["tone_a.wav", "tone_a.wav"], "the same file twice is allowed"
    api.post(f"/api/playlists/{p}/add", {"files": ["Sub/tone_d.wav"], "index": 999})
    assert ids(api, p)[-1] == "Sub/tone_d.wav"
    api.post(f"/api/playlists/{p}/add", {"files": ["short_1s.wav"], "index": -5})
    assert ids(api, p)[0] == "short_1s.wav"
    r = api.post(f"/api/playlists/{p}/add", {"files": ["nope.wav", "tone_b.wav"]})
    assert r.status == 200 and ids(api, p).count("tone_b.wav") == 2, "unknown files are skipped, known ones added"
    n = len(ids(api, p))
    for bad in ({"files": ["nope.wav"]}, {"files": []}, {}, {"files": ["../player.py"]}):
        assert api.post(f"/api/playlists/{p}/add", bad).status == 400, bad
    assert len(ids(api, p)) == n
    assert api.post("/api/playlists/9/add", {"files": ["tone_a.wav"]}).status == 400


@pytest.mark.sev(1)
@pytest.mark.covers("http.POST /api/playlists/{p}/add")
def test_adding_before_the_live_track_keeps_the_live_id_in_step(std):
    api = std
    api.cmd("0/1")
    api.wait_playing("0/1")
    api.post("/api/playlists/0/add", {"files": ["short_1s.wav"], "index": 0})
    assert api.state()["live_id"] == "0/2", "the live track moved down one place"
    assert api.state()["live_name"] == "tone_b"


@pytest.mark.sev(3)
@pytest.mark.parametrize("path,body", [("/api/playlists/0/add", {"files": None}), ("/api/playlists/0/add", {"files": 5}),
                                       ("/api/playlists/0/add", {"files": "tone_a.wav"}), ("/api/playlists/0/add", {"files": ["tone_a.wav"], "index": "x"}),
                                       ("/api/playlists/0/add", {"files": ["tone_a.wav"], "index": None}), ("/api/playlists/reorder", None),
                                       ("/api/move", {"from": [0], "to": [0, 0]}), ("/api/move", {"from": 5, "to": [0, 0]}),
                                       ("/api/move", {"from": [0, 0], "to": ["a", "b"]}), ("/api/playlists/0/trim", {"track": None}),
                                       ("/api/playlists/0/trim", {"track": 0, "in": "abc"}), ("/api/playlists/0/trim", {"track": 0, "in": [1]}),
                                       ("/api/playlists/0/norm", {"mode": {"a": 1}}), ("/api/playlists/0/norm", {"ref": []}),
                                       ("/api/playlists/0/norm", {"lufs": "x"}), ("/api/playlists/0/triggers", {"track": 0, "action": "add", "at": "x", "file": "tone_a.wav"})])
def test_malformed_bodies_never_cause_a_server_error(std, path, body):
    api = std
    r = api.post(path, body) if body is not None else api.request("POST", path, raw="[1,2")
    assert r.status < 500, f"{path} {body} -> HTTP {r.status} {r.text[:120]}"
    assert api.state()["state"] == "stopped"


@pytest.mark.sev(3)
@pytest.mark.parametrize("method,path", [("POST", "/api/playlists/abc/rename"), ("POST", "/api/playlists/abc/trim"), ("POST", "/api/playlists/abc/norm"),
                                         ("POST", "/api/playlists/abc/add"), ("DELETE", "/api/playlists/abc"), ("DELETE", "/api/playlists/abc/def"),
                                         ("DELETE", "/api/playlists/0/def"), ("GET", "/api/playlists/abc/triggers"), ("POST", "/api/playlists/abc/triggers"),
                                         ("POST", "/api/playlists/1.5/rename"), ("DELETE", "/api/playlists/99999999999999999999")])
def test_non_numeric_playlist_id_in_the_url_is_a_client_error(std, method, path):
    r = std.request(method, path, body={"name": "x", "track": 0, "files": ["tone_a.wav"]} if method == "POST" else None)
    assert r.status < 500, f"{method} {path} -> HTTP {r.status} (a server error for a typo in the URL)"


@pytest.mark.sev(2)
@pytest.mark.covers("http.DELETE /api/playlists/{p}/{t}")
def test_remove_track_and_the_cue_follows(std):
    api = std
    api.cmd("0/2/focus")
    assert api.delete("/api/playlists/0/0").status == 200
    assert ids(api, 0) == ["tone_b.wav", "tone_c.wav"]
    assert api.state()["focus_id"] == "0/1", "the cue stays on tone_c"
    assert "tone_a.wav" in {f["id"] for f in api.library()["files"]}, "the file stays in the library"
    api.delete("/api/playlists/0/1")
    api.delete("/api/playlists/0/0")
    assert ids(api, 0) == []
    assert api.state()["focus_id"] in ("0/0", "-")
    for bad in ("/api/playlists/0/0", "/api/playlists/0/-1", "/api/playlists/9/0"):
        assert api.delete(bad).status == 400, bad


@pytest.mark.sev(2)
@pytest.mark.covers("http.POST /api/move")
def test_move_track_within_and_between_playlists(std):
    api = std
    assert api.post("/api/move", {"from": [0, 0], "to": [0, 2]}).status == 200
    assert ids(api, 0) == ["tone_b.wav", "tone_c.wav", "tone_a.wav"]
    assert api.post("/api/move", {"from": [0, 2], "to": [1, 1]}).status == 200
    assert ids(api, 0) == ["tone_b.wav", "tone_c.wav"] and ids(api, 1)[1] == "tone_a.wav"
    assert api.post("/api/move", {"from": [1, 1], "to": [1, 1]}).status == 200
    for bad in ({"from": [9, 0], "to": [0, 0]}, {"from": [0, 9], "to": [0, 0]}, {"from": [0, 0], "to": [9, 0]}, {}, {"from": [0, 0]}):
        assert api.post("/api/move", bad).status == 400, bad
    r = api.post("/api/move", {"from": [0, 0], "to": [1, 999]})
    assert r.status == 200 and ids(api, 1)[-1] == "tone_b.wav", "an index past the end goes to the end"


@pytest.mark.sev(2)
@pytest.mark.covers("http.POST /api/move")
def test_moving_a_track_takes_its_trim_end_action_and_crossfade_along(std):
    api = std
    api.cmd("0/1/in/0.5")
    api.cmd("0/1/out/2")
    api.cmd("0/1/end/loop")
    api.cmd("0/1/xftime/2")
    api.post("/api/move", {"from": [0, 1], "to": [1, 0]})
    t = api.playlists()[1]["tracks"][0]
    assert t["id"] == "tone_b.wav" and t["trim"] == {"in": 0.5, "out": 2.0} and t["end"] == "loop" and t["xfade"] == 2000, t


@pytest.mark.sev(1)
@pytest.mark.covers("http.POST /api/move")
def test_moving_the_live_track_keeps_it_live(std):
    api = std
    api.cmd("0/1")
    api.wait_playing("0/1")
    api.post("/api/move", {"from": [0, 1], "to": [1, 0]})
    s = api.state()
    assert s["live_id"] == "1/0" and s["live_name"] == "tone_b" and s["state"] == "playing"


@pytest.mark.sev(2)
def test_playlists_are_saved_to_disk(std, managed):
    api = std
    api.cmd("0/1/end/loop")
    time.sleep(0.3)
    d = json.loads((managed.workdir / "playlists.json").read_text("utf-8"))
    assert [p["name"] for p in d["playlists"]] == ["A", "B"]
    assert d["playlists"][0]["end_actions"] == {"tone_b.wav": "loop"}
