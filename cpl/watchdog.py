"""The audio watchdog (2.8.0): notices when the output has stopped advancing while something should be playing, and restarts the audio engine.

Two parts, both testable without a sound card:
  * Heartbeat: a silent half-second sound looped on one reserved mixer channel. SDL's audio callback consumes it; each time it is seen to
    finish, the output has moved on, so `beats` goes up. If the callback stalls, the sound never finishes and `beats` stops. Nothing is added
    to the audio callback, the sound is silence (the mix is bit-identical), and it only runs while something is playing.
  * Watchdog: pure logic. It is given the beat counter, "should something be playing", a restart function and the clock, so tests drive it with a
    fake clock and a fake output.

The watchdog only ever restarts the audio engine (the caller closes and reopens the mixer like a device change and carries the live track on);
it never restarts the service or the process.
"""
from cpl import clock

STALL_S = 10.0                    # no beat for this long while something should be playing = stalled
MAX_RESTARTS = 3                  # at most this many restarts ...
WINDOW_S = 600.0                  # ... in this many seconds; then it gives up and leaves the Audio engine check bad
INFO_S = 3600.0                   # one INFO line per hour while playing
BEAT_S = 0.5                      # length of the silent heartbeat sound


class Heartbeat:
    """A silent sound on a reserved channel; see the module doc. `poll()` is called from tick() while something is playing."""

    def __init__(self, pygame_mixer):
        self.mx = pygame_mixer
        self.beats = 0
        self._ch = self._snd = None
        self._started = False
        self.frozen = False           # test hook (CP_TEST_WATCHDOG): stop counting, as if the callback had stalled

    def reset(self):
        """The mixer was closed and reopened: the old channel and sound are gone."""
        self._ch = self._snd = None
        self._started = False
        self.frozen = False

    def _make(self):
        fmt = self.mx.get_init()
        if not fmt:
            return False
        rate, size, chans = fmt
        self._snd = self.mx.Sound(buffer=bytes(int(rate * BEAT_S) * chans * (abs(size) // 8)))
        self._snd.set_volume(0.0)
        self._ch = self.mx.Channel(0)             # channel 0 is reserved (devices.init_mixer): find_channel never hands it to a track
        return True

    def poll(self):
        if self.frozen:
            return
        if self._ch is None and not self._make():
            return
        busy = self._ch.get_busy()
        if self._started and not busy:
            self.beats += 1                       # it played to its end: the output advanced by at least BEAT_S
            self._started = False
        if not busy:
            self._ch.play(self._snd)
            self._started = True


class Watchdog:
    def __init__(self, probe, should_play, restart, enabled=lambda: True, log=print, on_restart=lambda: None, can_restart=lambda: True):
        self.probe, self.should_play, self.restart, self.enabled, self.log = probe, should_play, restart, enabled, log
        self.can_restart = can_restart     # False while the Live output is already known to be missing: a dummy output's silence is not a stall to restart
        self.on_restart = on_restart       # called after each restart (the push message)
        self.stalled = False
        self.gave_up = False
        self.restarts = []            # clock.monotonic() of each restart, kept for WINDOW_S
        self.total = 0
        self._beats = None
        self._since = None            # when the output last moved (or when we started waiting)
        self._last_restart = None
        self._info_at = None          # when the last hourly 'running' line was written (only while playing)

    def poll(self):
        now = clock.monotonic()
        self.restarts = [t for t in self.restarts if now - t < WINDOW_S]
        if not self.enabled() or not self.should_play():
            self._since = now                                    # idle, paused or switched off: nothing to watch; the wait starts when playing starts
            self._beats = None
            if not self.enabled():
                self.stalled = self.gave_up = False
            return
        if self._info_at is None:
            self._info_at = now
        elif now - self._info_at >= INFO_S:
            self._info_at = now
            self.log(f"Watchdog: running, {self.total} restart{'s' if self.total != 1 else ''} since start")
        beats = self.probe()
        if self._since is None or self._beats is None:
            self._beats, self._since = beats, now                # first look after playing began
            return
        if beats != self._beats:
            self._beats, self._since = beats, now
            self.stalled = self.gave_up = False                  # the output moves again (restarted, or it came back by itself)
            return
        if now - self._since < STALL_S:
            return
        if not self.can_restart():
            self._since = now                                    # the Live output check already says what is wrong; no restart, nothing counted
            return
        self.stalled = True
        if len(self.restarts) >= MAX_RESTARTS:
            if not self.gave_up:
                self.gave_up = True
                self.log(f"Watchdog: audio output stalled; {MAX_RESTARTS} restarts in {int(WINDOW_S // 60)} min already, not restarting again")
            self._since = now
            return
        self.restarts.append(now)
        self.total += 1
        self.log(f"Watchdog: audio engine restarted (output stalled for {int(STALL_S)} s)")
        self._since = now                                        # the new engine gets its own 10 s
        self._beats = None
        self._last_restart = now
        try:
            self.restart()
        except Exception as e:
            self.log(f"Watchdog: the restart failed: {e}")
        try:
            self.on_restart()
        except Exception as e:
            self.log(f"Watchdog: the restart notice failed: {e}")
