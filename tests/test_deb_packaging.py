#!/usr/bin/env python3
"""The Debian package (packaging/, 2.9.1), checked without Docker or network.

    python tests/test_deb_packaging.py          # exit 0 = all pass (skips cleanly without git, sh or bash)

  * packaging/build-in-container.sh is RUN with STAGE_ONLY=1 into a temp folder (no apt, no pip, no dpkg-deb): the staged file
    set is exactly the tracked player.py, requirements.txt, cpl/, static/ plus VERSION, the doc files, the unit, the
    /etc/default conffile, the lintian overrides and DEBIAN/; nothing from tests/, docs/, prompts/, no __pycache__, key or data.
  * the version comes from APP_VERSION in cpl/config.py; DEB_VERSION=2.9.1-rc2 becomes 2.9.1~rc2 (VERSION keeps 2.9.1-rc2).
  * modes: maintainer scripts 0755, every other file 0644, folders 0755; the maintainer scripts pass sh -n, the build scripts bash -n.
  * the unit has the required keys and none of the sandboxing / real-time / limit keys; ExecStart runs the venv in /opt.
  * every systemctl call in the maintainer scripts is guarded by /run/systemd/system, the upgrade path never starts, stops or
    restarts the service, and no rm in prerm/postrm names a data file.
"""
import os, re, shutil, stat, subprocess, sys, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PK = ROOT / "packaging"
APP = "opt/cue-media-engine"
SCRIPTS = ("postinst", "prerm", "postrm")
DATA_NAMES = ("config.json", "state.json", "playlists.json", "durations.json", "resume.json", "elevenlabs.key", "media")
HAVE = shutil.which("git") and shutil.which("sh") and shutil.which("bash") and os.name != "nt"


def app_version():
    m = re.search(r'^APP_VERSION\s*=\s*"([^"]+)"', (ROOT / "cpl" / "config.py").read_text(), re.M)
    return m.group(1)


def stage(tmp, **env):
    out = Path(tmp) / "root"
    e = {k: v for k, v in os.environ.items() if k not in ("DEB_VERSION", "DEB_MAINTAINER", "ARCH", "DEBIAN_RELEASE")}
    e.update(STAGE_ONLY="1", STAGE_DIR=str(out), **env)
    r = subprocess.run(["bash", str(PK / "build-in-container.sh")], env=e, capture_output=True, text=True)
    if r.returncode != 0:
        raise AssertionError("STAGE_ONLY build failed:\n" + r.stdout + r.stderr)
    return out


def files_under(root):
    return {str(p.relative_to(root)).replace(os.sep, "/") for p in root.rglob("*") if p.is_file() or p.is_symlink()}


def control(root):
    return dict(re.findall(r"^([A-Za-z-]+):\s*(.*)$", (root / "DEBIAN" / "control").read_text(), re.M))


def code_only(text):
    """Shell text without comments and quoted strings (good enough for these scripts: no escaped quotes inside strings)."""
    out = []
    for line in text.splitlines():
        line = re.sub(r'"[^"]*"', '""', line)
        line = re.sub(r"'[^']*'", "''", line)
        line = re.sub(r"(^|\s)#.*$", "", line)
        out.append(line)
    return out


def function_body(text, name):
    m = re.search(r"^%s\(\)\s*\{\n(.*?)^\}" % re.escape(name), text, re.M | re.S)
    return m.group(1) if m else None


