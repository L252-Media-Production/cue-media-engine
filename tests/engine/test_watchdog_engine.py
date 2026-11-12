"""2.8.0 watchdog inside the real player (fake clock, dummy audio): a stalled output restarts the audio engine and the live track carries on."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from harness.engine import EngineCase          # noqa: E402


class WatchdogInPlayer(EngineCase):
    WATCHDOG = True
    async def start_stalled(self):
        await self.load("a.wav", "b.wav")
        self.assertTrue(self.P.play(0, 0))
        self.P.HB.poll = lambda: None                      # no heartbeat ever finishes: the output does not move
        self.logs = []
        self.P.WD.log = self.logs.append
        self.inits = []
        real = self.P.init_mixer
        self.patch("init_mixer", lambda dev: (self.inits.append(dev), real(dev))[1])
        self.rebase()
        self.at(0.0)                                       # the main loop ticks every 50 ms: the watchdog's wait starts with the first tick of the track

    async def test_stall_restarts_the_engine_once_and_playback_resumes_at_the_position(self):
        await self.start_stalled()
        for s in range(1, 100):                            # up to 9.9 s in steps of 0.1 s: nothing yet
            self.at(s / 10.0)
        self.assertEqual(len(self.inits), 0)
        self.at(10.0)
        self.at(10.2)
        self.assertEqual(len(self.inits), 1, self.logs)
        self.assertEqual(self.logs, ["Watchdog: audio engine restarted (output stalled for 10 s)"])
        d = self.live()
        self.assertIsNotNone(d)
        self.assertEqual(self.pt(), (0, 0))
        self.assertGreater(d.fpos(), 9.5)                  # carried on from where it was, not from the start
        self.assertLess(d.fpos(), 10.6)
        self.assertTrue(self.P.WD.stalled)                 # stays bad until the new output delivers a beat
        self.P.HB.beats += 1
        self.at(10.4)
        self.assertFalse(self.P.WD.stalled)

    async def test_nothing_happens_while_paused(self):
        await self.start_stalled()
        self.P.pause_all()
        self.at(60.0)
        self.assertEqual(len(self.inits), 0)
        self.assertFalse(self.P.WD.stalled)

    async def test_switched_off_in_settings_means_no_action(self):
        await self.start_stalled()
        self.P.CFG["watchdog"] = False
        self.at(30.0)
        self.assertEqual(len(self.inits), 0)

    async def test_health_report_shows_the_engine_check(self):
        await self.start_stalled()
        for s in range(1, 103):
            self.at(s / 10.0)
        rep = self.P.health_report(force=True)
        eng = {c["id"]: c for c in rep["checks"]}["audio_engine"]
        self.assertEqual((eng["status"], rep["state"]), ("bad", "problem"))
