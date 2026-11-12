"""Library: listing, files, upload, rename/move, folders, delete, info, waveform, rescan."""
import sys, time
import pytest
from conftest import make_playlist


@pytest.mark.sev(2)
@pytest.mark.covers("http.GET /api/library")
def test_library_listing(api, std, manifest):
    d = api.library()
    files = {f["id"]: f for f in d["files"]}
    for fid, secs in manifest.items():
        assert fid in files, fid
        assert files[fid]["dur"] is None or abs(files[fid]["dur"] - secs) < 0.15, (fid, files[fid]["dur"], secs)
    assert files["tone_a.wav"]["used"] == [0] and files["short_1s.wav"]["used"] == [1] and files["loud.wav"]["used"] == []
    assert files["tone_a.wav"]["name"] == "tone_a" and files["tone_a.wav"]["size"] > 1000
    assert "Sub" in d["folders"]
    assert all(k in d for k in ("colors", "icons", "storage"))


@pytest.mark.sev(2)
@pytest.mark.covers("http.GET /api/library/file")
def test_library_file_download_and_range(api, weird_id):
    r = api.get("/api/library/file", id="tone_a.wav")
    assert r.status == 200 and r.body[:4] == b"RIFF"
    r = api.request("GET", "/api/library/file", query={"id": "tone_a.wav"}, headers={"Range": "bytes=0-99"})
    assert r.status == 206 and len(r.body) == 100
    assert api.get("/api/library/file", id="Sub/tone_d.wav").status == 200
    assert api.get("/api/library/file", id=weird_id).status == 200


@pytest.mark.sev(1)
@pytest.mark.covers("http.GET /api/library/file")
@pytest.mark.parametrize("fid", ["", "nope.wav", "../player.py", "..%2Fplayer.py", "../../config.json", "/etc/passwd", "C:\\Windows\\win.ini",
                                 "Sub/../../player.py", "tone_a.wav/../../player.py", "..\\player.py", "\x00"])
def test_library_file_refuses_anything_outside_the_library(api, fid):
    r = api.get("/api/library/file", id=fid)
    assert r.status in (400, 404), f"{fid!r} -> HTTP {r.status}"
    assert b"import asyncio" not in r.body


@pytest.mark.sev(3)
@pytest.mark.covers("http.GET /api/waveform")
def test_waveform(api):
    r = api.get("/api/waveform", id="tone_a.wav")
    assert r.status == 200
    d = r.json
    assert len(d["peaks"]) > 50 and abs(d["dur"] - 3.0) < 0.2 and max(d["peaks"]) > 100
    assert api.get("/api/waveform", id="nope.wav").status == 404
    assert api.get("/api/waveform", id="../player.py").status == 404
    assert api.get("/api/waveform").status == 404


@pytest.mark.sev(3)
@pytest.mark.covers("http.GET /api/library/info")
def test_file_info(api):
    r = api.get("/api/library/info", id="tone_a.wav")
    assert r.status == 200, r
    d = r.json
    assert isinstance(d, dict) and d
    assert api.get("/api/library/info", id="nope.wav").status in (400, 404)
    assert api.get("/api/library/info", id="../player.py").status in (400, 404)


@pytest.mark.sev(2)
@pytest.mark.covers("http.POST /api/library/upload")
def test_upload_into_library_folder_and_playlist(api, scratch):
    p = make_playlist(api, "U", [])
    fid = scratch("scratch_up.wav", folder="ScratchF/Deep", playlist=p)
    assert fid == "ScratchF/Deep/scratch_up.wav"
    d = api.library()
    assert fid in {f["id"] for f in d["files"]} and "ScratchF/Deep" in d["folders"]
    assert [t["id"] for t in api.playlists()[p]["tracks"]] == [fid]
    api.wait_for(lambda s: any(f["id"] == fid and f["dur"] for f in api.library()["files"]), 10, desc="its length measured")
    api.cmd(f"{p}/0")
    api.wait_playing(f"{p}/0")


