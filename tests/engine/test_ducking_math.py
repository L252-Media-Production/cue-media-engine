"""Gap 6 (docs/split-plan.md 5.4): the ducking numbers.

Part 1, pure functions (cpl.dsp): golden vectors for duck_key (RMS of the louder channel per 10 ms) and duck_curve (the dB of reduction per 10 ms, with the
signature duck_curve(key, level, ratio, threshold_db, hold) introduced in split step P3), hold mode on and off, and the limits.
Part 2, the duck loop with the fake clock: every iteration of _duck_loop is one 10 ms step of the fake clock, so attack and release follow
gr(k) = target * (1 - exp(-k * 10 ms / attack)) and gr(k) = gr0 * exp(-k * 10 ms / release) exactly, and the background decks are scaled by 10^(-gr/20)."""
import asyncio
import math
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from harness.appcopy import copy_app            # noqa: E402
from harness.appload import load_app            # noqa: E402
from harness.engine import EngineCase           # noqa: E402
from harness.instance import PROJECT            # noqa: E402

WIN = 480                                        # frames per 10 ms at 48 kHz


def raw_stereo(windows):
    """windows: list of (left, right) constant sample values, one per 10 ms -> raw 16-bit stereo bytes."""
    a = np.zeros((len(windows) * WIN, 2), dtype="<i2")
    for i, (l, r) in enumerate(windows):
        a[i * WIN:(i + 1) * WIN, 0], a[i * WIN:(i + 1) * WIN, 1] = l, r
    return a.tobytes()


