"""State identity (docs/split-plan.md 4.2 / 4.6 step 1): the containers that other modules import BY NAME must never be rebound.

Run:  SDL_AUDIODRIVER=dummy python3 -I tests/test_state_identity.py

Records id() of every stable container right after import and asserts that it is unchanged after load() (both the current
format and the old one that goes through migrate_old), stop_all() with a live track, set_device(), and a rescan of the library.
It also checks that the content really was replaced in place (a load must not leave stale entries behind).
Where the containers live (cpl.state once it exists, otherwise the application module) is found by looking, so the test
works before and after step 2 of P4; once cpl.state exists the application module must hold the very same objects.
"""
import importlib, json, os, shutil, sys, tempfile, unittest, wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from harness.appcopy import copy_app   # noqa: E402
from harness.appload import load_app  # noqa: E402

os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
SRC = Path(__file__).resolve().parent.parent / "player.py"
CONTAINERS = ["playlists", "FOLDER_COLORS", "FOLDER_ICONS", "FOLDER_FLAGS", "LIBDIRS", "library", "focus", "decks", "ISSUES", "DEV_MISSING", "DURS"]


def make_wav(path, seconds=3, rate=22050):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(bytes(int(seconds * rate) * 2))


class StateIdentity(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="identtest-"))
        (self.dir / "media" / "library").mkdir(parents=True)
        (self.dir / "config.json").write_text('{"http_port": 18192, "osc_in_port": 18193}')
        copy_app(self.dir, SRC.parent)
        for n in ("a.wav", "b.wav"):
            make_wav(self.dir / "media" / "library" / n)
        self.app = load_app(self.dir)
        self.P = self.app.P
        L = importlib.import_module("cpl.loudness")
        real_loud = L.request_loudness
        L.request_loudness = lambda: None
        S = importlib.import_module("cpl.state")
        S.on_save[:] = [L.request_loudness if h is real_loud else h for h in S.on_save]      # save() reaches it through the hook list
        self.P.init_mixer(None)
        self.P.scan_library()
        self.has_state = (self.dir / "cpl" / "state.py").is_file()
        self.home = importlib.import_module("cpl.state") if self.has_state else self.P
        self.ids = {n: id(getattr(self.home, n)) for n in CONTAINERS}

    async def asyncTearDown(self):
        try:
            self.P.stop_all()
            self.P.pygame.mixer.quit()
        finally:
            self.app.unload()
            shutil.rmtree(self.dir, ignore_errors=True)

    def same(self, where):
        for n in CONTAINERS:
            self.assertEqual(id(getattr(self.home, n)), self.ids[n], f"{n} was rebound by {where}")
            if self.has_state:                                      # the importers hold the same object
                self.assertIs(getattr(self.P, n), getattr(self.home, n), f"legacy.{n} is not state.{n} after {where}")

    def test_identity_after_import(self):
        self.same("import")

    def test_load_current_format(self):
        (self.dir / "playlists.json").write_text(json.dumps({"version": 2, "playlists": [{"name": "X", "tracks": ["a.wav"]}], "known": ["a.wav", "b.wav"]}))
        self.P.playlists[:] = [{"name": "stale", "tracks": []}, {"name": "stale2", "tracks": []}]
        self.P.load()
        self.same("load()")
        self.assertEqual([p["name"] for p in self.P.playlists], ["X"])               # replaced in place, nothing stale left

    def test_load_old_format_goes_through_migrate_old(self):
        (self.dir / "playlists.json").write_text(json.dumps({"playlists": [{"name": "Old", "tracks": ["a.wav"]}]}))
        self.P.playlists[:] = [{"name": "stale", "tracks": []}]
        self.P.load()
        self.same("load() of the old format")
        self.assertIn("Old", [p["name"] for p in self.P.playlists])
        self.assertNotIn("stale", [p["name"] for p in self.P.playlists])

    def test_load_without_a_file(self):
        self.P.playlists[:] = [{"name": "stale", "tracks": []}]
        self.P.load()
        self.same("load() without playlists.json")
        self.assertEqual(self.P.playlists, [])

    async def test_stop_all_set_device_and_rescan(self):
        self.P.playlists[:] = [{"name": "A", "tracks": ["a.wav", "b.wav"]}]
        await self.P.ensure_loaded(str(self.P.LIB / "a.wav"))
        self.assertTrue(self.P.play(0, 0))
        self.assertTrue(self.P.decks)
        self.P.stop_all()
        self.same("stop_all()")
        await self.P.ensure_loaded(str(self.P.LIB / "a.wav"))
        self.assertTrue(self.P.play(0, 0))
        self.P.set_device(None)
        self.same("set_device()")
        make_wav(self.dir / "media" / "library" / "c.wav")
        self.P.rescan_library()
        self.same("a rescan")
        self.assertIn("c.wav", self.P.library)


if __name__ == "__main__":
    unittest.main(verbosity=2)
