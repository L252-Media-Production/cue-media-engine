"""Live input, Duck only (cpl/liveinput.py): the detector with the fake clock.

There is no capture device here. The test plays the part of the capture helper: it writes constant-valued blocks (RMS = |value| / 32768, exactly)
into the shared ring (cpl.helpers.ring) one 10 ms block at a time, advances the fake clock by 10 ms and calls LI.poll(), which is what the player's
10 ms loop does. Everything the detector decides (attack, hold, release, Armed, Duck now, loss of input, Solo) is therefore measured on the real
code with exact numbers. What is NOT covered here: a real Dante / analog device, the helper process (tests/api/test_live_input.py runs that with
a synthetic source) and the audio actually leaving the speakers."""
import json
import math
import os
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from harness.engine import EngineCase           # noqa: E402

BLOCK = 480


def dc(db):
    """The constant 16-bit sample whose RMS is closest to `db` dBFS, and the exact RMS it has."""
    v = int(round(10 ** (db / 20.0) * 32768))
    return min(v, 32767), min(v, 32767) / 32768.0


class InputCase(EngineCase):
    LIB = {"bg.wav": (60, 0), "bg2.wav": (60, 0)}
    PLAYLISTS = [{"name": "bg", "tracks": ["bg.wav", "bg2.wav"]}]
    ATTACK, RELEASE = 40, 200

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.lin = self.app.mod("liveinput")
        self.ringmod = self.app.mod("helpers.ring")
        self.LI = self.lin.LI
        P = self.P
        P.CFG.update(duck_attack_ms=self.ATTACK, duck_release_ms=self.RELEASE, duck_ratio=6.0, duck_threshold_db=-30.0, input_threshold_db=-30.0, duck_hold=False,
                     input_device="Fake input", input_channel=1, input_gain_db=0.0, input_armed=True)
        self.path = self.dir / "ring.bin"
        self.writer = self.ringmod.Ring(self.path, writer=True, create=True)
        self.LI.attach(self.path)
        self.writer.new_epoch()
        self.LI.status = {"state": "ok", "reason": "", "channels": 2}
        await self.load("bg.wav")
        self.assertTrue(P.play(0, 0))
        self.bg = self.S.live_deck
        self.log = []

    async def asyncTearDown(self):
        self.LI.attach_closed = True
        self.writer.close()
        await super().asyncTearDown()

    # ---- the capture helper's part
    def block(self, db, advance=True, write=True):
        """One 10 ms block at `db` dBFS: written, 10 ms of fake time, one detector step. Returns the exact RMS written."""
        v, rms = dc(db)
        if self.LI.ptr is None:                    # the first poll after an attach / reopen only finds the starting position (as in the player)
            self.LI.poll()
        if write:
            self.writer.write(np.full(BLOCK, v, dtype=np.int16))
        if advance:
            self.fake.t += 0.01
        self.LI.poll()
        self.log.append((self.LI.gr, self.LI.level_db, self.bg.duck_in, self.bg.channel.get_volume()))
        return rms

    def blocks(self, db, n, **kw):
        return [self.block(db, **kw) for _ in range(n)]

    def target(self, rms, gain=0.0):
        db = 20 * math.log10(max(rms * 10 ** (gain / 20), 1e-6))
        return max(0.0, db - self.P.CFG["input_threshold_db"]) * (1 - 1 / self.P.CFG["duck_ratio"])


class Detector(InputCase):
    def test_silence_does_nothing(self):
        self.blocks(-90, 50)
        self.assertEqual(self.LI.gr, 0.0)
        self.assertEqual(self.bg.duck_in, 1.0)
        self.assertTrue(self.LI.alive)
        self.assertFalse(self.LI.signal(), "-90 dBFS is not a signal")

    def test_a_burst_below_the_threshold_does_not_duck_but_is_a_signal(self):
        self.blocks(-40, 40)                      # threshold is -30
        self.assertEqual(self.LI.gr, 0.0)
        self.assertEqual(self.bg.duck_in, 1.0)
        self.assertTrue(self.LI.signal(), "-40 dBFS is above the -60 dBFS signal level")

    def test_signal_present_needs_more_than_minus_60_within_the_last_half_second(self):
        self.blocks(-61, 20)
        self.assertFalse(self.LI.signal())
        self.blocks(-55, 1)
        self.assertTrue(self.LI.signal())
        self.blocks(-90, 49)                      # 490 ms later
        self.assertTrue(self.LI.signal())
        self.blocks(-90, 2)                       # 510 ms later
        self.assertFalse(self.LI.signal())

    def test_attack_follows_one_minus_exp_to_the_target_like_play_on_top(self):
        rms = None
        for k in range(1, 41):
            rms = self.block(-20)
            tgt = self.target(rms)
            self.assertGreater(tgt, 0)
            if k == 1:
                self.approx(self.LI.gr, tgt * (1 - math.exp(-0.01 / (self.ATTACK / 1000))), 1e-6)
        self.approx(self.LI.gr, tgt * (1 - math.exp(-40 * 0.01 / (self.ATTACK / 1000))), 1e-4, "after 400 ms (10 time constants)")
        self.approx(self.bg.duck_in, 10 ** (-self.LI.gr / 20), 1e-3)
        self.approx(self.bg.channel.get_volume(), self.bg.duck_in, 1 / 128 + 2e-3)

    def test_release_follows_exp_decay_after_the_speech_stops(self):
        self.blocks(-20, 60)
        gr0 = self.LI.gr
        self.assertGreater(gr0, 5)
        self.blocks(-90, 20)                      # 200 ms = one release time constant
        self.approx(self.LI.gr, gr0 * math.exp(-1), 1e-4)
        self.blocks(-90, 200)
        self.assertEqual(self.LI.gr, 0.0)
        self.assertEqual(self.bg.duck_in, 1.0, "back at full level")

    def test_hold_keeps_the_depth_for_the_hold_time_then_releases(self):
        self.P.CFG["duck_hold"] = True            # the shared Play on Top switch; the hold time is the fixed HOLD_S (1 s)
        self.blocks(-20, 80)
        depth = self.LI.hold_depth
        self.approx(depth, self.target(dc(-20)[1]), 1e-6)
        self.blocks(-90, 99)                      # 990 ms of silence: still held
        self.assertGreaterEqual(self.LI.gr, 0.98 * depth)
        self.blocks(-90, 60)                      # past the hold time: the release has started
        self.assertLess(self.LI.gr, 0.5 * depth)
        self.blocks(-90, 400)
        self.assertEqual(self.LI.gr, 0.0)

    def test_there_is_no_second_hold_setting(self):
        self.assertNotIn("input_hold_ms", self.P.CFG)
        self.P.CFG["input_hold_ms"] = 5          # a leftover from rc1 (config.json) is ignored and removed
        self.lin.sanitize_config()
        self.assertNotIn("input_hold_ms", self.P.CFG)
        self.P.CFG["duck_hold"] = True
        self.blocks(-20, 80)
        self.blocks(-90, 50)
        self.assertGreater(self.LI.gr, 0.95 * self.LI.hold_depth, "held for the fixed hold time whatever input_hold_ms said")

    def test_the_play_on_top_hold_switch_turns_the_input_hold_on_and_off(self):
        out = {}
        for hold in (True, False):
            self.P.CFG["duck_hold"] = hold
            self.LI.reset_detector(); self.writer.new_epoch()
            self.blocks(-20, 80)
            self.blocks(-90, 50)
            out[hold] = self.LI.gr
        self.assertGreater(out[True], 3 * out[False] + 1, out)

    def test_without_hold_the_depth_follows_the_level_between_words(self):
        self.P.CFG["duck_hold"] = False
        self.blocks(-20, 80)
        g1 = self.LI.gr
        self.blocks(-90, 29)
        self.assertLess(self.LI.gr, 0.5 * g1, "no hold: already releasing after 290 ms")

    def test_a_click_shorter_than_the_attack_barely_ducks_and_is_released(self):
        self.P.CFG["duck_attack_ms"] = 100
        self.blocks(-90, 10)
        self.block(-3)                            # one 10 ms click, far over the threshold
        peak = self.LI.gr
        full = self.target(dc(-3)[1])
        self.assertLess(peak, 0.12 * full, "10 ms of a 100 ms attack reaches under 10 % of the depth")
        self.assertGreater(peak, 0)
        self.blocks(-90, 300)
        self.assertEqual(self.LI.gr, 0.0)

    def test_the_input_gain_moves_the_threshold(self):
        self.blocks(-40, 40)
        self.assertEqual(self.LI.gr, 0.0)
        self.P.CFG["input_gain_db"] = 24.0
        self.blocks(-40, 60)
        self.assertGreater(self.LI.gr, 0)
        rms = dc(-40)[1]
        self.approx(self.LI.gr, self.target(rms, 24.0), 0.05)
        self.approx(self.LI.level_db, 20 * math.log10(rms) + 24.0, 1e-6, "the meter shows the level after the gain")
        self.P.CFG["input_gain_db"] = -12.0
        self.blocks(-20, 300)
        self.assertEqual(self.LI.gr, 0.0, "-20 dBFS - 12 dB = -32 dBFS is under the -30 dB threshold")

    def test_the_two_ducking_factors_multiply_and_never_overwrite_each_other(self):
        self.bg.duck = 0.5                        # Play on Top's factor
        self.bg.apply()
        self.blocks(-20, 80)
        self.assertLess(self.bg.duck_in, 1.0)
        self.assertEqual(self.bg.duck, 0.5)
        self.approx(self.bg.channel.get_volume(), 0.5 * self.bg.duck_in, 1 / 128 + 2e-3)

    def test_a_deck_started_while_ducking_is_ducked_too(self):
        self.blocks(-20, 80)
        gr = self.LI.gr
        self.P.play(0, 1) if False else None
        d2 = self.P.Deck((0, 1), "x", self.bg.sound, self.bg.channel)
        self.P.decks.append(d2)
        self.blocks(-20, 1)
        self.approx(d2.duck_in, 10 ** (-self.LI.gr / 20), 1e-3)


