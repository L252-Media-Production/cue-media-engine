"""RAM indicator data (2.7.3 Phase 1), in-process with the fake clock: in / loading / out transitions, the `full` flag, the 1 s cache,
and that reading never changes the LRU order (so looking at the indicator can never decide which track is dropped).
Sizes: the mixer decodes to 48 kHz stereo 16-bit, so 120 s = 23.04 MB and 100 s = 19.2 MB; the budget has a 64 MiB floor (67.1 MB), so a + b + c (65.3 MB, 97 %) fill it and a fourth evicts the oldest."""
import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from harness.engine import EngineCase          # noqa: E402


class RamInfo(EngineCase):
    LIB = {"a.wav": 120, "b.wav": 120, "c.wav": 100, "d.wav": 120}
    PLAYLISTS = [{"name": "A", "tracks": ["a.wav", "b.wav", "c.wav", "d.wav"]}]

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.warm = self.app.mod("warm")
        self.cache = self.app.mod("cache")
        self.P.CFG["cache_mb"] = 64

    def refresh(self):
        self.fake.t += 1.1                                  # the page-facing numbers are cached for 1 s
        return self.warm.ram_info(), self.warm.ram_states()

    async def test_out_loading_in(self):
        info, st = self.refresh()
        self.assertEqual((info["tracks_total"], info["tracks_in_ram"], info["full"]), (4, 0, False))
        self.assertEqual(set(st.values()), {"out"})
        task = asyncio.ensure_future(self.P.ensure_loaded(str(self.P.LIB / "a.wav")))
        await asyncio.sleep(0)                              # the load is in flight (WAV decode runs in an executor)
        info, st = self.refresh()
        self.assertEqual(st["a.wav"], "loading")
        self.assertTrue(info["loading"])
        await task
        info, st = self.refresh()
        self.assertEqual((st["a.wav"], st["b.wav"], info["tracks_in_ram"]), ("in", "out", 1))

    async def test_full_flag(self):
        await self.load("a.wav", "b.wav", "c.wav")
        info, st = self.refresh()
        self.assertGreaterEqual(info["used_mb"], 0.95 * info["budget_mb"], info)
        self.assertEqual(st["d.wav"], "out")
        self.assertTrue(info["full"], info)
        self.P.playlists[0]["tracks"].remove("d.wav")       # everything of the show is in RAM: nothing is being dropped, so not "full"
        info, st = self.refresh()
        self.assertEqual((info["tracks_total"], info["tracks_in_ram"], info["full"]), (3, 3, False), info)
        self.P.playlists[0]["tracks"].append("d.wav")
        await self.load("d.wav")                            # the fourth evicts the oldest (a)
        info, st = self.refresh()
        self.assertEqual((st["a.wav"], st["d.wav"], info["tracks_in_ram"]), ("out", "in", 3))
        self.assertTrue(info["full"], info)

    async def test_reading_does_not_touch_lru_order(self):
        await self.load("a.wav", "b.wav", "c.wav")
        before = list(self.cache._cache)
        for _ in range(5):
            self.refresh()
        from aiohttp.test_utils import make_mocked_request
        resp = await self.P.h_lists(make_mocked_request("GET", "/api/playlists"))
        self.assertIn(b'"ram": "in"', resp.body)
        self.assertEqual(list(self.cache._cache), before)   # same order as before reading
        await self.load("d.wav")
        self.assertNotIn(str(self.P.LIB / "a.wav"), self.cache._cache)    # the oldest went, not something we "touched" by looking
        self.assertIn(str(self.P.LIB / "b.wav"), self.cache._cache)

    async def test_one_second_cache_and_cost(self):
        info, _ = self.refresh()
        await self.load("a.wav")
        self.assertEqual(self.warm.ram_info()["tracks_in_ram"], info["tracks_in_ram"])   # still the cached numbers inside 1 s
        self.assertEqual(self.refresh()[0]["tracks_in_ram"], 1)
        self.P.playlists[0]["tracks"][:] = ["a.wav", "b.wav", "c.wav", "d.wav"] * 125     # 500 tracks, four files
        t0 = time.perf_counter()
        for _ in range(200):
            self.refresh()
        per = (time.perf_counter() - t0) / 200 * 1000
        print(f"\nram_info + ram_states recompute, 500-track playlist: {per:.3f} ms each")
        self.assertLess(per, 5)
