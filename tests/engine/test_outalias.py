"""2.8.0 output-alias: the alias table (cpl/outalias.py) and how health shows an aliased output. Pure logic, no real time, no device is opened.
Real data from the NUC (2026-11-11) is the fixture: the loopback card that Inferno (Dante over IP) uses shows up twice."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from cpl import config, health as H, outalias as OA      # noqa: E402

NUC = ["Dante USB I/O Module, USB Audio", "HDA Intel PCH, ALC233 Analog", "HDA Intel PCH, ALC233 Digital", "HDA Intel PCH, HDMI 0", "HDA Intel PCH, HDMI 1",
       "HDA Intel PCH, HDMI 2", "Loopback, Loopback PCM", "Loopback, Loopback PCM (2)"]
LB1, LB2 = NUC[6], NUC[7]


class Table(unittest.TestCase):
    def setUp(self):
        self.old = config.CFG.get("output_aliases")
        config.CFG["output_aliases"] = None

    def tearDown(self):
        config.CFG["output_aliases"] = self.old

    def test_nothing_saved_uses_the_built_in_default(self):
        self.assertTrue(OA.is_default())
        by = {e["name"]: e for e in OA.info(NUC)}
        self.assertEqual([e["name"] for e in OA.info(NUC)], NUC)                   # same names, same order
        self.assertEqual(by[LB1]["label"], "Dante over IP")
        self.assertEqual((by[LB1]["group"], by[LB1]["live_only"], by[LB1]["hidden"]), ("Network audio", True, False))
        self.assertTrue(by[LB2]["hidden"])
        self.assertEqual(by[LB2]["label"], LB2)                                     # no label: the raw name
        for n in NUC[:6]:
            self.assertEqual(by[n], {"name": n, "label": n, "hidden": False, "group": "", "live_only": False})

    def test_a_saved_table_replaces_the_default_completely(self):
        config.CFG["output_aliases"] = OA.clean_aliases([{"match": NUC[0], "label": "Main"}])
        by = {e["name"]: e for e in OA.info(NUC)}
        self.assertEqual(by[NUC[0]]["label"], "Main")
        self.assertEqual(by[LB1]["label"], LB1)
        self.assertFalse(by[LB2]["hidden"])
        config.CFG["output_aliases"] = []                                           # saved empty = no aliases at all
        self.assertFalse(OA.is_default())
        self.assertTrue(all(e["label"] == e["name"] and not e["hidden"] for e in OA.info(NUC)))

    def test_matching_is_exact_and_case_sensitive(self):
        self.assertIsNone(OA.lookup("loopback, loopback pcm"))
        self.assertIsNone(OA.lookup(LB1 + " "))
        self.assertIsNone(OA.lookup("Loopback, Loopback PCM (3)"))
        self.assertIsNotNone(OA.lookup(LB1))

    def test_an_alias_for_a_device_that_is_not_there_does_nothing_and_is_kept(self):
        config.CFG["output_aliases"] = OA.clean_aliases([{"match": "Not plugged in", "label": "X", "hidden": True}])
        self.assertEqual(OA.info(NUC), [{"name": n, "label": n, "hidden": False, "group": "", "live_only": False} for n in NUC])
        self.assertEqual(len(OA.table()), 1)

    def test_validation(self):
        bad = [("a string", "must be a list"), ([1], "object"), ([{}], "needed"), ([{"match": 5}], "text"), ([{"match": "x" * 81}], "80"),
               ([{"match": "a", "hidden": "yes"}], "true or false"), ([{"match": "a", "live_only": 1}], "true or false"),
               ([{"match": "a", "label": 3}], "text"), ([{"match": "a", "group": "g" * 81}], "80"),
               ([{"match": "a"}, {"match": "a"}], "twice"), ([{"match": str(i)} for i in range(33)], "at most 32")]
        for v, word in bad:
            with self.assertRaises(ValueError, msg=repr(v)[:40]) as c:
                OA.clean_aliases(v)
            self.assertIn(word, str(c.exception))
        self.assertEqual(len(OA.clean_aliases([{"match": str(i)} for i in range(32)])), 32)
        self.assertEqual(OA.clean_aliases([{"match": "a", "label": "  L "}])[0]["label"], "L")

    def test_one_bad_entry_in_a_damaged_saved_table_does_not_break_the_list(self):
        config.CFG["output_aliases"] = [{"match": LB1, "label": "Dante over IP"}, 5, {"match": None}, {"match": LB2, "hidden": "x"}, {"match": LB1, "label": "dup"}]
        self.assertEqual([e["match"] for e in OA.table()], [LB1])
        self.assertEqual(OA.label_of(LB1), "Dante over IP")
        config.CFG["output_aliases"] = "garbage"
        self.assertEqual(OA.table(), [])
        self.assertEqual(len(OA.info(NUC)), len(NUC))

    def test_shown_is_label_first_raw_in_brackets_and_plain_when_unaliased(self):
        self.assertEqual(OA.shown(LB1), "Dante over IP (Loopback, Loopback PCM)")
        self.assertEqual(OA.shown(NUC[0]), NUC[0])
        self.assertEqual(OA.shown(LB2), LB2)                                        # hidden but unlabelled: as it is

    def test_the_table_in_use_is_a_copy(self):
        OA.table()[0]["label"] = "changed"
        self.assertEqual(OA.DEFAULT_ALIASES[0]["label"], "Dante over IP")


if __name__ == "__main__":
    unittest.main()
