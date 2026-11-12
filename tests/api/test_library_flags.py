"""Library folder flags (2.7.4): favorite and hidden, shared by every browser, kept in step with rename and delete.
Web page only: they must not appear in snapshot() / command() output."""
import pytest


def flags(api):
    return api.library().get("flags", {})


@pytest.mark.sev(2)
@pytest.mark.covers("http.GET /api/library/folder/flags", "http.POST /api/library/folder/flags")
def test_flags_set_list_clear(api, scratch):
    assert api.post("/api/library/folder", {"path": "FlagDir/Inner"}).status == 200
    try:
        assert "FlagDir" not in flags(api)
        r = api.post("/api/library/folder/flags", {"path": "FlagDir", "fav": True})
        assert r.status == 200 and r.json["flags"]["FlagDir"] == {"fav": True}
        r = api.post("/api/library/folder/flags", {"path": "FlagDir", "hidden": True})
        assert flags(api)["FlagDir"] == {"fav": True, "hidden": True}      # setting one flag keeps the other
        assert api.get("/api/library/folder/flags").json["flags"]["FlagDir"] == {"fav": True, "hidden": True}
        api.post("/api/library/folder/flags", {"path": "FlagDir", "fav": False})
        assert flags(api)["FlagDir"] == {"hidden": True}
        api.post("/api/library/folder/flags", {"path": "FlagDir", "hidden": False})
        assert "FlagDir" not in flags(api)                                 # nothing set: the entry is gone
    finally:
        api.delete("/api/library/folder", path="FlagDir", force="1")


@pytest.mark.sev(2)
@pytest.mark.covers("http.POST /api/library/folder/flags")
def test_flags_bad_input_is_tolerated(api):
    assert api.post("/api/library/folder/flags", {"path": "NoSuchFolder", "fav": True}).status == 404
    assert api.post("/api/library/folder/flags", {"path": "..", "fav": True}).status == 404
    assert api.post("/api/library/folder/flags", {"path": "", "fav": True}).status == 404
    assert api.post("/api/library/folder/flags", {}).status == 404
    assert api.post("/api/library/folder", {"path": "FlagBad"}).status == 200
    try:
        for bad in ("yes", 1, None, [], {}):
            assert api.post("/api/library/folder/flags", {"path": "FlagBad", "fav": bad}).status == 400, bad
        assert "FlagBad" not in flags(api)
        assert api.post("/api/library/folder/flags", {"path": "FlagBad", "unknown": True}).status == 200   # unknown keys are ignored
        assert "FlagBad" not in flags(api)
        assert api.get("/api/state").status == 200 and api.get("/api/library").status == 200
    finally:
        api.delete("/api/library/folder", path="FlagBad", force="1")


@pytest.mark.sev(2)
@pytest.mark.covers("http.POST /api/library/rename", "http.DELETE /api/library/folder")
def test_flags_follow_rename_and_move_and_drop_on_delete(api):
    assert api.post("/api/library/folder", {"path": "FlagA/Sub"}).status == 200
    assert api.post("/api/library/folder", {"path": "FlagTarget"}).status == 200
    try:
        api.post("/api/library/folder/flags", {"path": "FlagA", "fav": True})
        api.post("/api/library/folder/flags", {"path": "FlagA/Sub", "hidden": True})
        assert api.post("/api/library/rename", {"from": "FlagA", "to": "FlagB"}).status == 200
        f = flags(api)
        assert f.get("FlagB") == {"fav": True} and f.get("FlagB/Sub") == {"hidden": True} and "FlagA" not in f
        assert api.post("/api/library/rename", {"from": "FlagB", "to": "FlagTarget/FlagB"}).status == 200      # a move is a rename
        f = flags(api)
        assert f.get("FlagTarget/FlagB") == {"fav": True} and f.get("FlagTarget/FlagB/Sub") == {"hidden": True}
        assert "FlagB" not in f
        assert api.delete("/api/library/folder", path="FlagTarget/FlagB", force="1").status == 200
        f = flags(api)
        assert "FlagTarget/FlagB" not in f and "FlagTarget/FlagB/Sub" not in f
    finally:
        api.delete("/api/library/folder", path="FlagTarget", force="1")
        api.delete("/api/library/folder", path="FlagA", force="1")
        api.delete("/api/library/folder", path="FlagB", force="1")


@pytest.mark.sev(3)
def test_flags_are_not_in_snapshot_or_variables(api):
    assert api.post("/api/library/folder", {"path": "FlagSnap"}).status == 200
    try:
        api.post("/api/library/folder/flags", {"path": "FlagSnap", "fav": True, "hidden": True})
        for url in ("/api/state", "/api/variables"):
            assert "FlagSnap" not in api.get(url).body.decode(), url
    finally:
        api.delete("/api/library/folder", path="FlagSnap", force="1")
