"""2.8.0 push on state change (cpl/alerts.py): the state machine with the fake clock and a fake HTTP sender. No real sleeps, no network."""
import json
import sys
import unittest
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from cpl import alerts as A                      # noqa: E402
from cpl import clock                            # noqa: E402

URL = "https://hooks.example.com/services/T0/B0/SECRETKEY"


class Fake:
    def __init__(self):
        self.t = 1_800_000_000.0                 # a wall time; monotonic is the same number minus nothing, which is fine for differences

    def monotonic(self):
        return self.t

    def time(self):
        return self.t

    def sleep(self, s):
        self.t += s


def rep(state, bad="", warn="", summary=""):
    checks = [{"id": "live_output", "status": "bad" if bad else "ok", "title": "Live output", "text": bad}]
    checks.append({"id": "disk", "status": "warn" if warn else "ok", "title": "Media drive space", "text": warn})
    return {"state": state, "summary": summary, "checks": checks}


class Case(unittest.TestCase):
    def setUp(self):
        self.fake = Fake()
        clock.install(self.fake)
        self.cfg = {"push_enabled": True, "push_url": URL, "push_events": {k: True for k in A.EVENTS}, "push_hold": False}
        self.sent = []                           # (url, parsed body)
        self.fail = []                           # exceptions / statuses to produce, one per call
        self.sleeps = []
        self.logs = []
        self.playing = False
        self.poster = A.Poster(lambda: self.cfg["push_url"], post=self.post, sleep=self.sleeps.append, log=self.logs.append, inline=True)
        self.n = A.Notifier(self.cfg, lambda: "L252 NUC", lambda: self.playing, self.poster)

    def tearDown(self):
        clock.install(None)

    def post(self, url, data, timeout):
        self.timeout = timeout
        if self.fail:
            f = self.fail.pop(0)
            if isinstance(f, Exception):
                raise f
            return f
        self.sent.append((url, json.loads(data.decode("utf-8"))))
        return 200

    def run_state(self, seconds, rp):
        for _ in range(int(seconds)):
            self.fake.t += 1
            self.n.observe(rp)

    def texts(self):
        return [b["text"] for _, b in self.sent]


