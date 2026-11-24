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


WORKFLOW = ROOT / ".github" / "workflows" / "deb.yml"
CI_VERSION = PK / "ci-version.sh"


def top_sections(text):
    """{top-level key: its block text} of a YAML file (the key line included); no YAML library needed."""
    out, key, buf = {}, None, []
    for line in text.splitlines():
        m = re.match(r"^([A-Za-z_][\w-]*):", line)
        if m:
            if key:
                out[key] = "\n".join(buf)
            key, buf = m.group(1), [line]
        elif key:
            buf.append(line)
    if key:
        out[key] = "\n".join(buf)
    return out


def job_block(text, name):
    m = re.search(r"^  %s:\n(.*?)(?=^  [A-Za-z_][\w-]*:\n|\Z)" % re.escape(name), top_sections(text)["jobs"] + "\n", re.M | re.S)
    return m.group(1) if m else None


class Workflow(unittest.TestCase):
    """.github/workflows/deb.yml: when it runs, what it may do, and how the version is chosen (prompt 07 decisions)."""

    @classmethod
    def setUpClass(cls):
        cls.text = WORKFLOW.read_text()
        cls.on = top_sections(cls.text)["on"]

    def test_parses(self):
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML not installed (the text checks below still run)")
        d = yaml.safe_load(self.text)
        on = d[True]                                          # YAML 1.1 reads the key "on" as True
        self.assertEqual(set(on), {"push", "workflow_dispatch"})
        self.assertEqual(on["push"]["tags"], ["v*"])
        self.assertEqual(on["push"]["branches"], ["release/**"])
        self.assertEqual(d["permissions"], {"contents": "read"})
        self.assertEqual(d["jobs"]["release"]["permissions"], {"contents": "write"})
        self.assertNotIn("permissions", d["jobs"]["build"])

    def test_triggers(self):
        events = re.findall(r"^  ([a-z_]+):", self.on, re.M)
        self.assertEqual(events, ["push", "workflow_dispatch"], "only push and workflow_dispatch may start this workflow")
        self.assertRegex(self.on, r'(?m)^    tags: \["v\*"\]')
        self.assertRegex(self.on, r'(?m)^    branches: \["release/\*\*"\]')
        for bad in ("pull_request", "pull_request_target", "schedule", "workflow_run", "repository_dispatch"):
            self.assertNotRegex(self.text, r"(?m)^\s*%s\s*:" % bad, bad)

    def test_paths(self):
        m = re.search(r"(?m)^    paths:\n((?:      - .*\n)+)", self.on + "\n")
        self.assertIsNotNone(m, "push needs a paths: list")
        paths = re.findall(r'- "([^"]+)"', m.group(1))
        self.assertEqual(paths, ["packaging/**", ".github/workflows/deb.yml", "requirements.txt", "player.py", "cpl/**", "static/**"])

    def test_concurrency(self):
        c = top_sections(self.text).get("concurrency", "")
        self.assertIn("group: deb-${{ github.ref }}", c)
        self.assertIn("cancel-in-progress: ${{ github.ref_type == 'branch' }}", c, "never cancel a tag build")

    def test_permissions(self):
        self.assertEqual(top_sections(self.text)["permissions"].strip(), "permissions:\n  contents: read")
        self.assertEqual(len(re.findall(r"contents: write", self.text)), 1)
        rel = job_block(self.text, "release")
        self.assertIn("    permissions:\n      contents: write", rel)
        self.assertNotIn("permissions", job_block(self.text, "build"))

    def test_release_only_on_tags(self):
        rel = job_block(self.text, "release")
        self.assertIn("    if: github.event_name == 'push' && startsWith(github.ref, 'refs/tags/v')\n", rel)
        self.assertIn("needs: build", rel)
        self.assertNotIn("gh release", job_block(self.text, "build"), "a branch build never touches a Release")

    def test_no_trace_and_no_secrets(self):
        self.assertNotRegex(self.text, r"set -[a-z]*x|set -o xtrace|bash -x")
        self.assertEqual(re.findall(r"\$\{\{\s*secrets\.", self.text), [], "only github.token may be used")
        self.assertEqual(set(re.findall(r"\$\{\{\s*github\.token\s*\}\}", self.text)), {"${{ github.token }}"})

    def test_actions_pinned(self):
        uses = re.findall(r"uses: (\S+)", self.text)
        self.assertEqual({u.split("@")[0] for u in uses},
                         {"actions/checkout", "actions/upload-artifact", "actions/download-artifact"})
        for u in uses:
            self.assertRegex(u, r"@[0-9a-f]{40}$", u)

    def test_version_step(self):
        build = job_block(self.text, "build")
        i_ver, i_build = build.find("name: Package version"), build.find("name: Build the package")
        self.assertTrue(0 < i_ver < i_build, "the version step runs before the build")
        step = build[i_ver:i_build]
        self.assertIn("REF_TYPE: ${{ github.event_name == 'push' && github.ref_type || 'manual' }}", step)
        self.assertIn("REF_NAME: ${{ github.ref_name }}", step)
        self.assertIn('packaging/ci-version.sh "$REF_TYPE" "$REF_NAME" "$(git rev-parse HEAD)"', step)
        self.assertIn('echo "DEB_VERSION=$v" >> "$GITHUB_ENV"', step)
        self.assertIn("LINT: \"1\"", build)
        self.assertIn("timeout-minutes: 45", build)