class PureDsp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = Path(tempfile.mkdtemp(prefix="dsptest-"))
        copy_app(cls.dir, PROJECT)
        (cls.dir / "media" / "library").mkdir(parents=True)
        cls.app = load_app(cls.dir)
        cls.dsp = cls.app.mod("dsp")

    @classmethod
    def tearDownClass(cls):
        cls.app.unload()
        shutil.rmtree(cls.dir, ignore_errors=True)

    # ---- duck_key
    def test_duck_key_is_the_rms_of_the_louder_channel_per_10_ms(self):
        raw = raw_stereo([(0, 0)] * 5 + [(16384, 8192)] * 10 + [(3277, 0)] * 5 + [(0, 0)] * 5)
        key = self.dsp.duck_key(raw)
        self.assertEqual(key.dtype, np.float32)
        want = [0.0] * 5 + [0.5] * 10 + [3277 / 32768] * 5 + [0.0] * 5
        np.testing.assert_allclose(key, want, atol=1e-6)

    def test_duck_key_picks_the_right_channel_when_it_is_the_louder_one(self):
        key = self.dsp.duck_key(raw_stereo([(1000, 16384)] * 3))
        np.testing.assert_allclose(key, [0.5] * 3, atol=1e-6)

    def test_duck_key_of_a_sine_is_amplitude_over_root_two(self):
        n = np.arange(WIN * 10)
        a = np.zeros((len(n), 2), dtype="<i2")
        a[:, 0] = np.round(16384 * np.sin(2 * np.pi * 1000 * n / 48000))        # ten whole cycles in every 10 ms window
        key = self.dsp.duck_key(a.tobytes())
        self.assertEqual(len(key), 10)
        np.testing.assert_allclose(key, [16384 / math.sqrt(2) / 32768] * 10, atol=2e-3)

    def test_duck_key_ignores_a_partial_window_and_returns_none_for_less_than_one_window(self):
        raw = raw_stereo([(16384, 0)] * 3) + bytes(4 * 200)                   # three windows and a bit
        self.assertEqual(len(self.dsp.duck_key(raw)), 3)
        self.assertIsNone(self.dsp.duck_key(bytes(4 * (WIN - 1))))
        self.assertIsNone(self.dsp.duck_key(b""))
        self.assertIsNone(self.dsp.duck_key(None))

    # ---- duck_curve
    KEY = np.array([0.0] * 5 + [0.5] * 10 + [3277 / 32768] * 5 + [0.0] * 5, dtype=np.float32)

    def expect(self, key, level, ratio, thr):
        db = 20 * np.log10(np.maximum(key * max(level, 1e-4), 1e-6))
        return np.minimum(np.clip(db - thr, 0, None) * (1 - 1 / max(1.0, ratio)), 60.0)

    def test_duck_curve_golden_values_without_hold(self):
        c = self.dsp.duck_curve(self.KEY, 1.0, 6.0, -30.0, False)
        self.assertEqual(c.dtype, np.float32)
        self.assertEqual(len(c), len(self.KEY))
        # golden numbers: (dB over the threshold) * (1 - 1/ratio)
        np.testing.assert_allclose(c[:5], 0.0)
        np.testing.assert_allclose(c[5:15], 19.98283, atol=1e-3)               # 0.5 -> -6.02 dB -> 23.98 dB over -30 -> x 5/6
        np.testing.assert_allclose(c[15:20], 8.33376, atol=1e-3)               # 0.1 -> -20.0 dB -> 10.0 dB over -> x 5/6
        np.testing.assert_allclose(c[20:], 0.0)
        np.testing.assert_allclose(c, self.expect(self.KEY, 1.0, 6.0, -30.0), atol=1e-4)

    def test_duck_curve_hold_keeps_the_typical_depth_between_the_first_and_last_loud_moment(self):
        c = self.dsp.duck_curve(self.KEY, 1.0, 6.0, -30.0, True)
        # active part = windows 5..19; the 75th percentile of its values is the loud level; the quieter windows are raised to it
        np.testing.assert_allclose(c[:5], 0.0)
        np.testing.assert_allclose(c[5:20], 19.98283, atol=1e-3)
        np.testing.assert_allclose(c[20:], 0.0)

    def test_duck_curve_hold_fills_gaps_with_the_75th_percentile_depth_not_the_maximum(self):
        key = np.array([0.5] * 3 + [0.0] * 2 + [3277 / 32768] * 12 + [0.0] * 3, dtype=np.float32)
        free = self.dsp.duck_curve(key, 1.0, 6.0, -30.0, False)
        held = self.dsp.duck_curve(key, 1.0, 6.0, -30.0, True)
        act = free[:17]
        depth = float(np.percentile(act[act > 0.05], 75))
        self.assertAlmostEqual(depth, 8.33376, delta=1e-3, msg="12 quiet and 3 loud windows: the 75th percentile is the quiet level")
        np.testing.assert_allclose(held[0:3], free[0:3], atol=1e-6, err_msg="loud windows stay as deep as they are")
        np.testing.assert_allclose(held[3:5], depth, atol=1e-4, err_msg="the gap inside the active part is raised to the typical depth")
        np.testing.assert_allclose(held[17:], 0.0)

    def test_duck_curve_hold_depth_is_the_75th_percentile_not_the_60th_or_the_median(self):
        # 5 loud + 10 quiet windows and a gap between them: sorted, the 75th percentile (position 10.5 of 0..14) is a LOUD value, the 60th (8.4) a quiet one
        key = np.array([0.5] * 5 + [0.0] + [3277 / 32768] * 10, dtype=np.float32)
        held = self.dsp.duck_curve(key, 1.0, 6.0, -30.0, True)
        np.testing.assert_allclose(held[5], 19.98283, atol=1e-3, err_msg="the gap is raised to the loud depth: that is where the 75th percentile lies")
        np.testing.assert_allclose(held[:5], 19.98283, atol=1e-3)
        np.testing.assert_allclose(held[6:], 19.98283, atol=1e-3, err_msg="and the quiet windows are raised to it as well")

    def test_duck_curve_follows_level_ratio_and_threshold(self):
        for level, ratio, thr in ((0.5, 6.0, -30.0), (1.0, 2.0, -30.0), (1.0, 20.0, -12.0), (0.25, 3.0, -40.0)):
            c = self.dsp.duck_curve(self.KEY, level, ratio, thr, False)
            np.testing.assert_allclose(c, self.expect(self.KEY, level, ratio, thr), atol=1e-4, err_msg=f"level {level} ratio {ratio} threshold {thr}")
        # a quieter top track (level 0.5 = -6 dB) ducks 5/6 of 6.02 dB less
        a = self.dsp.duck_curve(self.KEY, 1.0, 6.0, -30.0, False)[5]
        b = self.dsp.duck_curve(self.KEY, 0.5, 6.0, -30.0, False)[5]
        self.assertAlmostEqual(a - b, 6.0206 * 5 / 6, delta=1e-3)

    def test_duck_curve_no_ducking_at_ratio_one_or_when_the_threshold_is_never_reached(self):
        np.testing.assert_allclose(self.dsp.duck_curve(self.KEY, 1.0, 1.0, -30.0, False), 0.0)
        np.testing.assert_allclose(self.dsp.duck_curve(self.KEY, 1.0, 6.0, 0.0, False), 0.0)
        np.testing.assert_allclose(self.dsp.duck_curve(self.KEY, 1.0, 0.2, -30.0, False), 0.0, err_msg="a ratio below 1 counts as 1")

    def test_duck_curve_never_asks_for_more_than_60_db(self):
        c = self.dsp.duck_curve(np.array([1.0, 1.0], dtype=np.float32), 1.0, 20.0, -100.0, False)
        np.testing.assert_allclose(c, 60.0)

    def test_duck_curve_returns_none_without_a_key(self):
        self.assertIsNone(self.dsp.duck_curve(None, 1.0, 6.0, -30.0, False))
        self.assertIsNone(self.dsp.duck_curve(np.array([], dtype=np.float32), 1.0, 6.0, -30.0, False))


