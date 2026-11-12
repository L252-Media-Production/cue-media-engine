"""Base class for the in-process engine tests (tests/engine/): a COPY of the application is imported with load_app (fresh module state per test),
the clock is a fake (cpl.clock.install), the mixer is SDL's dummy driver, and nothing listens on a port.

Conventions (docs/split-plan.md 4.4): anything a test replaces is replaced on the module that CALLS it, through `self.patch(name, value)`;
`self.mod_of(name)` says which module that is today (everything is still in cpl.legacy; later split steps change ONE table, MODULE_OF, not the tests).
Time: `self.at(seconds)` sets the fake clock to (start + seconds) exactly and runs one tick(); use binary fractions (0.25, 0.5 ...) for exact values.
"""
import asyncio, os, shutil, sys, tempfile, time as real_time, unittest, wave
from pathlib import Path

os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
from harness.appcopy import copy_app            # noqa: E402
from harness.appload import load_app            # noqa: E402
from harness.instance import PROJECT            # noqa: E402

# Which module holds the code a test patches / calls. Today everything is in cpl.legacy; a split step that moves a name edits its line here.
MODULE_OF = {"request_loudness": "cpl.loudness", "loud_pending": "cpl.loudness", "request_warm": "cpl.warm", "_warm_loop": "cpl.warm"}      # the module that CALLS the function (plan 4.4); a name that is not listed is still in cpl.legacy
HOOK_LISTS = {"request_warm": "on_change", "request_loudness": "on_save"}     # a function that bump() / save() reach only through a hook list (cpl.state): patch() replaces its entry there too


class FakeTime:
    def __init__(self):
        self.t = 1000.0

    def monotonic(self):
        return self.t

    def time(self):
        return 1.7e9 + self.t

    def __getattr__(self, name):
        return getattr(real_time, name)


def make_wav(path, seconds, rate=22050, channels=1, dc=0):
    """A silent WAV, or (dc != 0) a constant sample value `dc` (16-bit) in every channel: its RMS is exactly |dc| / 32768."""
    n = int(seconds * rate)
    frame = int(dc).to_bytes(2, "little", signed=True) * channels
    with wave.open(str(path), "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(frame * n)


class EngineCase(unittest.IsolatedAsyncioTestCase):
    WATCHDOG = False       # THE explicit test hook: engine tests run with the watchdog off (never the shipped default, which is on: tests/engine/test_health_defaults.py); a test class that needs it sets WATCHDOG = True
    LIB = {"a.wav": 12, "b.wav": 12, "c.wav": 12}      # name -> seconds (silence) or (seconds, dc_value) or (seconds, dc_value, rate, channels)
    PLAYLISTS = [{"name": "A", "tracks": ["a.wav", "b.wav", "c.wav"]}]

    async def asyncSetUp(self):
        self._argv = list(sys.argv)
        self.dir = Path(tempfile.mkdtemp(prefix="engtest-"))
        (self.dir / "media" / "library").mkdir(parents=True)
        (self.dir / "config.json").write_text('{"http_port": 18192, "osc_in_port": 18193}')
        copy_app(self.dir, PROJECT)
        self.secs = {}
        for name, spec in self.LIB.items():
            spec = spec if isinstance(spec, tuple) else (spec,)
            make_wav(self.dir / "media" / "library" / name, spec[0], *(spec[2:4] if len(spec) > 2 else ()), dc=(spec[1] if len(spec) > 1 else 0))
            self.secs[name] = float(spec[0])
        self.app = load_app(self.dir)
        self.P = P = self.app.P
        self.S = self.app.mod("state")                    # the shared state (cpl.state): live_deck and the other scalars are S.<name>
        self.clock = self.app.mod("clock")
        self.fake = FakeTime()
        self.clock.install(self.fake)
        self.patched = []
        self.patched_hooks = []
        self.patch("request_loudness", lambda: None)
        async def idle():                                      # the background warm-up would decode every file as soon as the loop yields
            return None
        self.patch("_warm_loop", idle)
        P.CFG["watchdog"] = self.WATCHDOG                         # the fake clock jumps minutes while the dummy output delivers nothing: the 2.8.0 watchdog would call that a stall (test_watchdog_engine.py switches it on)
        P.init_mixer(None)
        P.scan_library()
        P.playlists[:] = [dict(pl, tracks=list(pl["tracks"])) for pl in self.PLAYLISTS]
        for fid, secs in self.secs.items():
            P.DURS[fid] = (0, 0, secs)
        self.t0 = self.fake.t

    async def asyncTearDown(self):
        try:
            for mod, name, old in reversed(self.patched):
                setattr(mod, name, old)
            for hooks, saved in reversed(self.patched_hooks):
                hooks[:] = saved
            self.P.stop_all()
            self.P.pygame.mixer.quit()
        finally:
            self.clock.install(None)
            self.app.unload()
            sys.argv[:] = self._argv
            shutil.rmtree(self.dir, ignore_errors=True)

    # ---- helpers
    def mod_of(self, name):
        return self.app.modules.get(MODULE_OF.get(name)) if MODULE_OF.get(name) else self.P

    def patch(self, name, value):
        mod = self.mod_of(name)
        old = getattr(mod, name)
        self.patched.append((mod, name, old))
        setattr(mod, name, value)
        lst = HOOK_LISTS.get(name)
        if lst:                                            # also replace the registered entry (plan 4.4: two patch points for the same function)
            hooks = getattr(self.S, lst)
            self.patched_hooks.append((hooks, list(hooks)))
            hooks[:] = [value if h is old else h for h in hooks]

    # shared mutable state (live_deck, pending ...): one place to change when split step P4 moves it into cpl.state
    def _state_owner(self, name):
        S = self.app.modules.get("cpl.state")
        return S if S is not None and hasattr(S, name) else self.P

    def get_state(self, name):
        return getattr(self._state_owner(name), name)

    def set_state(self, name, value):
        setattr(self._state_owner(name), name, value)

    async def load(self, *names):
        for n in names:
            await self.P.ensure_loaded(str(self.P.LIB / n))

    def at(self, seconds, tick=True):
        """Set the fake clock to start + seconds and run one tick of the player."""
        self.fake.t = self.t0 + seconds
        if tick:
            self.P.tick()

    def rebase(self):
        """Make 'now' the new zero of at()."""
        self.t0 = self.fake.t

    def approx(self, a, b, tol=1e-3, msg=None):
        self.assertAlmostEqual(a, b, delta=tol, msg=msg)

    def live(self):
        return self.S.live_deck

    def pt(self):
        d = self.S.live_deck
        return tuple(d.pt) if d is not None and d.pt else None
