"""2.8.0 health model (cpl/health.py): pure checks and the overall state. No clock, no audio: the inputs are plain dicts."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from cpl import health as H            # noqa: E402

GB = 1024 ** 3


def base(**kw):
    inp = {"starting": False, "live": {"name": "Dante USB", "present": True, "open": True},
           "preview": {"configured": False}, "engine": {}, "companion": {"polled": True, "silent_s": 0, "host_found": True},
           "disk": {"free": 200 * GB, "total": 500 * GB}, "cache": {"measured": True}, "uptime_s": 3 * 86400 + 4 * 3600 + 5}
    inp.update(kw)
    return inp


def by_id(h):
    return {c["id"]: c for c in h["checks"]}


class HealthModel(unittest.TestCase):
    def test_all_ok_is_ready_with_seven_checks(self):
        h = H.evaluate(base())
        self.assertEqual(h["state"], "ready")
        self.assertEqual(h["summary"], "")
        self.assertEqual([c["id"] for c in h["checks"]], list(H.ORDER))
        self.assertEqual(len(h["checks"]), 7)
        self.assertTrue(all(c["status"] == "ok" for c in h["checks"]))
        self.assertEqual(by_id(h)["uptime"]["text"], "Up 3 d 4 h")

    def test_starting_until_ready_but_a_problem_wins(self):
        self.assertEqual(H.evaluate(base(starting=True))["state"], "starting")
        self.assertEqual(H.evaluate(base(starting=True, live={"name": "X", "present": False}))["state"], "problem")

    def test_live_output_missing_is_bad_and_names_the_device(self):
        h = H.evaluate(base(live={"name": "Dante USB", "present": False, "open": True}))
        c = by_id(h)["live_output"]
        self.assertEqual((h["state"], c["status"]), ("problem", "bad"))
        self.assertIn("The live output (Dante USB) is not available.", c["text"])

    def test_preview_missing_warns_only_with_the_switch_and_a_device(self):
        pv = {"configured": True, "name": "Phones", "present": False, "amber": True}
        self.assertEqual(by_id(H.evaluate(base(preview=pv)))["preview_output"]["status"], "warn")
        self.assertEqual(H.evaluate(base(preview=pv))["state"], "degraded")
        self.assertEqual(by_id(H.evaluate(base(preview=dict(pv, amber=False))))["preview_output"]["status"], "ok")
        self.assertEqual(by_id(H.evaluate(base(preview=dict(pv, browser=True))))["preview_output"]["status"], "ok")
        self.assertEqual(by_id(H.evaluate(base(preview={"configured": False})))["preview_output"]["status"], "ok")

    def test_engine_stalled_and_gave_up_are_bad(self):
        self.assertEqual(H.evaluate(base(engine={"stalled": True}))["state"], "problem")
        c = by_id(H.evaluate(base(engine={"gave_up": True})))["audio_engine"]
        self.assertEqual(c["status"], "bad")
        self.assertIn("too often", c["text"])

    def test_companion_unknown_never_polled_then_warn_after_30_s(self):
        h = H.evaluate(base(companion={"polled": False, "silent_s": 0, "host_found": True}))
        self.assertEqual((by_id(h)["companion"]["status"], h["state"]), ("unknown", "ready"))
        for silent, want in ((0, "ok"), (30, "ok"), (30.5, "warn"), (500, "warn")):
            h = H.evaluate(base(companion={"polled": True, "silent_s": silent, "host_found": True}))
            self.assertEqual(by_id(h)["companion"]["status"], want, silent)
        h = H.evaluate(base(companion={"polled": False, "host_found": False}))
        self.assertEqual(by_id(h)["companion"]["status"], "warn")        # the address cannot be found, even if nobody ever polled

    def test_disk_thresholds(self):
        cases = [(200 * GB, 500 * GB, "ok"), (4 * GB, 500 * GB, "warn"), (60 * GB, 500 * GB, "ok"), (40 * GB, 500 * GB, "warn"), (6 * GB, 100 * GB, "warn"),   # below 10 %
                 (60 * GB, 1000 * GB, "warn"), (int(0.9 * GB), 500 * GB, "bad"), (1 * GB, 500 * GB, "warn")]
        for free, total, want in cases:
            self.assertEqual(by_id(H.evaluate(base(disk={"free": free, "total": total})))["disk"]["status"], want, (free, total))
        self.assertEqual(by_id(H.evaluate(base(disk=None)))["disk"]["status"], "unknown")
        self.assertEqual(H.evaluate(base(disk={"free": GB // 2, "total": 500 * GB}))["summary"], "Disk space critical")
        self.assertEqual(H.evaluate(base(disk={"free": 3 * GB, "total": 500 * GB}))["summary"], "Disk space low")

    def _disk_text(self, free, total):
        d = {"free": free} if total is None else {"free": free, "total": total}
        return by_id(H.evaluate(base(disk=d)))["disk"]

    def test_disk_percentage_is_free_over_total_whole_and_clamped(self):
        self.assertEqual(H.pct_text(2 * GB, 100 * GB), "2 %")
        self.assertEqual(H.pct_text(int(7.4 * GB), 100 * GB), "7 %")
        self.assertEqual(H.pct_text(int(7.6 * GB), 100 * GB), "8 %")
        self.assertEqual(H.pct_text(150 * GB, 100 * GB), "100 %")           # free larger than total: clamped
        self.assertEqual(H.pct_text(-5, 100 * GB), "0 %")                  # never negative
        self.assertEqual(H.pct_text(0, 100 * GB), "0 %")                   # really nothing free
        self.assertIsNone(H.pct_text(5 * GB, None))                        # total unknown: no percentage
        self.assertIsNone(H.pct_text(5 * GB, 0))

    def test_disk_rows_for_the_fake_cases(self):
        c = self._disk_text(2 * GB, 100 * GB)
        self.assertEqual(c["status"], "warn")
        self.assertIn("2.0 GB free (2 %)", c["text"])
        c = self._disk_text(int(0.4 * GB), 500 * GB)                       # critical text has no percentage; the amount is what matters
        self.assertEqual(c["status"], "bad")
        c = self._disk_text(int(1.5 * GB), 500 * GB)                       # 0.3 %: some space, under 1 %
        self.assertIn("1.5 GB free (less than 1 %)", c["text"])
        self.assertNotIn("(0 %)", c["text"])
        c = self._disk_text(900 * GB, 500 * GB)                            # free larger than total
        self.assertEqual(c["status"], "ok")
        c = self._disk_text(2 * GB, None)                                  # total unknown: judged on the absolute limits, no percentage printed
        self.assertEqual(c["status"], "warn")
        self.assertIn("2.0 GB free.", c["text"])
        self.assertNotIn("%", c["text"])
        self.assertEqual(self._disk_text(200 * GB, None)["status"], "ok")
        self.assertEqual(self._disk_text(GB // 2, None)["status"], "bad")

    def test_disk_thresholds_are_unchanged(self):
        self.assertEqual((H.DISK_WARN_PCT, H.DISK_WARN_BYTES, H.DISK_BAD_BYTES), (10.0, 5 * GB, 1 * GB))

    def test_cache_full_failing_unknown(self):
        self.assertEqual(by_id(H.evaluate(base(cache={"measured": True, "full": True})))["cache"]["status"], "warn")
        self.assertEqual(by_id(H.evaluate(base(cache={"measured": True, "failing": True})))["cache"]["status"], "warn")
        h = H.evaluate(base(cache={"measured": False}))
        self.assertEqual((by_id(h)["cache"]["status"], h["state"]), ("unknown", "ready"))

    def test_unknown_never_changes_the_state(self):
        h = H.evaluate(base(disk=None, cache={"measured": False}, companion={"polled": False}))
        self.assertEqual(h["state"], "ready")

    def test_sentence_only_when_not_ok(self):
        for c in H.evaluate(base())["checks"]:
            if c["id"] != "uptime":
                self.assertEqual(c["text"], "")

    def test_the_engine_row_always_carries_the_restart_count(self):
        for n, want in ((0, "Restarted 0 times since start"), (1, "Restarted 1 time since start"), (3, "Restarted 3 times since start")):
            c = by_id(H.evaluate(base(engine={"restarts": n})))["audio_engine"]
            self.assertEqual(c["note"], want)
            self.assertEqual(c["status"], "ok")
            self.assertEqual(c["text"], "")                      # the sentence stays empty while the row is ok
        small = H.compact(H.evaluate(base(engine={"restarts": 2})))
        self.assertEqual([c["note"] for c in small["checks"] if "note" in c], ["Restarted 2 times since start"])

    def test_uptime_text(self):
        self.assertEqual(H.uptime_text(90), "Up 1 min")
        self.assertEqual(H.uptime_text(3 * 3600 + 120), "Up 3 h 2 min")
        self.assertEqual(H.uptime_text(86400 * 12), "Up 12 d 0 h")


if __name__ == "__main__":
    unittest.main()
