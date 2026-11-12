#!/usr/bin/env python3
"""Player and Companion module versions (CLAUDE.md: the module warns when the player's major.minor differs from its own).

    python tests/test_module_version.py

  * static: the module version (companion-module/src/consts.js MODULE_VERSION and package.json) and APP_VERSION (cpl/config.py) have the same major.minor
  * with node and the module's node_modules: the REAL checkVersion() of companion-module/src/main.js says 'ok' for a player 2.7.1 with module 2.7.0 and
    for the same version, logs nothing; 'mismatch' (one warning per player version) for another major.minor; 'unknown' for no version
"""
import json, re, shutil, subprocess, sys, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MOD = ROOT / "companion-module"
sys.path.insert(0, str(Path(__file__).resolve().parent))
import gen_controls   # noqa: E402


def mm(v):
    return ".".join(re.match(r"(\d+)\.(\d+)", v).groups())


class ModuleVersion(unittest.TestCase):
    def versions(self):
        app = re.search(r'^APP_VERSION = "([^"]+)"', gen_controls.read_sources(ROOT / "player.py"), re.M).group(1)
        mod = re.search(r"MODULE_VERSION = '([^']+)'", (MOD / "src" / "consts.js").read_text()).group(1)
        pkg = json.loads((MOD / "package.json").read_text())["version"]
        return app, mod, pkg

    def test_same_major_minor(self):
        app, mod, pkg = self.versions()
        self.assertEqual(mod, pkg, "consts.js MODULE_VERSION must equal package.json version")
        self.assertEqual(mm(app), mm(mod), f"player {app} and module {mod} must share major.minor or the module warns at every start")

    def test_check_version_with_the_real_module_code(self):
        if not shutil.which("node") or not (MOD / "node_modules" / "@companion-module").is_dir():
            self.skipTest("node or companion-module/node_modules is not available")
        app, mod, pkg = self.versions()
        js = """
import M from %r
const logs = []
const self = { log: (lvl, msg) => logs.push([lvl, msg]), versionWarned: null }
const chk = (v) => M.prototype.checkVersion.call(self, v)
const out = { same: chk(%r), warnedAfterSame: logs.length }
out.patchAhead = chk(%r)
out.patchAheadLogs = logs.length
out.minorAhead = chk('2.9.0'); out.minorLogs = logs.length
out.again = chk('2.9.0'); out.againLogs = logs.length
out.major = chk('3.8.0')
out.none = chk(undefined); out.noneLogs = logs.length
console.log(JSON.stringify(out))
""" % ((MOD / "src" / "main.js").as_uri(), mod, mm(mod) + ".9")
        r = subprocess.run(["node", "--input-type=module", "-e", js], cwd=str(MOD), capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr[-800:])
        o = json.loads(r.stdout.strip().splitlines()[-1])
        self.assertEqual((o["same"], o["warnedAfterSame"]), ("ok", 0))
        self.assertEqual((o["patchAhead"], o["patchAheadLogs"]), ("ok", 0), "a patch release of the player (module x.y.0, player x.y.9) is ok and silent")
        self.assertEqual((o["minorAhead"], o["minorLogs"]), ("mismatch", 1))
        self.assertEqual((o["again"], o["againLogs"]), ("mismatch", 1), "one warning per distinct player version")
        self.assertEqual(o["major"], "mismatch")
        self.assertEqual(o["none"], "unknown")
        app_result = subprocess.run(["node", "--input-type=module", "-e", f"import M from {(MOD / 'src' / 'main.js').as_uri()!r}; const s={{log:()=>{{}},versionWarned:null}}; console.log(M.prototype.checkVersion.call(s, {app!r}))"],
                                    cwd=str(MOD), capture_output=True, text=True, timeout=60)
        self.assertEqual(app_result.stdout.strip(), "ok", f"player {app} with module {mod}: {app_result.stdout} {app_result.stderr[-300:]}")

    def test_mp_test_only_follows_a_new_test_time(self):
        """mp_test (2.7.5/2.7.6): the module has no OSC input; it reads test_message + test_sent_at from /api/state and must not show an old time as a new test."""
        if not shutil.which("node") or not (MOD / "node_modules" / "@companion-module").is_dir():
            self.skipTest("node or companion-module/node_modules is not available")
        js = """
import M from %r
const self = { state: {}, testSeenAt: null, testShown: '' }
const v = (st) => { self.state = st; return M.prototype.testValue.call(self) }
const out = []
out.push(v({}))                                                  // no test yet
out.push(v({ test_message: '10:00:00' }))                        // a message without a send time (player rc1): not shown
out.push(v({ test_message: '10:00:00', test_sent_at: 5.5 }))     // a new test
out.push(v({ test_message: '10:00:00', test_sent_at: 5.5 }))     // the same poll again: unchanged
out.push(v({ test_message: '10:00:09', test_sent_at: 14.5 }))    // another test
out.push(v({ test_message: '10:00:09', test_sent_at: 14.5 }))
out.push(v({ test_message: '', test_sent_at: null }))            // the player cleared it
out.push(v({ test_message: '10:00:09', test_sent_at: 14.5 }))    // the same old result reported again must show as a test again only because it is a new "seen" time
console.log(JSON.stringify(out))
""" % (MOD / "src" / "main.js").as_uri()
        r = subprocess.run(["node", "--input-type=module", "-e", js], cwd=str(MOD), capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr[-800:])
        self.assertEqual(json.loads(r.stdout.strip().splitlines()[-1]), ["", "", "10:00:00", "10:00:00", "10:00:09", "10:00:09", "", "10:00:09"])

    def run_module_prefix(self, config_prefix, reported):
        """The real startPolling / refreshStructure of main.js against a mock player; returns the variable IDs it declared after each prefix the player reports."""
        js = """
import M from %r
const log = []
const o = Object.create(M.prototype)
let reported = %s
Object.assign(o, { config: %s, varNames: [], rev: null, fails: 0, status: 'ok', busy: false, state: {}, playlists: [], lastPresetKey: '', slotCache: {} })
o.log = () => {}
o.updateStatus = () => {}
o.checkAllFeedbacks = () => {}
o.setActionDefinitions = () => {}
o.setFeedbackDefinitions = () => {}
o.applyPresets = () => { log.push(['presets', o.prefix]) }
o.setVariableValues = () => {}
o.setVariableDefinitions = (d) => log.push(['defs', Object.keys(d)])
o.api = async (path) => {
  if (path === '/api/state') return { rev: 1, player_version: '2.8.0', live_name: '-', variable_prefix: reported }
  if (path === '/api/variables') return { vars: [{ name: 'live_name', value: '-', info: 'Live' }] }
  return []
}
o.startPolling()
const wait = (ms) => new Promise((r) => setTimeout(r, ms))
await wait(400)
const first = log.filter((x) => x[0] === 'defs').map((x) => x[1])
reported = %s
await wait(400)
o.stopPolling()
const all = log.filter((x) => x[0] === 'defs').map((x) => x[1])
console.log(JSON.stringify({ first: first[first.length - 1], last: all[all.length - 1], declared: all.length, presets: log.filter((x) => x[0] === 'presets').map((x) => x[1]) }))
process.exit(0)
""" % ((MOD / "src" / "main.js").as_uri(), json.dumps(reported[0]), json.dumps({"host": "127.0.0.1", "port": 8080, "poll": 100, **({"prefix": config_prefix} if config_prefix is not None else {})}), json.dumps(reported[1]))
        r = subprocess.run(["node", "--input-type=module", "-e", js], cwd=str(MOD), capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr[-1200:])
        return json.loads(r.stdout.strip().splitlines()[-1])

    def test_module_declares_its_variables_with_the_prefix_the_player_reports(self):
        if not shutil.which("node") or not (MOD / "node_modules" / "@companion-module").is_dir():
            self.skipTest("node or companion-module/node_modules is not available")
        o = self.run_module_prefix("mp_", ("show_", "stage_"))
        self.assertIn("show_live_name", o["first"], o)
        self.assertIn("show_test", o["first"])
        self.assertTrue(all(k.startswith("show_") for k in o["first"]), "no variable keeps another prefix: " + str(o["first"][:5]))
        self.assertIn("stage_live_name", o["last"], "declared again when the player reports another prefix")
        self.assertTrue(all(k.startswith("stage_") for k in o["last"]))
        self.assertIn("stage_", o["presets"], "the presets that show variables are made again with the new prefix")

    def test_module_falls_back_when_the_player_reports_no_prefix(self):
        if not shutil.which("node") or not (MOD / "node_modules" / "@companion-module").is_dir():
            self.skipTest("node or companion-module/node_modules is not available")
        o = self.run_module_prefix(None, (None, None))
        self.assertTrue(all(k.startswith("mp_") for k in o["first"]), "no prefix anywhere: mp_  " + str(o["first"][:4]))
        o = self.run_module_prefix("foh_", (None, None))
        self.assertTrue(all(k.startswith("foh_") for k in o["first"]), "the module's own prefix when the player reports none")
        o = self.run_module_prefix("mp_", ("not valid!", "mp_"))
        self.assertTrue(all(k.startswith("mp_") for k in o["first"]), "an invalid reported prefix is ignored")


if __name__ == "__main__":
    unittest.main(verbosity=2)