class ArmedAndDuckNow(InputCase):
    def test_armed_off_no_level_can_duck_but_meter_and_signal_still_work(self):
        self.P.CFG["input_armed"] = False
        self.blocks(-3, 100)
        self.assertEqual(self.LI.gr, 0.0)
        self.assertEqual(self.bg.duck_in, 1.0)
        self.assertTrue(self.LI.signal())
        self.assertAlmostEqual(self.LI.level_db, 20 * math.log10(dc(-3)[1]), places=3)

    def test_switching_armed_off_while_ducked_releases_with_the_quick_ramp(self):
        self.blocks(-20, 80)
        self.assertGreater(self.LI.gr, 5)
        self.P.CFG["input_armed"] = False
        self.blocks(-20, 10)                      # a loud input, but nothing may duck from it now
        self.assertEqual(self.LI.gr, 0.0)

    def test_duck_now_holds_the_threshold_plus_12_db_depth_and_releases_when_pressed_again(self):
        self.P.CFG["input_armed"] = False
        self.blocks(-90, 5)
        self.assertTrue(self.LI.set_duck_now(True))
        self.blocks(-90, 200)                     # no input level at all
        want = 12 * (1 - 1 / 6.0)
        self.approx(self.LI.gr, want, 1e-3)
        self.assertTrue(self.LI.ducking())
        self.assertEqual(self.P.snapshot()["input_duck_now"], "1")
        self.assertEqual(self.P.snapshot()["input_ducking"], "1")
        self.assertTrue(self.LI.set_duck_now(False))
        self.blocks(-90, 300)
        self.assertEqual(self.LI.gr, 0.0)
        self.assertEqual(self.bg.duck_in, 1.0)

    def test_duck_now_follows_the_ducking_settings(self):
        self.P.CFG["input_armed"] = False
        self.P.CFG.update(duck_ratio=2.0, duck_threshold_db=-20.0, input_threshold_db=-20.0)
        self.blocks(-90, 5)
        self.LI.set_duck_now(True)
        self.blocks(-90, 300)
        self.approx(self.LI.gr, 12 * 0.5, 1e-3)


class Ramp(InputCase):
    """Fix 1 (rc2): the input's ducking is taken off with a short linear-in-dB ramp, never a single step. For every way it can end (loss of the
    input, a stalled stream, Armed off, Duck now off) the gain never steps by more than 3 dB between two 10 ms samples and is fully released within 100 ms."""
    DEEP = -5          # dBFS: asks for (-5 + 30) * 5/6 = 20.8 dB of reduction

    def duck_deep(self):
        self.blocks(self.DEEP, 100)
        self.assertGreater(self.LI.gr, 20)
        return self.LI.gr

    def measure(self, trigger, write_after=True, max_polls=15):
        """Run `trigger()` and then poll every 10 ms; return the gr sequence starting with the value before the trigger."""
        seq = [self.LI.gr]
        trigger()
        for _ in range(max_polls):
            self.block(-90 if write_after else -90, write=write_after)
            seq.append(self.LI.gr)
        return seq

    def check(self, seq, what):
        steps = [seq[k] - seq[k + 1] for k in range(len(seq) - 1)]
        self.assertLessEqual(max(steps), 3.0 + 1e-6, f"{what}: a step of {max(steps):.2f} dB in {seq}")
        self.assertTrue(all(st >= -1e-9 for st in steps), f"{what}: the gain went back up while releasing {seq}")
        done = next(k for k, g in enumerate(seq) if g == 0.0)
        self.assertLessEqual(done, 10, f"{what}: released after {done * 10} ms, not within 100 ms: {seq}")
        self.assertGreaterEqual(done, 5, f"{what}: a release faster than the 50 ms ramp is a click: {seq}")
        self.assertEqual(self.bg.duck_in, 1.0)

    def test_loss_of_the_input_ramps_off(self):
        self.duck_deep()
        def lose():
            self.LI.status = {"state": "error", "reason": "the input stream failed", "channels": 0}
        self.check(self.measure(lose, write_after=False), "loss")

    def test_a_stalled_stream_ramps_off(self):
        self.duck_deep()
        seq = [self.LI.gr]
        for _ in range(60):                         # nothing is written: after 0.5 s the stall is found
            self.block(-90, write=False)
            seq.append(self.LI.gr)
            if not self.LI.alive:
                break
        self.assertFalse(self.LI.alive)
        k = len(seq) - 1
        tail = [seq[k - 1]]
        for _ in range(12):
            self.block(-90, write=False)
            tail.append(self.LI.gr)
        self.check([seq[k - 1], seq[k]] + tail[1:], "stall")

    def test_armed_off_ramps_off(self):
        self.duck_deep()
        self.check(self.measure(lambda: self.P.CFG.update(input_armed=False)), "armed off")

    def test_duck_now_off_ramps_off(self):
        self.P.CFG["input_armed"] = False
        self.blocks(-90, 5)
        self.LI.set_duck_now(True)
        self.P.CFG.update(duck_ratio=20.0, duck_threshold_db=-60.0, input_threshold_db=-60.0)        # a deep forced dip (12 dB * 0.95 = 11.4 dB)
        self.blocks(-90, 120)
        self.assertGreater(self.LI.gr, 10)
        self.check(self.measure(lambda: self.LI.set_duck_now(False)), "duck now off")

    def test_a_deeper_dip_takes_longer_but_never_more_than_100_ms(self):
        self.P.CFG.update(duck_threshold_db=-60.0, input_threshold_db=-60.0, duck_ratio=20.0)
        self.blocks(0, 150)
        deep = self.LI.gr
        self.assertGreater(deep, 50)
        seq = self.measure(lambda: self.P.CFG.update(input_armed=False))
        done = next(k for k, g in enumerate(seq) if g == 0.0)
        self.assertLessEqual(done, 10)

    def test_the_release_curve_is_used_when_it_is_faster_than_the_ramp(self):
        self.P.CFG["duck_release_ms"] = 10
        self.blocks(-20, 60)
        seq = self.measure(lambda: self.P.CFG.update(input_armed=False))
        self.assertLessEqual(next(k for k, g in enumerate(seq) if g == 0.0), 6)

    def test_speech_while_duck_now_goes_off_keeps_the_speech_ducking(self):
        self.LI.set_duck_now(True)
        self.blocks(-20, 120)
        self.LI.set_duck_now(False)
        self.blocks(-20, 30)
        self.assertGreater(self.LI.gr, 0.9 * self.target(dc(-20)[1]), "the ramp stops at the level the speech asks for")