class Events(Case):
    def test_problem_starts_after_the_debounce_and_names_the_sentence(self):
        self.run_state(10, rep("ready"))
        self.run_state(4, rep("problem", bad="The live output (Dante USB) is not available. Start or plug in the device."))
        self.assertEqual(self.sent, [])                                  # 4 s: not yet
        self.run_state(2, rep("problem", bad="The live output (Dante USB) is not available. Start or plug in the device."))
        self.assertEqual(len(self.sent), 1)
        t = self.texts()[0]
        self.assertTrue(t.startswith("L252 NUC: PROBLEM \u2014 the live output (Dante USB) is not available. "), t)
        self.assertRegex(t, r"\d\d:\d\d$")
        body = self.sent[0][1]
        self.assertEqual(body["text"], body["content"])
        self.assertEqual((body["player"], body["event"], body["state"]), ("L252 NUC", "problem", "problem"))
        self.assertRegex(body["time"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d[+-]\d\d:\d\d$")

    def test_recovery_message(self):
        self.run_state(10, rep("ready"))
        self.run_state(10, rep("problem", bad="The live output (X) is not available."))
        self.run_state(10, rep("ready"))
        self.assertEqual(len(self.sent), 2)
        self.assertTrue(self.texts()[1].startswith("L252 NUC: Recovered \u2014 everything is ready. "))

    def test_a_flapping_state_that_never_holds_sends_nothing(self):
        self.run_state(10, rep("ready"))
        for _ in range(10):
            self.run_state(3, rep("problem", bad="The live output (X) is not available."))
            self.run_state(3, rep("ready"))
        self.assertEqual(self.sent, [])

    def test_degraded_over_five_minutes_is_sent_once_per_episode(self):
        self.run_state(10, rep("ready"))
        w = rep("degraded", warn="The media drive is running low: 3.0 GB free (1 %). Delete files.")
        self.run_state(300, w)
        self.assertEqual(self.sent, [])
        self.run_state(10, w)
        self.assertEqual(len(self.sent), 1)
        self.assertIn("Degraded for more than 5 minutes: the media drive is running low", self.texts()[0])
        self.run_state(600, w)
        self.assertEqual(len(self.sent), 1)                              # once
        self.run_state(10, rep("ready"))                                  # recovery message
        self.assertEqual(len(self.sent), 2)
        self.run_state(320, w)                                            # a new episode sends again
        self.assertEqual(len(self.sent), 3)

    def test_degraded_that_ends_early_sends_no_long_message_and_a_recovery(self):
        self.run_state(10, rep("ready"))
        self.run_state(60, rep("degraded", warn="x y"))
        self.run_state(10, rep("ready"))
        self.assertEqual([b["event"] for _, b in self.sent], ["recovered"])

    def test_watchdog_message_is_immediate(self):
        self.n.watchdog_restarted(10)
        self.assertEqual(len(self.sent), 1)
        self.assertTrue(self.texts()[0].startswith("L252 NUC: Audio engine restarted by the watchdog (output stalled for 10 s). "))
        self.assertEqual(self.sent[0][1]["event"], "watchdog")

    def test_each_event_can_be_switched_off(self):
        for ev in A.EVENTS:
            self.cfg["push_events"][ev] = False
        self.run_state(10, rep("ready"))
        self.run_state(10, rep("problem", bad="The live output (X) is not available."))
        self.run_state(10, rep("ready"))
        self.n.watchdog_restarted(10)
        self.assertEqual(self.sent, [])

    def test_off_and_no_address_send_nothing(self):
        self.cfg["push_enabled"] = False
        self.n.watchdog_restarted(10)
        self.cfg["push_enabled"], self.cfg["push_url"] = True, ""
        self.n.watchdog_restarted(10)
        self.assertEqual(self.sent, [])

    def test_starting_is_not_a_state_change_and_a_problem_at_start_is_sent(self):
        self.run_state(20, rep("starting"))
        self.assertEqual(self.sent, [])
        self.run_state(10, rep("problem", bad="The live output (X) is not available."))
        self.assertEqual(len(self.sent), 1)

    def test_problem_to_degraded_is_silent_then_ready_recovers(self):
        self.run_state(10, rep("problem", bad="The live output (X) is not available."))
        self.run_state(10, rep("degraded", warn="a b"))
        self.run_state(10, rep("ready"))
        self.assertEqual([b["event"] for _, b in self.sent], ["problem", "recovered"])


class Hold(Case):
    def test_messages_wait_while_playing_and_go_as_one_when_idle(self):
        self.cfg["push_hold"] = True
        self.playing = True
        self.run_state(10, rep("ready"))
        self.run_state(10, rep("problem", bad="The live output (X) is not available."))
        self.n.watchdog_restarted(10)
        self.assertEqual(self.sent, [])
        self.assertEqual(len(self.n.held), 2)
        self.playing = False
        self.run_state(1, rep("problem", bad="The live output (X) is not available."))
        self.assertEqual(len(self.sent), 1)
        t = self.texts()[0]
        self.assertTrue(t.startswith("L252 NUC: 2 messages while playing:\n- "), t)
        self.assertIn("PROBLEM", t)
        self.assertIn("watchdog", t)
        self.assertEqual(self.n.held, [])

    def test_a_single_held_message_is_sent_as_it_is(self):
        self.cfg["push_hold"] = True
        self.playing = True
        self.n.watchdog_restarted(10)
        self.playing = False
        self.n.flush()
        self.assertEqual(len(self.sent), 1)
        self.assertTrue(self.texts()[0].startswith("L252 NUC: Audio engine restarted"))

    def test_queue_is_bounded_to_fifty(self):
        self.cfg["push_hold"] = True
        self.playing = True
        for _ in range(80):
            self.n.watchdog_restarted(10)
        self.assertEqual(len(self.n.held), A.HOLD_MAX)
        self.assertEqual(self.n.dropped, 30)
        self.playing = False
        self.n.flush()
        self.assertEqual(len(self.sent), 1)
        self.assertIn("80 messages", self.texts()[0])
        self.assertIn("30 older ones", self.texts()[0])

    def test_the_test_message_ignores_the_hold_and_changes_no_state(self):
        self.cfg["push_hold"] = True
        self.playing = True
        before = (self.n.stable, self.n.cand, list(self.n.held))
        ok, reason = self.n.send_test()
        self.assertEqual((ok, reason), (True, ""))
        self.assertEqual(len(self.sent), 1)
        self.assertEqual(self.sent[0][1]["event"], "test")
        self.assertEqual(before, (self.n.stable, self.n.cand, list(self.n.held)))


class Sending(Case):
    def test_timeout_is_5_seconds_and_two_retries_with_backoff(self):
        self.fail = [TimeoutError(), TimeoutError()]
        ok = self.n.poster.deliver_now({"text": "x"}, retries=2)
        self.assertEqual(ok, (True, ""))                                   # the third try works
        self.assertEqual(self.sleeps, [1.0, 3.0])
        self.assertEqual(self.timeout, 5.0)

    def test_gives_up_after_three_tries_and_shows_the_reason(self):
        self.fail = [TimeoutError()] * 3
        self.assertEqual(self.n.poster.deliver_now({"text": "x"}, retries=2), (False, "Timed out"))
        self.assertEqual(self.poster.last_error, "Timed out")
        self.assertEqual(self.sent, [])

    def test_http_errors_show_the_code_and_a_404_is_not_retried(self):
        self.fail = [urllib.error.HTTPError(URL, 404, "Not Found", {}, None)]
        self.assertEqual(self.n.poster.deliver_now({"text": "x"}, retries=2), (False, "Refused (HTTP 404)"))
        self.assertEqual(self.sleeps, [])
        self.fail = [urllib.error.HTTPError(URL, 503, "x", {}, None)] * 3
        self.assertEqual(self.n.poster.deliver_now({"text": "x"}, retries=2), (False, "Refused (HTTP 503)"))
        self.assertEqual(len(self.sleeps), 2)

    def test_connection_reasons(self):
        import socket
        self.assertEqual(A.reason_of(urllib.error.URLError(socket.gaierror())), "Host not found")
        self.assertEqual(A.reason_of(urllib.error.URLError(ConnectionRefusedError())), "Connection refused")
        self.assertEqual(A.reason_of(urllib.error.URLError(socket.timeout())), "Timed out")
        self.assertEqual(A.reason_of(urllib.error.URLError("x")), "Could not connect")

    def test_success_clears_the_last_failure(self):
        self.fail = [TimeoutError()]
        self.n.poster.deliver_now({"text": "x"}, retries=0)
        self.assertEqual(self.poster.last_error, "Timed out")
        self.n.poster.deliver_now({"text": "x"}, retries=0)
        self.assertEqual(self.poster.last_error, "")

    def test_the_address_is_never_logged(self):
        self.fail = [TimeoutError()] * 3
        self.n.poster.deliver_now({"text": "x"}, retries=2)
        self.assertTrue(self.logs)
        self.assertFalse(any("SECRETKEY" in m or "hooks.example.com" in m for m in self.logs))

    def test_a_failing_send_never_raises_into_the_state_machine(self):
        self.fail = [RuntimeError("boom")] * 9
        self.run_state(10, rep("ready"))
        self.run_state(10, rep("problem", bad="The live output (X) is not available."))
        self.assertEqual(self.poster.last_error, "Could not send")

    def test_the_real_worker_is_a_thread_and_send_never_blocks(self):
        import threading, time as _t
        gate = threading.Event()
        calls = []

        def slow(url, data, timeout):
            calls.append(1)
            gate.wait(5)
            return 200
        p = A.Poster(lambda: URL, post=slow, sleep=lambda s: None, log=lambda m: None)
        t0 = _t.perf_counter()
        self.assertTrue(p.send({"text": "x"}))
        self.assertLess(_t.perf_counter() - t0, 0.5)                      # returned while the post is still waiting
        gate.set()


class Validation(unittest.TestCase):
    def test_only_http_and_https(self):
        self.assertEqual(A.clean_url("  https://a.example.com/x?y=1  "), "https://a.example.com/x?y=1")
        self.assertEqual(A.clean_url("http://10.0.0.5:5678/webhook/abc"), "http://10.0.0.5:5678/webhook/abc")
        self.assertEqual(A.clean_url(""), "")
        for bad in ("ftp://a.example.com/x", "javascript:alert(1)", "file:///etc/passwd", "a.example.com/x", "https://", "http:// bad", "https://h:99999/x", "gopher://x"):
            with self.assertRaises(ValueError, msg=bad):
                A.clean_url(bad)

    def test_masking_shows_only_the_host(self):
        m = A.mask_url(URL)
        self.assertEqual(m, "https://hooks.example.com/\u2026")
        self.assertNotIn("SECRETKEY", m)
        self.assertEqual(A.mask_url("http://10.0.0.5:5678/webhook/abc"), "http://10.0.0.5:5678/\u2026")
        self.assertEqual(A.mask_url(""), "")

    def test_events_are_checked(self):
        self.assertEqual(A.clean_events({"problem": False}), {"problem": False, "recovered": True, "degraded_long": True, "watchdog": True})
        with self.assertRaises(ValueError):
            A.clean_events({"problem": "yes"})


if __name__ == "__main__":
    unittest.main()
