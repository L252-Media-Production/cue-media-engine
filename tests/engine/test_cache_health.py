"""2.8.1: the Track cache row shows what the cache holds and its limit ("412 MB of 1,024 MB"), warns when the machine's MemAvailable is below 1 GB,
and the report has "Track cache memory: <used> MB of <limit> MB" next to Process memory (no effect on the state or the dot)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from harness.engine import EngineCase          # noqa: E402
from test_cache_limit import meminfo           # noqa: E402

MIB, GIB = 1048576, 1024 ** 3


def base(**over):
    inp = {"starting": False, "live": {"name": "x", "present": True, "open": True}, "preview": {"configured": False}, "engine": {},
           "companion": {"polled": True, "silent_s": 0, "host_found": True}, "disk": {"free": 200 * GIB, "total": 500 * GIB},
           "cache": {"measured": True}, "uptime_s": 5}
    inp.update(over)
    return inp


class Model(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
        from cpl import health
        self.H = health

    def row(self, **cache):
        h = self.H.evaluate(base(cache=cache))
        return next(c for c in h["checks"] if c["id"] == "cache"), h

    def test_amount_in_words(self):
        self.assertEqual(self.H.cache_amount(412 * MIB, 1024 * MIB), "412 MB of 1,024 MB")
        self.assertEqual(self.H.cache_amount(0, 7936 * MIB), "0 MB of 7,936 MB")
        c, h = self.row(measured=True, used=412 * MIB, limit=1024 * MIB, available=8 * GIB)
        self.assertEqual((c["status"], c["text"], c["note"], h["state"]), ("ok", "", "412 MB of 1,024 MB", "ready"))
        self.assertEqual(self.H.compact(h)["checks"][5]["note"], "412 MB of 1,024 MB")

    def test_low_memory_is_a_warning(self):
        c, h = self.row(measured=True, used=1, limit=GIB, available=GIB - 1)
        self.assertEqual((c["status"], c["text"], h["state"], h["summary"]), ("warn", "The machine is low on memory.", "degraded", "Low on memory"))
        c, h = self.row(measured=False, used=0, limit=GIB, available=200 * MIB)       # no playlist tracks: memory still matters
        self.assertEqual(c["status"], "warn")
        for avail in (GIB, 4 * GIB, None):
            c, h = self.row(measured=True, used=1, limit=GIB, available=avail)
            self.assertEqual((c["status"], h["state"]), ("ok", "ready"), avail)

    def test_state_rules_kept(self):
        self.assertEqual(self.row(measured=True, full=True, limit=GIB)[0]["status"], "warn")
        self.assertEqual(self.row(measured=True, full=True)[1]["summary"], "Track cache full")
        self.assertEqual(self.row(measured=True, failing=True)[0]["status"], "warn")
        c, h = self.row(measured=False, limit=GIB, used=0)
        self.assertEqual((c["status"], h["state"], c["note"]), ("unknown", "ready", "0 MB of 1,024 MB"))
        c, _ = self.row(measured=True)
        self.assertNotIn("note", c)                                              # older callers without the figures: no note

    def test_report_line(self):
        self.assertEqual(self.H.cache_memory_text(412 * MIB, 1024 * MIB), "Track cache memory: 412 MB of 1,024 MB")


class Live(EngineCase):
    LIB = {"a.wav": 60, "b.wav": 60}
    PLAYLISTS = [{"name": "A", "tracks": ["a.wav", "b.wav"]}]

    async def test_row_and_report_from_the_player(self):
        cache = self.app.mod("cache")
        cache.set_machine(meminfo(self.dir, 4, avail_gib=2.5), sysconf=False)
        self.P.CFG["cache_mb"] = 12288
        await self.load("a.wav")
        self.fake.t += 2
        rep = self.P.health_report(force=True)
        row = next(c for c in rep["checks"] if c["id"] == "cache")
        used = cache.cache_bytes()
        self.assertEqual(row["note"], f"{used / MIB:,.0f} MB of 1,024 MB")
        self.assertEqual(row["status"], "ok")
        text = self.P.health_report_text()
        lines = text.splitlines()
        i = next(k for k, line in enumerate(lines) if line.startswith("Process memory:"))
        self.assertEqual(lines[i + 1], f"Track cache memory: {used / MIB:,.0f} MB of 1,024 MB")
        self.assertTrue(lines[i + 2].startswith("Open files:"))
        cache.set_machine(meminfo(self.dir, 4, avail_gib=0.5, name="low"), sysconf=False)
        self.fake.t += 2
        rep = self.P.health_report(force=True)
        row = next(c for c in rep["checks"] if c["id"] == "cache")
        self.assertEqual((row["status"], row["text"]), ("warn", "The machine is low on memory."))     # (the overall state is covered by Model: this player is still "starting")


if __name__ == "__main__":
    unittest.main()