class Override(InputCase):
    """Fix 2 (rc2): Duck now is a manual override. It needs no input device, no ring and no Armed, and it survives the loss of the input."""
    def test_duck_now_works_with_no_input_device_at_all(self):
        self.P.CFG["input_device"] = None
        self.P.CFG["input_armed"] = False
        self.blocks(-90, 3, write=False)
        self.assertFalse(self.LI.alive)
        self.assertTrue(self.LI.set_duck_now(True))
        self.blocks(-90, 150, write=False)
        self.approx(self.LI.gr, 12 * (1 - 1 / 6.0), 1e-2)
        self.assertLess(self.bg.duck_in, 0.4)
        self.assertEqual(self.P.snapshot()["input_duck_now"], "1")
        self.assertEqual(self.P.snapshot()["input_ducking"], "1")
        info = self.LI.info()
        self.assertTrue(info["duck_now"])
        self.assertEqual(info["chip"], "No input")
        self.LI.set_duck_now(False)
        self.blocks(-90, 20, write=False)
        self.assertEqual(self.LI.gr, 0.0)
        self.assertEqual(self.P.snapshot()["input_duck_now"], "0")

    def test_losing_the_input_releases_only_the_input_driven_ducking(self):
        self.LI.set_duck_now(True)
        self.blocks(-5, 120)                       # speech on top of Duck now
        self.assertGreater(self.LI.gr, 18)
        forced = self.LI.forced_db()
        self.LI.status = {"state": "error", "reason": "device gone", "channels": 0}
        self.blocks(-90, 150, write=False)
        self.assertTrue(self.LI.duck_now, "Duck now is not cleared by the loss")
        self.approx(self.LI.gr, forced, 0.05, "it falls back to the forced depth, not to zero")
        self.assertEqual(self.LI.info()["chip"], "No input")
        self.assertEqual(self.P.snapshot()["input_duck_now"], "1")
        # the device returns: Duck now is still on, and speech ducks deeper again
        self.writer.new_epoch()
        self.LI.status = {"state": "ok", "reason": "", "channels": 2}
        self.blocks(-5, 100)
        self.assertTrue(self.LI.duck_now)
        self.assertGreater(self.LI.gr, forced + 5)

    def test_duck_now_survives_armed_off_and_an_unarmed_start(self):
        self.P.CFG["input_armed"] = False
        self.LI.set_duck_now(True)
        self.blocks(-90, 150)
        self.assertGreater(self.LI.gr, 8)
        self.P.CFG["input_armed"] = True
        self.P.CFG["input_armed"] = False
        self.blocks(-90, 20)
        self.assertGreater(self.LI.gr, 8)

    def test_it_is_not_saved_so_a_restart_clears_it(self):
        self.LI.set_duck_now(True)
        self.LI.set_config({"gain_db": 1})
        import json
        self.assertNotIn("duck", json.dumps(json.loads((self.dir / "state.json").read_text())))

    def test_the_command_and_the_api_never_refuse(self):
        self.LI.status = {"state": "error", "reason": "x", "channels": 0}
        self.block(-90)
        self.assertEqual(self.P.command(["input", "ducknow", "on"]), "ok")
        self.assertTrue(self.LI.duck_now)
        self.assertEqual(self.P.command(["input", "ducknow", "off"]), "ok")
        self.assertFalse(self.LI.duck_now)


class Safety(InputCase):
    def duck_all_the_way(self):
        self.blocks(-15, 100)
        self.assertGreater(self.LI.gr, 8)
        self.assertLess(self.bg.duck_in, 0.8)

    def assert_released(self, why):
        self.blocks(-90, 12, write=False)           # the 50-100 ms ramp
        self.assertEqual(self.LI.gr, 0.0, why)
        self.assertEqual(self.bg.duck_in, 1.0, why)
        self.approx(self.bg.channel.get_volume(), self.bg.vol * self.bg.gain * self.bg.duck, 1 / 128 + 1e-3)
        self.assertFalse(self.LI.ducking())
        self.assertEqual(self.LI.info()["chip"], "No input")
        self.assertTrue(self.LI.info()["reason"])
        self.assertTrue(self.P.CFG["input_armed"], "Armed is a setting and is kept")

    def test_a_stalled_stream_releases(self):
        self.duck_all_the_way()
        for _ in range(45):
            self.block(-90, write=False)
        self.assertTrue(self.LI.alive, "450 ms of nothing is not yet a stall")
        for _ in range(8):
            self.block(-90, write=False)
        self.assertFalse(self.LI.alive)
        self.assert_released("stall")
        self.assertIn("No audio", self.LI.info()["reason"])

    def test_a_stream_error_releases(self):
        self.duck_all_the_way()
        self.LI.status = {"state": "error", "reason": "the input stream failed", "channels": 0}
        self.LI.poll()
        self.assert_released("error")
        self.assertEqual(self.LI.info()["reason"], "the input stream failed")

    def test_a_removed_device_releases_and_recovers_when_it_returns(self):
        self.duck_all_the_way()
        self.LI.status = {"state": "error", "reason": "the input device \"Fake input\" disappeared (unplugged?)", "channels": 0}
        self.LI.poll()
        self.assert_released("device removed")
        self.blocks(-20, 30, write=False)          # still gone: stays released, nothing ducks
        self.assertEqual(self.bg.duck_in, 1.0)
        self.writer.new_epoch()
        self.LI.status = {"state": "ok", "reason": "", "channels": 2}
        self.blocks(-20, 60)
        self.assertTrue(self.LI.alive)
        self.assertEqual(self.LI.info()["chip"], "Signal present")
        self.assertGreater(self.LI.gr, 3)
        self.assertLess(self.bg.duck_in, 0.9)

    def test_no_device_chosen_means_no_input_and_no_input_ducking(self):
        self.P.CFG["input_device"] = None
        self.blocks(-20, 40)
        self.assertEqual(self.LI.gr, 0.0)
        self.assertFalse(self.LI.alive)
        self.assertEqual(self.LI.info()["reason"], "No input device chosen")

    def test_a_missing_saved_device_says_so(self):
        self.LI.status = {"state": "error", "reason": "the input device \"Fake input\" was not found (unplugged, or not running)", "channels": 0}
        self.block(-20)
        self.assertIn("retried every few seconds", self.LI.info()["reason"])

    async def test_an_error_inside_the_detector_never_reaches_the_player(self):
        import asyncio
        self.duck_all_the_way()

        def boom():
            raise RuntimeError("test")
        self.LI.poll = boom
        n = [0]
        real = asyncio.sleep

        async def fake(d, *a, **k):
            n[0] += 1
            self.fake.t += d
            if n[0] > 15:
                raise asyncio.CancelledError()
            await real(0)
        asyncio.sleep = fake
        try:
            with self.assertRaises(asyncio.CancelledError):
                await self.lin.loop()
        finally:
            asyncio.sleep = real
            del self.LI.poll
        self.assertEqual(n[0], 16, "the loop kept going after the error")
        self.assertFalse(self.LI.alive, "and the input counts as lost")
        self.assertEqual(self.LI.gr, 0.0, "the input ducking was ramped off")


