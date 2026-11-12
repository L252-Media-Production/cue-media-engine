"""File facts (split steps P5/P6, docs/split-plan.md 3.6 / 3.7): upload of MP3 and FLAC, the "i" popover fresh and cached, the format check run,
and durations.json after a rescan. They work with and without ffmpeg on the player (CPTEST_EXTRA_CONFIG='{"ffmpeg_path": "/nope/ffmpeg"}'): the facts
that need ffmpeg then say "needs ffmpeg" instead of giving values, and the built-in fallbacks are used. The MP3 / FLAC files are made with the ffmpeg
of THIS machine (skipped when there is none)."""
import json, subprocess, tempfile, time
from pathlib import Path
import pytest

from harness import libgen
from conftest import make_playlist


def _make(path, codec_args, hz, secs=2):
    ff = libgen.ffmpeg_exe()
    if not ff:
        pytest.skip("ffmpeg is needed on the test machine to create the MP3 / FLAC files")
    subprocess.run([ff, "-v", "error", "-y", "-f", "lavfi", "-i", f"sine=f={hz}:d={secs}:r=44100", "-ac", "2", *codec_args, str(path)], check=True)
    return Path(path).read_bytes()


@pytest.mark.sev(2)
@pytest.mark.covers("http.POST /api/library/upload")
@pytest.mark.parametrize("name,args,hz", [("scratch_up.mp3", ["-c:a", "libmp3lame", "-b:a", "128k"], 523), ("scratch_up.flac", ["-c:a", "flac"], 587)])
def test_upload_of_mp3_and_flac_is_stored_measured_and_plays(api, name, args, hz):
    with tempfile.TemporaryDirectory() as td:
        data = _make(Path(td) / name, args, hz)
    r = api.upload(name, data)
    assert r.status == 200, r
    fid = r.json["files"][0]["id"]
    try:
        assert fid == name
        api.wait_for(lambda s: any(f["id"] == fid and f["dur"] for f in api.library()["files"]), 20, desc="its length measured")
        dur = next(f["dur"] for f in api.library()["files"] if f["id"] == fid)
        assert 1.8 < dur < 2.3, dur
        p = make_playlist(api, "UF", [fid])
        api.cmd(f"{p}/0")
        s = api.wait_playing(f"{p}/0", 15)
        assert 1.8 < s["live_dur"] < 2.3
        api.cmd("stop")
        api.wait_state("stopped")
    finally:
        api.delete("/api/library", id=fid)


@pytest.mark.sev(3)
@pytest.mark.covers("http.GET /api/library/info")
def test_the_info_popover_data_is_complete_when_fresh_and_stable_when_cached(api, manifest):
    fid = "tone_e.mp3" if "tone_e.mp3" in manifest else "tone_a.wav"
    first = api.get("/api/library/info", id=fid)
    assert first.status == 200, first
    d1 = first.json
    for k in ("id", "name", "size", "dur", "status", "ffmpeg"):
        assert k in d1, (k, d1)
    assert d1["id"] == fid and d1["size"] > 0
    st = d1["status"]
    assert set(st) == {"probe", "loud", "peak", "vol"}
    deadline = time.time() + 30
    d = d1
    while time.time() < deadline and any(v == "measuring" for v in d["status"].values()):
        time.sleep(0.5)
        d = api.get("/api/library/info", id=fid).json
    assert not any(v == "measuring" for v in d["status"].values()), d["status"]
    if d["ffmpeg"]:
        assert d["status"]["probe"] == "ok" and d["status"]["loud"] == "ok", d["status"]
        assert d["lufs"] is not None and d["format"] and d["codec"], d
    else:
        assert d["status"]["probe"] in ("needs ffmpeg", "unavailable", "ok"), d["status"]
    again = api.get("/api/library/info", id=fid).json
    assert again == d, "the cached answer is the same as the settled one"


@pytest.mark.sev(3)
@pytest.mark.covers("http.GET /api/formats")
def test_the_format_check_runs_to_the_end_with_ffmpeg_and_says_so_without(api):
    plain = api.get("/api/formats")
    assert plain.status == 200 and plain.json["ok"] is True
    for k in ("available", "running", "deep", "done", "total", "problems"):
        assert k in plain.json, (k, plain.json)
    if not plain.json["available"]:                                  # ffmpeg missing on the player: the deep check is refused with a message
        deep = api.get("/api/formats", deep="1")
        assert deep.status == 415 and deep.json["ok"] is False and deep.json["error"]
        return
    assert api.get("/api/formats", deep="1").status == 200
    deadline, d = time.time() + 60, {}
    while time.time() < deadline:
        d = api.get("/api/formats").json
        if not d["running"] and d["total"] and d["done"] >= d["total"]:
            break
        time.sleep(0.5)
    assert not d["running"] and d["total"] > 0 and d["done"] == d["total"], d
    assert isinstance(d["problems"], list)


@pytest.mark.sev(2)
@pytest.mark.covers("http.GET /api/scan")
def test_durations_json_is_written_after_a_rescan(api, managed):
    lib = managed.workdir / "media" / "library"
    path = managed.workdir / "durations.json"
    libgen.write_tone(lib / "scratch_dur.wav", 410, 1.5, -12)
    try:
        assert api.res("rescan") == "ok"
        api.wait_for(lambda s: any(f["id"] == "scratch_dur.wav" and f["dur"] for f in api.library()["files"]), 20, desc="its length measured")
        t0 = time.time()
        data = {}
        while time.time() - t0 < 20:
            try:
                data = json.loads(path.read_text())
                if "scratch_dur.wav" in data:
                    break
            except (OSError, ValueError):
                pass
            time.sleep(0.3)
        assert "scratch_dur.wav" in data, "durations.json was not written after the rescan"
        size, mtime_ns, secs = data["scratch_dur.wav"]
        assert size == (lib / "scratch_dur.wav").stat().st_size and abs(secs - 1.5) < 0.1
    finally:
        (lib / "scratch_dur.wav").unlink(missing_ok=True)
        api.cmd("rescan")
        api.wait_for(lambda s: "scratch_dur.wav" not in {f["id"] for f in api.library()["files"]}, 10, desc="the file to leave")
