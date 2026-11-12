#!/usr/bin/env python3
"""The launchers and deploy scripts exist and are usable (a deploy commit once emptied run-player.bat, and a deploy of that would have put an empty file on the Windows box).

    python tests/test_launchers.py          # exit 0 = all pass

  * run-player.bat: not empty, every line ends with CRLF (no bare LF), checks for cpl\\__init__.py and static\\help.html, runs player.py
  * run-player.command: not empty, executable (file mode and, in git, 100755), checks for cpl/__init__.py and static/help.html, `bash -n` accepts it
  * deploy/deploy.sh and deploy/deploy.ps1: not empty; deploy.sh copies player.py, static/ and cpl/; deploy.ps1 copies player.py, run-player.bat, static and cpl
"""
import os, stat, subprocess, sys, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def read(rel):
    return (ROOT / rel).read_bytes()


class Launchers(unittest.TestCase):
    def test_run_player_bat(self):
        d = read("run-player.bat")
        self.assertGreater(len(d), 500, "run-player.bat is empty or truncated")
        self.assertEqual(d.count(b"\n"), d.count(b"\r\n"), "run-player.bat must use CRLF line endings only (.gitattributes: *.bat eol=crlf)")
        self.assertGreater(d.count(b"\r\n"), 20)
        low = d.lower()
        for needle in (rb'cpl\__init__.py', rb'static\help.html', b"player.py", b".venv", b"pip install"):
            self.assertIn(needle, low, f"run-player.bat does not mention {needle!r}")
        self.assertIn(b"python.exe\" -c \"import", low, "run-player.bat should check the installed packages when pip fails (offline)")

    def test_run_player_command(self):
        d = read("run-player.command")
        self.assertGreater(len(d), 500, "run-player.command is empty or truncated")
        self.assertTrue(d.startswith(b"#!"), "no shebang line")
        self.assertNotIn(b"\r", d, "run-player.command must have LF line endings")
        self.assertTrue((ROOT / "run-player.command").stat().st_mode & stat.S_IXUSR, "run-player.command is not executable (chmod +x)")
        for needle in (b"cpl/__init__.py", b"static/help.html", b"player.py"):
            self.assertIn(needle, d)
        self.assertEqual(subprocess.run(["bash", "-n", str(ROOT / "run-player.command")], capture_output=True).returncode, 0)

    def test_run_player_command_is_executable_in_git(self):
        r = subprocess.run(["git", "-C", str(ROOT), "ls-files", "-s", "run-player.command"], capture_output=True, text=True)
        if r.returncode != 0 or not r.stdout.strip():
            self.skipTest("not a git checkout")
        self.assertTrue(r.stdout.startswith("100755"), "run-player.command is not mode 100755 in git: " + r.stdout.strip())

    def test_deploy_scripts(self):
        sh, ps = read("deploy/deploy.sh"), read("deploy/deploy.ps1")
        self.assertGreater(len(sh), 100, "deploy.sh is empty")
        self.assertGreater(len(ps), 100, "deploy.ps1 is empty")
        for needle in (b"player.py", b"static", b"cpl"):
            self.assertIn(needle, sh, f"deploy.sh does not deploy {needle!r}")
            self.assertIn(needle, ps, f"deploy.ps1 does not deploy {needle!r}")
        self.assertIn(b"run-player.bat", ps, "deploy.ps1 copies run-player.bat: it must be the real one")
        self.assertEqual(subprocess.run(["bash", "-n", str(ROOT / "deploy/deploy.sh")], capture_output=True).returncode, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
