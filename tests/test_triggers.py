"""Trigger points: engine and data tests with a fake clock.

Run:  SDL_AUDIODRIVER=dummy python3 -I tests/test_triggers.py        (needs the packages of requirements.txt)

Each test loads its own copy of player.py into a temporary folder, so config.json, playlists.json and the library of the
real install are never read or written. Time is a fake clock: the Deck, the tick and the trigger logic all read
`cpl.clock`, whose source the tests replace (clock.install), so a 2-minute track is "played" in milliseconds.
"""
import asyncio, importlib.util, os, shutil, sys, tempfile, time as real_time, unittest, wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))      # -I drops the script folder from sys.path
from harness.appcopy import copy_app   # noqa: E402
from harness.appload import load_app  # noqa: E402

os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
SRC = Path(__file__).resolve().parent.parent / "player.py"
TICK = 0.05


class FakeTime:
    def __init__(self):
        self.t = 1000.0

    def monotonic(self):
        return self.t

    def time(self):
        return 1.7e9 + self.t

    def __getattr__(self, name):
        return getattr(real_time, name)


def make_wav(path, seconds, rate=22050):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(bytes(int(seconds * rate) * 2))


class TriggerTests(unittest.IsolatedAsyncioTestCase):
    """Library: main.wav (120 s), other.wav (60 s), vo.wav (3 s), vo2.wav (8 s).  Playlist 0 = main, other.  Playlist 1 = vo, vo2."""
    LIB = {"main.wav": 120, "other.wav": 60, "vo.wav": 3, "vo2.wav": 8}

    async def asyncSetUp(self, warm_loop=False):
        self.dir = Path(tempfile.mkdtemp(prefix="trigtest-"))
        (self.dir / "media" / "library").mkdir(parents=True)
        (self.dir / "config.json").write_text('{"http_port": 18190, "osc_in_port": 18191}')
        copy_app(self.dir, SRC.parent)
        for name, secs in self.LIB.items():
            make_wav(self.dir / "media" / "library" / name, secs)
        self.app = load_app(self.dir)                      # fresh module state per test (tests/harness/appload.py)
        P = self.P = self.app.P
        self.S = self.app.mod("state")                      # the shared state: S.live_deck
        self.fake = FakeTime()
        self.clock = self.app.mod("clock")
        self.clock.install(self.fake)
        L = self.app.mod("loudness")
        real_loud = L.request_loudness
        L.request_loudness = lambda: None
        self.S.on_save[:] = [L.request_loudness if h is real_loud else h for h in self.S.on_save]      # save() reaches it through the hook list (plan 4.4)
        self.warm_calls = []
        W = self.app.mod("warm")
        real_warm = W.request_warm

        def spy_warm():
            self.warm_calls.append((self.fake.t, list(P.trigger_targets())))
            real_warm()
        W.request_warm = spy_warm
        self.S.on_change[:] = [spy_warm if h is real_warm else h for h in self.S.on_change]      # bump() reaches it through the hook list (plan 4.4)
        self.assertIn(spy_warm, self.S.on_change)
        if not warm_loop:
            async def idle():                    # the background warm-up would decode every file as soon as the loop yields
                return None
            W._warm_loop = idle
        P.CFG["watchdog"] = False                         # the fake clock jumps while the dummy output delivers nothing: not a stall
        P.init_mixer(None)
        P.scan_library()
        P.playlists[:] = [{"name": "A", "tracks": ["main.wav", "other.wav"]}, {"name": "B", "tracks": ["vo.wav", "vo2.wav"]}]
        for fid, secs in self.LIB.items():
            P.DURS[fid] = (0, 0, float(secs))
        self.fires = []
        real_top = P._play_on_top

        def spy_top(p, t, tr):
            if p is None:                                          # only the trigger points (the operator's own Play on Top has a playlist entry)
                self.fires.append((round(self.fake.t - self.t0, 2), tr["id"], P.cached(tr["path"]) is not None))
            return real_top(p, t, tr)
        P._play_on_top = spy_top
        self.t0 = self.fake.t

    async def asyncTearDown(self):
        try:
            self.P.stop_all()
            self.P.pygame.mixer.quit()
        finally:
            self.app.unload()
            shutil.rmtree(self.dir, ignore_errors=True)

    # ---- helpers
    async def load_all(self, *names):
        for n in names:
            await self.P.ensure_loaded(str(self.P.LIB / n))

    async def start(self, p=0, t=0, preload=("main.wav", "vo.wav", "vo2.wav", "other.wav")):
        await self.load_all(*preload)
        self.assertTrue(self.P.play(p, t))
        self.t0 = self.fake.t

    def add(self, at, file="vo.wav", p=0, t=0, **kw):
        lst, err = self.P.set_triggers(p, t, "add", {"at": at, "file": file, **kw})
        self.assertIsNone(err, err)
        return next(x for x in lst if x["at"] == round(at, 3))["id"]

    def run_for(self, secs):
        for _ in range(int(round(secs / TICK))):
            self.fake.t += TICK
            self.P.tick()

    def pos(self):
        return self.S.live_deck.fpos()

    def notice(self):
        return (self.P.TRIG["notice"] or {}).get("kind")

    # ---- engine
    async def test_fires_once_at_the_time(self):
        self.add(10)
        await self.start()
        self.run_for(9.5)
        self.assertEqual(self.fires, [])
        self.run_for(1.0)
        self.assertEqual(len(self.fires), 1)
        self.assertAlmostEqual(self.fires[0][0], 10.0, delta=0.11)
        self.assertEqual(self.fires[0][1], "vo.wav")
        self.assertEqual(self.notice(), "fired")
        self.assertTrue(self.S.live_deck.top)                      # it went through the normal Play on Top
        self.run_for(30)
        self.assertEqual(len(self.fires), 1)                       # never again in the same pass

    async def test_two_triggers_in_order(self):
        self.add(5, "vo.wav")
        self.add(20, "vo2.wav")
        await self.start()
        self.run_for(25)
        self.assertEqual([f[1] for f in self.fires], ["vo.wav", "vo2.wav"])

    async def test_seek_over_does_not_fire(self):
        self.add(10)
        await self.start()
        self.run_for(5)
        self.assertTrue(self.P.seek_live(20))
        self.run_for(30)
        self.assertEqual(self.fires, [])

    async def test_seek_forward_to_just_before_still_fires(self):
        self.add(10)
        await self.start()
        self.assertTrue(self.P.seek_live(9))
        self.run_for(2)
        self.assertEqual(len(self.fires), 1)

    async def test_seek_back_rearms(self):
        self.add(10)
        await self.start()
        self.run_for(11)
        self.assertEqual(len(self.fires), 1)
        self.run_for(4)                                            # the voice-over (3 s) is over
        self.assertFalse(self.S.live_deck.top)
        self.assertTrue(self.P.seek_live(5))
        self.run_for(6)
        self.assertEqual(len(self.fires), 2)

    async def test_pause_holds(self):
        self.add(10)
        await self.start()
        self.run_for(9.0)
        self.P.pause_all()
        self.run_for(30)
        self.assertEqual(self.fires, [])
        self.P.resume_all()
        self.run_for(0.5)
        self.assertEqual(self.fires, [])
        self.run_for(1.5)
        self.assertEqual(len(self.fires), 1)

    async def test_loop_fires_every_pass(self):
        self.P.set_end(0, 0, "loop")
        self.add(10)
        await self.start()
        self.run_for(120 + 120 + 15)                               # passes 1, 2 and into 3
        self.assertEqual(len(self.fires), 3)
        self.assertAlmostEqual(self.fires[1][0], 130.0, delta=0.15)

    async def test_loop_once_flag_fires_first_pass_only(self):
        self.P.set_end(0, 0, "loop")
        self.add(10, once=True)
        await self.start()
        self.run_for(120 + 120 + 15)
        self.assertEqual(len(self.fires), 1)
        self.assertIsNone(self.P.next_trigger())                   # and nothing is announced as coming

    async def test_loop_once_end_action_second_pass(self):
        self.P.set_end(0, 0, "once")                               # plays twice
        self.add(10)
        self.add(30, "vo2.wav", once=True)
        await self.start()
        self.run_for(120 + 40)
        self.assertEqual([f[1] for f in self.fires], ["vo.wav", "vo2.wav", "vo.wav"])

    async def test_trigger_at_loop_end_is_not_missed(self):
        self.P.set_end(0, 0, "loop")
        self.add(119.98)
        await self.start()
        self.run_for(122)
        self.assertEqual(len(self.fires), 1)

    async def test_trim_in_after_trigger_never_fires(self):
        self.P.set_trim(0, 0, {"in": 30})
        self.add(10)
        await self.start()
        self.run_for(30)
        self.assertEqual(self.fires, [])
        self.assertTrue(self.P.trigger_json(0, 0)[0]["outside"])

    async def test_trim_out_before_trigger_never_fires(self):
        self.P.set_trim(0, 0, {"out": 20})
        self.add(40)
        await self.start()
        self.run_for(25)
        self.assertEqual(self.fires, [])

    async def test_trigger_at_the_in_point_fires(self):
        self.P.set_trim(0, 0, {"in": 30})
        self.add(30)
        await self.start()
        self.run_for(1)
        self.assertEqual(len(self.fires), 1)

    async def test_trigger_inside_trim_with_offset(self):
        self.P.set_trim(0, 0, {"in": 30, "out": 90})
        self.add(40)                                               # file time, so 10 s after the In point
        await self.start()
        self.run_for(9.5)
        self.assertEqual(self.fires, [])
        self.run_for(1.0)
        self.assertEqual(len(self.fires), 1)

    async def test_missing_target_is_kept_and_reported(self):
        self.add(10)
        os.remove(self.P.LIB / "vo.wav")
        self.P.scan_library()
        tj = self.P.trigger_json(0, 0)
        self.assertEqual(len(tj), 1)
        self.assertTrue(tj[0]["missing"])
        await self.start(preload=("main.wav",))
        self.run_for(12)
        self.assertEqual(self.fires, [])
        self.assertEqual(self.notice(), "failed")
        self.assertEqual(len(self.P.triggers_of(0, 0)), 1)         # the entry stays

    async def test_top_already_playing_skips_with_notice(self):
        self.add(10)
        await self.start()
        self.run_for(9)
        self.assertTrue(self.P.play_on_top(1, 1))                  # the operator's own Play on Top (8 s)
        self.run_for(2)
        self.assertEqual(self.fires, [])
        self.assertEqual(self.notice(), "skipped")
        self.assertIn("Play on Top", self.P.TRIG["notice"]["text"])
        self.run_for(10)
        self.assertEqual(self.fires, [])                           # and it does not fire late either

    async def test_disarmed_never_fires_and_rearms(self):
        self.P.set_end(0, 0, "loop")
        self.add(10)
        await self.start()
        self.P.set_triggers_armed(False)
        self.run_for(15)
        self.assertEqual(self.fires, [])
        self.assertEqual(self.notice(), "skipped")
        self.assertFalse(self.P.triggers_json()["triggers_armed"])
        self.P.set_triggers_armed(True)
        self.run_for(120)                                          # next pass
        self.assertEqual(len(self.fires), 1)
        self.assertIn('"triggers_armed": true', (self.dir / "config.json").read_text().lower().replace("true", "true"))

    async def test_skip_next_skips_exactly_one(self):
        self.P.set_end(0, 0, "loop")
        self.add(10)
        await self.start()
        self.run_for(1)
        nt = self.P.next_trigger()
        self.assertAlmostEqual(nt["in_seconds"], 9.0, delta=0.2)
        self.assertEqual(nt["target"], "vo")
        self.assertEqual(self.P.skip_next_trigger()["id"], nt["id"])
        self.run_for(15)
        self.assertEqual(self.fires, [])
        self.assertEqual(self.notice(), "skipped")
        self.assertEqual(self.P.next_trigger()["next_pass"], True)  # the next one is in the next pass
        self.run_for(120)
        self.assertEqual(len(self.fires), 1)

    async def test_crossfade_to_another_track_does_not_fire(self):
        self.add(10)
        await self.start()
        self.run_for(9.0)
        self.assertTrue(self.P.play(0, 1, 2000))                   # crossfade away; the old deck is still audible for 2 s
        self.run_for(5)
        self.assertEqual(self.fires, [])

    async def test_fade_out_does_not_fire(self):
        self.add(10)
        await self.start()
        self.run_for(8)
        self.P.fade_out(5000)
        self.run_for(4)
        self.assertEqual(self.fires, [])

    async def test_track_end_is_clean(self):
        self.add(115)
        await self.start(1)                                        # other.wav (60 s) has no triggers; main would
        self.run_for(70)
        self.assertIsNone(self.S.live_deck)
        self.assertEqual(self.fires, [])

    async def test_next_trigger_and_end_of_track(self):
        self.add(10, "vo2.wav")
        await self.start()
        self.run_for(0.1)
        nt = self.P.next_trigger()
        self.assertEqual((nt["target"], nt["missing"], nt["next_pass"]), ("vo2", False, False))
        self.assertAlmostEqual(nt["in_seconds"], 10.0, delta=0.2)
        self.run_for(11)
        self.assertIsNone(self.P.next_trigger())                   # fired, none left (the track plays once)

    async def test_manual_top_does_not_stop_tracking(self):
        self.add(30)
        await self.start()
        self.run_for(5)
        self.P.play_on_top(1, 0)                                   # a 3 s voice-over, over main
        self.run_for(5)
        self.assertIs(self.P.trig_deck(), self.S.live_deck)        # back on main afterwards
        self.run_for(30)
        self.assertEqual(len(self.fires), 1)

    # ---- device change
    async def test_device_change_keeps_state(self):
        self.add(3, "vo.wav")
        self.add(10, "vo2.wav")
        await self.start()
        self.run_for(5)
        self.assertEqual(len(self.fires), 1)                       # the first fired before the change
        self.run_for(1)                                            # ... and its 3 s voice-over is gone
        self.assertTrue(self.P.set_device(None))
        self.assertAlmostEqual(self.pos(), 6.0, delta=0.3)
        self.run_for(4.5)                                          # the cache was emptied by the change: vo2 is due at 10 s and must be re-decoded
        await asyncio.sleep(0.3)
        self.run_for(1.5)
        self.assertEqual([f[1] for f in self.fires], ["vo.wav", "vo2.wav"])    # the first was not repeated, the second fired once

    # ---- pre-load
    async def test_target_is_warmed_before_the_time_comes(self):
        await self.asyncTearDown()
        await self.asyncSetUp(warm_loop=True)
        self.add(10, "vo2.wav")
        await self.load_all("main.wav")
        self.assertTrue(self.P.play(0, 0))
        self.t0 = self.fake.t
        self.run_for(1)
        self.assertTrue(any("vo2.wav" in tg for _t, tg in self.warm_calls))
        for _ in range(40):                                        # let the real warm-up run
            await asyncio.sleep(0.05)
            if self.P.cached(str(self.P.LIB / "vo2.wav")) is not None:
                break
        self.run_for(9.5)
        self.assertEqual(len(self.fires), 1)
        self.assertTrue(self.fires[0][2], "target was not in the cache when the trigger fired")
        self.assertEqual(self.P.trigger_targets()[:1] or ["vo2.wav"], ["vo2.wav"])

    async def test_not_ready_target_fires_as_soon_as_it_is_loaded(self):
        self.add(10, "vo2.wav")
        await self.start(preload=("main.wav",))                    # vo2 is not decoded
        self.run_for(10.5)
        await asyncio.sleep(0)                                     # let the load that was asked for start
        self.assertEqual(self.fires, [])                           # due, waiting
        self.assertIn(str(self.P.LIB / "vo2.wav"), self.P._loading)
        for _ in range(40):
            await asyncio.sleep(0.05)
            if self.P.cached(str(self.P.LIB / "vo2.wav")) is not None:
                break
        self.run_for(0.5)
        self.assertEqual(len(self.fires), 1)
        self.assertTrue(self.fires[0][2])

    async def test_warm_order_puts_trigger_targets_first(self):
        self.add(10, "vo2.wav")
        await self.start()
        self.assertEqual(self.P.trigger_targets(), ["vo2.wav"])

    # ---- data model
    async def test_api_validation(self):
        P = self.P
        self.assertEqual(P.set_triggers(0, 0, "add", {"at": -1, "file": "vo.wav"})[1], "the time must be between 0 and 86400 seconds")
        self.assertIn("not in the library", P.set_triggers(0, 0, "add", {"at": 5, "file": "nope.wav"})[1])
        self.assertIn("not in the library", P.set_triggers(0, 0, "add", {"at": 5, "file": "../x.wav"})[1])
        self.assertIn("after the end", P.set_triggers(0, 0, "add", {"at": 500, "file": "vo.wav"})[1])
        self.assertIn("needs a time", P.set_triggers(0, 0, "add", {"file": "vo.wav"})[1])
        self.assertEqual(P.set_triggers(0, 9, "add", {"at": 1, "file": "vo.wav"})[1], "no such track")
        self.assertEqual(P.set_triggers(0, 0, "update", {"id": "zz", "at": 1})[1], "no such trigger")
        self.assertEqual(P.set_triggers(0, 0, "bogus", {})[1], "unknown action")
        for k in range(self.app.mod("triggers_data").TRIG_MAX):
            self.add(k + 1)
        self.assertIn("at most", P.set_triggers(0, 0, "add", {"at": 99, "file": "vo.wav"})[1])

    async def test_add_update_delete_set_and_order(self):
        P = self.P
        a = self.add(30)
        b = self.add(10, once=True)
        lst = P.triggers_of(0, 0)
        self.assertEqual([x["at"] for x in lst], [10, 30])         # sorted
        self.assertEqual((lst[0]["once"], lst[0]["enabled"], lst[1]["once"]), (True, True, False))
        P.set_triggers(0, 0, "update", {"id": a, "at": 5, "enabled": False, "file": "vo2.wav"})
        lst = P.triggers_of(0, 0)
        self.assertEqual((lst[0]["id"], lst[0]["at"], lst[0]["enabled"], lst[0]["file"]), (a, 5, False, "vo2.wav"))
        P.set_triggers(0, 0, "delete", {"id": b})
        self.assertEqual(len(P.triggers_of(0, 0)), 1)
        lst, err = P.set_triggers(0, 0, "set", {"triggers": [{"id": a, "at": 7}, {"at": 9, "file": "vo.wav", "once": "1"}]})
        self.assertIsNone(err)
        self.assertEqual([(x["at"], x["once"]) for x in lst], [(7, False), (9, True)])
        self.assertEqual(lst[0]["file"], "vo2.wav")                # kept from the existing entry
        P.set_triggers(0, 0, "set", {"triggers": []})
        self.assertNotIn("triggers", P.playlists[0])               # an empty list leaves no trace

    async def test_disabled_trigger_never_fires(self):
        i = self.add(10)
        self.P.set_triggers(0, 0, "update", {"id": i, "enabled": False})
        await self.start()
        self.run_for(15)
        self.assertEqual(self.fires, [])

    async def test_survive_save_and_load(self):
        P = self.P
        self.add(12.5, "vo2.wav", once=True)
        P.save()
        P.playlists[:] = []
        P.load()
        tg = P.triggers_of(0, 0)[0]
        self.assertEqual((tg["at"], tg["file"], tg["once"], tg["enabled"]), (12.5, "vo2.wav", True, True))

    async def test_rename_follows_both_the_track_and_the_target(self):
        P = self.P
        self.add(12, "vo.wav")
        self.assertEqual(P.lib_rename("vo.wav", "voice.wav")[1], 200)
        self.assertEqual(P.triggers_of(0, 0)[0]["file"], "voice.wav")
        self.assertEqual(P.lib_rename("main.wav", "song.wav")[1], 200)
        self.assertEqual(P.playlists[0]["tracks"][0], "song.wav")
        self.assertEqual(len(P.triggers_of(0, 0)), 1)
        self.assertFalse(P.trigger_json(0, 0)[0]["missing"])

    async def test_move_to_another_playlist_carries_triggers(self):
        P = self.P
        self.add(12)
        P.playlists.append({"name": "C", "tracks": []})
        self.assertEqual(P.move_track(0, 0, 2, 0), "ok")
        self.assertEqual(len(P.triggers_of(2, 0)), 1)
        self.assertNotIn("triggers", P.playlists[0])

    async def test_reorder_inside_a_playlist_keeps_triggers(self):
        P = self.P
        self.add(12)
        self.assertEqual(P.move_track(0, 0, 0, 1), "ok")
        self.assertEqual(P.playlists[0]["tracks"], ["other.wav", "main.wav"])
        self.assertEqual(len(P.triggers_of(0, 1)), 1)
        self.assertEqual(P.triggers_of(0, 0), [])

    async def test_removed_from_playlist_keeps_its_triggers_like_trims(self):
        P = self.P
        self.add(12)
        P.remove_from_playlist(0, 0)
        P.add_to_playlist(0, ["main.wav"])
        self.assertEqual(len(P.triggers_of(0, 1)), 1)

    async def test_nothing_reaches_companion(self):
        P = self.P
        self.add(12)
        await self.start()
        self.run_for(1)
        names = " ".join(P.snapshot()) + " " + " ".join(P.VAR_INFO) + " " + " ".join(P.list_vars())
        self.assertNotIn("trigger", names.lower())
        self.assertNotIn("trigger", P.command(["triggers", "arm"]) or "unknown")   # not a command either
        self.assertEqual(P.command(["triggers"]), "unknown")

    async def test_live_triggers_json_greys_fired_and_voiceover_has_a_fid(self):
        P = self.P
        self.add(5)
        self.add(20, "vo2.wav")
        await self.start()
        self.run_for(0.1)
        lt = P.live_triggers_json()
        self.assertEqual((lt["fid"], [(i["n"], i["fired"]) for i in lt["items"]]), ("main.wav", [(1, False), (2, False)]))
        self.run_for(6)                                            # the first fired; its voice-over is live now
        self.assertIsNone(self.S.live_deck.pt)
        self.assertEqual(self.S.live_deck.fid, "vo.wav")
        lt = P.live_triggers_json()                                # still describes the track underneath
        self.assertEqual((lt["fid"], [i["fired"] for i in lt["items"]]), ("main.wav", [True, False]))
        self.run_for(40)
        self.assertEqual(len(self.fires), 2)

    async def test_disabled_and_outside_triggers_are_not_listed_live(self):
        P = self.P
        i = self.add(5)
        self.add(500 if False else 119)
        P.set_trim(0, 0, {"out": 100})
        P.set_triggers(0, 0, "update", {"id": i, "enabled": False})
        await self.start()
        self.run_for(0.1)
        self.assertEqual(P.live_triggers_json()["items"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
