"""2.8.1 track cache limit, in-process with the fake clock and fake /proc/meminfo files.

The limit is the smallest of cache_mb, 25 % of the machine's RAM and the RAM minus 1 GB; least recently used tracks are dropped first, but never a
track that is playing (or fading), the track that follows the live one, the cue while something plays, the live track's trigger targets or the
previewed file. A track larger than the whole limit plays without being cached (one WARNING); a MemoryError sheds what is not in use and tries again.
Decoded audio is 48 kHz / 16-bit / stereo = 192,000 bytes per second; the test WAVs are 22.05 kHz mono and are converted on load.
"""
import asyncio
import contextlib
import io
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from harness.engine import EngineCase          # noqa: E402

MIB, GIB = 1048576, 1024 ** 3
BPS = 192000


def meminfo(d, total_gib, avail_gib=None, name="meminfo"):
    """A fake /proc/meminfo (kB values, like the kernel's)."""
    total_kb = int(total_gib * GIB / 1024)
    avail_kb = int((avail_gib if avail_gib is not None else total_gib * 0.7) * GIB / 1024)
    p = Path(d) / name
    p.write_text(f"MemTotal:       {total_kb} kB\nMemFree:        {avail_kb // 2} kB\nMemAvailable:   {avail_kb} kB\nBuffers:          1234 kB\n")
    return str(p)


class FakeSnd:
    """Stands in for a decoded pygame Sound where only its size matters (the warm-up planning tests)."""
    def __init__(self, secs):
        self.secs = secs

    def get_length(self):
        return self.secs