class Watchdog(InputCase):
    """Fix 4 (rc2): a detector that has not run for 250 ms must not leave the music ducked."""
    def test_a_blocked_detector_is_released_by_the_tick_and_recovers_by_itself(self):
        self.blocks(-5, 100)
        self.assertGreater(self.LI.gr, 18)
        self.assertEqual(self.LI.info()["chip"], "Signal present")
        t_block = self.fake.t
        released_at = None
        for k in range(1, 40):                      # the detector task does not run; the 50 ms tick does
            self.fake.t = t_block + 0.05 * k
            self.P.tick()
            if self.fake.t - t_block <= 0.25:
                self.assertTrue(self.LI.gr > 18, "not yet: the detector may only be 250 ms late")
            if self.LI.gr == 0.0 and released_at is None:
                released_at = self.fake.t - t_block
        self.assertIsNotNone(released_at)
        self.assertLessEqual(released_at, 0.25 + 0.15, f"released {released_at:.2f} s after the detector last ran")
        self.assertEqual(self.bg.duck_in, 1.0)
        self.assertEqual(self.LI.info()["chip"], "Detector stalled")
        self.assertIn("detector", self.LI.info()["reason"])
        self.assertEqual(self.P.snapshot()["input_ducking"], "0")
        # the detector runs again (late, with a gap): that poll is skipped, the next on-time one recovers
        self.writer.write(np.full(BLOCK * 50, dc(-5)[0], dtype=np.int16))
        self.LI.poll()
        self.assertTrue(self.LI.stalled)
        self.assertEqual(self.LI.gr, 0.0, "the audio written during the gap is old and is not analysed")
        self.blocks(-5, 100)
        self.assertFalse(self.LI.stalled)
        self.assertEqual(self.LI.info()["chip"], "Signal present")
        self.assertGreater(self.LI.gr, 18, "ducking from speech is back")

    def test_a_detector_that_runs_on_time_never_trips_the_watchdog(self):
        self.blocks(-5, 100)
        for k in range(60):
            self.block(-5)
            if k % 5 == 0:
                self.P.tick()
        self.assertFalse(self.LI.is_stalled())
        self.assertGreater(self.LI.gr, 18)

    def test_duck_now_is_not_touched_by_a_stalled_detector(self):
        self.LI.set_duck_now(True)
        self.blocks(-90, 150)
        forced = self.LI.gr
        self.assertGreater(forced, 8)
        t0 = self.fake.t
        for k in range(1, 20):
            self.fake.t = t0 + 0.05 * k
            self.P.tick()
        self.assertTrue(self.LI.duck_now)
        self.approx(self.LI.gr, forced, 0.3)


class SoloIsolation(InputCase):
    """Solo changes nothing the detector or Live can see: the same burst with Solo off and on gives the same level, reduction and deck volume at every step."""
    def run_burst(self, solo):
        self.log = []
        self.LI.reset_detector()
        self.writer.new_epoch()
        self.LI.status = {"state": "ok", "reason": "", "channels": 2}
        self.LI.set_solo(solo)
        self.blocks(-90, 10)
        self.blocks(-20, 60)
        self.blocks(-90, 60)
        self.blocks(-25, 20)
        self.blocks(-90, 100)
        return list(self.log), self.LI.signal(), self.LI.ducking()

    def test_solo_on_and_off_give_identical_detector_and_deck_numbers(self):
        a = self.run_burst(False)
        b = self.run_burst(True)
        c = self.run_burst(False)
        self.assertEqual(a, b, "Solo on changed the detector level, the reduction or the Live deck volume")
        self.assertEqual(a, c)
        self.assertGreater(max(x[0] for x in a[0]), 5, "the burst did duck, so the comparison means something")

    def test_the_detector_never_writes_to_the_ring_and_the_tap_is_a_read_only_map(self):
        before = self.writer.written
        self.LI.set_solo(True)
        self.blocks(-20, 10)
        self.assertEqual(self.writer.written, before + 10 * BLOCK, "only the helper (here: the test) writes")
        r = self.ringmod.Ring(self.path)           # how the preview worker opens it
        with self.assertRaises(PermissionError):
            r.write(np.zeros(4, dtype=np.int16))
        with self.assertRaises((ValueError, TypeError)):
            r._raw[0] = 1
        r.close()

    def test_two_readers_keep_separate_pointers(self):
        r1, r2 = self.ringmod.Ring(self.path), self.ringmod.Ring(self.path)
        self.writer.write(np.arange(1000, dtype=np.int16))
        p1, d1, _ = r1.read(self.writer.written - 1000)
        self.assertEqual(len(d1), 1000)
        p2, d2, _ = r2.read(p1 - 400)
        self.assertEqual(len(d2), 400, "the second reader is not moved by the first")
        np.testing.assert_array_equal(d2, d1[-400:])
        r1.close(); r2.close()


class ReuseOfPlayOnTop(InputCase):
    def settled(self, **cfg):
        self.P.CFG.update(cfg)
        self.LI.reset_detector()
        self.writer.new_epoch()
        self.blocks(-20, 400)
        return self.LI.gr

    def test_ratio_attack_release_and_hold_are_shared_with_play_on_top_and_the_threshold_is_its_own(self):
        base = self.settled()
        self.assertGreater(base, 5)
        self.assertLess(self.settled(input_threshold_db=-15.0), base - 4, "a higher threshold ducks less")
        self.assertLess(self.settled(input_threshold_db=-30.0, duck_ratio=2.0), base - 3, "a lower ratio ducks less")
        self.P.CFG["duck_ratio"] = 6.0
        self.LI.reset_detector(); self.writer.new_epoch()
        self.P.CFG["duck_attack_ms"] = 200
        self.blocks(-20, 5)
        slow = self.LI.gr
        self.P.CFG["duck_attack_ms"] = 10
        self.LI.reset_detector(); self.writer.new_epoch()
        self.blocks(-20, 5)
        self.assertGreater(self.LI.gr, 2 * slow, "a faster attack reaches the depth sooner")
        self.P.CFG["duck_release_ms"] = 1000
        self.blocks(-20, 100); g = self.LI.gr
        self.blocks(-90, 50)
        slowrel = self.LI.gr
        self.P.CFG["duck_release_ms"] = 50
        self.blocks(-20, 100); g = self.LI.gr
        self.blocks(-90, 50)
        self.assertLess(self.LI.gr, 0.2 * slowrel, "a shorter release comes back sooner")
        self.P.CFG.update(duck_hold=True, duck_release_ms=500)
        self.blocks(-20, 100)
        self.blocks(-90, 20)
        held = self.LI.gr
        self.P.CFG["duck_hold"] = False
        self.LI.reset_detector(); self.writer.new_epoch()
        self.blocks(-20, 100)
        self.blocks(-90, 20)
        self.assertLess(self.LI.gr, held, "hold on keeps the depth after the speech, hold off does not")

    def test_the_gain_computation_is_the_play_on_top_one(self):
        dsp = self.app.mod("dsp")
        for rms in (0.001, 0.02, 0.1, 0.5, 1.0):
            for gain, ratio, thr in ((0, 6, -30), (12, 3, -40), (-6, 20, -10)):
                a = dsp.input_target_db(rms, gain, ratio, thr)
                b = float(dsp.duck_curve(np.array([rms], dtype=np.float32), 10 ** (gain / 20), ratio, thr, False)[0])
                self.assertEqual(a, b)


