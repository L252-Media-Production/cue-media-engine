"""Is the Live output still there? Answered without putting the live stream at risk (2.8.0 follow-up).

Enumerating audio devices through SDL while a stream is running can block, and on some drivers it can disturb the stream. So:
  * while ANY deck exists (a track, a fade, a crossfade, paused or not) the health report makes NO SDL device-list call and opens no device.
    The Live output is judged by CardWatch: a plain read of /proc/asound/cards (Linux), which touches no device.
  * when nothing plays, DevWatch may refresh the SDL list, but never on the event loop: a worker thread, at most every REFRESH_S, never more than one
    at a time, and the caller never waits for it (a hung enumeration just leaves the last good list in place; after TIMEOUT_S it is reported as hung).
CardWatch never reports a false "gone": a card is only missing when this configured device was matched to a card earlier and that card has vanished.
A name that cannot be matched stays None (unknown) and the stall signal of the watchdog is what counts.
"""
import re, threading

from cpl import clock

REFRESH_S = 10.0              # the idle refresh of the SDL list
TIMEOUT_S = 2.0               # an enumeration that takes longer is "hung": its result is awaited, not waited for
CARDS_PATH = "/proc/asound/cards"
_HEAD = re.compile(r"^\s*(\d+)\s+\[([^\]]*)\]\s*:\s*(.*)$")


def norm(s):
    return re.sub(r"[^a-z0-9]", "", str(s or "").lower())


GENERIC = frozenset(["audio", "usb", "analog", "digital", "device", "card", "output", "speaker", "headphones", "hdmi", "usbaudio", "hdaintel"])


def _counted(s):
    """The normalised text, or "" when it is too short or one of the generic words (compared as a whole)."""
    n = norm(s)
    return n if len(n) >= 4 and n not in GENERIC else ""


def parse_cards(text):
    """-> [{"n": "0", "id": "Module", "texts": ["module", "danteusbiomodule"]}] from the text of /proc/asound/cards.
    The identifying texts are the bracketed id and the descriptive name (after " - " on the first line). The driver name (before " - ") and the
    second line (addresses) are NOT used. Generic and short texts are dropped."""
    cards = []
    for line in text.splitlines():
        m = _HEAD.match(line)
        if m:
            rest = m.group(3)
            desc = rest.split(" - ", 1)[1] if " - " in rest else ""
            texts = []
            for t in (_counted(m.group(2)), _counted(desc)):
                if t and t not in texts:
                    texts.append(t)
            cards.append({"n": m.group(1), "id": m.group(2).strip(), "texts": texts})
    return cards


def match_cards(cards, want):
    """-> (winners, score): the cards whose longest counted text contained in the device name is the longest of all. One winner = a match, several = a tie."""
    w = norm(want)
    best, win = 0, []
    for c in cards:
        sc = max([len(t) for t in c["texts"] if t in w] or [0])
        if sc > best:
            best, win = sc, [c]
        elif sc == best and sc:
            win.append(c)
    return win, best


class CardWatch:
    def __init__(self, path=None, log=print):
        self.path, self.log = path, log
        self.matched = {}                 # configured device name -> the ID (as in /proc/asound/cards, e.g. "Module") of the card it was matched to unambiguously.
                                          # Kept: that is how a vanished card is told from "cannot match". The card NUMBER is not kept: it changes after a replug.
        self.tied = set()                 # configured names for which several cards matched equally at some time (a second identical module was seen)
        self._logged = set()

    def cards(self):
        try:
            with open(self.path or CARDS_PATH, encoding="utf-8", errors="replace") as f:
                return parse_cards(f.read())
        except OSError:
            return None                   # no /proc/asound (macOS, Windows): no probe

    def check(self, want):
        """True = the card of this device is listed, False = it was listed and has gone, None = cannot tell (no probe, no card matches, or a tie)."""
        if not want:
            return None                   # the system default: no probe at all (the audio engine alone decides)
        cards = self.cards()
        if cards is None:
            return None
        win, _ = match_cards(cards, want)
        prior = self.matched.get(want)                       # the card id, never the number
        if len(win) == 1:
            c = win[0]
            if want in self.tied and prior is not None and c["id"] != prior and not any(x["id"] == prior for x in cards):
                # a second identical module was seen, and the card that was matched first is gone: this one may or may not be the same
                # device, so say so once and report "cannot tell" (never "gone", never a quiet "ok")
                key = ("lost", want, c["id"])
                if key not in self._logged:
                    self._logged.add(key)
                    self.log(f"Health: the live output matched sound card [{prior}] earlier, a second identical card appeared, and now only card {c['n']} [{c['id']}] is left: cannot tell if it is the same device")
                return None
            self.matched[want] = c["id"]
            if want not in self._logged:
                self._logged.add(want)
                self.log(f"Health: the live output matches sound card {c['n']} [{c['id']}]")
            return True
        if len(win) > 1:
            self.tied.add(want)
            key = ("tie", want, tuple(c["id"] for c in win))
            if key not in self._logged:
                self._logged.add(key)
                self.log("Health: the live output matches several sound cards equally (" + ", ".join(f"{c['n']} [{c['id']}]" for c in win) + "): cannot tell")
        if prior is not None:
            return any(c["id"] == prior for c in cards)      # matched before: it is gone only if that card id has gone
        return None


class DevWatch:
    """The SDL device list, refreshed only while idle, only in a thread, at most every REFRESH_S. `list_fn` and `start` are injected for tests."""

    def __init__(self, list_fn, cards, start=None):
        self.list_fn, self.cards = list_fn, cards
        self.start = start or self._thread
        self.names = None                 # the last good list (None = never read)
        self._t = -1e9                    # when the last refresh was started
        self._busy = False
        self._busy_at = 0.0

    @staticmethod
    def _thread(fn):
        threading.Thread(target=fn, daemon=True, name="devlist").start()

    def hung(self):
        return self._busy and clock.monotonic() - self._busy_at > TIMEOUT_S

    def _job(self):
        try:
            got = list(self.list_fn())
            self.names = got
        except Exception:
            pass                          # keep the last good list
        finally:
            self._busy = False

    def refresh(self, playing, force=False):
        """Never blocks. While `playing` it does nothing at all."""
        if playing or self._busy:
            return
        now = clock.monotonic()
        if not force and now - self._t < REFRESH_S:
            return
        self._t, self._busy_at, self._busy = now, now, True
        self.start(self._job)

    def live_present(self, want, playing):
        """True / False for 'the configured Live output is there'; unknown counts as True (the watchdog's stall signal covers it)."""
        if not want:
            return True
        card = self.cards.check(want)         # a plain file read: also while idle, so a match is learned before anything plays
        if playing:
            return card is not False
        if self.names is None:
            return card is not False
        return want in self.names

    def device_present(self, name):
        """A Preview or other device: from the last good list; unknown (never read) counts as present."""
        return True if self.names is None or not name else name in self.names
