"""lib_rename and move_track carry everything that belongs to a track (docs/split-plan.md 3.7, F8): the trim, the crossfade time, the end action
and the trigger points (both the ones the track owns and the ones that play it), and the decoded sound in the cache.

In-process with the fake-clock harness: a track a.wav in playlist A has a trim (In 1, Out 5), its own crossfade time (2.5 s), the end action "loop" and a
trigger point that plays b.wav; b.wav (also in A) has a trigger point that plays a.wav. a.wav is decoded (so it is in the cache). It is renamed into
a folder, then moved to playlist B; each step must leave all four settings and the trigger targets with the new name, nothing under the old one."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from harness.engine import EngineCase          # noqa: E402

NEW = "sub/renamed.wav"


class LibRename(EngineCase):
    LIB = {"a.wav": 12, "b.wav": 12, "c.wav": 12}
    PLAYLISTS = [{"name": "A", "tracks": ["a.wav", "b.wav"]}, {"name": "B", "tracks": ["c.wav"]}]

    async def asyncSetUp(self):
        await super().asyncSetUp()
        P = self.P
        self.assertTrue(P.set_trim(0, 0, {"in": 1, "out": 5, "end": "cut"}))
        self.assertTrue(P.set_xfade(0, 0, 2.5))
        self.assertTrue(P.set_end(0, 0, "loop"))
        lst, err = P.set_triggers(0, 0, "add", {"at": 3, "file": "b.wav"})
        self.assertIsNone(err, err)
        lst, err = P.set_triggers(0, 1, "add", {"at": 2, "file": "a.wav"})
        self.assertIsNone(err, err)
        await self.load("a.wav")
        self.old_path = str(P.LIB / "a.wav")
        self.new_path = str(P.LIB / NEW)
        self.assertIsNotNone(P.cached(self.old_path))
        self.before = self.snapshot(0, 0)

    def snapshot(self, p, t):
        P = self.P
        return {"end": P.end_of(p, t), "xfade_ms": P.xfade_of(p, t), "trim": dict(P.trim_of(p, t)),
                "triggers": [(x["at"], x["file"]) for x in P.triggers_of(p, t)]}

    def raw_keys(self):
        """every key of the per-file dicts of every playlist, plus every trigger target"""
        keys = set()
        for pl in self.P.playlists:
            for name in ("end_actions", "xfades", "trims", "triggers"):
                keys |= set(pl.get(name, {}))
            for lst in pl.get("triggers", {}).values():
                keys |= {x["file"] for x in lst}
        return keys

    async def test_rename_moves_all_four_settings_the_trigger_targets_and_the_cache(self):
        P = self.P
        res, status = P.lib_rename("a.wav", NEW)
        self.assertEqual((res, status), (NEW, 200))
        self.assertEqual(P.playlists[0]["tracks"], [NEW, "b.wav"])
        self.assertEqual(self.snapshot(0, 0), self.before, "the track's own settings and trigger point follow the rename")
        self.assertEqual([(x["at"], x["file"]) for x in P.triggers_of(0, 1)], [(2.0, NEW)], "the trigger of b.wav that PLAYS a.wav now plays the new name")
        self.assertNotIn("a.wav", self.raw_keys(), "nothing is left under the old name")
        self.assertIsNotNone(P.cached(self.new_path), "the decoded sound follows the file")
        self.assertIsNone(P.cached(self.old_path))

    async def test_rename_then_move_to_another_playlist_all_follow(self):
        P = self.P
        P.lib_rename("a.wav", NEW)
        self.assertEqual(P.move_track(0, 0, 1, 0), "ok")
        self.assertEqual(P.playlists[1]["tracks"], [NEW, "c.wav"])
        self.assertEqual(self.snapshot(1, 0), self.before, "trim, crossfade, end action and trigger point move with the entry")
        self.assertEqual(P.playlists[0]["tracks"], ["b.wav"])
        self.assertFalse(P.playlists[0].get("trims"), "the old playlist keeps nothing of it")
        self.assertFalse(P.playlists[0].get("xfades"))
        self.assertFalse(P.playlists[0].get("end_actions"))
        self.assertIsNotNone(P.cached(self.new_path), "moving between playlists does not touch the cache")

    async def test_rename_of_a_folder_carries_the_files_inside(self):
        P = self.P
        P.lib_rename("a.wav", NEW)
        res, status = P.lib_rename("sub", "moved")
        self.assertEqual((res, status), ("moved", 200))
        self.assertEqual(P.playlists[0]["tracks"][0], "moved/renamed.wav")
        self.assertEqual(self.snapshot(0, 0), self.before)
        self.assertIsNotNone(P.cached(str(P.LIB / "moved/renamed.wav")))


if __name__ == "__main__":
    import unittest
    unittest.main()
