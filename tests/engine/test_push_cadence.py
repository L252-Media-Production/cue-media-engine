"""The `remaining` variable goes out once per second while a track plays, with the health refresh (ALERT.observe(health_report())) running in the same
loop as the real ticker() does it. Fake clock, 50 ms steps, no real time: this is the deterministic form of the OSC-gap check that
tests/api/test_settings.py::test_prefix_change_while_a_track_plays_switches_cleanly makes in real time."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from harness.engine import EngineCase      # noqa: E402


class Out:
    def __init__(self, clock):
        self.clock, self.sent = clock, []

    def send_message(self, addr, val):
        self.sent.append((self.clock.t, addr, val))


class PushCadence(EngineCase):
    async def test_remaining_is_sent_every_second_with_the_health_refresh_running(self):
        P = self.P
        out = Out(self.fake)
        P.osc_out = out
        P.last_sent.clear()
        await self.load("a.wav")
        self.assertTrue(P.play(0, 0))
        last_health, last_full = -9.0, 0.0
        for i in range(1, 181):                                     # 9 s of the 12 s track, as ticker() does it every 50 ms
            self.fake.t = self.t0 + i * 0.05
            P.tick()
            if self.fake.t - last_health >= 1.0:
                last_health = self.fake.t
                P.ALERT.observe(P.health_report())
            if self.fake.t - last_full >= 5:
                last_full = self.fake.t
                P.push(True)
            else:
                P.push()
        name = f"/custom-variable/{P.CFG['var_prefix']}remaining/value"
        rem = [(t, v) for t, a, v in out.sent if a == name]
        changed = [t for k, (t, v) in enumerate(rem) if k == 0 or v != rem[k - 1][1]]
        self.assertGreaterEqual(len(changed), 8)
        gaps = [b - a for a, b in zip(changed, changed[1:])]
        self.assertLessEqual(max(gaps), 1.05, f"gaps {gaps}")


if __name__ == "__main__":
    unittest.main()