@unittest.skipUnless(shutil.which("sh") and os.name != "nt", "needs sh")
class CiVersion(unittest.TestCase):
    """packaging/ci-version.sh, run directly against a stand-in cpl/config.py."""

    def run_it(self, ref_type, ref_name, sha="b09456b0123456789abcdef0123456789abcdef0", app="2.9.1"):
        with tempfile.TemporaryDirectory() as d:
            cfg = Path(d) / "config.py"
            cfg.write_text(f'import os\nAPP_VERSION = "{app}"   # product version\nOTHER = "x"\n')
            return subprocess.run(["sh", str(CI_VERSION), ref_type, ref_name, sha, str(cfg)], capture_output=True, text=True)

    def ok(self, *a, **kw):
        r = self.run_it(*a, **kw)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stderr, "")
        return r.stdout.strip()

    def fails(self, *a, **kw):
        r = self.run_it(*a, **kw)
        self.assertNotEqual(r.returncode, 0, r.stdout)
        self.assertEqual(r.stdout, "")
        self.assertTrue(r.stderr.startswith("ci-version: "), r.stderr)
        return r.stderr

    def test_script(self):
        text = CI_VERSION.read_text()
        self.assertTrue(text.startswith("#!/bin/sh\n"))
        self.assertIn("\nset -eu\n", text)
        self.assertEqual(subprocess.run(["sh", "-n", str(CI_VERSION)]).returncode, 0)
        self.assertTrue(os.access(CI_VERSION, os.X_OK), "ci-version.sh must be executable (mode 100755)")
        # the same APP_VERSION expression as the build
        expr = "sed -nE 's/^APP_VERSION[[:space:]]*=[[:space:]]*\"([^\"]+)\".*/\\1/p'"
        self.assertIn(expr, text)
        self.assertIn(expr, (PK / "build-in-container.sh").read_text())

    def test_rc_tag(self):
        self.assertEqual(self.ok("tag", "v2.9.1-rc2"), "2.9.1-rc2")
        self.assertEqual(self.ok("tag", "v2.9.1-rc2", app="2.9.0"), "2.9.1-rc2", "an rc tag does not need the bump yet")

    def test_final_tag(self):
        self.assertEqual(self.ok("tag", "v2.9.1", app="2.9.1"), "2.9.1")
        self.assertIn("APP_VERSION", self.fails("tag", "v2.9.1", app="2.9.0"))

    def test_bad_tags(self):
        for t in ("v2.9", "vfoo", "2.9.1", "v2.9.1-beta1", "v2.9.1-rc", "v2.9.1-rc2x", "v2.9.1.4"):
            self.assertIn("not vX.Y.Z", self.fails("tag", t), t)

    def test_branch_and_manual(self):
        self.assertEqual(self.ok("branch", "release/2.9.1", app="2.9.0"), "2.9.0~ci.b09456b")
        self.assertEqual(self.ok("manual", "main", app="2.9.0"), "2.9.0~ci.b09456b")
        self.fails("branch", "release/2.9.1", sha="")
        self.fails("branch", "release/2.9.1", sha="not-a-sha")

    def test_ci_sorts_below_release(self):
        if not shutil.which("dpkg"):
            self.skipTest("needs dpkg")
        r = subprocess.run(["dpkg", "--compare-versions", "2.9.0~ci.b09456b", "lt", "2.9.0"])
        self.assertEqual(r.returncode, 0)

    def test_real_config(self):
        self.assertEqual(subprocess.run(["sh", str(CI_VERSION), "branch", "release/x", "abcdef0123"], capture_output=True,
                                        text=True).stdout.strip(), app_version() + "~ci.abcdef0")


if __name__ == "__main__":
    unittest.main(verbosity=2)
