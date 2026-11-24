#!/usr/bin/env python3
"""A deploy never deletes the install's own data: config.json, state.json, playlists.json, media/ and the ElevenLabs key file
elevenlabs.key (2.9.0). A redeploy that removed the key would silently disconnect the operator's account.

    python tests/test_deploy_keeps_data.py          # exit 0 = all pass

  * deploy/deploy.sh is RUN in a sandbox (a throw-away git clone as the source, a fake install folder holding the data files and a
    0600 key, CUEME_SRC / CUEME_APP point it there), twice: every data file is byte-identical afterwards and the key keeps
    mode 0600, while player.py, static/ and cpl/ were updated. Skipped without bash, git and rsync.
  * deploy/deploy.ps1 cannot run here (PowerShell / robocopy): it is checked statically. Its only writes to the install folder are
    Copy-Item of player.py, requirements.txt and run-player.bat, the robocopy /MIR of static and cpl (with /XF elevenlabs.key), the
    VERSION file, and removing a stale cpl folder; the key file is named in the exclusion.
"""
import os, re, shutil, stat, subprocess, sys, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = {"config.json": '{"http_port": 8080}\n', "state.json": '{"audio_device": null}\n', "playlists.json": '{"version": 2, "playlists": []}\n',
        "elevenlabs.key": "test-not-a-real-key-3333-abcd\n", "media/library/keep.wav": "RIFF-not-really-audio"}


def git(cwd, *args):
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", "-c", "commit.gpgsign=false", "-c", "tag.gpgsign=false", *args],
                   cwd=cwd, check=True, capture_output=True)


@unittest.skipUnless(shutil.which("bash") and shutil.which("git") and shutil.which("rsync") and os.name != "nt", "needs bash, git and rsync")
class DeploySh(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="cpdeploy-"))
        self.src, self.app, origin = self.tmp / "src", self.tmp / "app", self.tmp / "origin.git"
        self.src.mkdir()
        for rel in ("player.py", "requirements.txt"):
            shutil.copy2(ROOT / rel, self.src / rel)
        shutil.copytree(ROOT / "static", self.src / "static")
        shutil.copytree(ROOT / "cpl", self.src / "cpl", ignore=shutil.ignore_patterns("__pycache__"))
        git(self.src, "init", "-q", "-b", "main")
        git(self.src, "add", "-A")
        git(self.src, "commit", "-q", "-m", "one")
        git(self.src, "tag", "vtest-1")
        git(self.tmp, "clone", "-q", "--bare", str(self.src), str(origin))
        git(self.src, "remote", "add", "origin", str(origin))
        git(self.src, "fetch", "-q", "origin")
        git(self.src, "branch", "-q", "-u", "origin/main", "main")
        self.app.mkdir()
        for rel, text in DATA.items():
            p = self.app / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text)
        os.chmod(self.app / "elevenlabs.key", 0o600)
        (self.app / "static").mkdir()
        (self.app / "static" / "stale.js").write_text("old")
        (self.app / "cpl").mkdir()
        (self.app / "cpl" / "stale.py").write_text("old")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def deploy(self, ref):
        env = {**os.environ, "CUEME_SRC": str(self.src), "CUEME_APP": str(self.app)}
        r = subprocess.run(["bash", str(ROOT / "deploy" / "deploy.sh"), ref], env=env, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_data_and_key_survive_two_deploys(self):
        for ref in ("vtest-1", "main"):
            self.deploy(ref)
            for rel, text in DATA.items():
                self.assertTrue((self.app / rel).is_file(), f"{rel} was removed by the deploy")
                self.assertEqual((self.app / rel).read_text(), text, f"{rel} was changed by the deploy")
            self.assertEqual((self.app / "elevenlabs.key").stat().st_mode & 0o777, 0o600, "the key file lost its 0600 mode")
            self.assertEqual((self.app / "player.py").read_bytes(), (ROOT / "player.py").read_bytes())
            self.assertTrue((self.app / "cpl" / "elevenlabs.py").is_file())
            self.assertTrue((self.app / "static" / "app.js").is_file())
            self.assertFalse((self.app / "static" / "stale.js").exists(), "static/ is mirrored")
            self.assertFalse((self.app / "cpl" / "stale.py").exists(), "cpl/ is mirrored")


class DeployStatic(unittest.TestCase):
    def test_deploy_sh_writes_only_code(self):
        t = (ROOT / "deploy" / "deploy.sh").read_text()
        for line in t.splitlines():
            s = line.strip()
            if s.startswith("#") or "$APP" not in s:
                continue
            ok = (s.startswith("install -m 644 player.py requirements.txt") or "rsync -a --delete" in s and ('"$APP/static/"' in s or '"$APP/cpl/"' in s)
                  or '> "$APP/VERSION"' in s or s.startswith("echo ") or s.startswith("APP="))
            self.assertTrue(ok, f"deploy.sh writes to the install folder in an unexpected way: {s}")
            if "rsync" in s:
                self.assertIn("--exclude elevenlabs.key", s)

    def test_deploy_ps1_writes_only_code(self):
        t = (ROOT / "deploy" / "deploy.ps1").read_text()
        self.assertRegex(t, r"robocopy \$from \$to /MIR [^\r\n]*/XF elevenlabs\.key")
        mirrors = re.findall(r"Mirror \"\$Src\\(\w+)\" \"\$App\\(\w+)\"", t)
        self.assertEqual(sorted(mirrors), [("cpl", "cpl"), ("static", "static")], "only static and cpl are mirrored into the install folder")
        for line in t.splitlines():
            s = line.strip()
            if s.startswith("#") or "$App" not in s or s.startswith("$App ="):
                continue
            ok = (s.startswith('Copy-Item "$Src\\player.py","$Src\\requirements.txt","$Src\\run-player.bat" $App')
                  or 'Mirror "$Src\\' in s or 'Set-Content "$App\\VERSION"' in s or 'Get-Content "$App\\VERSION"' in s
                  or 'Remove-Item "$App\\cpl"' in s or 'Test-Path "$App\\cpl"' in s)
            self.assertTrue(ok, f"deploy.ps1 writes to the install folder in an unexpected way: {s}")
        self.assertNotRegex(t, r"Remove-Item\s+\"?\$App\"?\s", "never remove the install folder itself")


if __name__ == "__main__":
    unittest.main(verbosity=2)
