"""2.8.0 follow-up: the Live output check never enumerates SDL devices while audio plays (cpl/devwatch.py), with a fake /proc/asound/cards,
a fake SDL list and the fake clock. No real sleeps (the hung-enumeration test uses a threading.Event, not a delay)."""
import sys
import tempfile
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from harness.engine import EngineCase, FakeTime      # noqa: E402
from cpl import clock, devwatch as D                 # noqa: E402

CARDS = """ 0 [PCH            ]: HDA-Intel - HDA Intel PCH
                      HDA Intel PCH at 0xdf240000 irq 130
 1 [USB            ]: USB-Audio - Dante USB
                      Audinate Dante USB at usb-0000:00:14.0-1, high speed
"""
ONLY_PCH = CARDS.split(" 1 [USB")[0]
WANT = "Dante USB, USB Audio"


class Cards(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.f = Path(tempfile.mkdtemp(prefix="cards-")) / "cards"
        self.f.write_text(CARDS)
        self.logs = []
        self.cw = D.CardWatch(str(self.f), log=self.logs.append)

    def test_parse(self):
        c = D.parse_cards(CARDS)
        self.assertEqual([x["n"] for x in c], ["0", "1"])
        self.assertIn("danteusb", c[1]["texts"])

    def test_match_is_tolerant_and_logged_once_at_info(self):
        self.assertTrue(self.cw.check(WANT))
        self.assertTrue(self.cw.check(WANT))
        self.assertTrue(self.cw.check("Dante USB:  USB Audio (hw:1,0)"))
        self.assertEqual(sum("matches sound card 1" in m for m in self.logs), 2)      # one line per configured name

    def test_a_card_that_disappears_is_gone_only_after_it_was_matched(self):
        self.assertTrue(self.cw.check(WANT))
        self.f.write_text(ONLY_PCH)
        self.assertIs(self.cw.check(WANT), False)
        self.f.write_text(CARDS)
        self.assertTrue(self.cw.check(WANT))

    # --- card tracking is by the card ID in /proc/asound/cards (follow-up 3), never by the number, which changes after a replug
    DANTE = " {n} [Module         ]: USB-Audio - Dante USB IO Module\n                      Audinate Dante USB IO Module at usb-0000:00:14.0-1, high speed\n"
    DANTE2 = " {n} [Module_1       ]: USB-Audio - Dante USB IO Module\n                      Audinate Dante USB IO Module at usb-0000:00:14.0-2, high speed\n"
    PCH = " 0 [PCH            ]: HDA-Intel - HDA Intel PCH\n                      HDA Intel PCH at 0xdf240000 irq 130\n"
    DWANT = "Dante USB IO Module, USB Audio"

    def _dante(self, *cards):
        self.f.write_text("".join(cards))

    def test_the_same_id_under_another_card_number_is_still_found(self):
        self._dante(self.PCH.replace(" 0 [", " 1 [") + self.DANTE.format(n=0))       # Module is card 0
        self.assertTrue(self.cw.check(self.DWANT))
        self._dante(self.PCH, "", self.DANTE.format(n=2))                            # replugged: Module is now card 2, PCH is card 0
        self.assertTrue(self.cw.check(self.DWANT))
        self._dante(self.PCH)                                                        # unplugged for good
        self.assertIs(self.cw.check(self.DWANT), False)
        self._dante(self.PCH, self.DANTE.format(n=2))                                # a number that used to belong to something else must not fool it
        self.assertTrue(self.cw.check(self.DWANT))

    def test_a_number_taken_over_by_another_card_is_not_the_same_card(self):
        self._dante(self.DANTE.format(n=0))
        self.assertTrue(self.cw.check(self.DWANT))
        self._dante(self.PCH)                                                        # card 0 is now the PCH: the matched id "Module" is gone
        self.assertIs(self.cw.check(self.DWANT), False)

    def test_a_tie_while_the_first_is_still_listed_stays_ok(self):
        self._dante(self.PCH, self.DANTE.format(n=1))
        self.assertTrue(self.cw.check(self.DWANT))
        self._dante(self.PCH, self.DANTE.format(n=1), self.DANTE2.format(n=2))       # a second identical module
        self.assertTrue(self.cw.check(self.DWANT))
        self.assertTrue(any("equally" in m for m in self.logs))
        self._dante(self.PCH, self.DANTE.format(n=3), self.DANTE2.format(n=1))       # both renumbered, the first one keeps its id
        self.assertTrue(self.cw.check(self.DWANT))

    def test_the_first_unplugged_with_only_the_second_left_is_unknown_with_an_info_line(self):
        self._dante(self.PCH, self.DANTE.format(n=1))
        self.assertTrue(self.cw.check(self.DWANT))
        self._dante(self.PCH, self.DANTE.format(n=1), self.DANTE2.format(n=2))
        self.assertTrue(self.cw.check(self.DWANT))
        n = len(self.logs)
        self._dante(self.PCH, self.DANTE2.format(n=1))                               # same description, other id and number
        self.assertIsNone(self.cw.check(self.DWANT))                                 # never False (bad), never a silent True
        self.assertIsNone(self.cw.check(self.DWANT))
        info = [m for m in self.logs[n:] if "cannot tell" in m or "Module_1" in m]
        self.assertEqual(len(info), 1, self.logs[n:])                                # one INFO line, not one per poll
        self._dante(self.PCH, self.DANTE.format(n=1))                                # the first one is back: found by its id again
        self.assertTrue(self.cw.check(self.DWANT))

    def test_a_single_replug_under_a_new_id_with_no_tie_is_simply_matched(self):
        self._dante(self.PCH, self.DANTE.format(n=1))
        self.assertTrue(self.cw.check(self.DWANT))
        self._dante(self.PCH, self.DANTE2.format(n=1))                               # no second module was ever seen: nothing is ambiguous
        self.assertTrue(self.cw.check(self.DWANT))

    def test_an_unmatched_name_stays_unknown_never_bad(self):
        self.assertIsNone(self.cw.check("Some Interface XR18"))
        self.f.write_text(ONLY_PCH)
        self.assertIsNone(self.cw.check("Some Interface XR18"))

    def test_no_proc_asound_means_no_probe(self):
        cw = D.CardWatch("/nonexistent/asound/cards")
        self.assertIsNone(cw.check(WANT))

    def test_system_default_has_nothing_to_look_for(self):
        self.assertIsNone(self.cw.check(None))


FIX = Path(__file__).resolve().parent.parent / "fixtures" / "audio"
NUC = (FIX / "cards-nuc-2026-11-10.txt").read_text()
PI = (FIX / "cards-pi-2026-11-10.txt").read_text()
DANTE = "Dante USB I/O Module, USB Audio"
HEADSET = " 2 [Headset        ]: USB-Audio - Generic USB Headset\n                      Generic USB Headset at usb-0000:00:14.0-4, full speed\n"
DANTE2 = " 2 [Module_1       ]: USB-Audio - Dante USB I/O Module\n                      Audinate Dante USB I/O Module at usb-0000:00:14.0-4, full speed\n"


def which(text, want):
    win, _ = D.match_cards(D.parse_cards(text), want)
    return [c["n"] for c in win]


class RealCards(unittest.TestCase):
    def test_nuc_names(self):
        self.assertEqual(which(NUC, DANTE), ["0"])
        for n in ("HDA Intel PCH, ALC233 Analog", "HDA Intel PCH, ALC233 Digital", "HDA Intel PCH, HDMI 0", "HDA Intel PCH, HDMI 1", "HDA Intel PCH, HDMI 2"):
            self.assertEqual(which(NUC, n), ["1"], n)

    def test_driver_name_and_second_line_are_not_used(self):
        t = D.parse_cards(NUC)
        self.assertEqual(t[0]["texts"], ["module", "danteusbiomodule"])
        self.assertEqual(t[1]["texts"], ["hdaintelpch"])      # "pch" is 3 letters: not counted
        self.assertEqual(which(NUC, "Some USB Audio"), [])                 # the shared driver name no longer matches anything

    def test_a_second_usb_card_does_not_take_the_dante_device(self):
        self.assertEqual(which(NUC + HEADSET, DANTE), ["0"])
        self.assertEqual(which(NUC + HEADSET, "Generic USB Headset, USB Audio"), ["2"])

    def test_two_identical_modules_tie_and_are_unknown(self):
        txt = NUC + DANTE2
        self.assertEqual(sorted(which(txt, DANTE)), ["0", "2"])
        logs = []
        f = Path(tempfile.mkdtemp(prefix="cards-")) / "c"
        f.write_text(txt)
        cw = D.CardWatch(str(f), log=logs.append)
        self.assertIsNone(cw.check(DANTE))
        self.assertTrue(any("several sound cards equally" in m and "0 [Module" in m and "2 [Module_1" in m for m in logs))

    def test_gone_only_after_an_unambiguous_match_even_if_a_tie_follows(self):
        f = Path(tempfile.mkdtemp(prefix="cards-")) / "c"
        f.write_text(NUC)
        cw = D.CardWatch(str(f), log=lambda m: None)
        self.assertTrue(cw.check(DANTE))
        f.write_text(NUC + DANTE2)                       # now a tie: card 0 is still there, so not bad
        self.assertTrue(cw.check(DANTE))
        f.write_text(" 1 [PCH" + NUC.split(" 1 [PCH")[1])
        self.assertIs(cw.check(DANTE), False)

    def test_generic_words_are_excluded_as_whole_texts(self):
        self.assertEqual(D.parse_cards(PI)[0]["texts"], ["bcm2835headphones"])      # id "Headphones" is generic, the description counts
        self.assertEqual(D.norm("vc4-hdmi-0"), "vc4hdmi0")

    def test_pi_names(self):
        self.assertEqual(which(PI, "bcm2835 Headphones, bcm2835 Headphones"), ["0"])
        self.assertEqual(which(PI, "vc4-hdmi-0, MAI PCM i2s-hifi-0"), ["1"])
        self.assertEqual(which(PI, "vc4-hdmi-1, MAI PCM i2s-hifi-0"), ["2"])

    def test_system_default_has_no_probe_and_no_error(self):
        class Boom(D.CardWatch):
            def cards(self):
                raise AssertionError("probe must not run")
        cw = Boom(log=lambda m: self.fail(m))
        self.assertIsNone(cw.check(None))
        self.assertIsNone(cw.check(""))
        dw = D.DevWatch(lambda: [], cw)
        self.assertTrue(dw.live_present(None, True))
        self.assertTrue(dw.live_present("", False))


class Watch(unittest.TestCase):
    def setUp(self):
        self.fake = FakeTime()
        clock.install(self.fake)
        self.calls = 0
        self.names = [WANT, "Phones"]
        self.cw = D.CardWatch("/nonexistent")
        self.dw = D.DevWatch(self.list, self.cw, start=lambda fn: fn())     # inline: deterministic

    def tearDown(self):
        clock.install(None)

    def list(self):
        self.calls += 1
        return list(self.names)

    def test_idle_refresh_works_and_is_rate_limited(self):
        self.dw.refresh(False)
        self.assertEqual((self.calls, self.dw.names), (1, [WANT, "Phones"]))
        self.fake.t += 5
        self.dw.refresh(False)
        self.assertEqual(self.calls, 1)
        self.fake.t += 6
        self.names = ["Phones"]
        self.dw.refresh(False)
        self.assertEqual((self.calls, self.dw.names), (2, ["Phones"]))
        self.assertFalse(self.dw.live_present(WANT, False))

    def test_no_sdl_call_while_playing(self):
        for _ in range(50):
            self.fake.t += 1
            self.dw.refresh(True)
            self.dw.refresh(True, force=True)
        self.assertEqual(self.calls, 0)

    def test_a_hung_enumeration_does_not_block_and_keeps_the_last_value(self):
        self.dw.refresh(False)                                              # a good list first
        gate = threading.Event()
        started = threading.Event()

        def hang():
            started.set()
            gate.wait(10)
            return ["NEW"]
        dw = D.DevWatch(hang, self.cw)                                       # a real thread this time
        dw.names = [WANT]
        self.fake.t += 20
        dw.refresh(False)                                                    # returns at once although list_fn blocks
        started.wait(5)
        self.assertEqual(dw.names, [WANT])
        self.assertTrue(dw._busy)
        self.assertFalse(dw.hung())
        self.fake.t += 3
        self.assertTrue(dw.hung())
        dw.refresh(False)                                                    # no second thread while one is stuck
        self.assertTrue(dw.live_present(WANT, False))                        # the last good value still answers
        gate.set()

    def test_unknown_counts_as_present(self):
        self.assertTrue(self.dw.live_present(WANT, False))
        self.assertTrue(self.dw.device_present("Phones"))


class InPlayer(EngineCase):
    async def setup_card(self, text):
        import tempfile
        self.cf = Path(tempfile.mkdtemp(prefix="cards-")) / "cards"
        self.cf.write_text(text)
        self.P.DW.cards.path = str(self.cf)
        self.P.DW.cards.matched.clear()
        self.P.CFG["audio_device"] = WANT
        self.sdl = []
        self.P.DW.list_fn = lambda: (self.sdl.append(1), [WANT])[1]
        self.P.DW.start = lambda fn: fn()

    async def test_no_sdl_call_while_playing_and_a_vanished_card_is_bad(self):
        await self.setup_card(CARDS)
        await self.load("a.wav")
        self.assertEqual(self.P.health_report(force=True)["checks"][0]["status"], "ok")        # idle: one SDL read, the card matched
        self.assertEqual(len(self.sdl), 1)
        self.assertTrue(self.P.play(0, 0))
        self.sdl.clear()
        for s in range(1, 19):                                  # the 12 s track plays up to 9 s
            self.at(s * 0.5)
            rep = self.P.health_report(force=True)
        self.assertEqual(self.sdl, [], "no SDL device-list call while a track plays")
        self.assertEqual(rep["checks"][0]["status"], "ok")
        self.cf.write_text(ONLY_PCH)
        self.at(9.5)
        rep = self.P.health_report(force=True)
        c = rep["checks"][0]
        self.assertEqual((c["id"], c["status"], rep["state"]), ("live_output", "bad", "problem"))
        self.assertIn(f"({WANT}) is not available", c["text"])
        self.assertEqual(self.sdl, [])

    async def test_an_unmatched_card_is_unknown_not_bad_while_playing(self):
        await self.setup_card(ONLY_PCH)
        await self.load("a.wav")
        self.assertTrue(self.P.play(0, 0))
        self.at(1)
        self.assertEqual(self.P.health_report(force=True)["checks"][0]["status"], "ok")

    async def test_idle_again_after_playback_refreshes_the_list(self):
        await self.setup_card(CARDS)
        await self.load("a.wav")
        self.assertTrue(self.P.play(0, 0))
        self.at(1)
        self.P.health_report(force=True)
        self.assertEqual(self.sdl, [])
        self.P.stop_all()
        self.at(30)
        self.P.health_report(force=True)
        self.assertEqual(len(self.sdl), 1)

    async def test_copy_report_never_enumerates(self):
        await self.setup_card(CARDS)
        await self.load("a.wav")
        self.assertTrue(self.P.play(0, 0))
        self.sdl.clear()
        txt = self.P.health_report_text()
        self.assertEqual(self.sdl, [])
        self.assertIn("not checked while audio plays", txt)


if __name__ == "__main__":
    unittest.main()
