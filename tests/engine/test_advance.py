"""Gap 3 (docs/split-plan.md 5.4): what happens when a track ends by itself.

tick() notices the natural end of the live deck and calls auto_advance, which follows the playlist behavior (stop / loop_playlist / next_playlist /
shuffle) unless the track has its own end action: stop (ends the run whatever the playlist does), loop (never ends), once (two passes, then as default).
It does not advance while a load is pending; a Play on Top track that ends hands the live role back to the track under it instead of advancing."""
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from harness.engine import EngineCase          # noqa: E402

MODES = ("stop", "loop_playlist", "next_playlist", "shuffle")
ENDS = ("default", "once", "loop", "stop")
DUR = 2.0


class AdvanceBase(EngineCase):
    LIB = {"a.wav": DUR, "b.wav": DUR, "c.wav": DUR, "u.wav": DUR, "v.wav": 1.0, "long.wav": 30}
    PLAYLISTS = [{"name": "A", "tracks": ["a.wav", "b.wav", "c.wav"]}, {"name": "B", "tracks": ["u.wav", "v.wav"]}, {"name": "L", "tracks": ["long.wav"]}]

    async def asyncSetUp(self):
        await super().asyncSetUp()
        random.seed(1234)
        await self.load(*self.LIB)

    def run_for(self, seconds, step=0.25):
        """Advance the fake clock in steps of `step`, ticking each time."""
        n = round(seconds / step)
        for _ in range(n):
            self.fake.t += step
            self.P.tick()


def _next_live(self, prev, limit=8.0, step=0.25):
    """Tick until the live deck is no longer `prev` (or nothing is live); returns the live deck (None = stopped). Fails after `limit` seconds."""
    for _ in range(round(limit / step)):
        self.fake.t += step
        self.P.tick()
        if self.S.live_deck is not prev:
            return self.S.live_deck
    self.fail(f"the live deck did not change within {limit} s of fake time")


AdvanceBase.next_live = _next_live


def expected_after_end(mode, end, t, n=3):
    """-> ("stopped",) | ("same",) | ("track", p, t) | ("other", p) for what is live after the track t of playlist 0 has ended (end action `end`)."""
    if end == "stop":
        return ("stopped",)
    if end == "loop":
        return ("same",)
    if mode == "stop":
        return ("stopped",)
    if mode == "loop_playlist":
        return ("track", 0, (t + 1) % n)
    if mode == "next_playlist":
        return ("track", 0, t + 1) if t + 1 < n else ("track", 1, 0)
    return ("other", 0)                                # shuffle: any other track of the playlist


class AdvanceMatrix(AdvanceBase):
    async def scenario(self, mode, end, t):
        P = self.P
        self.assertTrue(P.set_play_mode(0, mode))
        self.assertTrue(P.set_end(0, t, end))
        self.assertTrue(P.play(0, t))
        first = self.S.live_deck
        self.assertEqual(first.passes, 2 if end == "once" else 1)
        self.assertEqual(first.loop, end == "loop")
        self.rebase()
        want = expected_after_end(mode, end, t)
        if end == "once":
            self.run_for(DUR * 1.5)
            self.assertIs(self.S.live_deck, first, "loop once: still in the second pass at 1.5 x the length")
            self.assertEqual(first.pass_no(), 2)
        elif end == "loop":
            self.run_for(DUR * 3.5)
            self.assertIs(self.S.live_deck, first, "a looping track never ends, whatever the playlist behavior")
            self.assertTrue(first.loop)
            return
        else:
            self.run_for(DUR * 0.75)
            self.assertIs(self.S.live_deck, first, "not over yet at 75 % of the length")
        if want[0] == "stopped":
            live = self.next_live(first)                              # until it has ended (it is the only deck)
            self.assertIsNone(live, f"mode {mode}, end {end}: playback stops")
            self.assertEqual(P.decks, [])
            self.run_for(DUR)
            self.assertIsNone(self.S.live_deck, "and stays stopped")
            return
        live = self.next_live(first)
        self.assertIsNotNone(live, f"mode {mode}, end {end}: the next track must be playing")
        if want[0] == "track":
            self.assertEqual(tuple(live.pt), want[1:], f"mode {mode}, end {end}")
        else:
            self.assertEqual(live.pt[0], 0)
            self.assertNotEqual(live.pt[1], t, "shuffle picks another track of the playlist")
        self.assertEqual(len(P.decks), 1, "the ended deck is gone, only the next one is playing")
        if end == "once":
            self.assertGreaterEqual(self.fake.t - self.t0, DUR * 2 - 1e-6, "loop once: it advanced only after the second pass")


def _make(mode, end, t):
    async def test(self):
        await self.scenario(mode, end, t)
    return test


for _m in MODES:
    for _e in ENDS:
        for _t in (1, 2):
            setattr(AdvanceMatrix, f"test_{_m}_end_{_e}_track{_t}", _make(_m, _e, _t))