class CacheCase(EngineCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.cache = self.app.mod("cache")
        self.warm = self.app.mod("warm")
        self.machine(31)

    def machine(self, total_gib, avail_gib=None, sysconf=False):
        self.cache.set_machine(meminfo(self.dir, total_gib, avail_gib) if total_gib else str(self.dir / "no-meminfo"), sysconf=sysconf)

    def path(self, name):
        return str(self.P.LIB / name)

    def in_cache(self, *names):
        return [n for n in names if self.cache.has(self.path(n))]

    def quiet(self):
        return contextlib.redirect_stdout(io.StringIO())


class LimitRules(CacheCase):
    def test_smallest_of_three_rules(self):
        lp = self.cache.limit_parts
        for setting, gib, want, by in [(12288, 4, 1 * GIB, "share"), (12288, 16, 4 * GIB, "share"), (12288, 31, int(31 * GIB * 0.25), "share"),
                                       (768, 4, 768 * MIB, "setting"), (768, 31, 768 * MIB, "setting"), (2048, 2, 512 * MIB, "share"),
                                       (100000, 1.2, int(0.2 * GIB), "spare")]:
            r = lp(setting, int(gib * GIB))
            self.assertEqual((r["limit"], r["by"]), (want, by), (setting, gib, r))

    def test_floor_and_bad_setting(self):
        self.assertEqual(self.cache.limit_parts(10, None)["limit"], 64 * MIB)        # the old 64 MB floor of cache_mb
        self.assertEqual(self.cache.limit_parts(100000, int(0.5 * GIB))["limit"], 64 * MIB)
        self.assertEqual(self.cache.limit_parts("nonsense", None)["limit"], 768 * MIB)

    def test_read_from_meminfo(self):
        for gib in (4, 16, 31):
            self.machine(gib)
            self.P.CFG["cache_mb"] = 12288
            self.assertEqual(self.cache.machine_ram(), int(gib * GIB / 1024) * 1024)
            self.assertEqual(self.cache.limit_bytes(), min(12288 * MIB, int(self.cache.machine_ram() * 0.25), self.cache.machine_ram() - GIB))

    def test_no_meminfo_macos(self):
        self.machine(None, sysconf=False)                                            # no /proc/meminfo and no sysconf: only the setting
        self.P.CFG["cache_mb"] = 12288
        self.assertIsNone(self.cache.machine_ram())
        self.assertEqual(self.cache.limit_bytes(), 12288 * MIB)
        self.assertIsNone(self.cache.mem_available())
        self.cache.set_machine(str(self.dir / "no-meminfo"), sysconf=True)          # macOS: no /proc/meminfo, os.sysconf gives the RAM
        total = self.cache.machine_ram()
        self.assertTrue(total is None or total > 0)
        if total:
            self.assertLessEqual(self.cache.limit_bytes(), int(total * 0.25))

    def test_header_readout_uses_the_limit(self):
        self.machine(4)
        self.P.CFG["cache_mb"] = 12288
        self.assertEqual(self.cache.mem_info()["cache_budget"], GIB)
        self.fake.t += 2
        self.assertEqual(self.warm.ram_info()["budget_mb"], 1024.0)


class NucFixture(CacheCase):
    """The NUC's library: 52 tracks, 6.1 GB decoded in all, cache_mb 12288 (the header showed 12.0 GB). Fake sounds: the warm-up planning only."""
    N, TOTAL = 52, 6.1 * GIB
    LIB = {"a.wav": 1}
    PLAYLISTS = [{"name": "A", "tracks": []}]

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.P.CFG["cache_mb"] = 12288
        per = self.TOTAL / BPS / self.N
        self.ids = [f"t{i:02d}.flac" for i in range(self.N)]
        self.lens = {f: per * (0.7 + 0.6 * (i % 2)) for i, f in enumerate(self.ids)}          # long and short tracks, same total
        self.P.library.clear()
        self.P.library.update({f: 1 for f in self.ids})
        self.P.playlists[:] = [{"name": "Show", "tracks": list(self.ids[:30])}, {"name": "Second", "tracks": list(self.ids[30:])}]
        for f in self.ids:
            self.P.DURS[f] = (1, 1, self.lens[f])
        self.order = []

        async def fake_load(path):
            snd = self.cache.cached(path)
            if snd is None:
                self.order.append(Path(path).name)
                snd = FakeSnd(self.lens[Path(path).name])
                self.cache.cache_put(path, snd)
            return snd
        self.patched.append((self.warm, "ensure_loaded", self.warm.ensure_loaded))
        self.warm.ensure_loaded = fake_load
        self.real_warm = next(o for m, n, o in self.patched if n == "_warm_loop")

    async def test_31_gb_keeps_everything(self):
        self.machine(31)
        await self.real_warm()
        self.assertEqual(len(self.order), self.N)
        self.assertEqual(sorted(self.order), sorted(self.ids))
        self.assertEqual(len(self.cache._cache), self.N)                               # nothing evicted
        self.assertAlmostEqual(self.cache.cache_bytes() / GIB, 6.1, delta=0.01)
        self.assertLess(self.cache.cache_bytes(), self.cache.fill_bytes())
        self.fake.t += 2
        self.assertFalse(self.warm.ram_info()["full"])

    async def test_4_gb_stops_at_the_fill_level(self):
        self.machine(4)
        await self.real_warm()
        lim = self.cache.limit_bytes()
        self.assertEqual(lim, GIB)
        self.assertLessEqual(self.cache.cache_bytes(), lim)
        self.assertLess(len(self.order), self.N)
        self.assertEqual(self.order, self.ids[:len(self.order)])                      # in playlist order from the cue, and then it stopped
        self.assertEqual(len(self.cache._cache), len(self.order))                     # nothing was loaded and then dropped
        self.assertGreater(self.cache.cache_bytes(), self.cache.fill_bytes() - max(self.lens.values()) * BPS)     # stopped at the first track that did not fit
        self.assertGreater(self.cache.cache_bytes() + self.lens[self.ids[len(self.order)]] * BPS, self.cache.fill_bytes())

    async def test_order_from_the_cue_and_soon_first(self):
        self.machine(4)
        self.P.focus[:] = [0, 10]
        await self.real_warm()
        self.assertEqual(self.order[0], self.ids[10])                                   # the cue first, then onwards
        self.assertEqual(self.order[1:4], self.ids[11:14])


class Protection(CacheCase):
    """64 MB limit (the floor). 120 s at 48 kHz stereo = 23.04 MB, so two tracks fit and a third drops the least recently used."""
    LIB = {"a.wav": 120, "b.wav": 120, "c.wav": 120, "d.wav": 120, "e.wav": 120}
    PLAYLISTS = [{"name": "A", "tracks": ["a.wav", "b.wav", "c.wav", "d.wav"], "mode": "loop_playlist"}, {"name": "B", "tracks": ["e.wav"]}]

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.P.CFG["cache_mb"] = 64

    async def test_lru_order(self):
        await self.load("a.wav", "b.wav")
        self.cache.cached(self.path("a.wav"))                                         # a is used again: b is now the oldest
        await self.load("c.wav")
        self.assertEqual(self.in_cache("a.wav", "b.wav", "c.wav"), ["a.wav", "c.wav"])

    async def test_playing_and_next_are_never_dropped(self):
        await self.load("a.wav")
        self.assertTrue(self.P.play(0, 0))
        await self.load("b.wav")                                                      # the next track (loop playlist: b)
        self.P.focus[:] = [0, 0]
        for n in ("c.wav", "d.wav", "e.wav"):
            await self.load(n)
            self.assertEqual(self.in_cache("a.wav", "b.wav"), ["a.wav", "b.wav"], n)
            self.assertIn(n, self.in_cache(n))
        self.assertEqual(self.in_cache("c.wav", "d.wav"), [])                         # the others went, oldest first

    async def test_cue_and_crossfade_decks_are_kept(self):
        await self.load("a.wav", "c.wav")
        self.assertTrue(self.P.play(0, 0))
        self.assertTrue(self.P.play(0, 2, 3000))                                     # crossfade a -> c: both decks play
        self.assertEqual(len(self.P.decks), 2)
        self.P.focus[:] = [1, 0]
        await self.load("e.wav")                                                      # e is the cue
        await self.load("b.wav")                                                      # over the limit: something must go, but a, c and e are in use
        self.assertEqual(self.in_cache("a.wav", "c.wav", "e.wav"), ["a.wav", "c.wav", "e.wav"])

    async def test_previewed_track_is_kept(self):
        await self.load("d.wav", "a.wav")
        self.P.preview.fid = "d.wav"
        self.P.preview.status = {"state": "playing", "pos": 1.0, "dur": 120.0, "error": ""}
        self.assertTrue(self.P.play(0, 0))
        await self.load("c.wav")
        self.assertIn("d.wav", self.in_cache("d.wav"))
        self.P.preview.status = {"state": "stopped", "pos": 0.0, "dur": 0.0, "error": ""}

    async def test_nothing_playing_plain_lru(self):
        await self.load("a.wav", "b.wav", "c.wav")                                    # nothing live: the cue is not pinned (2.7.3 behaviour)
        self.assertEqual(self.in_cache("a.wav", "b.wav", "c.wav"), ["b.wav", "c.wav"])

    async def test_check_soon_asks_for_the_next_track(self):
        calls = []
        self.patch("request_warm", lambda: calls.append(1))
        await self.load("a.wav")
        self.assertTrue(self.P.play(0, 0))
        self.warm.check_soon()
        self.assertEqual(calls, [1])                                                  # b (next) is not decoded
        self.warm.check_soon()
        self.assertEqual(calls, [1])                                                  # at most once a second
        await self.load("b.wav")
        self.fake.t += 1.5
        self.warm.check_soon()
        self.assertEqual(calls, [1])                                                  # next and cue decoded: nothing to do



class WarmWhenFull(CacheCase):
    """100 s = 19.2 MB: three are past the fill level (80 % of 64 MB = 53.7 MB), a fourth is over the limit (67.1 MB)."""
    LIB = {"a.wav": 100, "b.wav": 100, "c.wav": 100, "d.wav": 100}
    PLAYLISTS = [{"name": "A", "tracks": ["a.wav", "b.wav", "c.wav", "d.wav"], "mode": "loop_playlist"}]

    async def test_warm_up_decodes_the_next_track_when_full(self):
        self.P.CFG["cache_mb"] = 64
        real = next(o for m, n, o in self.patched if n == "_warm_loop")
        await self.load("a.wav", "c.wav", "d.wav")
        self.assertTrue(self.P.play(0, 0))
        self.assertGreater(self.cache.cache_bytes(), self.cache.fill_bytes())        # past the fill level: the old warm-up would stop here
        await real()
        self.assertEqual(self.in_cache("a.wav", "b.wav"), ["a.wav", "b.wav"])        # b (next) decoded anyway, and a (playing) kept
        self.assertEqual(len(self.in_cache("c.wav", "d.wav")), 1)                    # one of the others made room
        self.assertLessEqual(self.cache.cache_bytes(), self.cache.limit_bytes())


class Oversize(CacheCase):
    LIB = {"big.wav": 400, "a.wav": 60}                                               # 400 s = 76.8 MB > 64 MB
    PLAYLISTS = [{"name": "A", "tracks": ["big.wav", "a.wav"]}]

    async def test_plays_uncached_with_one_warning(self):
        self.P.CFG["cache_mb"] = 64
        await self.load("a.wav")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            snd = await self.P.ensure_loaded(self.path("big.wav"))
            snd2 = await self.P.ensure_loaded(self.path("big.wav"))
        self.assertEqual(out.getvalue().count("WARNING"), 1, out.getvalue())
        self.assertIn("big.wav", out.getvalue())
        self.assertAlmostEqual(snd.get_length(), 400, delta=0.01)
        self.assertFalse(self.cache.has(self.path("big.wav")))
        self.assertTrue(self.cache.is_oversize(self.path("big.wav")))
        self.assertEqual(self.in_cache("a.wav"), ["a.wav"])                           # nothing else was dropped to make room
        self.assertEqual(snd.get_raw(), snd2.get_raw())
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertTrue(self.P.play(0, 0))
            for _ in range(50):
                if self.live() is not None:
                    break
                await asyncio.sleep(0.02)
        self.assertEqual(self.pt(), (0, 0))

    async def test_miss_has_the_same_samples_as_the_cached_path(self):
        self.P.CFG["cache_mb"] = 768
        cached = await self.P.ensure_loaded(self.path("big.wav"))
        self.assertTrue(self.cache.has(self.path("big.wav")))
        raw_cached = cached.get_raw()
        self.P.cache_drop(self.path("big.wav"))
        self.P.CFG["cache_mb"] = 64                                                  # now larger than the limit: a miss every time
        with self.quiet():
            self.assertTrue(self.P.play(0, 0))
            for _ in range(100):
                if self.live() is not None:
                    break
                await asyncio.sleep(0.02)
        self.assertEqual(self.pt(), (0, 0))
        self.assertFalse(self.cache.has(self.path("big.wav")))
        self.assertEqual(self.live().sound.get_raw(), raw_cached)                      # bit for bit the same audio


@unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg makes the compressed test file")
class CompressedMiss(CacheCase):
    LIB = {"a.wav": 1}
    PLAYLISTS = [{"name": "A", "tracks": []}]

    async def test_flac_miss_equals_cached(self):
        f = self.P.LIB / "tone.flac"
        subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=20:sample_rate=48000", "-ac", "2", str(f)], check=True)
        self.P.scan_library()
        self.P.CFG["cache_mb"] = 768
        a = (await self.P.ensure_loaded(str(f))).get_raw()
        self.P.cache_drop(str(f))
        self.P.CFG["cache_mb"] = 64
        self.cache.set_machine(meminfo(self.dir, 31), sysconf=False)
        b = (await self.P.ensure_loaded(str(f))).get_raw()                           # 3.8 MB: still cached at 64 MB, decoded again from the file
        self.assertEqual(a, b)


class OutOfMemory(CacheCase):
    LIB = {"a.wav": 60, "b.wav": 60, "c.wav": 60, "d.wav": 60}
    PLAYLISTS = [{"name": "A", "tracks": ["a.wav", "b.wav", "c.wav", "d.wav"]}]

    async def test_memory_error_sheds_and_retries(self):
        await self.load("a.wav", "b.wav")
        self.assertTrue(self.P.play(0, 0))                                            # a plays: it must survive the shed
        real = self.P.pygame.mixer.Sound
        n = {"left": 1}

        def flaky(*a, **k):
            if n["left"]:
                n["left"] -= 1
                raise MemoryError()
            return real(*a, **k)
        self.P.pygame.mixer.Sound = flaky
        out = io.StringIO()
        try:
            with contextlib.redirect_stdout(out):
                snd = await self.P.ensure_loaded(self.path("c.wav"))
        finally:
            self.P.pygame.mixer.Sound = real
        self.assertIsNotNone(snd)
        self.assertIn("WARNING: out of memory", out.getvalue())
        self.assertEqual(self.in_cache("a.wav", "b.wav", "c.wav"), ["a.wav", "c.wav"])    # b (not in use) was dropped, a (playing) kept
        self.assertEqual(self.pt(), (0, 0))

    async def test_memory_error_twice_is_a_load_error_not_a_crash(self):
        real = self.P.pygame.mixer.Sound

        def broke(*a, **k):
            raise MemoryError()
        self.P.pygame.mixer.Sound = broke
        try:
            with self.quiet():
                with self.assertRaisesRegex(RuntimeError, "not enough memory"):
                    await self.P.ensure_loaded(self.path("d.wav"))
                self.assertTrue(self.P.play(0, 3))                                    # the play path reports it like any load error
                for _ in range(50):
                    if not self.S.pending:
                        break
                    await asyncio.sleep(0.02)
        finally:
            self.P.pygame.mixer.Sound = real
        self.assertIsNone(self.S.pending)
        self.assertIn("not enough memory", self.S.LAST_LOAD_ERR[1])
        await self.load("a.wav")
        self.assertTrue(self.P.play(0, 0))                                            # and the player plays on
        self.assertEqual(self.pt(), (0, 0))

    async def test_memory_error_while_cutting_a_trim(self):
        await self.load("a.wav", "b.wav")
        self.P.playlists[0].setdefault("trims", {})
        self.P.set_trim(0, 0, {"in": 5.0})
        real = self.P.cut_sound
        n = {"left": 1}

        def flaky(*a):
            if n["left"]:
                n["left"] -= 1
                raise MemoryError()
            return real(*a)
        self.patch("cut_sound", flaky)
        with self.quiet():
            self.assertTrue(self.P.play(0, 0))
        self.assertEqual(self.pt(), (0, 0))
        self.approx(self.live().lo, 5.0)


class PeekNext(CacheCase):
    LIB = {"a.wav": 1, "b.wav": 1, "c.wav": 1, "d.wav": 1}
    PLAYLISTS = [{"name": "A", "tracks": ["a.wav", "b.wav", "c.wav"]}, {"name": "B", "tracks": ["d.wav"]}]

    def test_modes(self):
        plm = self.app.mod("playlists")
        pl = self.P.playlists[0]
        pl["mode"] = "loop_playlist"
        self.assertEqual([plm.peek_next(0, t) for t in range(3)], ["b.wav", "c.wav", "a.wav"])
        pl["mode"] = "next_playlist"
        self.assertEqual(plm.peek_next(0, 2), "d.wav")
        pl["mode"] = "stop"
        self.assertIsNone(plm.peek_next(0, 0))
        plm.set_end(0, 0, "loop")
        self.assertEqual(plm.peek_next(0, 0), "a.wav")
        plm.set_end(0, 0, "stop")
        pl["mode"] = "loop_playlist"
        self.assertIsNone(plm.peek_next(0, 0))

    def test_shuffle_peek_matches_and_changes_nothing(self):
        plm = self.app.mod("playlists")
        self.P.playlists[0]["mode"] = "shuffle"
        self.assertIsNone(plm.peek_next(0, 0))                                        # empty bag: drawn at the moment the track ends
        first = plm.next_in_order(0, 0)[0]                                            # fills the bag
        cur = first
        for _ in range(4):
            bag = list(plm._bag.get(0, []))
            want = plm.peek_next(0, cur)
            self.assertEqual(plm._bag.get(0, []), bag)                                # read only
            nxt = plm.next_in_order(0, cur)[0]
            if want is not None:
                self.assertEqual(self.P.playlists[0]["tracks"][nxt], want)
            cur = nxt


if __name__ == "__main__":
    unittest.main()