class DuckLoop(EngineCase):
    LIB = {"bg.wav": (30, 0), "dc.wav": (3, 16384, 48000, 2), "late.wav": (3, 0)}
    PLAYLISTS = [{"name": "bg", "tracks": ["bg.wav"]}, {"name": "top", "tracks": ["dc.wav", "late.wav"]}]
    ATTACK, RELEASE = 40, 200
    TARGET = (20 * math.log10(0.5) + 30.0) * (1 - 1 / 6.0)                   # dB of reduction for a constant half-scale top track

    async def asyncSetUp(self):
        await super().asyncSetUp()
        P = self.P
        P.CFG.update(duck_attack_ms=self.ATTACK, duck_release_ms=self.RELEASE, duck_ratio=6.0, duck_threshold_db=-30.0, duck_hold=False, top_track_pct=100)
        await self.load("bg.wav", "dc.wav")
        for _ in range(60):                                                   # the level key of a loaded track is worked out in the background
            if str(P.LIB / "dc.wav") in P._key:
                break
            await asyncio.sleep(0.05)
        self.assertIn(str(P.LIB / "dc.wav"), P._key, "the ducking key of the top track was not worked out")
        self.real_sleep = asyncio.sleep

        async def fake_sleep(delay, *a, **k):                                 # one duck-loop iteration = 10 ms of fake time and one turn of the event loop
            self.fake.t += delay
            await self.real_sleep(0)
        self.addCleanup(setattr, asyncio, "sleep", asyncio.sleep)
        asyncio.sleep = fake_sleep

    async def pump(self, n=1):
        for _ in range(n):
            await self.real_sleep(0)

    async def arm(self, top=(1, 0)):
        P = self.P
        self.assertTrue(P.play(0, 0))
        self.bg = self.S.live_deck
        self.rebase()
        self.assertTrue(P.play_on_top(*top))
        self.top = self.S.live_deck
        self.assertTrue(self.top.top)
        self.assertIs(P.DUCK["top"], self.top)
        await self.pump(1)                                                    # the loop starts: it records its first time stamp

    async def test_attack_follows_one_minus_exp_toward_the_target_and_scales_the_background(self):
        await self.arm()
        done = 0
        for k in (1, 2, 4, 8, 16, 32, 64):
            await self.pump(k - done)
            done = k
            want = self.TARGET * (1 - math.exp(-k * 0.01 / (self.ATTACK / 1000)))
            self.approx(self.P.DUCK["gr"], want, 1e-6, f"gain reduction after {k} steps")
            self.approx(self.bg.duck, 10 ** (-want / 20), 1.5e-3, f"background level after {k} steps")
            self.approx(self.bg.channel.get_volume(), self.bg.duck, 1 / 128 + 2e-3)
        self.assertGreater(self.P.DUCK["gr"], 0.98 * self.TARGET, "after 640 ms (16 time constants) the background is fully ducked")
        self.assertEqual(self.top.duck, 1.0, "the top track itself is never ducked")

    async def test_release_follows_exp_decay_back_to_full_level_after_the_top_track_ends(self):
        await self.arm()
        await self.pump(100)
        gr0 = self.P.DUCK["gr"]
        self.assertGreater(gr0, 0.99 * self.TARGET)
        self.top.started -= 100.0                                              # the top track is over
        self.P.tick()
        self.assertNotIn(self.top, self.P.decks)
        self.assertIs(self.S.live_deck, self.bg, "and the background is live again")
        done = 0
        for j in (1, 5, 10, 20, 40):
            await self.pump(j - done)
            done = j
            want = gr0 * math.exp(-j * 0.01 / (self.RELEASE / 1000))
            self.approx(self.P.DUCK["gr"], want, 1e-6, f"gain reduction {j * 10} ms after the top track ended")
            self.approx(self.bg.duck, 10 ** (-want / 20), 1.5e-3)
        await self.pump(160)                                                   # total 2.0 s = 10 time constants
        self.assertEqual(self.P.DUCK["gr"], 0.0)
        self.assertEqual(self.bg.duck, 1.0, "the background is back at full level")
        self.assertIsNone(self.P.DUCK["top"])
        self.assertEqual(self.P.DUCK["bg"], [])
        await self.pump(2)
        self.assertTrue(self.P.DUCK["task"].done(), "the loop ends when the duck is released")

    async def test_the_dip_starts_20_ms_before_the_loud_part_of_the_top_track(self):
        P = self.P
        import wave                                                           # "late.wav" is rewritten here: 0.5 s of silence, then 1.5 s of half-scale DC
        path = self.dir / "media" / "library" / "late.wav"
        with wave.open(str(path), "wb") as w:
            w.setnchannels(2); w.setsampwidth(2); w.setframerate(48000)
            w.writeframes(bytes(4 * 24000) + (16384).to_bytes(2, "little") * 2 * 72000)
        P.scan_library()
        P.DURS["late.wav"] = (0, 0, 2.0)
        await self.load("late.wav")
        for _ in range(60):
            if str(P.LIB / "late.wav") in P._key:
                break
            await asyncio.sleep(0.05)
        await self.arm(top=(1, 1))
        first_dip = None
        for k in range(1, 80):
            await self.pump(1)
            if P.DUCK["gr"] > 0 and first_dip is None:
                first_dip = self.top.fpos() - 0.01                             # the position the loop used in this iteration
        self.assertIsNotNone(first_dip)
        self.assertGreaterEqual(first_dip, 0.48 - 1e-6)
        self.assertLess(first_dip, 0.50, "the first reduction comes before the loud part begins at 0.50 s (20 ms look-ahead)")

    async def test_stop_all_clears_the_duck_at_once(self):
        await self.arm()
        await self.pump(50)
        self.assertGreater(self.P.DUCK["gr"], 0)
        self.P.stop_all()
        self.assertEqual(self.P.DUCK["gr"], 0.0)
        self.assertIsNone(self.P.DUCK["top"])