class AdvanceDetails(AdvanceBase):
    async def test_shuffle_plays_every_other_track_before_any_track_repeats(self):
        P = self.P
        P.set_play_mode(0, "shuffle")
        P.play(0, 0)
        seen = [self.S.live_deck.pt[1]]
        for _ in range(2):
            seen.append(self.next_live(self.S.live_deck).pt[1])
        self.assertEqual(seen[0], 0)
        self.assertEqual(sorted(seen[1:]), [1, 2], f"the two advances after track 0 must cover tracks 1 and 2 once each: {seen}")

    async def test_loop_playlist_goes_round_and_round(self):
        P = self.P
        P.set_play_mode(0, "loop_playlist")
        P.play(0, 0)
        order = [self.S.live_deck.pt[1]]
        for _ in range(4):
            order.append(self.next_live(self.S.live_deck).pt[1])
        self.assertEqual(order, [0, 1, 2, 0, 1])

    async def test_next_playlist_runs_on_into_the_following_playlist_and_stops_after_the_last_one(self):
        P = self.P
        P.set_play_mode(0, "next_playlist")
        P.set_play_mode(1, "next_playlist")
        P.set_play_mode(2, "next_playlist")
        P.play(0, 2)
        self.assertEqual(tuple(self.next_live(self.S.live_deck).pt), (1, 0), "the end of playlist A continues with the first track of B")
        self.assertEqual(tuple(self.next_live(self.S.live_deck).pt), (1, 1))
        self.assertEqual(tuple(self.next_live(self.S.live_deck).pt), (2, 0), "the end of playlist B continues with playlist L")

    async def test_a_track_set_to_stop_ends_the_run_even_in_the_middle_of_loop_playlist(self):
        P = self.P
        P.set_play_mode(0, "loop_playlist")
        P.set_end(0, 1, "stop")
        P.play(0, 0)
        self.assertEqual(tuple(self.next_live(self.S.live_deck).pt), (0, 1))
        self.assertIsNone(self.next_live(self.S.live_deck), "track 1 is set to stop: the run ends there")

    async def test_switching_loop_off_while_looping_plays_out_the_pass_and_then_advances(self):
        P = self.P
        P.set_play_mode(0, "loop_playlist")
        P.set_end(0, 0, "loop")
        P.play(0, 0)
        d = self.S.live_deck
        self.rebase()
        self.run_for(DUR * 2.5)
        self.assertIs(self.S.live_deck, d)
        P.set_end(0, 0, "default")                     # 'loop' is switched off half way through the third pass
        self.run_for(DUR * 0.25)
        self.assertIs(self.S.live_deck, d, "the pass that is running is played out")
        self.run_for(DUR * 0.75)
        self.assertEqual(tuple(self.S.live_deck.pt), (0, 1), "then it carries on with the next track")


class NoAdvanceWhilePending(AdvanceBase):
    async def end_a_track_with(self, pending):
        P = self.P
        calls = []
        real = P.auto_advance
        self.patch("auto_advance", lambda d: (calls.append(d), real(d))[1])
        P.set_play_mode(0, "loop_playlist")
        P.play(0, 0)
        ended = self.S.live_deck
        self.set_state("pending", pending)
        self.rebase()
        self.run_for(DUR + 0.5)
        return ended, calls

    async def test_a_pending_load_blocks_auto_advance_and_is_left_alone(self):
        job = {"token": 77, "pt": [0, 2], "fid": "c.wav", "name": "c", "xfade": 0}
        ended, calls = await self.end_a_track_with(job)
        self.assertEqual(calls, [], "auto_advance must not run while a track is loading")
        self.assertNotIn(ended, self.P.decks, "the finished deck is removed anyway")
        self.assertIsNone(self.S.live_deck)
        self.assertEqual(self.P.decks, [])
        self.assertIs(self.get_state("pending"), job, "and the pending job is not touched")

    async def test_control_without_a_pending_load_the_same_track_does_advance(self):
        ended, calls = await self.end_a_track_with(None)
        self.assertEqual(calls, [ended], "auto_advance is called once, with the deck that ended")
        self.assertEqual(tuple(self.S.live_deck.pt), (0, 1))


class PlayOnTopHandBack(AdvanceBase):
    async def test_when_the_top_track_ends_the_background_becomes_live_again_and_nothing_advances(self):
        P = self.P
        calls = []
        real = P.auto_advance
        self.patch("auto_advance", lambda d: (calls.append(d), real(d))[1])
        P.set_play_mode(2, "loop_playlist")
        self.assertTrue(P.play(2, 0))                                   # a 30 s background track
        bg = self.S.live_deck
        self.rebase()
        self.run_for(1.0)
        self.assertTrue(P.play_on_top(1, 1))                           # the 1 s voice-over
        top = self.S.live_deck
        self.assertTrue(top.top)
        self.assertIs(top.under, bg)
        self.assertIn(bg, top.bg)
        self.assertIs(self.S.live_deck, top)
        self.run_for(0.5)
        self.assertIs(self.S.live_deck, top, "still on top at 0.5 s")
        self.run_for(1.0)                                              # 1.5 s after the start: the 1 s voice-over is over
        self.assertNotIn(top, P.decks)
        self.assertIs(self.S.live_deck, bg, "the background is live again")
        self.assertEqual(P.decks, [bg])
        self.assertEqual(calls, [], "a top track that ends is not an auto-advance")
        self.assertEqual(tuple(self.S.live_deck.pt), (2, 0), "and the background was not replaced")

    async def test_the_background_then_ends_on_its_own_and_advances_normally(self):
        P = self.P
        P.set_play_mode(2, "loop_playlist")
        P.play(2, 0)                                                   # 30 s
        bg = self.S.live_deck
        self.rebase()
        self.run_for(0.5)
        P.play_on_top(1, 1)
        self.run_for(1.5)                                              # voice-over over
        self.assertIs(self.S.live_deck, bg)
        again = self.next_live(bg, limit=40.0)                         # the background ends at 30 s: loop_playlist plays it again
        self.assertIsNot(again, bg)
        self.assertEqual(tuple(again.pt), (2, 0))
        self.assertGreaterEqual(self.fake.t - self.t0, 30.0 - 1e-6)

    async def test_play_on_top_with_nothing_playing_is_a_plain_play_without_hand_back(self):
        P = self.P
        self.assertTrue(P.play_on_top(1, 1))
        d = self.S.live_deck
        self.assertFalse(d.top, "with nothing to duck it simply plays")
        self.run_for(1.5)
        self.assertIsNone(self.S.live_deck)