@unittest.skipUnless(HAVE, "needs git, sh and bash")
class Staged(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="cpdeb-")
        cls.root = stage(Path(cls.tmp) / "a", DEBIAN_RELEASE="12", ARCH="amd64")
        cls.rc = stage(Path(cls.tmp) / "b", DEBIAN_RELEASE="13", ARCH="arm64", DEB_VERSION="2.9.1-rc2")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_file_set(self):
        r = subprocess.run(["git", "-C", str(ROOT), "ls-files", "-z", "--", "player.py", "requirements.txt", "cpl", "static"],
                           capture_output=True, check=True)
        tracked = {f for f in r.stdout.decode().split("\0") if f}
        self.assertIn("player.py", tracked)
        doc = "usr/share/doc/cue-media-engine/"
        expect = {f"{APP}/{f}" for f in tracked} | {f"{APP}/VERSION", doc + "copyright", doc + "NOTICE", doc + "README.md",
                  doc + "changelog.gz", "etc/default/cue-media-engine", "usr/share/lintian/overrides/cue-media-engine",
                  "DEBIAN/control", "DEBIAN/conffiles", "DEBIAN/postinst", "DEBIAN/prerm", "DEBIAN/postrm"}
        for root, unit in ((self.root, "lib/systemd/system/cue-media-engine.service"),
                           (self.rc, "usr/lib/systemd/system/cue-media-engine.service")):
            got = files_under(root)
            self.assertEqual(got, expect | {unit}, "staged files differ from the expected set")
            for f in got:
                parts = f.split("/")
                for bad in ("tests", "docs", "prompts", "__pycache__", ".venv", ".claude", "companion-module", "deploy", "assets"):
                    self.assertNotIn(bad, parts, f)
                self.assertFalse(f.endswith((".key", ".pyc")), f)
                if f.startswith(APP + "/"):
                    rel = f[len(APP) + 1:]
                    self.assertNotIn(rel.split("/")[0], DATA_NAMES, f)
        self.assertEqual((self.root / "DEBIAN" / "conffiles").read_text(), "/etc/default/cue-media-engine\n")
        self.assertEqual((self.root / "usr/share/doc/cue-media-engine/copyright").read_bytes(), (ROOT / "LICENSE").read_bytes())

    def test_version(self):
        v = app_version()
        self.assertEqual((self.root / APP / "VERSION").read_text().strip(), v)
        self.assertEqual(control(self.root)["Version"], v.replace("-rc", "~rc"))
        self.assertEqual(control(self.rc)["Version"], "2.9.1~rc2")
        self.assertEqual((self.rc / APP / "VERSION").read_text().strip(), "2.9.1-rc2")

    def test_control(self):
        c = control(self.root)
        self.assertEqual(c["Package"], "cue-media-engine")
        self.assertEqual(c["Architecture"], "amd64")
        self.assertEqual(control(self.rc)["Architecture"], "arm64")
        self.assertEqual((c["Section"], c["Priority"]), ("sound", "optional"))
        self.assertEqual(c["Homepage"], "https://github.com/L252-Media-Production/cue-media-engine")
        self.assertEqual(c["Maintainer"], "L252 Media Production <support@cuemestage.com>")
        self.assertTrue(c["Installed-Size"].isdigit())
        deps = [d.strip().split(" ")[0] for d in c["Depends"].split(",")]
        for d in ("python3", "python3-venv", "ffmpeg", "alsa-utils", "adduser"):
            self.assertIn(d, deps)
        self.assertIn("python3 (>= 3.11), python3 (<< 3.12)", c["Depends"])
        self.assertIn("python3 (>= 3.13), python3 (<< 3.14)", control(self.rc)["Depends"])
        self.assertNotRegex((self.root / "DEBIAN" / "control").read_text(), r"@[A-Z_]+@")

    def test_modes(self):
        for root in (self.root, self.rc):
            for p in [root] + list(root.rglob("*")):
                m = stat.S_IMODE(p.lstat().st_mode)
                rel = str(p.relative_to(root))
                if p.is_dir():
                    self.assertEqual(m, 0o755, rel)
                elif rel in ("DEBIAN/" + s for s in SCRIPTS):
                    self.assertEqual(m, 0o755, rel)
                else:
                    self.assertEqual(m, 0o644, rel)

    def test_mtimes_from_head_commit(self):
        t = int(subprocess.run(["git", "-C", str(ROOT), "log", "-1", "--format=%ct"], capture_output=True, text=True, check=True).stdout)
        self.assertEqual({int(p.lstat().st_mtime) for p in self.root.rglob("*")}, {t})