class Settings(InputCase):
    def setUp(self):
        self.mock = Path(tempfile.mkdtemp(prefix="mockdev-"))
        (self.mock / "mock_inputs.json").write_text(json.dumps(["Fake input", "Dante Virtual Soundcard", "Analog 1-2"]))
        self.old_env = os.environ.get("CP_TEST_DEVICES")
        os.environ["CP_TEST_DEVICES"] = str(self.mock)

    def tearDown(self):
        if self.old_env is None:
            os.environ.pop("CP_TEST_DEVICES", None)
        else:
            os.environ["CP_TEST_DEVICES"] = self.old_env

    def state(self):
        return json.loads((self.dir / "state.json").read_text())

    def test_valid_values_are_applied_and_saved_as_they_are_made(self):
        self.assertIsNone(self.LI.set_config({"gain_db": 6.5}))
        self.assertIsNone(self.LI.set_config({"channel": 2}))
        self.assertIsNone(self.LI.set_config({"armed": False}))
        self.assertIsNone(self.LI.set_config({"device": "Analog 1-2"}))
        s = self.state()
        self.assertEqual((s["input_gain_db"], s["input_channel"], s["input_armed"], s["input_device"]), (6.5, 2, False, "Analog 1-2"))

    def test_the_gain_range_is_minus_12_to_plus_24(self):
        for ok in (-12, -12.0, 0, 24, "24", 3.25):
            self.assertIsNone(self.LI.set_config({"gain_db": ok}), ok)
        for bad in (-12.1, 24.1, 100, "x", None, float("nan"), float("inf"), True, [1]):
            before = dict(self.P.CFG)
            self.assertTrue(self.LI.set_config({"gain_db": bad}), f"{bad!r} should be refused")
            self.assertEqual(self.P.CFG["input_gain_db"], before["input_gain_db"], "nothing changes on a refusal")

    def test_the_channel_must_be_a_whole_number_from_1_to_64(self):
        for ok in (1, 2, 64, "3", 4.0):
            self.assertIsNone(self.LI.set_config({"channel": ok}), ok)
        for bad in (0, 65, -1, 1.5, "x", None, True):
            self.assertTrue(self.LI.set_config({"channel": bad}), f"{bad!r} should be refused")

    def test_an_unknown_device_is_refused_and_a_valid_one_selected(self):
        self.assertEqual(self.LI.set_config({"device": "No such card"}), "unknown device")
        self.assertEqual(self.P.CFG["input_device"], "Fake input")
        self.assertIsNone(self.LI.set_config({"device": "Dante Virtual Soundcard"}))
        self.assertIsNone(self.LI.set_config({"device": None}), "none = no input")
        self.assertIsNone(self.P.CFG["input_device"])

    def test_one_bad_value_in_a_request_changes_nothing(self):
        self.assertTrue(self.LI.set_config({"gain_db": 5, "channel": 99}))
        self.assertEqual(self.P.CFG["input_gain_db"], 0.0)

    def test_saved_values_that_are_garbage_fall_back_to_defaults(self):
        self.P.CFG.update(input_gain_db=999, input_channel="seven", input_armed="yes", input_device=5)
        self.lin.sanitize_config()
        self.assertEqual((self.P.CFG["input_gain_db"], self.P.CFG["input_channel"], self.P.CFG["input_armed"], self.P.CFG["input_device"]),
                         (0.0, 1, True, None))

    def test_defaults_are_off_armed_gain_zero_channel_one(self):
        cfg = self.app.mod("config").CFG
        self.assertIs(cfg["input_armed"] is False, True) if False else None
        # a fresh install: read the declared defaults from a clean module copy
        import importlib, re
        src = (self.dir / "cpl" / "config.py").read_text()
        for key, val in (("input_device", "None"), ("input_channel", "1"), ("input_gain_db", "0.0"), ("input_armed", "False")):
            self.assertRegex(src, r'"%s":\s+%s,' % (key, re.escape(val)))

    def test_duck_now_and_solo_are_not_saved(self):
        self.LI.set_duck_now(True) if self.LI.alive else None
        self.LI.set_solo(True)
        self.LI.set_config({"gain_db": 1})
        s = self.state()
        self.assertNotIn("duck_now", json.dumps(s))
        self.assertNotIn("solo", json.dumps(s))


class Variables(InputCase):
    def test_the_four_variables_follow_the_state(self):
        v = self.P.snapshot()
        self.assertEqual((v["input_armed"], v["input_duck_now"], v["input_signal"], v["input_ducking"]), ("1", "0", "0", "0"))
        self.blocks(-20, 80)
        v = self.P.snapshot()
        self.assertEqual((v["input_signal"], v["input_ducking"]), ("1", "1"))
        self.P.CFG["input_armed"] = False
        self.assertEqual(self.P.snapshot()["input_armed"], "0")

    def test_the_commands_follow_the_grammar(self):
        P = self.P
        self.assertEqual("ok", P.command(["input", "armed", "off"]))
        self.assertFalse(P.CFG["input_armed"])
        self.assertEqual("ok", P.command(["input", "armed", "toggle"]))
        self.assertTrue(P.CFG["input_armed"])
        self.assertEqual("ok", P.command(["input", "armed", "0"]))
        self.assertFalse(P.CFG["input_armed"])
        self.blocks(-90, 5)
        self.assertEqual("ok", P.command(["input", "ducknow", "on"]))
        self.assertTrue(self.LI.duck_now)
        self.assertEqual("ok", P.command(["input", "ducknow", "toggle"]))
        self.assertFalse(self.LI.duck_now)
        self.assertEqual(P.command(["input", "armed", "maybe"]), "invalid")
        self.assertEqual(P.command(["input", "nothing"]), "invalid")
        self.assertEqual(P.command(["input"]), "invalid")
        self.LI.status = {"state": "error", "reason": "x", "channels": 0}
        self.block(-90)
        self.assertEqual(P.command(["input", "ducknow", "on"]), "ok", "Duck now is a manual override: never refused")