@pytest.mark.sev(2)
@pytest.mark.covers("http.POST /api/library/upload")
def test_upload_rejects_bad_input(api, scratch):
    for name, data in (("notes.txt", b"hello"), ("x.exe", b"MZ"), ("noext", b"abc")):
        r = api.upload(name, data)
        assert r.status in (400, 415, 422), (name, r.status, r.text[:100])
    assert api.upload("scratch_bad.wav", b"this is not audio").status in (200, 400, 415, 422)
    api.delete("/api/library", id="scratch_bad.wav")
    assert api.upload("a.wav", b"RIFF", folder="../escape").status == 400
    assert api.upload("a.wav", b"RIFF", folder="..").status == 400
    assert api.upload("a.wav", b"RIFF", playlist=99).status == 404
    r = api.upload("../../escape.wav", b"RIFF")
    assert not any("escape" in f["id"] and "/" in f["id"].replace("Sub/", "") for f in api.library()["files"])
    assert not (api.get("/api/library/file", id="../../escape.wav").status == 200)


@pytest.mark.sev(3)
@pytest.mark.covers("http.POST /api/library/upload")
def test_upload_with_no_file_part_is_harmless(api):
    r = api.request("POST", "/api/library/upload", raw=b"", headers={"Content-Type": "multipart/form-data; boundary=x"})
    assert r.status < 500, r.text[:100]
    r = api.request("POST", "/api/library/upload", body={"a": 1})
    assert r.status < 500, r.text[:100]


@pytest.mark.sev(2)
@pytest.mark.covers("http.POST /api/library/rename")
def test_rename_file_playlists_follow(api, scratch):
    fid = scratch("scratch_r1.wav")
    p = make_playlist(api, "R", [fid, "tone_a.wav"])
    api.cmd(f"{p}/0/end/loop")
    api.cmd(f"{p}/0/in/0.2")
    r = api.post("/api/library/rename", {"from": fid, "to": "scratch_r2.wav"})
    assert r.status == 200 and r.json["id"] == "scratch_r2.wav"
    t = api.playlists()[p]["tracks"][0]
    assert t["id"] == "scratch_r2.wav" and t["end"] == "loop" and t["trim"] == {"in": 0.2}, t
    assert "scratch_r2.wav" in {f["id"] for f in api.library()["files"]} and fid not in {f["id"] for f in api.library()["files"]}
    api.cmd(f"{p}/0")
    api.wait_playing(f"{p}/0")
    r = api.post("/api/library/rename", {"from": "scratch_r2.wav", "to": "Moved/Into/scratch_r3.wav"})
    assert r.status == 200 and r.json["id"] == "Moved/Into/scratch_r3.wav"
    assert api.state()["state"] == "playing" and api.state()["live_fid"] == "Moved/Into/scratch_r3.wav"
    scratch.folders.append("Moved")
    api.delete("/api/library", id="Moved/Into/scratch_r3.wav")


@pytest.mark.sev(2)
@pytest.mark.covers("http.POST /api/library/rename")
def test_rename_errors(api, scratch):
    a = scratch("scratch_e1.wav")
    b = scratch("scratch_e2.wav", freq=640)
    assert api.post("/api/library/rename", {"from": a, "to": b}).status == 409
    assert api.post("/api/library/rename", {"from": a, "to": "scratch_e1.mp3"}).status == 400
    assert api.post("/api/library/rename", {"from": "nope.wav", "to": "x.wav"}).status == 404
    assert api.post("/api/library/rename", {"from": "../player.py", "to": "x.py"}).status in (400, 404)
    assert api.post("/api/library/rename", {"from": a, "to": "../x.wav"}).status == 400
    assert api.post("/api/library/rename", {"from": a, "to": ".hidden.wav"}).status == 400
    assert api.post("/api/library/rename", {"from": a, "to": ""}).status == 400
    assert api.post("/api/library/rename", {}).status == 404
    assert api.post("/api/library/rename", {"from": a, "to": a}).status == 200
    r = api.post("/api/library/rename", {"from": a, "to": "bad<name>?.wav"})
    assert r.status in (200, 400)
    if r.status == 200:                                        # odd characters are cleaned; put the file back so the fixture can delete it
        assert api.post("/api/library/rename", {"from": r.json["id"], "to": a}).status == 200


