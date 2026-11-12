"""Gap 2 (docs/split-plan.md 5.4): fade and crossfade shape over time, with the fake clock.

Equal power: the new deck rises as sin(x*pi/2), the old one falls as cos(x*pi/2), x = elapsed / fade length, so new^2 + old^2 = 1 all the way.
Out-point fade: a track with an Out point and end = fade starts to fade when the time left equals the fade length."""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from harness.engine import EngineCase          # noqa: E402


class CrossfadeShape(EngineCase):
    async def start_crossfade(self, ms=1000):
        await self.load("a.wav", "b.wav")
        self.assertTrue(self.P.play(0, 0))
        self.old = self.S.live_deck
        self.rebase()
        self.assertTrue(self.P.play(0, 1, ms))
        self.new = self.S.live_deck
        self.assertIsNot(self.new, self.old)

    async def test_starts_with_the_new_deck_silent_and_the_old_at_full_level(self):
        await self.start_crossfade()
        self.assertEqual(self.new.vol, 0.0)
        self.assertEqual(self.old.vol, 1.0)
        self.assertIn(self.old, self.P.decks)
        self.assertEqual(self.new.pt, [0, 1])

    async def test_equal_power_values_at_25_50_75_percent(self):
        await self.start_crossfade(1000)
        for frac in (0.25, 0.5, 0.75):
            self.at(frac)
            want_new, want_old = math.sin(frac * math.pi / 2), math.cos(frac * math.pi / 2)
            self.approx(self.new.vol, want_new, 1e-6, f"new deck at {frac:.0%}")
            self.approx(self.old.vol, want_old, 1e-6, f"old deck at {frac:.0%}")
            self.approx(self.new.vol ** 2 + self.old.vol ** 2, 1.0, 1e-6, f"power sum at {frac:.0%}")
            # the volume really reaches the mixer channel (it has 128 steps)
            self.approx(self.new.channel.get_volume(), want_new, 1 / 128 + 1e-3)
            self.approx(self.old.channel.get_volume(), want_old, 1 / 128 + 1e-3)

    async def test_at_100_percent_the_new_deck_is_full_and_the_old_one_is_removed(self):
        await self.start_crossfade(1000)
        self.at(0.75)
        self.assertIn(self.old, self.P.decks)
        old_ch, old_snd = self.old.channel, self.old.sound
        self.at(1.0)
        self.assertEqual(self.new.vol, 1.0)
        self.assertIsNone(self.new.fade)
        self.assertNotIn(self.old, self.P.decks, "the faded-out deck must be removed from the decks")
        self.assertIsNot(old_ch.get_sound(), old_snd, "and its channel stopped")
        self.assertIs(self.S.live_deck, self.new)
        self.assertEqual(len(self.P.decks), 1)

    async def test_old_deck_stays_until_its_fade_has_ended_not_before(self):
        await self.start_crossfade(1000)
        self.at(0.9375)                                           # 15/16 of the fade
        self.assertIn(self.old, self.P.decks)
        self.assertGreater(self.old.vol, 0.0)
        self.at(1.0625)
        self.assertNotIn(self.old, self.P.decks)

    async def test_a_zero_length_crossfade_is_a_cut(self):
        await self.load("a.wav", "b.wav")
        self.P.play(0, 0)
        old = self.S.live_deck
        self.P.play(0, 1, 0)
        self.assertNotIn(old, self.P.decks)
        self.assertEqual(self.S.live_deck.vol, 1.0)
        self.assertIsNone(self.S.live_deck.fade)

    async def test_fade_out_follows_the_same_curve_and_ends_with_nothing_playing(self):
        await self.load("a.wav")
        self.P.play(0, 0)
        d = self.S.live_deck
        self.rebase()
        self.P.fade_out(1000)
        for frac in (0.25, 0.5, 0.75):
            self.at(frac)
            self.approx(d.vol, math.cos(frac * math.pi / 2), 1e-6, f"fade out at {frac:.0%}")
        self.at(1.0)
        self.assertNotIn(d, self.P.decks)
        self.assertIsNone(self.S.live_deck)

    async def test_a_second_crossfade_during_the_first_keeps_every_deck_consistent(self):
        await self.load("a.wav", "b.wav", "c.wav")
        self.P.play(0, 0)
        a = self.S.live_deck
        self.rebase()
        self.P.play(0, 1, 1000)
        b = self.S.live_deck
        self.at(0.5)
        self.rebase()
        self.P.play(0, 2, 1000)                                    # c comes in while b is half way in and a half way out
        c = self.S.live_deck
        self.at(1.0)
        self.assertNotIn(a, self.P.decks, "a was already fading out and is gone now")
        self.assertNotIn(b, self.P.decks, "b has been told to fade out as well")
        self.assertEqual(c.vol, 1.0)
        self.assertEqual([d for d in self.P.decks], [c])


