"""2.8.0 follow-up 3: the report's "Audio driver:" line, with a fake SDL layer (no device, no ctypes)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from cpl import audiodrv as A      # noqa: E402


class Fake:
    def __init__(self, name):
        self.name, self.calls = name, 0

    def __call__(self):
        self.calls += 1
        return self.name


class DriverName(unittest.TestCase):
    def test_alsa_is_shown_as_sdl_names_it(self):
        self.assertEqual(A.Driver(Fake("alsa")).text(True), "alsa")

    def test_names_are_lower_case(self):
        for sdl in ("coreaudio", "pipewire", "pulseaudio"):
            self.assertEqual(A.Driver(Fake(sdl.upper())).text(True), sdl)

    def test_an_unknown_name_is_shown_not_replaced(self):
        self.assertEqual(A.Driver(Fake("somefuturedriver")).text(True), "somefuturedriver")

    def test_not_open_yet_is_not_detected_and_does_not_ask_sdl(self):
        f = Fake("alsa")
        d = A.Driver(f)
        self.assertTrue(d.text(False).startswith("not detected"))
        self.assertEqual(f.calls, 0)
        self.assertEqual(d.text(True), "alsa")            # read after the first open
        self.assertEqual(d.text(False), "alsa")           # and kept (a device change closes the mixer for a moment)
        self.assertEqual(f.calls, 1)

    def test_sdl_names_nothing_while_open_is_not_detected_and_retried(self):
        f = Fake(None)
        d = A.Driver(f)
        self.assertIn("SDL did not name", d.text(True))
        f.name = "alsa"
        self.assertEqual(d.text(True), "alsa")

    def test_a_failing_layer_is_not_detected_never_unknown(self):
        def boom():
            raise OSError("no")
        t = A.Driver(boom).text(True)
        self.assertTrue(t.startswith("not detected"))
        self.assertNotIn("unknown", t)

    def test_the_real_layer_names_the_dummy_driver(self):
        import os
        os.environ["SDL_AUDIODRIVER"] = "dummy"
        import pygame
        pygame.mixer.init()
        try:
            self.assertEqual(A.Driver().read(True), "dummy")
        finally:
            pygame.mixer.quit()


if __name__ == "__main__":
    unittest.main()