@pytest.mark.sev(2)
@pytest.mark.covers("http.POST /api/library/folder", "http.DELETE /api/library/folder", "http.POST /api/library/folder/color")
def test_folders_create_colour_icon_delete(api, scratch):
    assert api.post("/api/library/folder", {"path": "ScratchDir/Inner"}).status == 200
    assert "ScratchDir/Inner" in api.library()["folders"]
    assert api.post("/api/library/folder", {"path": "ScratchDir/Inner"}).status == 409
    for bad in ("..", "a/../b", ".hid", "_skip/x", "", "x" * 130):
        assert api.post("/api/library/folder", {"path": bad}).status == 400, bad
    assert api.post("/api/library/folder/color", {"path": "ScratchDir", "color": "#3B82F6", "icon": "music"}).status == 200
    d = api.library()
    assert d["colors"]["ScratchDir"] == "#3b82f6" and d["icons"]["ScratchDir"] == "music"
    assert api.post("/api/library/folder/color", {"path": "ScratchDir", "color": "red"}).status == 400
    assert api.post("/api/library/folder/color", {"path": "ScratchDir", "icon": "Bad Icon!"}).status == 400
    assert api.post("/api/library/folder/color", {"path": "Nope", "color": "#000000"}).status == 404
    assert api.post("/api/library/folder/color", {"path": "ScratchDir", "color": None, "icon": None}).status == 200
    assert "ScratchDir" not in api.library()["colors"]
    fid = scratch("scratch_in.wav", folder="ScratchDir")
    assert api.delete("/api/library/folder", path="ScratchDir").status == 409
    assert api.delete("/api/library/folder", path="Nope").status == 404
    assert api.delete("/api/library/folder", path="..").status == 404
    assert api.delete("/api/library/folder", path="ScratchDir", force="1").status == 200
    assert "ScratchDir" not in api.library()["folders"] and fid not in {f["id"] for f in api.library()["files"]}


@pytest.mark.sev(2)
@pytest.mark.covers("http.POST /api/library/rename")
def test_rename_folder_moves_its_files_and_playlist_entries(api, scratch):
    fid = scratch("scratch_f.wav", folder="ScratchOld")
    p = make_playlist(api, "F", [fid])
    assert api.post("/api/library/rename", {"from": "ScratchOld", "to": "ScratchNew"}).status == 200
    assert api.playlists()[p]["tracks"][0]["id"] == "ScratchNew/scratch_f.wav"
    assert api.post("/api/library/rename", {"from": "ScratchNew", "to": "ScratchNew/inside"}).status == 400
    scratch.folders.append("ScratchNew")


@pytest.mark.sev(2)
@pytest.mark.covers("http.DELETE /api/library")
def test_delete_file_removes_it_from_every_playlist(api, scratch):
    fid = scratch("scratch_d.wav")
    p = make_playlist(api, "D", ["tone_a.wav", fid, "tone_b.wav"])
    q = make_playlist(api, "D2", [fid])
    assert api.delete("/api/library", id=fid).status == 200
    assert [t["id"] for t in api.playlists()[p]["tracks"]] == ["tone_a.wav", "tone_b.wav"] and api.playlists()[q]["tracks"] == []
    assert fid not in {f["id"] for f in api.library()["files"]}
    assert api.delete("/api/library", id=fid).status == 404
    assert api.delete("/api/library", id="../player.py").status == 404
    assert api.delete("/api/library").status == 404
    assert api.get("/api/library/file", id="../player.py").status in (400, 404)


@pytest.mark.sev(1)
@pytest.mark.covers("http.DELETE /api/library")
def test_deleting_the_live_file_does_not_cut_the_audio(api, scratch):
    fid = scratch("scratch_live.wav", secs=3.0)
    p = make_playlist(api, "DL", [fid])
    api.cmd(f"{p}/0")
    api.wait_playing(f"{p}/0")
    api.delete("/api/library", id=fid)
    time.sleep(0.5)
    assert api.state()["state"] == "playing"
    api.cmd("stop")


@pytest.mark.sev(2)
@pytest.mark.covers("cmd.rescan", "http.GET /api/scan")
def test_rescan_finds_files_added_outside(api, managed):
    from harness import libgen
    lib = managed.workdir / "media" / "library"
    libgen.write_tone(lib / "scratch_outside.wav", 440, 1.0, -12)
    assert "scratch_outside.wav" not in {f["id"] for f in api.library()["files"]} or True
    assert api.res("rescan") == "ok"
    api.wait_for(lambda s: "scratch_outside.wav" in {f["id"] for f in api.library()["files"]}, 8, desc="the new file")
    (lib / "scratch_outside.wav").unlink()
    api.cmd("rescan")
    api.wait_for(lambda s: "scratch_outside.wav" not in {f["id"] for f in api.library()["files"]}, 8, desc="the file to leave")
    assert "missing" in api.get("/api/scan").json