class StereoCase(InputCase):
    """A stereo pair: the ring carries two channels per frame. The test plays the capture helper: it writes (480, 2) blocks."""
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.P.CFG.update(input_channels=[1, 2], input_channel=1)
        self.writer.new_epoch(2)
        self.LI.reset_detector()
        self.LI.status = {"state": "ok", "reason": "", "channels": 2, "names": []}

    def sblock(self, left, right, advance=True, write=True):
        """One 10 ms block with the left channel at `left` dBFS and the right one at `right` dBFS."""
        if self.LI.ptr is None:
            self.LI.poll()
        (vl, rl), (vr, rr) = dc(left), dc(right)
        if write:
            self.writer.write(np.stack([np.full(BLOCK, vl, dtype=np.int16), np.full(BLOCK, vr, dtype=np.int16)], axis=1))
        if advance:
            self.fake.t += 0.01
        self.LI.poll()
        self.log.append((self.LI.gr, self.LI.level_db, tuple(self.LI.levels_db), self.bg.duck_in, self.bg.channel.get_volume()))
        return rl, rr

    def sblocks(self, left, right, n, **kw):
        return [self.sblock(left, right, **kw) for _ in range(n)]


class StereoPair(StereoCase):
    def test_only_left_loud_ducks(self):
        rl, rr = self.sblocks(-5, -90, 120)[-1]
        self.assertGreater(self.LI.gr, 18)
        self.approx(self.LI.gr, self.target(rl), 0.05)
        self.assertTrue(self.LI.signal())
        self.approx(self.LI.levels_db[0], 20 * math.log10(rl), 1e-3)
        self.assertLess(self.LI.levels_db[1], -80)
        self.approx(self.LI.level_db, self.LI.levels_db[0], 1e-9, "level_db stays, as the maximum")

    def test_only_right_loud_ducks_the_same(self):
        rl, rr = self.sblocks(-90, -5, 120)[-1]
        self.approx(self.LI.gr, self.target(rr), 0.05)
        self.approx(self.LI.level_db, self.LI.levels_db[1], 1e-9)
        self.assertTrue(self.LI.signal())

    def test_both_loud_is_the_maximum_not_the_sum(self):
        rl, rr = self.sblocks(-12, -12, 150)[-1]
        self.approx(self.LI.gr, self.target(rl), 0.05)
        self.sblocks(-20, -10, 150)
        self.approx(self.LI.gr, self.target(dc(-10)[1]), 0.05, "the louder channel counts")

    def test_both_quiet_does_not_duck_and_is_no_signal(self):
        self.sblocks(-90, -80, 60)
        self.assertEqual(self.LI.gr, 0.0)
        self.assertFalse(self.LI.signal())
        self.sblocks(-61, -90, 10)
        self.assertFalse(self.LI.signal())
        self.sblocks(-90, -50, 1)
        self.assertTrue(self.LI.signal(), "signal present when EITHER channel is above -60 dBFS")

    def test_the_gain_applies_to_both_channels(self):
        self.P.CFG["input_gain_db"] = 24.0
        rl, rr = self.sblocks(-50, -45, 150)[-1]
        self.approx(self.LI.levels_db[0], 20 * math.log10(rl) + 24, 1e-3)
        self.approx(self.LI.levels_db[1], 20 * math.log10(rr) + 24, 1e-3)
        self.approx(self.LI.gr, self.target(rr, 24.0), 0.05)
        self.assertGreater(self.LI.gr, 5)
        self.P.CFG["input_gain_db"] = -12.0
        self.sblocks(-20, -20, 300)
        self.assertEqual(self.LI.gr, 0.0)

    def test_attack_hold_and_release_are_the_shared_ones(self):
        self.P.CFG["duck_hold"] = True
        self.sblocks(-5, -90, 100)
        depth = self.LI.hold_depth
        self.sblocks(-90, -90, 90)
        self.assertGreater(self.LI.gr, 0.95 * depth)
        self.sblocks(-90, -90, 200)
        self.assertEqual(self.LI.gr, 0.0)

    def test_the_release_ramp_after_a_loss_is_the_same(self):
        self.sblocks(-5, -90, 100)
        seq = [self.LI.gr]
        self.LI.status = {"state": "error", "reason": "gone", "channels": 0, "names": []}
        for _ in range(12):
            self.sblock(-90, -90, write=False)
            seq.append(self.LI.gr)
        steps = [seq[k] - seq[k + 1] for k in range(len(seq) - 1)]
        self.assertLessEqual(max(steps), 3.0 + 1e-6)
        self.assertEqual(seq[-1], 0.0)

    def test_the_state_has_per_channel_levels_and_the_pair(self):
        self.sblocks(-30, -40, 20)
        i = self.LI.info()
        self.assertTrue(i["stereo"])
        self.assertEqual(i["channel_list"], [1, 2])
        self.assertEqual(len(i["levels_db"]), 2)
        self.assertEqual(i["level_db"], max(i["levels_db"]))
        self.assertEqual(i["channel_label"], "Channel 1/Channel 2")
        self.assertEqual(self.P.meters_json()["input"]["levels_db"], i["levels_db"])
        self.assertTrue(self.P.meters_json()["input"]["stereo"])

    def test_solo_changes_nothing_for_a_pair(self):
        def burst(solo):
            self.log = []
            self.LI.reset_detector(); self.writer.new_epoch(2)
            self.LI.status = {"state": "ok", "reason": "", "channels": 2, "names": []}
            self.LI.set_solo(solo)
            self.sblocks(-90, -90, 10); self.sblocks(-20, -60, 60); self.sblocks(-90, -8, 60); self.sblocks(-90, -90, 100)
            return list(self.log), self.LI.signal(), self.LI.ducking()
        a, b, c = burst(False), burst(True), burst(False)
        self.assertEqual(a, b, "Solo on changed the detector level, the reduction or the Live deck volume")
        self.assertEqual(a, c)
        self.assertGreater(max(x[0] for x in a[0]), 5)


class MonoSelection(InputCase):
    """A single channel: the ring carries one channel. (Which device column the helper takes is tested through the fake helper in tests/api/test_live_input.py.)"""
    def test_the_info_of_a_single_channel(self):
        self.P.CFG.update(input_channels=[2], input_channel=2)
        self.blocks(-30, 10)
        i = self.LI.info()
        self.assertFalse(i["stereo"])
        self.assertEqual(i["channel_list"], [2])
        self.assertEqual(i["channel"], 2)
        self.assertEqual(len(i["levels_db"]), 1)
        self.assertEqual(i["channel_label"], "Channel 2")