@unittest.skipUnless(HAVE, "needs git, sh and bash")
class Scripts(unittest.TestCase):
    def test_syntax(self):
        for s in SCRIPTS:
            self.assertEqual(subprocess.run(["sh", "-n", str(PK / s)]).returncode, 0, s)
            self.assertTrue((PK / s).read_text().startswith("#!/bin/sh\n"), s)
            self.assertIn("\nset -e\n", (PK / s).read_text(), s)
        for s in ("build-deb.sh", "build-in-container.sh"):
            self.assertEqual(subprocess.run(["bash", "-n", str(PK / s)]).returncode, 0, s)

    def test_systemctl_always_guarded(self):
        for s in SCRIPTS:
            lines = code_only((PK / s).read_text())
            for i, line in enumerate(lines):
                if not re.search(r"\bsystemctl\b", line):
                    continue
                prev = next((l for l in reversed(lines[:i]) if l.strip()), "")
                guarded = ("[ -d /run/systemd/system ] || return 0" in prev.strip()
                           or re.search(r"\bhave_systemd\s*&&\s*systemctl\b", line))
                self.assertTrue(guarded, f"{s}:{i + 1}: unguarded systemctl: {line.strip()}")
            text = (PK / s).read_text()
            if "have_systemd" in text:
                self.assertRegex(text, r"have_systemd\(\)\s*\{\s*\[ -d /run/systemd/system \];\s*\}")

    def test_upgrade_never_restarts(self):
        text = (PK / "postinst").read_text()
        self.assertNotIn("restart", " ".join(code_only(text)), "postinst may only print the restart hint, never run it")
        body = function_body(text, "upgrade")
        self.assertIsNotNone(body)
        self.assertNotRegex(" ".join(code_only(body)), r"\b(start|stop|restart|try-restart|reload-or-restart|enable)\b")
        self.assertIn("Restart when ready: sudo systemctl restart cue-media-engine", body)
        self.assertRegex(text, r'if \[ -z "\$2" \]; then\s+fresh_install\s+else\s+upgrade')
        prerm = (PK / "prerm").read_text()
        self.assertRegex(prerm, r"upgrade\|failed-upgrade\)\s*;;", "prerm must do nothing on upgrade")
        for s in SCRIPTS:
            for arg in {"postinst": ("configure", "abort-upgrade"), "prerm": ("remove", "upgrade"),
                        "postrm": ("remove", "purge", "upgrade", "abort-install", "disappear")}[s]:
                self.assertIn(arg, (PK / s).read_text(), f"{s} must handle {arg}")

    def test_no_data_in_rm(self):
        for s in ("prerm", "postrm"):
            for i, line in enumerate((PK / s).read_text().splitlines()):
                if re.search(r"(^|[;&|]\s*|\s)rm(dir)?\s", line) and "echo" not in line:
                    for name in DATA_NAMES:                  # as a whole path part ("cue-media-engine" is not "media")
                        self.assertNotRegex(line, r"(?<![\w.-])%s(?![\w.-])" % re.escape(name), f"{s}:{i + 1} removes data: {line.strip()}")

    def test_unit(self):
        text = (PK / "cue-media-engine.service").read_text()
        kv = {}
        for line in text.splitlines():
            if "=" in line and not line.startswith(("#", ";")):
                k, v = line.split("=", 1)
                kv.setdefault(k.strip(), []).append(v.strip())
        want = {"User": "cueme", "WorkingDirectory": "/opt/cue-media-engine", "EnvironmentFile": "-/etc/default/cue-media-engine",
                "Restart": "always", "RestartSec": "2", "WantedBy": "multi-user.target",
                "ExecStart": "/opt/cue-media-engine/.venv/bin/python player.py"}
        for k, v in want.items():
            self.assertEqual(kv.get(k), [v], k)
        self.assertTrue(kv["ExecStart"][0].startswith("/opt/cue-media-engine/"))
        after = " ".join(kv.get("After", []))
        self.assertIn("network-online.target", after)
        self.assertIn("sound.target", after)
        for k in ("ProtectSystem", "ProtectHome", "CPUSchedulingPolicy", "CPUSchedulingPriority", "CPUQuota", "MemoryMax",
                  "PrivateDevices", "DeviceAllow", "Nice", "LimitRTPRIO", "AllowedCPUs", "CPUAffinity"):
            self.assertNotIn(k, kv, f"{k} is not allowed in the unit (packaging/README.md, decision 5)")

    def test_default_file_all_commented(self):
        lines = [l for l in (PK / "default").read_text().splitlines() if l.strip()]
        self.assertTrue(all(l.lstrip().startswith("#") for l in lines))
        self.assertIn("# SDL_AUDIODRIVER=alsa", lines)


if __name__ == "__main__":
    unittest.main(verbosity=2)
