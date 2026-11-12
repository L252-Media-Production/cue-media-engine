"""2.8.0 audio watchdog (cpl/watchdog.py): the logic with a fake clock and a fake output, and the Heartbeat with a fake mixer.
No real sleeps: the fake clock is moved by hand."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from harness.appload import load_app            # noqa: E402
from harness.engine import FakeTime             # noqa: E402
from harness.appcopy import copy_app            # noqa: E402
from harness.instance import PROJECT            # noqa: E402
import shutil, tempfile                          # noqa: E402


class Rig(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="wdtest-"))
        (self.dir / "media" / "library").mkdir(parents=True)
        (self.dir / "config.json").write_text('{"http_port": 18194, "osc_in_port": 18195}')
        copy_app(self.dir, PROJECT)
        self._argv = list(sys.argv)
        self.app = load_app(self.dir)
        self.clock = self.app.mod("clock")
        self.wd = self.app.mod("watchdog")
        self.fake = FakeTime()
        self.clock.install(self.fake)
        self.playing, self.beats, self.restarts, self.logs = True, 0, 0, []
        self.W = self.make()

    def make(self, enabled=lambda: True):
        return self.wd.Watchdog(lambda: self.beats, lambda: self.playing, self.do_restart, enabled=enabled, log=self.logs.append)

    def do_restart(self):
        self.restarts += 1

    def tearDown(self):
        self.clock.install(None)
        self.app.unload()
        sys.argv[:] = self._argv
        shutil.rmtree(self.dir, ignore_errors=True)

    def run_for(self, seconds, beat_every=None, step=0.05):
        """Advance the fake clock, polling every `step` s; the output beats every `beat_every` s (None = stalled)."""
        end = self.fake.t + seconds
        nxt = self.fake.t + beat_every if beat_every else None
        while self.fake.t < end - 1e-9:
            self.fake.t += step
            if nxt is not None and self.fake.t >= nxt:
                self.beats += 1
                nxt += beat_every
            self.W.poll()


class WatchdogLogic(Rig):
    def test_idle_and_paused_never_act(self):
        self.playing = False
        self.run_for(120)
        self.assertEqual((self.restarts, self.W.stalled), (0, False))

    def test_playing_and_beating_never_acts(self):
        self.run_for(120, beat_every=0.5)
        self.assertEqual((self.restarts, self.W.stalled), (0, False))

    def test_no_action_under_ten_seconds(self):
        self.run_for(9.5)
        self.assertEqual((self.restarts, self.W.stalled), (0, False))

    def test_one_restart_at_ten_seconds_and_it_is_logged(self):
        self.run_for(10.2)
        self.assertEqual(self.restarts, 1)
        self.assertTrue(self.W.stalled)
        self.assertEqual(self.logs, ["Watchdog: audio engine restarted (output stalled for 10 s)"])

    def test_start_of_playback_gets_a_full_window(self):
        self.playing = False
        self.run_for(30)
        self.playing = True
        self.run_for(9.5)
        self.assertEqual(self.restarts, 0)               # the wait counts from the play command, not from earlier silence
        self.run_for(1)
        self.assertEqual(self.restarts, 1)

    def test_pause_in_the_middle_resets_the_wait(self):
        self.run_for(8)
        self.playing = False
        self.run_for(5)
        self.playing = True
        self.run_for(9)
        self.assertEqual(self.restarts, 0)

    def test_recovery_clears_the_bad_state(self):
        self.run_for(10.2)
        self.assertTrue(self.W.stalled)
        self.run_for(2, beat_every=0.5)                    # the new engine delivers audio
        self.assertEqual((self.W.stalled, self.W.gave_up), (False, False))
        self.run_for(60, beat_every=0.5)
        self.assertEqual(self.restarts, 1)

    def test_restart_limit_three_in_ten_minutes(self):
        self.run_for(10.2 * 3 + 1)
        self.assertEqual(self.restarts, 3)
        self.run_for(60)                                   # still stalled: it must not restart a fourth time
        self.assertEqual(self.restarts, 3)
        self.assertTrue(self.W.gave_up)
        self.assertTrue(self.W.stalled)
        self.assertEqual(sum("not restarting again" in m for m in self.logs), 1)

    def test_limit_window_expires_after_ten_minutes(self):
        self.run_for(10.2 * 3 + 1)
        self.run_for(600)
        self.assertGreater(self.restarts, 3)               # the first restarts aged out of the window

    def test_gave_up_clears_when_the_output_moves_again(self):
        self.run_for(10.2 * 3 + 20)
        self.assertTrue(self.W.gave_up)
        self.run_for(2, beat_every=0.5)
        self.assertFalse(self.W.gave_up)
        self.assertFalse(self.W.stalled)

    def test_one_info_line_per_hour_while_playing(self):
        self.run_for(3 * 3600 + 60, beat_every=0.5, step=1.0)
        lines = [m for m in self.logs if m.startswith("Watchdog: running")]
        self.assertEqual(lines, ["Watchdog: running, 0 restarts since start"] * 3)

    def test_no_hourly_line_while_idle(self):
        self.playing = False
        self.run_for(3 * 3600, step=5.0)
        self.assertEqual(self.logs, [])

    def test_the_hourly_line_counts_restarts(self):
        self.run_for(10.2)
        self.assertEqual(self.restarts, 1)
        self.run_for(3600, beat_every=0.5, step=1.0)
        self.assertIn("Watchdog: running, 1 restart since start", self.logs)

    def test_switch_off_means_no_action(self):
        self.W = self.make(enabled=lambda: False)
        self.run_for(60)
        self.assertEqual((self.restarts, self.W.stalled), (0, False))

    def test_a_failing_restart_is_logged_and_does_not_raise(self):
        def boom():
            raise RuntimeError("no device")
        self.W.restart = boom
        self.run_for(10.2)
        self.assertTrue(any("restart failed" in m for m in self.logs))


class FakeChannel:
    def __init__(self):
        self.busy = False
        self.plays = 0

    def get_busy(self):
        return self.busy

    def play(self, snd):
        self.busy = True
        self.plays += 1


class FakeMixer:
    def __init__(self):
        self.ch = FakeChannel()

    def get_init(self):
        return (48000, -16, 2)

    class Sound:
        def __init__(self, buffer=None):
            self.n = len(buffer)

        def set_volume(self, v):
            pass

    def Channel(self, n):
        return self.ch


class HeartbeatTests(Rig):
    def test_beats_count_finished_sounds_only(self):
        mx = FakeMixer()
        hb = self.wd.Heartbeat(mx)
        hb.poll()
        self.assertEqual((hb.beats, mx.ch.plays), (0, 1))     # starting the sound is not a beat
        hb.poll()
        self.assertEqual((hb.beats, mx.ch.plays), (0, 1))     # still playing: the output has not moved on, nothing to count
        mx.ch.busy = False                                     # the audio callback consumed it
        hb.poll()
        self.assertEqual((hb.beats, mx.ch.plays), (1, 2))
        hb.frozen = True                                       # the test hook: as if the callback stalled
        mx.ch.busy = False
        hb.poll()
        self.assertEqual((hb.beats, mx.ch.plays), (1, 2))

    def test_the_sound_is_half_a_second_of_silence(self):
        mx = FakeMixer()
        hb = self.wd.Heartbeat(mx)
        hb.poll()
        self.assertEqual(hb._snd.n, int(48000 * 0.5) * 2 * 2)
        self.assertEqual(sum(1 for _ in [hb._snd]), 1)


if __name__ == "__main__":
    unittest.main()