class Choices(InputCase):
    def labels(self, n, names=None, sel=None):
        return [(c["group"], c["label"]) for c in self.lin.channel_choices(n, names, sel)]

    def test_a_two_channel_device_has_exactly_three_choices(self):
        self.assertEqual(self.labels(2), [("Stereo pair", "Channel 1/Channel 2 (stereo)"), ("Single channel", "Channel 1 (mono)"), ("Single channel", "Channel 2 (mono)")])

    def test_three_channels_pairs_first_and_an_odd_last_channel_has_no_pair(self):
        got = self.labels(3)
        self.assertEqual([l for g, l in got if g == "Stereo pair"], ["Channel 1/Channel 2 (stereo)", "Channel 2/Channel 3 (stereo)"])
        self.assertEqual([l for g, l in got if g == "Single channel"], ["Channel 1 (mono)", "Channel 2 (mono)", "Channel 3 (mono)"])
        self.assertEqual([g for g, l in got], ["Stereo pair"] * 2 + ["Single channel"] * 3, "pairs come first")

    def test_eight_channels(self):
        got = self.labels(8)
        self.assertEqual(len([1 for g, l in got if g == "Stereo pair"]), 7)
        self.assertEqual(len([1 for g, l in got if g == "Single channel"]), 8)
        self.assertEqual(got[6], ("Stereo pair", "Channel 7/Channel 8 (stereo)"))
        self.assertEqual(got[7], ("Single channel", "Channel 1 (mono)"))

    def test_the_devices_own_names_are_used_when_it_reports_them(self):
        got = self.labels(2, ["Mic L", "Mic R"])
        self.assertEqual(got[0][1], "Mic L/Mic R (stereo)")
        self.assertEqual(got[2][1], "Mic R (mono)")
        self.assertEqual(self.labels(3, ["A", "", "C"])[1][1], "Channel 2/C (stereo)")

    def test_the_saved_choice_is_always_in_the_menu(self):
        got = self.lin.channel_choices(0, None, [11, 12])
        self.assertIn("11-12", [c["v"] for c in got])
        self.assertEqual(len(self.lin.channel_choices(0)), 7 + 8, "an unknown device offers eight channels")

    def test_the_value_of_each_choice_round_trips_through_the_validation(self):
        for c in self.lin.channel_choices(8):
            self.assertEqual(self.lin.clean_channels([int(x) for x in c["v"].split("-")]), c["channels"])

    def test_validation_of_channel_lists(self):
        ok = self.lin.clean_channels
        self.assertEqual(ok([1, 2]), [1, 2]); self.assertEqual(ok(3), [3]); self.assertEqual(ok("4"), [4]); self.assertEqual(ok([64]), [64]); self.assertEqual(ok([63, 64]), [63, 64])
        for bad in ([], [1, 2, 3], [1, 3], [2, 1], [1, 1], [0], [65], [64, 65], ["x"], None, True, [1.5], {}):
            with self.assertRaises(ValueError, msg=repr(bad)):
                ok(bad)

    def test_info_choices_follow_the_device_channel_count(self):
        self.LI.status = {"state": "ok", "reason": "", "channels": 2, "names": []}
        self.assertEqual([c["v"] for c in self.LI.info()["choices"]], ["1-2", "1", "2"])
        self.LI.status = {"state": "ok", "reason": "", "channels": 8, "names": []}
        self.assertEqual(len(self.LI.info()["choices"]), 15)


class SavedChannel(InputCase):
    def test_a_channel_saved_before_stereo_pairs_is_the_same_single_channel(self):
        self.P.CFG.pop("input_channels", None)
        self.P.CFG["input_channel"] = 2
        self.lin.sanitize_config()
        self.assertEqual(self.P.CFG["input_channels"], [2])
        self.assertEqual(self.LI.channels(), [2])

    def test_the_default_of_a_fresh_setup_is_channel_1(self):
        self.P.CFG["input_channels"] = None
        self.P.CFG["input_channel"] = 1
        self.lin.sanitize_config()
        self.assertEqual(self.P.CFG["input_channels"], [1])
        src = (self.dir / "cpl" / "config.py").read_text()
        self.assertRegex(src, r'"input_channel":\s+1,')
        self.assertRegex(src, r'"input_channels":\s+None,')

    def test_the_new_key_wins_and_both_are_saved(self):
        import json
        self.assertIsNone(self.LI.set_config({"channels": [3, 4]}))
        s = json.loads((self.dir / "state.json").read_text())
        self.assertEqual((s["input_channels"], s["input_channel"]), ([3, 4], 3))
        self.P.CFG.update(input_channels=[3, 4], input_channel=9)
        self.lin.sanitize_config()
        self.assertEqual(self.P.CFG["input_channels"], [3, 4])
        self.assertEqual(self.P.CFG["input_channel"], 3)

    def test_garbage_falls_back_to_channel_1(self):
        self.P.CFG.update(input_channels=[2, 5], input_channel="x")
        self.lin.sanitize_config()
        self.assertEqual(self.P.CFG["input_channels"], [1])

    def test_set_config_accepts_the_old_channel_argument(self):
        self.assertIsNone(self.LI.set_config({"channel": 2}))
        self.assertEqual(self.P.CFG["input_channels"], [2])
        self.assertIsNone(self.LI.set_config({"channels": [1, 2]}))
        self.assertEqual(self.P.CFG["input_channel"], 1)
        for bad in ({"channels": [1, 3]}, {"channels": [1, 2, 3]}, {"channels": []}, {"channels": "1-2"}, {"channel": 0}):
            before = list(self.P.CFG["input_channels"])
            self.assertTrue(self.LI.set_config(bad), bad)
            self.assertEqual(self.P.CFG["input_channels"], before)

    def test_a_saved_choice_larger_than_the_device_falls_back_with_a_plain_note(self):
        import json
        self.P.CFG.update(input_channels=[5, 6], input_channel=5)
        self.LI.status = {"state": "error", "reason": "channel 6 does not exist: the device has 2 channels", "channels": 2, "names": [], "fault": "channels"}
        self.block(-90, write=False)
        self.assertEqual(self.P.CFG["input_channels"], [1, 2], "the first valid choice: the first stereo pair")
        self.assertIn("Channel 5/Channel 6 is not on Fake input (it has 2 channels); using Channel 1/Channel 2 instead.", self.LI.note)
        self.assertEqual(self.LI.info()["note"], self.LI.note)
        self.assertEqual(json.loads((self.dir / "state.json").read_text())["input_channels"], [1, 2], "saved, so the menu shows what is used")
        self.assertNotIn("error", self.LI.note.lower())
        self.LI.set_config({"channels": [2]})
        self.assertEqual(self.LI.note, "", "the note goes away when the choice is changed")

    def test_a_one_channel_device_falls_back_to_channel_1(self):
        self.P.CFG.update(input_channels=[2], input_channel=2)
        self.LI.status = {"state": "error", "reason": "x", "channels": 1, "names": [], "fault": "channels"}
        self.block(-90, write=False)
        self.assertEqual(self.P.CFG["input_channels"], [1])


class Switching(StereoCase):
    def test_changing_the_choice_restarts_the_capture_shows_switching_ramps_off_and_recovers(self):
        self.sblocks(-5, -90, 100)
        self.assertGreater(self.LI.gr, 18)
        seq = [self.LI.gr]
        self.assertIsNone(self.LI.set_config({"channels": [2]}))         # (no helper process in this test: restart_helper only resets the state)
        self.assertTrue(self.LI.switching)
        for _ in range(12):
            self.sblock(-90, -90, write=False)
            seq.append(self.LI.gr)
            self.assertEqual(self.LI.info()["chip"], "Switching…")
        steps = [seq[k] - seq[k + 1] for k in range(len(seq) - 1)]
        self.assertLessEqual(max(steps), 3.0 + 1e-6, seq)
        self.assertEqual(seq[-1], 0.0, "ducking released with the ramp while it restarts")
        self.assertEqual(self.LI.info()["reason"], "Switching the input…")
        self.assertEqual(self.bg.duck_in, 1.0)
        # the new helper opens the device with ONE channel: new epoch, status ok, audio flows
        self.writer.new_epoch(1)
        self.LI.status = {"state": "ok", "reason": "", "channels": 2, "names": []}
        self.block(-5)
        self.block(-5)
        for _ in range(100):
            self.block(-5)
        self.assertFalse(self.LI.switching)
        self.assertTrue(self.LI.alive)
        self.assertEqual(self.LI.info()["chip"], "Signal present")
        self.assertEqual(len(self.LI.levels_db), 1, "one bar for a single channel")
        self.assertGreater(self.LI.gr, 18, "normal behaviour is back by itself")

    def test_a_failed_new_capture_says_why_instead_of_switching(self):
        self.sblocks(-5, -90, 20)
        self.LI.set_config({"channels": [2]})
        self.block(-90, write=False)
        self.assertEqual(self.LI.info()["chip"], "Switching…")
        self.LI.status = {"state": "error", "reason": "could not open the input device (busy)", "channels": 0, "names": []}
        self.LI.status_at = self.LI.restart_at + 1
        self.block(-90, write=False)
        self.assertEqual(self.LI.info()["chip"], "No input")
        self.assertIn("busy", self.LI.info()["reason"])