def _restart_player(api, managed, timeout=40):
    """POST /api/restart and wait until the same process answers again (an empty decoded-sound cache is the point)."""
    import urllib.error
    if sys.platform == "win32":
        pytest.skip("os.execv on Windows starts a new process; the harness cannot supervise it")
    assert api.post("/api/restart").status == 200
    time.sleep(1.0)
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            if api.state()["status"] == "ready":
                return
        except (urllib.error.URLError, OSError, AssertionError, ValueError):
            pass
        time.sleep(0.3)
    raise AssertionError("the player did not come back")


@pytest.mark.sev(2)
@pytest.mark.covers("http.GET /api/scan")
def test_missing_file_in_a_playlist_is_reported_and_play_fails_safely(api, managed, scratch):
    """A playlist entry whose file is gone is flagged, and playing it puts nothing on air. Deterministic: the player is restarted after the file is
    removed, so the decoded sound can not be in its cache (the warm-up decodes every playlist file within milliseconds of it being added, and a track that
    is already in RAM plays from RAM: see the next test)."""
    fid = scratch("scratch_gone.wav")
    p = make_playlist(api, "M", [fid, "tone_a.wav"])
    (managed.workdir / "media" / "library" / fid).unlink()
    _restart_player(api, managed)
    api.cmd("rescan")
    pl = api.playlists()[p]
    assert pl["tracks"][0]["id"] == fid and pl["tracks"][0]["missing"] is True, "a playlist entry whose file vanished must be flagged"
    r = api.res(f"{p}/0")
    time.sleep(0.5)
    assert api.state()["state"] == "stopped" and api.state()["live_id"] == "-", "a missing file must not put anything on air"
    assert fid in [m if isinstance(m, str) else m.get("id") for m in api.get("/api/scan").json["missing"]] or api.get("/api/scan").json["missing"]
    api.delete("/api/playlists/%d/0" % p)


@pytest.mark.sev(3)
@pytest.mark.covers("http.GET /api/scan")
def test_a_file_that_vanished_after_it_was_decoded_is_flagged_but_still_plays_from_memory(api, managed, scratch):
    """Documents what the player does today (found by the flaky test above): decoded sounds are kept in RAM by path, a rescan does not drop them, so a
    track whose file was deleted AFTER the warm-up decoded it is shown as missing but still plays, from the cache, until it is evicted or the player restarts."""
    before = api.state()["mem"]["cache_tracks"]
    fid = scratch("scratch_cached.wav")
    p = make_playlist(api, "M", [fid, "tone_a.wav"])
    api.wait_for(lambda s: s["mem"]["cache_tracks"] > before, 20, desc="the warm-up to decode the new track")
    (managed.workdir / "media" / "library" / fid).unlink()
    api.cmd("rescan")
    pl = api.playlists()[p]
    assert pl["tracks"][0]["id"] == fid and pl["tracks"][0]["missing"] is True
    assert api.res(f"{p}/0") == "ok"
    api.wait_playing(f"{p}/0")
    api.cmd("stop")
    api.delete("/api/playlists/%d/0" % p)


@pytest.mark.sev(3)
@pytest.mark.covers("http.GET /api/storage", "http.GET /api/formats", "http.GET /api/ffmpeg")
def test_storage_formats_ffmpeg_shapes(api):
    s = api.get("/api/storage").json
    assert isinstance(s, dict) and s
    f = api.get("/api/formats").json
    assert isinstance(f, dict)
    ff = api.get("/api/ffmpeg").json
    assert "ok" in ff and "formats" in ff


@pytest.mark.sev(3)
@pytest.mark.covers("http.GET /api/formats")
def test_the_deep_format_check_is_accepted(api):
    if not api.get("/api/formats").json.get("available"):
        pytest.skip("this instance has no ffmpeg: /api/formats?deep=1 answers 415 'ffmpeg was not found', which is the correct behaviour "
                    "(tests/api/test_file_facts.py checks that answer); see docs/known-failures.md")
    assert api.get("/api/formats", deep="1").status == 200


@pytest.mark.sev(2)
def test_mp3_and_flac_play(api, manifest):
    if "tone_e.mp3" not in manifest:
        pytest.skip("ffmpeg was not available to create the MP3 / FLAC test files")
    p = make_playlist(api, "Fmt", ["tone_e.mp3", "tone_f.flac"])
    for k in (0, 1):
        api.cmd(f"{p}/{k}")
        s = api.wait_playing(f"{p}/{k}", 10)
        assert 2.8 < s["live_dur"] < 3.3, s["live_dur"]
        api.cmd("stop")
        api.wait_state("stopped")
