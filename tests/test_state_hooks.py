"""Hook registration (docs/split-plan.md 4.5 gate item 8, and F2 / F3 / F6): the hooks of cpl.state are registered after the import,
and they are called at the right points. Run:  SDL_AUDIODRIVER=dummy python3 -I tests/test_state_hooks.py

  * S.on_change holds request_warm; S.on_save holds request_loudness; S.notify is not the default no-op (what is registered
    so far is listed in REGISTERED, which grows with each hook commit of step P4)
  * bump() raises rev by one and then runs the on_change hooks in order; save() runs on_save after bump(), after the file is written
"""
import asyncio, importlib, os, shutil, sys, tempfile, unittest, wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from harness.appcopy import copy_app   # noqa: E402
from harness.appload import load_app  # noqa: E402

os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
SRC = Path(__file__).resolve().parent.parent / "player.py"
REGISTERED = ["on_change", "on_save", "notify"]


class Hooks(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="hooktest-"))
        (self.dir / "media" / "library").mkdir(parents=True)
        (self.dir / "config.json").write_text('{"http_port": 18194, "osc_in_port": 18195}')
        copy_app(self.dir, SRC.parent)
        self.app = load_app(self.dir)
        self.P = self.app.P
        self.S = self.app.mod("state")

    def tearDown(self):
        self.app.unload()
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_hooks_are_registered_after_import(self):
        S, P = self.S, self.P
        if "on_change" in REGISTERED:
            self.assertIn(self.app.mod("warm").request_warm, S.on_change)
        if "on_save" in REGISTERED:
            self.assertIn(self.app.mod("loudness").request_loudness, S.on_save)
        if "notify" in REGISTERED:
            self.assertIsNot(S.notify, S._no_notify)
            self.assertIs(S.notify, P.push)

    def test_bump_raises_rev_then_runs_on_change_in_order(self):
        S = self.S
        seen, saved = [], list(S.on_change)
        try:
            S.on_change[:] = [lambda: seen.append(("a", S.rev)), lambda: seen.append(("b", S.rev))]
            r = S.rev
            self.P.bump()
            self.assertEqual(seen, [("a", r + 1), ("b", r + 1)])
        finally:
            S.on_change[:] = saved

    @unittest.skipUnless("on_save" in REGISTERED, "on_save is added in a later commit of P4")
    def test_save_runs_on_save_after_the_file_and_after_bump(self):
        S, P = self.S, self.P
        seen, saved_s, saved_c = [], list(S.on_save), list(S.on_change)
        try:
            S.on_change[:] = [lambda: seen.append(("bump", P.DATA.exists()))]
            S.on_save[:] = [lambda: seen.append(("saved", S.rev))]
            r = S.rev
            P.save()
            self.assertEqual(seen, [("bump", True), ("saved", r + 1)])
        finally:
            S.on_change[:] = saved_c
            S.on_save[:] = saved_s


def _wav(path, secs=2, rate=22050):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(bytes(int(secs * rate) * 2))


class RealHookPath(unittest.IsolatedAsyncioTestCase):
    """The hooks as the application really uses them: NOTHING in S.on_change / S.on_save is replaced. The spies sit INSIDE the real functions
    (request_warm starts `_warm_loop`, request_loudness asks `loud_pending`); both are looked up by name at call time, so a spy on them
    still lets the real function run, and it is only reached if the hook list really calls request_warm / request_loudness."""
    IDS = ["a.wav", "b.wav", "c.wav"]

    async def asyncSetUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="hookreal-"))
        (self.dir / "media" / "library").mkdir(parents=True)
        (self.dir / "config.json").write_text('{"http_port": 18196, "osc_in_port": 18197}')
        copy_app(self.dir, SRC.parent)
        for n in self.IDS:
            _wav(self.dir / "media" / "library" / n)
        self.app = load_app(self.dir)
        self.P, self.S = self.app.P, self.app.mod("state")
        P = self.P
        self.hooks_before = (list(self.S.on_change), list(self.S.on_save))
        self.warm_calls, self.loud_calls = [], []
        L = self.app.mod("loudness")
        W = self.W = self.app.mod("warm")
        real_warm_loop, real_pending = W._warm_loop, L.loud_pending

        async def warm_spy():
            self.warm_calls.append(1)
            return await real_warm_loop()

        def loud_spy():
            self.loud_calls.append(1)
            return real_pending()
        W._warm_loop, L.loud_pending = warm_spy, loud_spy
        P.init_mixer(None)
        (self.dir / "playlists.json").write_text('{"version": 2, "playlists": [{"name": "A", "tracks": %s}], "known": %s}' % (str(self.IDS).replace("'", '"'), str(self.IDS).replace("'", '"')))

    async def asyncTearDown(self):
        try:
            t = self.W._warm["task"]
            if t and not t.done():
                await asyncio.wait_for(t, 10)
            self.P.stop_all()
            self.P.pygame.mixer.quit()
        finally:
            self.app.unload()
            shutil.rmtree(self.dir, ignore_errors=True)

    async def settle(self):
        t = self.W._warm["task"]
        if t:
            await asyncio.wait_for(t, 20)
        await asyncio.sleep(0.05)

    async def test_the_hook_lists_are_untouched_and_hold_the_real_functions(self):
        self.assertEqual(self.S.on_change, [self.app.mod("warm").request_warm])
        self.assertEqual(self.S.on_save, [self.app.mod("loudness").request_loudness])

    async def test_load_warms_the_playlist_and_asks_for_loudness(self):
        P = self.P
        P.load()                                     # ends with save() -> bump() -> on_change, then on_save
        self.assertEqual((list(self.S.on_change), list(self.S.on_save)), self.hooks_before, "a hook list changed")
        await self.settle()
        self.assertGreaterEqual(len(self.warm_calls), 1, "load() did not reach request_warm through the hook")
        self.assertGreaterEqual(len(self.loud_calls), 1, "load() / save() did not reach request_loudness through the hook")
        for fid in self.IDS:
            self.assertIsNotNone(P.cached(str(P.LIB / fid)), f"{fid} was not decoded by the warm-up")

    async def test_a_playlist_change_through_bump_starts_a_new_warm_up(self):
        P = self.P
        P.load()
        await self.settle()
        n = len(self.warm_calls)
        _wav(self.dir / "media" / "library" / "d.wav")
        P.scan_library()
        P.playlists[0]["tracks"].append("d.wav")
        self.assertIsNone(P.cached(str(P.LIB / "d.wav")))
        r = self.S.rev
        P.bump()                                     # what every playlist edit ends with
        self.assertEqual(self.S.rev, r + 1)
        await self.settle()
        self.assertEqual(len(self.warm_calls), n + 1, "bump() did not reach request_warm through the hook")
        self.assertIsNotNone(P.cached(str(P.LIB / "d.wav")), "the new track was not decoded")

    async def test_save_asks_for_loudness_after_the_file_is_written(self):
        P = self.P
        P.load()
        await self.settle()
        n = len(self.loud_calls)
        if P.DATA.exists():
            P.DATA.unlink()
        P.save()
        self.assertTrue(P.DATA.exists())
        self.assertEqual(len(self.loud_calls), n + 1, "save() did not reach request_loudness through the hook")


if __name__ == "__main__":
    unittest.main(verbosity=2)
