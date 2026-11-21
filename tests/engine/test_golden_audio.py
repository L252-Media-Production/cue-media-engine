"""Audio spec fixtures (docs/AUDIO-SPEC.md, tests/golden-audio/): the committed JSON files must equal what the code does now.

If this fails after a change of audio behaviour, the change must be deliberate: regenerate (PYTHONHASHSEED=0 python tests/golden-audio/generate.py --write),
bump SPEC_VERSION in tests/golden-audio/generate.py and the "Spec version" line of docs/AUDIO-SPEC.md, and add an "Audio spec N" line to CHANGELOG.md."""
import importlib.util
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
GOLD = ROOT / "tests" / "golden-audio"
sys.path.insert(0, str(GOLD))
sys.path.insert(0, str(ROOT / "tests"))
_spec = importlib.util.spec_from_file_location("golden_audio_generate", GOLD / "generate.py")
gen = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gen)


class GoldenAudio(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.docs = gen.build_all()

    def test_committed_fixtures_equal_the_code(self):
        problems = gen.compare(self.docs)
        self.assertEqual(problems, [], "audio behaviour changed (see docs/AUDIO-SPEC.md):\n  " + "\n  ".join(problems[:40]))

    def test_every_fixture_carries_the_spec_version(self):
        files = sorted(gen.FIXTURES.glob("*.json"))
        self.assertGreaterEqual(len(files), 8)
        for f in files:
            self.assertEqual(json.loads(f.read_text())["spec_version"], gen.SPEC_VERSION, f.name)

    def test_the_spec_document_names_the_same_version(self):
        spec = (ROOT / "docs" / "AUDIO-SPEC.md").read_text()
        m = re.search(r"^Spec version:\s*(\d+)", spec, re.M)
        self.assertIsNotNone(m, "docs/AUDIO-SPEC.md must start with 'Spec version: N'")
        self.assertEqual(int(m.group(1)), gen.SPEC_VERSION)

    def test_the_comparison_notices_a_change_and_ignores_explanations(self):
        d = json.loads(json.dumps(self.docs["fades"]))
        d["cases"]["crossfade_1000ms"]["rows"][3]["new"] += 0.01
        d["cases"]["crossfade_1000ms"]["rows"][3]["_info_x"] = "ignored"
        d["about"] += "!"
        self.assertEqual(gen.compare({**self.docs, "fades": d})[0].split(":")[0], "fades/cases/crossfade_1000ms/rows[3]/new")
        self.assertEqual(len(gen.compare({**self.docs, "fades": d})), 2)          # the changed number and the changed text (about), nothing for _info*
        self.assertEqual(gen.compare({**self.docs, "x": self.docs["fades"]})[0], "x.json: not committed")


if __name__ == "__main__":
    unittest.main()
