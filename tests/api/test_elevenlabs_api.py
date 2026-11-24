"""ElevenLabs (2.9.0) through a real player instance, with the fake ElevenLabs of the CP_TEST_ELEVENLABS hook (no network): the key is
never returned by any GET route, never in the log, kept in a 0600 file next to config.json; the one-use preview link; the whole
generate / save flow over HTTP; the routes go through the same-site check; a failing call leaves the health alone.
The key below is made up for the test and is not a real ElevenLabs key."""
import json, os, re, shutil, subprocess, tempfile, time
from pathlib import Path

import pytest

from harness import client
from harness.instance import Instance

pytestmark = [pytest.mark.noreset]
KEY = "test-not-a-real-key-1111-qrst"
ROOT = Path(__file__).resolve().parent.parent.parent


def fake_mp3(path):
    """A short real mp3 when ffmpeg is there (the page can decode it), otherwise bytes that only look like one."""
    ff = shutil.which("ffmpeg")
    if ff and subprocess.run([ff, "-v", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=1.5", "-ac", "1", "-b:a", "64k", str(path)]).returncode == 0:
        return
    path.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00" + os.urandom(4000))


@pytest.fixture(scope="module")
def rig():
    d = Path(tempfile.mkdtemp(prefix="cpel-"))
    fake_mp3(d / "speech.mp3")
    spec = {"key": KEY,
            "voices": {"status": 200, "body": {"voices": [{"voice_id": "v1", "name": "Narrator", "category": "premade", "preview_url": None}], "has_more": False, "total_count": 1}},
            "usage": {"status": 200, "body": {"character_count": 100, "character_limit": 10000}},
            "models": {"status": 401, "body": {"detail": {"status": "missing_permissions", "message": "missing the permission models_read"}}},
            "speech": {"status": 200, "file": "speech.mp3"}}
    (d / "fake.json").write_text(json.dumps(spec))
    inst = Instance(wav_only=True, extra_env={"CP_TEST_ELEVENLABS": str(d)})
    inst.start()
    api = client.Api(inst.base_url, osc_port=inst.osc_port)
    yield inst, api, d
    inst.stop()
    shutil.rmtree(d, ignore_errors=True)


def spec_set(d, what, value):
    s = json.loads((d / "fake.json").read_text())
    s[what] = value
    (d / "fake.json").write_text(json.dumps(s))


def job_done(api):
    for _ in range(200):
        s = api.get("/api/elevenlabs/job").json
        if s["state"] != "running":
            return s
        time.sleep(0.05)
    raise AssertionError("the generation did not finish")


def get_routes():
    src = (ROOT / "cpl" / "legacy.py").read_text()
    return sorted(p for p in re.findall(r'web\.get\("(/api/[^"{]*)"', src) if p not in ("/api/live",))


def test_no_key_state(rig):
    inst, api, d = rig
    r = api.get("/api/elevenlabs").json
    assert r["key"] == {"set": False, "last4": "", "note": ""}
    g = api.post("/api/elevenlabs/generate", {"name": "x", "text": "y", "voice_id": "v1"})
    assert g.status == 400 and g.json["kind"] == "no_key"


def test_key_saved_privately_and_never_returned(rig):
    inst, api, d = rig
    r = api.post("/api/elevenlabs/key", {"key": KEY})
    assert r.status == 200 and r.json["key"] == {"set": True, "last4": "qrst", "note": ""}
    assert KEY not in r.text
    kf = inst.workdir / "elevenlabs.key"
    assert kf.is_file()
    if os.name != "nt":
        assert kf.stat().st_mode & 0o777 == 0o600
    for f in ("config.json", "state.json"):
        p = inst.workdir / f
        assert not p.exists() or KEY not in p.read_text()
    t = api.post("/api/elevenlabs/test").json
    assert (t["level"], t["title"]) == ("ok", "Key works")
    seen = []
    for path in get_routes():
        resp = api.get(path)
        seen.append(path)
        assert KEY not in resp.text, path
        assert KEY[:-4] not in resp.text, path
    assert "/api/elevenlabs" in seen and "/api/state" in seen and "/api/health/report" in seen and "/api/settings" in seen
    for line in (d / "calls.jsonl").read_text().splitlines():
        assert KEY not in line


def test_generate_preview_save_over_http(rig):
    inst, api, d = rig
    api.post("/api/elevenlabs/key", {"key": KEY})
    v = api.get("/api/elevenlabs/voices").json
    assert v["ok"] and v["voices"][0]["id"] == "v1"
    m = api.get("/api/elevenlabs/models").json
    assert m == {"ok": True, "models": None, "default_limit": 10000}, "no models_read: only the default model"
    u = api.get("/api/elevenlabs/usage").json
    assert u["usage"]["left"] == 9900
    r = api.post("/api/elevenlabs/generate", {"name": "House open", "text": "The house is now open.", "voice_id": "v1", "voice_name": "Narrator"})
    assert r.status == 200, r.text
    assert api.post("/api/elevenlabs/generate", {"name": "B", "text": "b", "voice_id": "v1"}).status in (200, 409)
    s = job_done(api)
    assert s["state"] == "done", s
    link = api.post("/api/elevenlabs/preview", {"cmd": "link"}).json
    assert link["ok"] and link["url"].startswith("/api/elevenlabs/audio?t=")
    assert str(inst.workdir) not in json.dumps(link) and "_import" not in json.dumps(link), "no file path leaves the player"
    cross = api.request("GET", link["url"], headers={"Sec-Fetch-Site": "cross-site"})
    assert cross.status == 403, "the same-site check covers the audio link"
    a = api.request("GET", link["url"])
    assert a.status == 200 and a.headers.get("Content-Type", "").startswith("audio/mpeg")
    assert a.body == (d / "speech.mp3").read_bytes()
    assert api.request("GET", link["url"]).status == 404, "one use"
    bad = api.post("/api/elevenlabs/save", {"name": "House open", "folder": "../../etc"})
    assert bad.status == 400 and bad.json["field"] == "folder", bad.text
    bad = api.post("/api/elevenlabs/save", {"name": "House open", "new_folder": "../escape"})
    assert bad.status == 400 and bad.json["field"] == "new_folder", bad.text
    assert not (inst.workdir / "media" / "escape").exists() and not (inst.workdir / "escape").exists()
    sv = api.post("/api/elevenlabs/save", {"name": "House open", "new_folder": "Generated"})
    assert sv.status == 200 and sv.json["id"] == "Generated/House open.mp3", sv.text
    lib = api.get("/api/library").json
    row = [f for f in lib["files"] if f["id"] == "Generated/House open.mp3"]
    assert row and row[0].get("gen") is True
    assert "Generated" in lib["folders"]
    meta = api.get("/api/elevenlabs/track", id="Generated/House open.mp3").json
    assert meta["text"] == "The house is now open." and meta["voice_id"] == "v1" and KEY not in json.dumps(meta)
    assert not list((inst.workdir / "_import").glob("gen-*")), "the temporary file is gone after Save"


def test_discard_removes_temp(rig):
    inst, api, d = rig
    api.post("/api/elevenlabs/key", {"key": KEY})
    api.post("/api/elevenlabs/generate", {"name": "Tmp", "text": "temporary", "voice_id": "v1"})
    assert job_done(api)["state"] == "done"
    assert list((inst.workdir / "_import").glob("gen-*"))
    assert api.post("/api/elevenlabs/discard").json["deleted"] is True
    assert not list((inst.workdir / "_import").glob("gen-*"))


def test_failure_leaves_health_alone_and_log_clean(rig):
    inst, api, d = rig
    api.post("/api/elevenlabs/key", {"key": KEY})
    before = api.get("/api/state").json["health"]
    for spec in ({"status": 401, "body": {"detail": {"status": "quota_exceeded", "message": "quota"}}},
                 {"status": 429, "body": {"detail": {"status": "system_busy", "message": "busy"}}, "headers": {"Retry-After": "7"}},
                 {"network": True}):
        spec_set(d, "speech", spec)
        api.post("/api/elevenlabs/generate", {"name": "Fail", "text": "x", "voice_id": "v1"})
        s = job_done(api)
        assert s["state"] == "error"
    assert s["error"]["kind"] == "network"
    spec_set(d, "speech", {"status": 429, "body": {"detail": {"status": "system_busy"}}, "headers": {"Retry-After": "7"}})
    api.post("/api/elevenlabs/generate", {"name": "Fail", "text": "x", "voice_id": "v1"})
    s = job_done(api)
    assert s["error"]["kind"] == "rate" and s["error"]["retry_s"] == 7
    after = api.get("/api/state").json["health"]
    assert (after["status"], after.get("state")) == (before["status"], before.get("state"))
    spec_set(d, "speech", {"status": 200, "file": "speech.mp3"})
    api.post("/api/elevenlabs/key", {"key": "test-not-a-real-key-2222-wrong"})
    t = api.post("/api/elevenlabs/test").json
    assert (t["level"], t["title"]) == ("bad", "Key not valid")
    api.post("/api/elevenlabs/key", {"key": KEY})
    inst.log.flush()
    log = (inst.workdir / "player.log").read_text(errors="replace")
    assert KEY not in log and "test-not-a-real-key-2222-wrong" not in log


def test_remove_key(rig):
    inst, api, d = rig
    api.post("/api/elevenlabs/key", {"key": KEY})
    r = api.delete("/api/elevenlabs/key")
    assert r.json["key"]["set"] is False
    assert not (inst.workdir / "elevenlabs.key").exists()
    assert api.post("/api/elevenlabs/key", {"key": "has spaces in it"}).status == 400
