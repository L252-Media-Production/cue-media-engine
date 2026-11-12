"""Gap 7 (docs/split-plan.md 5.1 / 5.4): the order of work inside tick(), as a contract.

tick() does, in this order:  (1) update every deck and remove the finished ones, noting which was the live track / a Play on Top track /
a background under a top track;  (2) hand the live role back from a finished top track to the track under it;  (3) forget a live deck that is
no longer playing;  (4) auto_advance(ended)  unless a load is pending;  (5) triggers_tick()  (an error there is contained);  (6) monitor_sync();
(7) update_meters();  (8) save_resume().
The spies record, at the moment they are called, which decks exist, which is live, and whether a load is pending."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from harness.engine import EngineCase          # noqa: E402

TAIL = ["triggers_tick", "monitor_sync", "update_meters", "save_resume"]


class TickOrder(EngineCase):
    LIB = {"a.wav": 2, "b.wav": 2, "c.wav": 2, "v.wav": 1, "long.wav": 30}
    PLAYLISTS = [{"name": "A", "tracks": ["a.wav", "b.wav", "c.wav"]}, {"name": "V", "tracks": ["v.wav"]}, {"name": "L", "tracks": ["long.wav"]}]

    async def asyncSetUp(self):
        await super().asyncSetUp()
        P = self.P
        await self.load(*self.LIB)
        self.calls, self.adv = [], []
        P.set_play_mode(0, "loop_playlist")

        def snap(name):
            ds = tuple(tuple(d.pt) if d.pt else None for d in P.decks)
            live = tuple(self.S.live_deck.pt) if self.S.live_deck is not None and self.S.live_deck.pt else None
            self.calls.append({"name": name, "decks": ds, "live": live, "pending": bool(self.get_state("pending"))})

        real_adv = P.auto_advance

        def adv(deck):
            snap("auto_advance")
            self.adv.append(deck)
            return real_adv(deck)
        self.patch("auto_advance", adv)
        for n in TAIL:
            self.patch(n, (lambda n=n: lambda *a, **k: snap(n))())

    def names(self):
        return [c["name"] for c in self.calls]

    def call(self, name):
        return next(c for c in self.calls if c["name"] == name)

    def tick_at(self, seconds):
        self.calls.clear()
        self.adv.clear()
        self.at(seconds)

    async def test_a_quiet_tick_runs_the_four_steps_in_order_and_advances_nothing(self):
        self.P.play(0, 0)
        self.rebase()
        self.tick_at(0.5)
        self.assertEqual(self.names(), TAIL)

    async def test_a_finished_live_track_is_removed_before_auto_advance_and_the_next_track_is_live_for_the_rest(self):
        P = self.P
        P.play(0, 0)
        first = self.S.live_deck
        self.rebase()
        self.tick_at(2.25)
        self.assertEqual(self.names(), ["auto_advance"] + TAIL)
        c = self.call("auto_advance")
        self.assertEqual(c["decks"], (), "the finished deck is already removed when auto_advance runs")
        self.assertIsNone(c["live"], "and it is no longer the live deck")
        self.assertEqual(self.adv, [first], "auto_advance gets the deck that ended, once")
        for n in TAIL:
            self.assertEqual(self.call(n)["live"], (0, 1), f"{n} already sees the next track as live")
            self.assertEqual(self.call(n)["decks"], ((0, 1),))

    async def test_a_pending_load_suppresses_only_the_auto_advance(self):
        P = self.P
        P.play(0, 0)
        self.set_state("pending", {"token": 5, "pt": [0, 2], "fid": "c.wav", "name": "c", "xfade": 0})
        self.rebase()
        self.tick_at(2.25)
        self.assertEqual(self.names(), TAIL, "everything else still runs")
        self.assertEqual(self.call("triggers_tick")["decks"], ())
        self.assertIsNone(self.call("triggers_tick")["live"])
        self.assertTrue(self.call("update_meters")["pending"])
        self.assertEqual(self.adv, [])

    async def test_a_finished_top_track_hands_the_live_role_back_before_anything_else_runs(self):
        P = self.P
        P.play(2, 0)                                                    # 30 s background
        bg = self.S.live_deck
        self.rebase()
        self.at(0.5)
        P.play_on_top(1, 0)                                             # 1 s voice-over
        top = self.S.live_deck
        self.tick_at(1.75)
        self.assertEqual(self.names(), TAIL, "no auto_advance for a top track")
        self.assertNotIn(top, P.decks)
        self.assertIs(self.S.live_deck, bg)
        for n in TAIL:
            self.assertEqual(self.call(n)["live"], (2, 0), f"{n} sees the background as live again")
            self.assertEqual(self.call(n)["decks"], ((2, 0),))

    async def test_background_and_top_finish_in_the_same_tick_the_run_carries_on_from_the_background(self):
        P = self.P
        P.play(0, 0)                                                    # a: 2 s
        bg = self.S.live_deck
        self.rebase()
        self.at(1.5)
        P.play_on_top(1, 0)                                             # v: 1 s, runs to 2.5
        top = self.S.live_deck
        self.assertIs(top.under, bg)
        self.tick_at(3.0)                                               # both are over
        self.assertEqual(self.names(), ["auto_advance"] + TAIL)
        self.assertEqual(self.adv, [bg], "the background ended while it was covered: the run carries on from IT, in its playlist")
        self.assertEqual(self.call("auto_advance")["decks"], (), "both finished decks are gone when auto_advance runs")
        self.assertEqual(self.call("triggers_tick")["live"], (0, 1))

    async def test_the_same_with_a_pending_load_nothing_is_started(self):
        P = self.P
        P.play(0, 0)
        self.rebase()
        self.at(1.5)
        P.play_on_top(1, 0)
        self.set_state("pending", {"token": 9, "pt": [0, 2], "fid": "c.wav", "name": "c", "xfade": 0})
        self.tick_at(3.0)
        self.assertEqual(self.names(), TAIL)
        self.assertEqual(self.adv, [])
        self.assertEqual(P.decks, [])
        self.assertIsNone(self.S.live_deck)

    async def test_the_background_ending_under_a_top_track_is_remembered_and_acted_on_when_the_top_ends(self):
        P = self.P
        P.play(0, 0)
        bg = self.S.live_deck
        self.rebase()
        self.at(1.5)
        P.play_on_top(1, 0)
        top = self.S.live_deck
        self.tick_at(2.25)                                              # the background ends first (2.0), the top is still playing
        self.assertEqual(self.names(), TAIL, "nothing is started while the top track plays")
        self.assertIs(top.under_ended, bg)
        self.assertIs(self.S.live_deck, top)
        self.assertEqual(P.decks, [top])
        self.tick_at(2.75)                                              # the top ends (2.5)
        self.assertEqual(self.names(), ["auto_advance"] + TAIL)
        self.assertEqual(self.adv, [bg])

    async def test_an_error_in_the_trigger_step_does_not_stop_the_rest_of_the_tick(self):
        P = self.P
        P.play(0, 0)
        self.rebase()
        self.calls.clear()

        def boom():
            self.calls.append({"name": "triggers_tick", "decks": (), "live": None, "pending": False})
            raise RuntimeError("trigger trouble")
        self.patch("triggers_tick", boom)
        self.at(0.5)                                                    # must not raise
        self.assertEqual(self.names(), TAIL, "monitor_sync, update_meters and save_resume still run after the error")

    async def test_every_deck_is_updated_even_when_one_of_them_ends_in_the_same_tick(self):
        P = self.P
        await self.load("long.wav")
        P.play(2, 0)
        a = self.S.live_deck
        self.rebase()
        self.at(0.5)
        P.play_on_top(1, 0)
        top = self.S.live_deck
        a.start_fade(0.0, 1000)                                         # a fade on the background...
        self.at(1.0)                                                    # ... 0.5 s into it
        self.assertLess(a.vol, 1.0, "the background deck was updated in a tick where the top deck is also alive")
