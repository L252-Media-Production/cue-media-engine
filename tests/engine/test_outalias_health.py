"""2.8.0 output-alias: how health shows an aliased output (cpl/health.py): matching stays on the raw name. Pure logic, no real time, no device is opened.
Real data from the NUC (2026-11-11) is the fixture: the loopback card that Inferno (Dante over IP) uses shows up twice."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from cpl import config, health as H, outalias as OA      # noqa: E402

NUC = ["Dante USB I/O Module, USB Audio", "HDA Intel PCH, ALC233 Analog", "HDA Intel PCH, ALC233 Digital", "HDA Intel PCH, HDMI 0", "HDA Intel PCH, HDMI 1",
       "HDA Intel PCH, HDMI 2", "Loopback, Loopback PCM", "Loopback, Loopback PCM (2)"]
LB1, LB2 = NUC[6], NUC[7]


class HealthKeepsRawNames(unittest.TestCase):
    def inp(self, **live):
        return {"starting": False, "live": {"name": LB1, "shown": OA.shown(LB1), "present": True, "open": True, **live}, "preview": {"configured": False},
                "engine": {}, "companion": {"polled": True, "silent_s": 0, "host_found": True},
                "disk": {"free": 200 * 1024 ** 3, "total": 500 * 1024 ** 3}, "cache": {"measured": True}, "uptime_s": 5}

    def test_the_result_does_not_depend_on_the_alias(self):
        plain = self.inp()
        plain["live"].pop("shown")
        self.assertEqual(H.compact(H.evaluate(self.inp())), H.compact(H.evaluate(plain)))
        self.assertEqual({c["id"]: c["status"] for c in H.evaluate(self.inp())["checks"]}["live_output"], H.OK)

    def test_a_missing_aliased_output_is_bad_for_the_same_reason_as_before_and_names_both(self):
        r = {c["id"]: c for c in H.evaluate(self.inp(present=False))["checks"]}["live_output"]
        self.assertEqual(r["status"], H.BAD)
        self.assertIn("Dante over IP (Loopback, Loopback PCM)", r["text"])

    def test_an_unaliased_output_reads_exactly_as_before(self):
        i = self.inp(name=NUC[0], present=False)
        i["live"]["shown"] = OA.shown(NUC[0])
        self.assertIn(f"The live output ({NUC[0]}) is not available.", {c["id"]: c for c in H.evaluate(i)["checks"]}["live_output"]["text"])


if __name__ == "__main__":
    unittest.main()