class PauseDuringFade(EngineCase):
    async def test_pause_freezes_the_fade_and_resume_continues_from_the_same_point(self):
        await self.load("a.wav", "b.wav")
        self.P.play(0, 0)
        old = self.S.live_deck
        self.rebase()
        self.P.play(0, 1, 1000)
        new = self.S.live_deck
        self.at(0.25)
        v_new, v_old = new.vol, old.vol
        self.approx(v_new, math.sin(math.pi / 8), 1e-6)
        self.P.pause_all()
        self.at(5.25)                                             # five seconds of pause
        self.assertEqual((new.vol, old.vol), (v_new, v_old), "a paused fade must not move")
        self.assertIn(old, self.P.decks)
        self.P.resume_all()
        self.at(5.5)                                              # 0.25 s after the resume = 0.5 of the fade
        self.approx(new.vol, math.sin(math.pi / 4), 1e-6, "50 % of the fade, counted without the pause")
        self.approx(old.vol, math.cos(math.pi / 4), 1e-6)
        self.at(5.75)                                             # 0.5 s after the resume = 0.25 + 0.5 = 75 % of the fade
        self.approx(new.vol, math.sin(0.75 * math.pi / 2), 1e-6)
        self.approx(old.vol, math.cos(0.75 * math.pi / 2), 1e-6)
        self.at(6.0625)                                           # 0.8125 s after the resume = 100 %
        self.assertNotIn(old, self.P.decks)
        self.assertEqual(new.vol, 1.0)

    async def test_the_position_of_a_paused_track_does_not_run_on(self):
        await self.load("a.wav")
        self.P.play(0, 0)
        d = self.S.live_deck
        self.rebase()
        self.at(2.0)
        pos = d.fpos()
        self.P.pause_all()
        self.at(30.0)
        self.assertEqual(d.fpos(), pos)
        self.P.resume_all()
        self.at(31.0)
        self.approx(d.fpos(), pos + 1.0, 1e-6)


class OutPointFade(EngineCase):
    LIB = {"a.wav": 12, "b.wav": 12}

    async def start_trimmed(self, end="fade", fade_ms=1000, out=10.0):
        await self.load("a.wav")
        self.assertTrue(self.P.set_trim(0, 0, {"out": out, "end": end, "fade_ms": fade_ms}))
        self.assertTrue(self.P.play(0, 0))
        self.d = self.S.live_deck
        self.rebase()
        self.assertEqual(self.d.hi, out)
        self.approx(self.d.duration, out, 1e-3)

    async def test_the_fade_starts_when_the_time_left_equals_the_fade_length(self):
        await self.start_trimmed(fade_ms=1000, out=10.0)
        self.assertEqual(self.d.end_fade_ms, 1000)
        self.at(8.5)
        self.assertIsNone(self.d.fade)
        self.assertEqual(self.d.vol, 1.0)
        self.at(8.9375)
        self.assertIsNone(self.d.fade, "still more than the fade length left")
        self.at(9.0625)                                           # 0.9375 s left: inside the last second
        self.assertIsNotNone(self.d.fade)
        self.assertTrue(self.d._outfaded)
        self.assertEqual(self.d.fade["b"], 0.0)
        self.approx(self.d.fade["len"], 10.0 - 9.0625, 1e-3, "the fade runs exactly to the Out point")

    async def test_the_fade_reaches_silence_at_the_out_point_and_the_track_then_ends_by_itself(self):
        await self.start_trimmed(fade_ms=1000, out=10.0)
        self.at(9.0625)
        self.at(9.5)
        x = (9.5 - 9.0625) / (10.0 - 9.0625)
        self.approx(self.d.vol, math.cos(x * math.pi / 2), 1e-3)
        self.at(9.9375)
        x = (9.9375 - 9.0625) / (10.0 - 9.0625)
        self.approx(self.d.vol, math.cos(x * math.pi / 2), 1e-3, "nearly silent just before the Out point")
        self.assertLess(self.d.vol, 0.11)
        self.at(10.0625)
        self.assertNotIn(self.d, self.P.decks)
        self.assertTrue(self.d.natural, "it ended by itself, not by a stop")
        self.assertIsNone(self.S.live_deck)

    async def test_with_a_cut_edge_there_is_no_fade_and_the_track_stops_at_the_out_point(self):
        await self.start_trimmed(end="cut", fade_ms=1000, out=10.0)
        self.assertEqual(self.d.end_fade_ms, 0)
        self.at(9.5)
        self.assertIsNone(self.d.fade)
        self.assertEqual(self.d.vol, 1.0)
        self.at(10.0625)
        self.assertNotIn(self.d, self.P.decks)

    async def test_a_fade_longer_than_the_playing_part_is_capped_at_the_part(self):
        await self.start_trimmed(fade_ms=10000, out=3.0)          # 3 s part, 10 s fade asked for
        self.at(0.0625)
        self.assertIsNotNone(self.d.fade, "the fade covers the whole 3 s part")
        self.approx(self.d.fade["len"], 3.0 - 0.0625, 1e-3)
