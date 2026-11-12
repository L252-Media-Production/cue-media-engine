"""2.7.4: fade-in at A (trim "start": "fade", "fade_in_ms"), with the fake clock.

Applied by _start only, on a start at the In point; the same equal-power curve as every other fade (sin(x*pi/2) up to the level).
A crossfade into the track wins; a resume or seek part-way in never fades; a track played on top fades up to its set level; Cut (the default) is as in 2.7.3."""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from harness.engine import EngineCase          # noqa: E402


class FadeIn(EngineCase):
    async def start(self, trim, ms=0):
        await self.load("a.wav", "b.wav", "c.wav")
        self.assertTrue(self.P.set_trim(0, 0, trim))
        self.rebase()
        self.assertTrue(self.P.play(0, 0, ms))
        return self.S.live_deck

    async def test_default_is_a_cut_full_level_at_once(self):
        await self.load("a.wav")
        self.P.play(0, 0)
        d = self.S.live_deck
        self.assertEqual((d.vol, d.fade, d.fade_in_ms), (1.0, None, 0))

    async def test_trim_without_the_fade_in_is_unchanged(self):
        d = await self.start({"in": 1.0, "out": 9.0})
        self.assertEqual((d.vol, d.fade, d.fade_in_ms), (1.0, None, 0))

    async def test_fade_in_follows_the_equal_power_curve_and_ends_at_full_level(self):
        d = await self.start({"start": "fade", "fade_in_ms": 1500})
        self.assertEqual(d.fade_in_ms, 1500)
        self.assertEqual(d.vol, 0.0)
        for frac in (0.25, 0.5, 0.75):
            self.at(1.5 * frac)
            self.approx(d.vol, math.sin(frac * math.pi / 2), 1e-6, f"at {frac:.0%}")
        self.at(1.5)
        self.assertEqual(d.vol, 1.0)
        self.assertIsNone(d.fade)

    async def test_fade_in_from_a_set_in_point(self):
        d = await self.start({"in": 2.0, "start": "fade", "fade_in_ms": 1000})
        self.assertEqual((d.vol, d.fade_in_ms), (0.0, 1000))
        self.at(1.0)
        self.assertEqual(d.vol, 1.0)

    async def test_cut_keeps_the_value_but_does_not_apply_it(self):
        d = await self.start({"fade_in_ms": 1500})
        self.assertEqual((d.vol, d.fade, d.fade_in_ms), (1.0, None, 0))

    async def test_the_default_length_is_used_when_the_track_has_no_own_value(self):
        self.P.CFG["trim_fadein_ms"] = 800
        d = await self.start({"start": "fade"})
        self.assertEqual(d.fade_in_ms, 800)

    async def test_the_default_is_not_applied_to_a_cut_start(self):
        self.P.CFG["trim_fadein_ms"] = 800
        d = await self.start({"in": 1.0})
        self.assertEqual(d.fade_in_ms, 0)

    async def test_a_crossfade_into_the_track_wins(self):
        await self.load("a.wav", "b.wav")
        self.P.set_trim(0, 1, {"start": "fade", "fade_in_ms": 5000})
        self.P.play(0, 0)
        self.rebase()
        self.P.play(0, 1, 1000)
        new = self.S.live_deck
        self.assertEqual(new.fade_in_ms, 0)
        self.at(0.5)
        self.approx(new.vol, math.sin(math.pi / 4), 1e-6, "the crossfade curve, not the fade-in")
        self.at(1.0)
        self.assertEqual(new.vol, 1.0, "full after the crossfade time, not after the 5 s fade-in")

    async def test_the_fade_is_never_longer_than_the_part_that_plays(self):
        d = await self.start({"in": 1.0, "out": 3.0, "start": "fade", "fade_in_ms": 9000})
        self.assertLessEqual(d.fade_in_ms, 2000)

    async def test_resume_part_way_in_does_not_fade(self):
        await self.load("a.wav")
        self.P.set_trim(0, 0, {"start": "fade", "fade_in_ms": 1500})
        tr = self.P.track(0, 0)
        snd = await self.P.ensure_loaded(tr["path"])
        self.assertTrue(self.P._start(0, 0, tr, snd, 0, offset=4.0))
        d = self.S.live_deck
        self.assertEqual((d.vol, d.fade, d.fade_in_ms), (1.0, None, 0))

    async def test_resume_at_the_in_point_does_fade(self):
        await self.load("a.wav")
        self.P.set_trim(0, 0, {"start": "fade", "fade_in_ms": 1500})
        tr = self.P.track(0, 0)
        snd = await self.P.ensure_loaded(tr["path"])
        self.assertTrue(self.P._start(0, 0, tr, snd, 0, offset=0.0))
        self.assertEqual(self.S.live_deck.fade_in_ms, 1500)

    async def test_a_paused_start_does_not_fade(self):
        await self.load("a.wav")
        self.P.set_trim(0, 0, {"start": "fade", "fade_in_ms": 1500})
        tr = self.P.track(0, 0)
        snd = await self.P.ensure_loaded(tr["path"])
        self.assertTrue(self.P._start(0, 0, tr, snd, 0, paused=True))
        self.assertEqual(self.S.live_deck.fade_in_ms, 0)

    async def test_seek_into_the_middle_does_not_start_a_new_fade(self):
        d = await self.start({"start": "fade", "fade_in_ms": 1000})
        self.at(1.0)
        self.assertEqual(d.vol, 1.0)
        self.P.seek_live(6.0)
        self.at(1.1)
        live = self.S.live_deck
        self.assertEqual(live.vol, 1.0)
        self.assertIsNone(live.fade)

    async def test_a_track_on_top_fades_up_to_its_set_level(self):
        await self.load("a.wav", "b.wav")
        self.P.CFG["top_track_pct"] = 60
        self.P.set_trim(0, 1, {"start": "fade", "fade_in_ms": 1000})
        self.P.play(0, 0)
        self.rebase()
        self.assertTrue(self.P.play_on_top(0, 1) is not False)
        top = next(x for x in self.P.decks if x.top)
        self.assertEqual((top.vol, top.fade_in_ms), (0.0, 1000))
        self.at(0.5)
        self.approx(top.vol, 0.6 * math.sin(math.pi / 4), 1e-6)
        self.at(1.0)
        self.approx(top.vol, 0.6, 1e-6)
