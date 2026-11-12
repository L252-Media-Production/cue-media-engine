"""2.8.0 follow-up: what ships. The Watchdog is ON in a fresh default config, the engine harness switches it off only through its explicit hook, the test hooks
are inert without their environment variables, and a Live output that is missing (the player left on the dummy output) is reported, not restarted in a loop."""
import inspect
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from harness.engine import EngineCase                      # noqa: E402
from harness.appload import load_app                       # noqa: E402
from harness.appcopy import copy_app                       # noqa: E402
from harness.instance import PROJECT                       # noqa: E402


class ShippedDefaults(unittest.TestCase):
    def test_a_fresh_default_config_has_the_watchdog_on(self):
        d = Path(tempfile.mkdtemp(prefix="deftest-"))
        argv = list(sys.argv)
        try:
            (d / "media" / "library").mkdir(parents=True)
            (d / "config.json").write_text('{"http_port": 18196, "osc_in_port": 18197}')       # no watchdog key, no state.json, no overrides
            copy_app(d, PROJECT)
            app = load_app(d)
            try:
                CFG = app.mod("config").CFG
                self.assertIs(CFG["watchdog"], True)
                self.assertIs(CFG["health_preview_amber"], True)
                self.assertIs(CFG["push_enabled"], False)
            finally:
                app.unload()
        finally:
            sys.argv[:] = argv
            shutil.rmtree(d, ignore_errors=True)

    def test_the_harness_turns_it_off_only_through_its_explicit_hook(self):
        self.assertIs(EngineCase.WATCHDOG, False)
        src = inspect.getsource(EngineCase.asyncSetUp)
        self.assertIn('P.CFG["watchdog"] = self.WATCHDOG', src)
        self.assertNotIn('["watchdog"] = False', src)

    def test_the_default_in_the_source_of_config_is_true(self):
        text = (PROJECT / "cpl" / "config.py").read_text()
        self.assertRegex(text, r'"watchdog": True,')


class HooksInert(EngineCase):
    async def test_the_disk_hook_has_no_effect_without_its_variable(self):
        os.environ.pop("CP_TEST_DISK_FREE_GB", None)
        self.P._disk_read()
        real = shutil.disk_usage(self.P.MEDIA)
        got = self.P._hdisk["v"]
        self.assertLess(abs(got["total"] - real.total), 1024 ** 2)
        self.assertGreater(got["total"], 1024 ** 3)                 # not the fake 500 GB default

    async def test_the_disk_hook_works_when_set(self):
        os.environ["CP_TEST_DISK_FREE_GB"] = "2,500"
        try:
            self.P._disk_read()
            self.assertEqual(self.P._hdisk["v"]["free"], 2 * 1024 ** 3)
        finally:
            os.environ.pop("CP_TEST_DISK_FREE_GB", None)

    async def test_the_disk_hook_keeps_the_real_total_unless_told_otherwise(self):
        real = shutil.disk_usage(self.P.MEDIA).total
        os.environ["CP_TEST_DISK_FREE_GB"] = "2"
        try:
            self.P._disk_read()
            self.assertEqual(self.P._hdisk["v"], {"free": 2 * 1024 ** 3, "total": real})
            os.environ["CP_TEST_DISK_TOTAL_GB"] = "100"
            self.P._disk_read()
            self.assertEqual(self.P._hdisk["v"], {"free": 2 * 1024 ** 3, "total": 100 * 1024 ** 3})
        finally:
            os.environ.pop("CP_TEST_DISK_FREE_GB", None)
            os.environ.pop("CP_TEST_DISK_TOTAL_GB", None)

    async def test_no_stall_route_without_the_variable(self):
        src = (PROJECT / "cpl" / "legacy.py").read_text()
        self.assertIn('if os.environ.get("CP_TEST_WATCHDOG"):', src)


class DummyOutput(EngineCase):
    WATCHDOG = True

    async def test_missing_live_output_is_bad_and_the_watchdog_never_restarts(self):
        await self.load("a.wav")
        self.S.DEV_MISSING["output"] = "Dante USB"                  # what main() sets when the saved device was not there: the player is on the default / dummy output
        self.P.CFG["audio_device"] = None
        self.assertTrue(self.P.play(0, 0))
        self.P.HB.poll = lambda: None                               # the dummy output never completes a heartbeat in this test
        self.inits = []
        real = self.P.init_mixer
        self.patch("init_mixer", lambda dev: (self.inits.append(dev), real(dev))[1])
        self.logs = []
        self.P.WD.log = self.logs.append
        for s in range(0, 600):
            self.at(s * 0.1)                                        # 60 s: six times the stall window
        self.assertEqual(self.inits, [], self.logs)
        self.assertEqual(self.logs, [])
        self.assertEqual(self.P.WD.total, 0)
        rep = self.P.health_report(force=True)
        chk = {c["id"]: c for c in rep["checks"]}
        self.assertEqual((chk["live_output"]["status"], rep["state"]), ("bad", "problem"))
        self.assertIn("(Dante USB) is not available", chk["live_output"]["text"])
        self.assertEqual(chk["audio_engine"]["status"], "ok")        # not a stall: the Live output check says what is wrong, and the restart limit is never touched
        self.assertFalse(self.P.WD.gave_up)

    async def test_a_real_stall_still_restarts_when_the_output_is_there(self):
        await self.load("a.wav")
        self.assertTrue(self.P.play(0, 0))
        self.P.HB.poll = lambda: None
        self.inits = []
        real = self.P.init_mixer
        self.patch("init_mixer", lambda dev: (self.inits.append(dev), real(dev))[1])
        self.at(0.0)
        for s in range(1, 105):
            self.at(s * 0.1)
        self.assertEqual(len(self.inits), 1)


if __name__ == "__main__":
    unittest.main()
