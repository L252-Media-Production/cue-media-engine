#!/usr/bin/env python3
"""The launchers and deploy scripts exist and are usable (a deploy commit once emptied run-player.bat, and a deploy of that would have put an empty file on the Windows box).

    python tests/test_launchers.py          # exit 0 = all pass

  * run-player.bat: not empty, every line ends with CRLF (no bare LF), checks for cpl\\__init__.py and static\\help.html, runs player.py
  * run-player.command: not empty, executable (file mode and, in git, 100755), checks for cpl/__init__.py and static/help.html, `bash -n` accepts it
  * deploy/deploy.sh and deploy/deploy.ps1: not empty; deploy.sh copies player.py, static/ and cpl/; deploy.ps1 copies player.py, run-player.bat, static and cpl
  * 2.9.1: no personal path (no D:\\ and no old source clone) in either script; deploy.ps1 has CRLF only, the -App parameter, CUEME_APP,
    CUEME_SRC, the source = the script's own repository, the default C:\\Apps\\CueME, and the same three first lines as deploy.sh
    (same labels, same rule names, same stop message); deploy.sh's source is its own repository. If pwsh is installed, deploy.ps1 is
    run with CUEME_APP / -App naming a missing folder: it prints the three lines and stops without creating anything (it never
    reaches git or robocopy). deploy.sh itself is run in tests/test_deploy_keeps_data.py.
"""
import os, re, shutil, stat, subprocess, sys, tempfile, unittest
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

    def test_deploy_scripts_no_personal_paths(self):
        sh, ps = read("deploy/deploy.sh"), read("deploy/deploy.ps1")
        for d in (sh, ps):
            self.assertTrue(b"D:\\" not in d.upper(), "no D:\\ path in the deploy scripts (the repository is public)")
            for old in (b"CompanionPlayer-src", b"companionplayer-src", b"D:\\Tools"):
                self.assertNotIn(old, d)
        self.assertIn(b'SRC=${CUEME_SRC:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}', sh, "deploy.sh: source = its own repository")

    def test_deploy_ps1_folders(self):
        ps = read("deploy/deploy.ps1")
        self.assertEqual(ps.count(b"\n"), ps.count(b"\r\n"), "deploy.ps1 must use CRLF line endings only")
        t = ps.decode()
        self.assertIn("$DefaultApp = 'C:\\Apps\\CueME'", t)
        self.assertRegex(t, r"param\(\s*\[Parameter\(Mandatory\)\]\[string\]\$Ref,\s*\[string\]\$App = ''\s*\)", "-App is a parameter")
        self.assertIn("$Src = if ($env:CUEME_SRC) { $env:CUEME_SRC } else { Split-Path -Parent $PSScriptRoot }", t)
        self.assertIn("elseif ($env:CUEME_APP) { $App = $env:CUEME_APP; $Rule = 'set by CUEME_APP' }", t)
        self.assertIn("if ($App) { $Rule = 'set by -App' }", t)
        self.assertNotRegex(t, r"Read-Host", "the script never prompts")
        # the three lines come first: before the folder check, the running-player check and git
        first = t.index('Write-Output "Source folder:  $Src"')
        self.assertLess(t.index('Write-Output "Source origin:  $Origin"'), t.index('Write-Output "Install folder: $App ($Rule)"'))
        for later in ("Test-Path -LiteralPath $App", "Get-CimInstance", "Invoke-G fetch"):
            self.assertLess(first, t.index(later))
        self.assertIn(".venv", t[t.index("Deployed"):], "the end says how to create a missing .venv")

    def test_deploy_scripts_print_the_same(self):
        sh, ps = read("deploy/deploy.sh").decode(), read("deploy/deploy.ps1").decode()
        for s in ('"Source folder:  $', '"Source origin:  $', '"Install folder: $', "set by CUEME_APP", "default",
                  "Check the path or create the folder first. Nothing was changed."):
            self.assertIn(s, sh)
            self.assertIn(s, ps)
        self.assertIn("Stopped: the install folder $APP does not exist ($RULE).", sh)
        self.assertIn("Stopped: the install folder $App does not exist ($Rule).", ps)

    def test_deploy_ps1_runs_in_pwsh(self):
        pwsh = shutil.which("pwsh")
        if not pwsh:
            self.skipTest("pwsh is not installed")
        with tempfile.TemporaryDirectory() as td:
            missing = Path(td) / "typo"
            env = {k: v for k, v in os.environ.items() if k not in ("CUEME_SRC", "CUEME_APP")}
            for args, extra, rule in (([], {"CUEME_APP": str(missing)}, "set by CUEME_APP"), (["-App", str(missing)], {}, "set by -App")):
                r = subprocess.run([pwsh, "-NoProfile", "-File", str(ROOT / "deploy/deploy.ps1"), "-Ref", "main", *args],
                                   env={**env, **extra}, capture_output=True, text=True, timeout=60)
                self.assertNotEqual(r.returncode, 0)
                lines = r.stdout.splitlines()
                self.assertEqual(lines[0], f"Source folder:  {ROOT}")
                self.assertTrue(lines[1].startswith("Source origin:  "))
                self.assertEqual(lines[2], f"Install folder: {missing} ({rule})")
                self.assertIn("Stopped: the install folder", r.stdout + r.stderr)
                self.assertFalse(missing.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
