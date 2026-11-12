#!/usr/bin/env python3
"""Cold starts of the release (stand-alone; start disposable harness instances, nothing else is touched).

    python tests/test_cold_start.py [--old-rev v2.7.0]

  1. a CLEAN folder (library only: no playlists.json, state.json, resume.json, durations.json): the player comes up ready, with no playlists, serves every
     page, and writes playlists.json
  2. an EXISTING folder of the same build: playlists with a trim, a crossfade time, an end action and a trigger point, resume on, a hard kill: after the
     restart the playlists are identical and the track carries on
  3. an UPGRADE: the data files written by the PREVIOUS release (default v2.7.0, started from `git archive`) are copied into a folder of this build; the
     new build reads them (playlists, trim, crossfade, end action, trigger) and resumes the track that the old build was playing
"""
import argparse, json, os, shutil, subprocess, sys, tempfile, time, unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from harness import client           # noqa: E402
from harness.instance import Instance  # noqa: E402

OLD_REV = os.environ.get("COLD_OLD_REV", "v2.7.0")
DATA = ("playlists.json", "state.json", "resume.json", "durations.json", "formats.json", "fileinfo.json", "loudness.json")


def archive(rev, dest):
    has_cpl = subprocess.run(["git", "-C", str(ROOT), "cat-file", "-e", f"{rev}:cpl"], capture_output=True).returncode == 0
    tar = subprocess.run(["git", "-C", str(ROOT), "archive", rev, "player.py", "static", "requirements.txt"] + (["cpl"] if has_cpl else []), capture_output=True, check=True).stdout
    subprocess.run(["tar", "-x", "-C", str(dest)], input=tar, check=True)


def build_show(api):
    """a playlist whose first tracks carry every per-track setting that has to survive a restart / an upgrade"""
    assert api.post("/api/playlists", {"name": "Show"}).status == 200
    assert api.post("/api/playlists/0/add", {"files": ["long_120s.wav", "tone_a.wav", "tone_b.wav"]}).status == 200
    assert api.post("/api/playlists/0/trim", {"track": 0, "in": 1.0, "out": 90.0, "fade_ms": 800}).status == 200
    assert api.res("0/1/xftime/2.5") == "ok"
    assert api.res("0/1/end/loop") == "ok"
    assert api.post("/api/playlists/0/triggers", {"track": 0, "action": "add", "at": 30, "file": "tone_b.wav"}).status == 200


def check_show(tc, st):
    tc.assertEqual(st["tracks"], ["long_120s.wav", "tone_a.wav", "tone_b.wav"])
    tc.assertEqual((st["trim"].get("in"), st["trim"].get("out"), st["trim"].get("fade_ms")), (1.0, 90.0, 800))
    tc.assertIn(st["xfade"], (2.5, 2500))
    tc.assertEqual(st["end"], "loop")
    tc.assertEqual(st["trigger"], [(30.0, "tone_b.wav")])


def settings_of(api):
    pl = api.playlists()[0]
    return {"tracks": [t["id"] for t in pl["tracks"]], "trim": pl["tracks"][0]["trim"], "xfade": pl["tracks"][1]["xfade"], "end": pl["tracks"][1]["end"],
            "trigger": [(x["at"], x["file"]) for x in api.get("/api/playlists/0/triggers", track=0).json["triggers"]]
            if api.get("/api/playlists/0/triggers", track=0).status == 200 else None}


def wait_resume(inst, timeout=15):
    t0, f = time.time(), inst.workdir / "resume.json"
    while time.time() - t0 < timeout:
        try:
            d = json.loads(f.read_text())
            if d.get("pos", 0) >= 2.0 and not d.get("paused"):
                return d
        except (OSError, ValueError):
            pass
        time.sleep(0.2)
    raise AssertionError("resume.json was not written")


class ColdStart(unittest.TestCase):
    def mk(self, tree=ROOT, **cfg):
        inst = Instance(project_dir=tree, wav_only=True, extra_config={"resume_on_start": True, "resume_save_s": 1, **cfg})
        inst.start()
        self.addCleanup(inst.stop)
        return inst, client.Api(inst.base_url, osc_port=inst.osc_port)

    def test_1_clean_folder(self):
        inst, api = self.mk()
        self.assertFalse((inst.workdir / "resume.json").exists(), "a clean folder has no resume.json")
        s = api.state()
        self.assertEqual(s["status"], "ready")
        self.assertEqual(api.playlists(), [])
        self.assertEqual(s["state"], "stopped")
        for path in ("/", "/help", "/stage", "/variables", "/api/variables", "/api/library", "/api/devices"):
            self.assertEqual(api.request("GET", path).status, 200, path)
        self.assertTrue((inst.workdir / "playlists.json").exists(), "playlists.json is written at start-up")
        self.assertEqual(json.loads((inst.workdir / "playlists.json").read_text())["version"], 2)

    def test_2_existing_folder_hard_kill(self):
        inst, api = self.mk()
        build_show(api)
        before = settings_of(api)
        check_show(self, before)
        self.assertEqual(api.res("0/0"), "ok")
        api.wait_playing("0/0")
        time.sleep(3.0)
        saved = wait_resume(inst)
        inst._signal("KILL")
        inst.proc.wait(10)
        inst.restart()
        s = api.wait_for(lambda s: s["state"] == "playing", 25, desc="resumed")
        self.assertEqual(s["live_id"], "0/0")
        self.assertGreaterEqual(s["live_pos"], saved["pos"] - 0.2)
        self.assertEqual(settings_of(api), before)

    def test_3_upgrade_from_the_previous_release(self):
        with tempfile.TemporaryDirectory(prefix="oldtree-") as old_tree:
            archive(OLD_REV, old_tree)
            old, oapi = self.mk(tree=old_tree)
            build_show(oapi)
            before = settings_of(oapi)
            check_show(self, before)
            old_version = oapi.state()["version"]
            self.assertEqual(oapi.res("0/0"), "ok")
            oapi.wait_playing("0/0")
            time.sleep(3.0)
            saved = wait_resume(old)
            old._signal("KILL")
            old.proc.wait(10)
            files = {rel: (old.workdir / rel).read_bytes() for rel in DATA if (old.workdir / rel).exists()}
        self.assertIn("playlists.json", files)
        self.assertIn("resume.json", files)
        new, napi = self.mk()
        new._signal("TERM")
        new.proc.wait(10)
        for rel, data in files.items():                                  # the old build's data files into the new build's folder
            (new.workdir / rel).write_bytes(data)
        new.restart()
        s = napi.wait_for(lambda s: s["state"] == "playing", 25, desc="resumed after the upgrade")
        self.assertEqual(s["live_id"], "0/0")
        self.assertGreaterEqual(s["live_pos"], saved["pos"] - 0.2)
        self.assertEqual(settings_of(napi), before, "playlists, trim, crossfade, end action and trigger point survive the upgrade")
        self.assertNotEqual(napi.state()["version"], old_version, "the folder was read by the NEW build")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--old-rev")
    a, rest = ap.parse_known_args()
    if a.old_rev:
        os.environ["COLD_OLD_REV"] = a.old_rev
        OLD_REV = a.old_rev
    unittest.main(argv=[sys.argv[0]] + rest, verbosity=2)
