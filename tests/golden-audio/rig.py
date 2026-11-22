"""A disposable in-process player for the golden-audio generator (the same recipe as tests/harness/engine.py, without unittest).

    async with Rig(lib={"a.wav": 12}, playlists=[{"name": "A", "tracks": ["a.wav"]}]) as r:
        await r.load("a.wav")
        r.P.play(0, 0)
        r.at(0.25)                     # fake clock = start + 0.25 s, then one tick()

A COPY of the app is imported into a temp folder (the real config, library and state are never opened), the clock is the fake one from
cpl/clock.py, the mixer is SDL's dummy driver, nothing listens on a port. Nothing here touches cpl/: every hook is a patch on the imported copy.
"""
import os
import shutil
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
TESTS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TESTS))
from harness.appcopy import copy_app            # noqa: E402
from harness.appload import load_app            # noqa: E402
from harness.engine import FakeTime, make_wav   # noqa: E402
from harness.instance import PROJECT            # noqa: E402

TICK = 0.05                                     # the player's tick period


class Rig:
    def __init__(self, lib, playlists=None, cfg=None):
        """lib: name -> seconds | (seconds, dc_value) | (seconds, dc_value, rate, channels) (see harness.engine.make_wav)."""
        self.lib, self.playlists, self.cfg = lib, playlists, cfg or {}

    async def __aenter__(self):
        self._argv = list(sys.argv)
        self.dir = Path(tempfile.mkdtemp(prefix="goldaudio-"))
        (self.dir / "media" / "library").mkdir(parents=True)
        (self.dir / "config.json").write_text('{"http_port": 18194, "osc_in_port": 18195}')
        copy_app(self.dir, PROJECT)
        self.secs = {}
        for name, spec in self.lib.items():
            spec = spec if isinstance(spec, tuple) else (spec,)
            make_wav(self.dir / "media" / "library" / name, spec[0], *(spec[2:4] if len(spec) > 2 else ()), dc=(spec[1] if len(spec) > 1 else 0))
            self.secs[name] = float(spec[0])
        self.app = load_app(self.dir)
        self.P = self.app.P
        self.S = self.app.mod("state")
        self.clock = self.app.mod("clock")
        self.fake = FakeTime()
        self.clock.install(self.fake)
        self._patched = []
        self.patch(self.app.mod("loudness"), "request_loudness", lambda: None, hook="on_save")
        async def idle():                                  # the background warm-up would decode every file as soon as the loop yields
            return None
        self.patch(self.app.mod("warm"), "_warm_loop", idle)
        self.P.CFG["watchdog"] = False                     # the fake clock jumps while the dummy output delivers nothing: not a stall
        self.P.CFG.update(self.cfg)
        self.P.init_mixer(None)
        self.P.scan_library()
        self.set_playlists(self.playlists or [{"name": "A", "tracks": list(self.lib)}])
        for fid, secs in self.secs.items():
            self.P.DURS[fid] = (0, 0, secs)
        self.t0 = self.fake.t
        return self

    async def __aexit__(self, *exc):
        try:
            for mod, name, old, hook in reversed(self._patched):
                setattr(mod, name, old)
            self.P.stop_all()
            self.P.pygame.mixer.quit()
        finally:
            self.clock.install(None)
            self.app.unload()
            sys.argv[:] = self._argv
            shutil.rmtree(self.dir, ignore_errors=True)

    def patch(self, mod, name, value, hook=None):
        old = getattr(mod, name)
        self._patched.append((mod, name, old, hook))
        setattr(mod, name, value)
        if hook:                                           # bump() / save() reach the function through a hook list (cpl.state)
            lst = getattr(self.app.mod("state"), hook)
            lst[:] = [value if h is old else h for h in lst]

    def set_playlists(self, playlists):
        self.P.playlists[:] = [dict(pl, tracks=list(pl["tracks"])) for pl in playlists]

    def reset(self, playlists=None, cfg=None):
        """Between scenarios of one group: stop everything, forget per-playlist data, restore the clock origin."""
        self.P.stop_all()
        self.set_playlists(playlists or self.playlists or [{"name": "A", "tracks": list(self.lib)}])
        for k, v in (cfg or {}).items():
            self.P.CFG[k] = v
        self.t0 = self.fake.t

    async def load(self, *names):
        for n in names:
            await self.P.ensure_loaded(str(self.P.LIB / n))

    def at(self, seconds, tick=True):
        """Fake clock = t0 + seconds exactly (use binary fractions for exact values), then one tick of the player."""
        self.fake.t = self.t0 + seconds
        if tick:
            self.P.tick()

    def rebase(self):
        self.t0 = self.fake.t

    def run_for(self, seconds, step=TICK, each=None):
        """Advance the fake clock `seconds` in steps of `step`, ticking each time; `each(elapsed)` is called after every tick."""
        n = int(round(seconds / step))
        for i in range(1, n + 1):
            self.fake.t += step
            self.P.tick()
            if each:
                each(round(i * step, 6))

    def live(self):
        return self.S.live_deck