class InputThreshold(StereoCase):
    """The Live input has its own ducking threshold (input_threshold_db, -60..0 dB, 1 dB steps); the other ducking values stay shared with Play on Top."""
    def burst(self, left, right=None, n=300):
        self.LI.reset_detector(); self.writer.new_epoch(2)
        self.LI.status = {"state": "ok", "reason": "", "channels": 2, "names": []}
        self.sblocks(left, left if right is None else right, n)
        return self.LI.gr

    def test_a_signal_at_minus_35_ducks_with_threshold_minus_40_and_not_with_minus_30(self):
        self.P.CFG["input_threshold_db"] = -40.0
        low = self.burst(-35)
        self.assertGreater(low, 1.0, "5 dB over the threshold ducks")
        self.P.CFG["input_threshold_db"] = -30.0
        self.assertEqual(self.burst(-35), 0.0, "5 dB under the threshold does not duck")
        self.assertEqual(self.bg.duck_in, 1.0)

    def test_the_depth_follows_the_documented_curve_of_the_input_threshold(self):
        for thr in (-50.0, -40.0, -25.0):
            self.P.CFG["input_threshold_db"] = thr
            g = self.burst(-20)
            self.assertAlmostEqual(g, max(0.0, -20 - thr) * (1 - 1 / 6.0), delta=0.6, msg=thr)

    def test_a_stereo_pair_uses_the_louder_channel(self):
        self.P.CFG["input_threshold_db"] = -30.0
        self.assertEqual(self.burst(-50, -45), 0.0, "both under")
        self.assertGreater(self.burst(-50, -20), 5.0, "the right channel alone ducks")
        self.assertGreater(self.burst(-20, -50), 5.0, "the left channel alone ducks")
        self.assertEqual(self.burst(-31, -50), 0.0, "the louder one is still under")

    def test_a_change_takes_effect_without_a_restart(self):
        self.P.CFG["input_threshold_db"] = -30.0
        self.sblocks(-35, -35, 200)
        self.assertEqual(self.LI.gr, 0.0)
        self.assertIsNone(self.LI.set_config({"threshold_db": -45}))
        self.sblocks(-35, -35, 200)
        self.assertGreater(self.LI.gr, 1.0)
        self.assertIsNone(self.LI.set_config({"threshold_db": -20}))
        self.sblocks(-35, -35, 400)
        self.assertEqual(self.LI.gr, 0.0, "back under: released")

    def test_values_are_clamped_rounded_and_bad_ones_refused(self):
        for given, want in ((-40, -40.0), ("-41", -41.0), (-60, -60.0), (0, 0.0), (-75, -60.0), (12, 0.0), (-35.4, -35.0), (-35.6, -36.0)):
            self.assertIsNone(self.LI.set_config({"threshold_db": given}), given)
            self.assertEqual(self.P.CFG["input_threshold_db"], want, given)
        keep = self.P.CFG["input_threshold_db"]
        for bad in ("x", None, True, [1], {}, float("nan"), float("inf"), "-inf"):
            self.assertTrue(self.LI.set_config({"threshold_db": bad}), f"{bad!r} should be refused")
            self.assertEqual(self.P.CFG["input_threshold_db"], keep, "nothing changes on a refusal")
        self.assertTrue(self.LI.set_config({"threshold_db": -20, "gain_db": 99}), "one bad value changes nothing")
        self.assertEqual(self.P.CFG["input_threshold_db"], keep)

    def test_it_is_saved_and_reported(self):
        self.LI.set_config({"threshold_db": -44})
        self.assertEqual(json.loads((self.dir / "state.json").read_text())["input_threshold_db"], -44.0)
        i = self.LI.info()
        self.assertEqual((i["threshold_db"], i["threshold_default"], i["threshold_min"], i["threshold_max"]), (-44.0, -30.0, -60.0, 0.0))

    def test_an_old_config_without_the_setting_keeps_the_level_the_detector_used(self):
        # before this setting the detector used the Play on Top threshold: whatever it was, it becomes the starting value, and the behaviour is identical
        for old in (-30.0, -22.0, -41.0):
            self.P.CFG.update(duck_threshold_db=old, input_threshold_db=None)
            self.lin.sanitize_config()
            self.assertEqual(self.P.CFG["input_threshold_db"], old)
            self.assertEqual(json.loads((self.dir / "state.json").read_text())["input_threshold_db"], old, "the migration is saved")
            g = self.burst(-15)
            self.assertAlmostEqual(g, (-15 - old) * (1 - 1 / 6.0), delta=0.6)
        self.assertEqual(self.lin.THR_DEFAULT, -30.0)
        import re
        self.assertRegex((self.dir / "cpl" / "config.py").read_text(), r'"duck_threshold_db":\s+-30\.0,')       # the shipped Play on Top threshold = the default
        self.P.CFG.update(input_threshold_db=-12.0, duck_threshold_db=-30.0)
        self.lin.sanitize_config()
        self.assertEqual(self.P.CFG["input_threshold_db"], -12.0, "a saved value is kept")
        self.P.CFG["input_threshold_db"] = "garbage"
        self.lin.sanitize_config()
        self.assertEqual(self.P.CFG["input_threshold_db"], -30.0)
        self.P.CFG["input_threshold_db"] = 99
        self.lin.sanitize_config()
        self.assertEqual(self.P.CFG["input_threshold_db"], 0.0, "out of range is clamped")

    def test_play_on_top_and_the_input_threshold_do_not_affect_each_other(self):
        self.P.CFG.update(duck_threshold_db=-30.0, input_threshold_db=-30.0)
        a = self.burst(-20)
        self.P.CFG["duck_threshold_db"] = -10.0
        self.assertEqual(self.burst(-20), a, "moving the Play on Top threshold does not move the input's")
        self.P.CFG["input_threshold_db"] = -50.0
        self.assertEqual(self.P.CFG["duck_threshold_db"], -10.0)
        self.assertIsNone(self.LI.set_config({"threshold_db": -45}))
        self.assertEqual(self.P.CFG["duck_threshold_db"], -10.0, "setting the input's does not touch Play on Top's")
        # Play on Top itself still reads its own threshold
        dsp = self.app.mod("dsp")
        key = np.full(50, 10 ** (-20 / 20.0), dtype=np.float32)
        hi = float(dsp.duck_curve(key, 1.0, 6.0, -10.0, False).max()); lo = float(dsp.duck_curve(key, 1.0, 6.0, -30.0, False).max())
        self.assertLess(hi, lo)

    def test_solo_changes_nothing_at_any_threshold(self):
        outs = []
        for solo in (False, True):
            self.P.CFG["input_threshold_db"] = -38.0
            self.LI.set_solo(solo); self.log = []
            self.LI.reset_detector(); self.writer.new_epoch(2)
            self.LI.status = {"state": "ok", "reason": "", "channels": 2, "names": []}
            self.sblocks(-90, -90, 10); self.sblocks(-35, -50, 50); self.sblocks(-90, -90, 60)
            outs.append(list(self.log))
        self.assertEqual(outs[0], outs[1])
        self.assertGreater(max(x[0] for x in outs[0]), 0.5)


if __name__ == "__main__":
    unittest.main()
