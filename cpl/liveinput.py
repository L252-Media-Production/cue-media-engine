"""Live input, Duck only (2.7.5): the player listens to one input channel and ducks the playlist audio while someone talks.

Parts, and who owns what:
  * the capture helper process (cpl/helpers/input_worker.py) owns the capture device and is the only writer of a shared ring (cpl/helpers/ring.py);
  * the DETECTOR (this module, `poll()`) is one reader of the ring with its own read pointer; it turns each 10 ms block into a level, runs the
    Play on Top gain computation on it (cpl.dsp.input_target_db = duck_curve, and duck_smooth for attack / release) and sets `Deck.duck_in` on
    every live deck. The Solo tap is another reader (in the preview worker, its own pointer, preview bus only): it never touches this module's state.
  * Where the detector runs, and why: in the player process, as a small task (every 10 ms: copy at most a few hundred samples out of the ring,
    one RMS per 10 ms block, a few float operations) rather than in the helper. The ratio, attack, release and hold are the ones
    of Play on Top (the threshold is the Live input's own, `input_threshold_db`) (`CFG`), changed at runtime from the web page and Companion; keeping the detector next to them means one source of truth, no
    protocol to push settings to a helper, and it runs on the same fake clock as the other engine tests. The helper stays a dumb pipe, which is what
    makes it safe to lose.
Safety: when the ring stops moving (stalled helper, stream error, device gone) or the helper says it has no device, ducking, including "Duck now",
is dropped AT ONCE (multipliers back to 1, no release ramp) and the chip says "No input" with the reason. The helper keeps retrying to reopen
the device; when audio flows again the input recovers by itself. Armed is kept (it is a setting).
Clock drift: ignored in 2.7.5. Duck only analyses the level and never plays the input into Live, so a separate analog interface cannot drift against
the output. This MUST be revisited (resampling / drift correction) when Play only or Both ships, because then the input is mixed into Live."""
import asyncio, json, math, sys
from pathlib import Path

from cpl import clock
from cpl.config import BASE, CFG, LAUNCHER
from cpl.devices import list_capture_devices
from cpl.dsp import duck_smooth, input_blocks, input_target_db, np
from cpl.helpers.ring import RATE, Ring
from cpl.persist import save_state
from cpl.state import decks
from cpl.util import log_once, spawn

BLOCK = RATE // 100                  # 10 ms, the same step as the Play on Top ducking
GAIN_MIN, GAIN_MAX = -12.0, 24.0     # input gain range (dB)
THR_MIN, THR_MAX = -60.0, 0.0        # the Live input's own ducking threshold (dB), 1 dB steps
THR_DEFAULT = -30.0                  # what the detector used before it had its own setting (the shipped Play on Top threshold); the "Reset" value
CHANNEL_MAX = 64
SIGNAL_DB = -60.0                    # "Signal present": the input (before the input gain) was above this within the last SIGNAL_WINDOW seconds
SIGNAL_WINDOW = 0.5
STALL_S = 0.5                        # the ring has not moved for this long (player clock): there is no input
FORCE_OVER_DB = 12.0                 # "Duck now" asks for the reduction a signal this far over the threshold would
RAMP_MIN_S, RAMP_MAX_S, RAMP_STEP_DB = 0.05, 0.10, 3.0   # release without a click: see LiveInput._start_ramp
DETECTOR_STALL_S = 0.25              # the detector task has not run for this long: it is treated as lost
HOLD_S = 1.0                         # with the shared "Stay ducked" switch on, the dip is held this long after the speech stops (a fixed value, not a setting)
RESPAWN_S = 2.0                      # the helper is restarted this long after it died
RING_FILE = BASE / "_input" / "ring.bin"


def clean_gain(v):
    """The input gain as a float within range, or raises ValueError (not a number / out of range)."""
    if isinstance(v, bool):
        raise ValueError("the input gain must be a number of dB")
    try:
        x = float(v)
    except (TypeError, ValueError):
        raise ValueError("the input gain must be a number of dB")
    if not math.isfinite(x) or not GAIN_MIN <= x <= GAIN_MAX:
        raise ValueError(f"the input gain must be between {GAIN_MIN:+g} and {GAIN_MAX:+g} dB")
    return round(x, 1)


def clean_threshold(v):
    """The Live input threshold as a float of whole dB, clamped to THR_MIN..THR_MAX. Raises ValueError for anything that is not a finite number."""
    if isinstance(v, bool):
        raise ValueError("the input threshold must be a number of dB")
    try:
        x = float(v)
    except (TypeError, ValueError):
        raise ValueError("the input threshold must be a number of dB")
    if not math.isfinite(x):
        raise ValueError("the input threshold must be a number of dB")
    return float(min(THR_MAX, max(THR_MIN, round(x))))


def clean_channel(v):
    if isinstance(v, bool):
        raise ValueError("the channel must be a whole number from 1 to %d" % CHANNEL_MAX)
    try:
        x = float(v)
    except (TypeError, ValueError):
        raise ValueError("the channel must be a whole number from 1 to %d" % CHANNEL_MAX)
    if not math.isfinite(x) or x != int(x) or not 1 <= x <= CHANNEL_MAX:
        raise ValueError("the channel must be a whole number from 1 to %d" % CHANNEL_MAX)
    return int(x)


def clean_channels(v):
    """The chosen channels: [n] (one channel, mono) or [n, n+1] (a stereo pair). Accepts a number (= [number]) too. Raises ValueError otherwise."""
    if isinstance(v, (list, tuple)):
        if len(v) not in (1, 2):
            raise ValueError("choose one channel or a stereo pair of two neighbouring channels")
        out = [clean_channel(x) for x in v]
        if len(out) == 2 and out[1] != out[0] + 1:
            raise ValueError("a stereo pair is two neighbouring channels, such as 1 and 2")
        return out
    return [clean_channel(v)]


def channel_label(chs, names=None):
    """'Channel 1/Channel 2' for a pair, 'Channel 3' for one channel; the device's own names when it reports them."""
    nm = lambda c: (names[c - 1] if names and 0 < c <= len(names) and names[c - 1] else f"Channel {c}")
    return "/".join(nm(c) for c in chs)


def channel_choices(n, names=None, selected=None):
    """The Channels menu for a device with `n` channels (0 = not known yet: eight are offered): the stereo pairs first (1/2, 2/3, 3/4 ...; an odd last
    channel has no pair), then every single channel. The saved choice is always in the list, so the menu can show it."""
    top = max(int(n or 0), 0) or 8
    sel = list(selected or [])
    top = max(top, max(sel) if sel else 0)
    pairs = [[c, c + 1] for c in range(1, top)]
    singles = [[c] for c in range(1, top + 1)]
    out = [{"v": "-".join(map(str, c)), "channels": c, "group": "Stereo pair", "label": channel_label(c, names) + " (stereo)"} for c in pairs]
    out += [{"v": str(c[0]), "channels": c, "group": "Single channel", "label": channel_label(c, names) + " (mono)"} for c in singles]
    return out


def as_bool(v):
    if isinstance(v, str):
        return v.strip().lower() in ("1", "true", "on", "yes")
    return bool(v)


def sanitize_config():
    """state.json / config.json are hand-editable: a bad saved value falls back to its default instead of breaking the player."""
    try:
        CFG["input_gain_db"] = clean_gain(CFG.get("input_gain_db", 0.0))
    except ValueError:
        CFG["input_gain_db"] = 0.0
    # the threshold: a setting saved before the Live input had its own (absent) keeps the level the detector used then, the Play on Top threshold as it is now
    migrate = CFG.get("input_threshold_db") is None
    try:
        CFG["input_threshold_db"] = clean_threshold(CFG["duck_threshold_db"] if migrate else CFG["input_threshold_db"])
    except (ValueError, KeyError, TypeError):
        CFG["input_threshold_db"] = THR_DEFAULT
    if migrate:
        save_state()
    # the channels: the new list wins; a setting saved before stereo pairs (only "input_channel") is the same single channel; anything bad falls back to channel 1
    for src in (CFG.get("input_channels"), CFG.get("input_channel")):
        if src is None:
            continue
        try:
            CFG["input_channels"] = clean_channels(src)
            break
        except ValueError:
            continue
    else:
        CFG["input_channels"] = [1]
    CFG["input_channel"] = CFG["input_channels"][0]
    CFG["input_armed"] = as_bool(CFG.get("input_armed", False))
    d = CFG.get("input_device")
    CFG["input_device"] = d if isinstance(d, str) and d else None
    CFG.pop("input_hold_ms", None)                  # rc1 had a second hold time; the hold is now the Play on Top one (the shared switch), the old key is ignored


class LiveInput:
    def __init__(self):
        self.ring = None                  # the Ring this detector reads (read-only); None until start() / attach()
        self.ring_path = None
        self.proc = None
        self.status = {"state": "error", "reason": "", "channels": 0}       # the helper's last report
        self.status_at = -1e9
        self.respawn_at = 0.0
        self.spawning = False
        self.started = False
        self.solo = False                 # Solo listening on the preview output (not saved, off at every start)
        self.duck_now = False             # forced ducking (not saved)
        self.note = ""                    # a plain note for the card (a saved choice the device cannot offer fell back to the first valid one)
        self.switching = False            # the capture is being restarted for a new device or channel choice: the chip says "Switching…"
        self.restart_at = -1e9
        self.on_solo = None               # hook set by the player: called when the Solo state or the ring must be (re)sent to the preview output
        self.reset_detector()

    # ------------------------------------------------------------ detector state
    def reset_detector(self):
        self.ptr = None
        self.epoch = None
        self.pend = np.zeros((0, 1), dtype=np.int16) if np is not None else None
        self.gr = 0.0                      # dB of reduction the input asks for right now (after attack / release)
        self.audio_t = 0.0                 # seconds of input audio analysed since the ring was attached (the detector's own time base)
        self.last_signal = -1e9
        self.hold_until = -1e9
        self.hold_depth = 0.0
        self.last_w = None
        self.last_move = clock.monotonic()
        self.level_db = -90.0              # latest block level after the input gain (the louder channel of a pair: what ducking uses)
        self.levels_db = []                # ... and the level of each chosen channel (one or two values)
        self.alive = False
        self.why = "No input device chosen"
        self.mult = 1.0
        self.ramp_rate = None              # dB per second while a quick, click-free release runs (None = none)
        self.prev_armed, self.prev_force = bool(CFG["input_armed"]), False
        self.last_poll = clock.monotonic() # when the detector task last ran (the watchdog in the 50 ms tick looks at it)
        self.last_idle = self.last_poll
        self.stalled = False

    def attach(self, path, create=False):
        """Map the ring read-only. The player calls this at start; tests call it with a ring they write themselves."""
        if self.ring is not None:
            self.ring.close()
        self.ring_path = str(path)
        if create:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            Ring(path, writer=True, create=True).close()
        self.ring = Ring(path)
        self.reset_detector()

    # ------------------------------------------------------------ settings
    def set_config(self, vals):
        """Validate and apply {device, channels, gain_db, threshold_db, armed}. Returns an error text or None. Nothing changes when anything is invalid."""
        new = {}
        try:
            if "device" in vals:
                d = vals["device"]
                if d is not None and (not isinstance(d, str) or len(d) > 300):
                    raise ValueError("unknown device")
                new["input_device"] = d or None
            if "channels" in vals:
                new["input_channels"] = clean_channels(vals["channels"])
            elif "channel" in vals:
                new["input_channels"] = clean_channels(vals["channel"])
            if "gain_db" in vals:
                new["input_gain_db"] = clean_gain(vals["gain_db"])
            if "threshold_db" in vals:
                new["input_threshold_db"] = clean_threshold(vals["threshold_db"])
            if "armed" in vals:
                new["input_armed"] = as_bool(vals["armed"])
        except ValueError as e:
            return str(e)
        if new.get("input_device") and new["input_device"] not in list_capture_devices() and new["input_device"] != CFG["input_device"]:
            return "unknown device"
        restart = any(k in new and new[k] != CFG[k] for k in ("input_device", "input_channels"))
        if "input_channels" in new:
            new["input_channel"] = new["input_channels"][0]
        CFG.update(new)
        if restart or "input_channels" in new:
            self.note = ""
        save_state()
        if restart:
            self.restart_helper()
        if self.on_solo:
            self.on_solo()
        return None

    def set_duck_now(self, on):
        """Duck now is a manual override: it works with or without an input device, with Armed on or off, and stays on until it is switched off
        (from the card, Companion or the API) or the player restarts. Losing the input does not clear it."""
        self.duck_now = bool(on)
        return True

    def set_solo(self, on):
        self.solo = bool(on)
        if self.on_solo:
            self.on_solo()

    # ------------------------------------------------------------ the helper process
    def restart_helper(self):
        old, self.proc = self.proc, None
        self.switching, self.restart_at = bool(CFG["input_device"]), clock.monotonic()
        self.status = {"state": "error", "reason": "starting", "channels": 0}
        self.respawn_at = 0.0
        self.pend = self.pend[:0]
        if self.alive:                                 # the old capture is gone from this moment: the input ducking ramps off, the chip says so at once
            self.hold_depth, self.hold_until = 0.0, -1e9
            self._start_ramp()
            self.alive, self.why, self.level_db, self.levels_db, self.last_signal = False, "Switching the input…", -90.0, [], -1e9
        if old is not None and old.returncode is None:
            try:
                old.stdin.write(b'{"cmd":"quit"}\n')
                old.stdin.close()
            except Exception:
                pass
            try:
                old.kill()
            except Exception:
                pass

    async def _spawn(self):
        try:
            arg = json.dumps({"device": CFG["input_device"], "channels": self.channels(), "ring": self.ring_path})
            proc = await asyncio.create_subprocess_exec(sys.executable, str(LAUNCHER), "--input", arg,
                                                        stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE)
        except Exception as e:
            self.status = {"state": "error", "reason": f"could not start the input helper: {e}", "channels": 0}
            self.respawn_at = clock.monotonic() + RESPAWN_S
            return
        finally:
            self.spawning = False
        self.proc = proc
        self.status = {"state": "error", "reason": "starting", "channels": 0}
        spawn(self._read(proc))

    async def _read(self, proc):
        while True:
            line = await proc.stdout.readline()
            if not line:
                break
            try:
                st = json.loads(line)
            except Exception as e:
                log_once("inread", "the input helper sent an unreadable line", e)
                continue
            if proc is self.proc:
                self.status, self.status_at = st, clock.monotonic()
        if proc is self.proc:
            self.proc = None
            self.status = {"state": "error", "reason": "the input helper stopped; restarting it", "channels": 0}
            self.respawn_at = clock.monotonic() + RESPAWN_S

    def supervise(self):
        """Start the helper when it should run and is not running. Called from the loop task, never blocks."""
        if self.ring is None or self.proc is not None or self.spawning or not CFG["input_device"]:
            return
        if clock.monotonic() < self.respawn_at:
            return
        self.spawning = True
        spawn(self._spawn())

    # ------------------------------------------------------------ detector
    def _apply(self, mult):
        self.mult = mult
        for d in decks:
            if abs(d.duck_in - mult) > 0.0005 or (mult == 1.0 and d.duck_in != 1.0):
                d.duck_in = mult
                d.apply()

    def forced_db(self):
        """The reduction "Duck now" holds: what a signal FORCE_OVER_DB over the threshold would ask for (so it follows threshold and ratio)."""
        lv = min(1.0, 10.0 ** ((float(CFG["duck_threshold_db"]) + FORCE_OVER_DB) / 20.0))
        return input_target_db(lv, 0.0, CFG["duck_ratio"], CFG["duck_threshold_db"])

    def _start_ramp(self):
        """Take the input's ducking off quickly but without a click: a linear-in-dB ramp of RAMP_MIN_S, longer when the dip is deep so that one
        10 ms step never exceeds RAMP_STEP_DB (up to RAMP_MAX_S, so a dip deeper than 30 dB steps by more than 3 dB). The normal release curve is
        used instead whenever it is faster. Used for the loss of the input, a stalled detector, Armed off and Duck now off."""
        if self.gr <= 0.0:
            self.ramp_rate = None
            return
        dur = min(RAMP_MAX_S, max(RAMP_MIN_S, self.gr / RAMP_STEP_DB * (BLOCK / RATE)))
        self.ramp_rate = self.gr / dur                 # dB per second

    def _step(self, rms, dt):
        """One detector step of `dt` seconds. `rms` is the 10 ms block level (0..1) of the chosen channel, a list of them for a stereo pair (the louder one
        counts: one active mic is enough), or None when there is no input (then only Duck now can duck)."""
        gain = float(CFG["input_gain_db"])
        per = None
        if isinstance(rms, (list, tuple)):
            per, rms = list(rms), max(rms)
        if (self.prev_armed and not CFG["input_armed"]) or (self.prev_force and not self.duck_now):
            self._start_ramp()
        self.prev_armed, self.prev_force = bool(CFG["input_armed"]), bool(self.duck_now)
        tgt = 0.0
        if rms is not None:
            self.audio_t += dt
            raw_db = 20.0 * math.log10(max(rms, 1e-6))
            self.level_db = raw_db + gain
            self.levels_db = [20.0 * math.log10(max(v, 1e-6)) + gain for v in (per if per is not None else [rms])]
            if raw_db > SIGNAL_DB:
                self.last_signal = self.audio_t
            if CFG["input_armed"]:
                tgt = input_target_db(rms, gain, CFG["duck_ratio"], CFG["input_threshold_db"])
        if rms is not None and CFG["input_armed"] and CFG["duck_hold"]:      # the shared "Stay ducked" switch: keep the depth for HOLD_S after the speech stops
            if tgt > 0.05:
                self.hold_until = self.audio_t + HOLD_S
                self.hold_depth = max(self.hold_depth, tgt)
            elif self.audio_t < self.hold_until:
                tgt = self.hold_depth
            else:
                self.hold_depth = 0.0
        else:
            self.hold_depth, self.hold_until = 0.0, -1e9
        if self.duck_now:                                  # a manual override: independent of the input and of Armed
            tgt = max(tgt, self.forced_db())
        new = duck_smooth(self.gr, tgt, dt, CFG["duck_attack_ms"], CFG["duck_release_ms"])
        if self.ramp_rate is not None:
            if tgt < self.gr:
                new = min(new, max(tgt, self.gr - self.ramp_rate * dt))
            if new <= tgt + 1e-6 or tgt >= self.gr:
                self.ramp_rate = None
        if tgt == 0.0 and new < 0.05:
            new = 0.0
        self.gr = new

    def _no_input(self, why, now):
        """There is no (usable) input: the input-driven ducking ramps off, Duck now (a manual override) is untouched."""
        fresh = self.alive
        if fresh:
            self.hold_depth, self.hold_until = 0.0, -1e9
            self._start_ramp()
        self.alive, self.why = False, why
        self.level_db = -90.0
        self.levels_db = []
        self.last_signal = -1e9
        if self.pend is not None:
            self.pend = self.pend[:0]
        dt = BLOCK / RATE if fresh else max(0.001, min(0.2, now - self.last_idle))      # the step that finds the loss is one block long, not the time since the last audio
        self.last_idle = now
        self._step(None, dt)
        self._finish()

    def _finish(self):
        mult = 10.0 ** (-self.gr / 20.0) if self.gr > 0.0 else 1.0
        if abs(mult - self.mult) > 0.0005 or (self.gr == 0.0 and self.mult != 1.0) or any(d.duck_in != self.mult for d in decks):
            self._apply(mult)

    def poll(self):
        """One detector step: read what the helper wrote since last time and update the ducking. Cheap and non-blocking (called every 10 ms)."""
        now = clock.monotonic()
        gap = now - self.last_poll
        self.last_poll = now
        ring = self.ring
        self.stalled = False
        if gap > DETECTOR_STALL_S:
            # this task was late (the event loop was blocked): what the ring holds is old, so it is skipped, the input ducking ramps off
            # and the chip says so for this step; the next on-time step recovers by itself
            self.stalled = True
            if ring is not None:
                self.ptr, self.pend = ring.written, self.pend[:0]
                self.last_w, self.last_move = self.ptr, now
            self._no_input("The input detector stalled", now)
            return
        if ring is None or np is None:
            self._no_input("The input is not available" if np is None else "No input device chosen", now)
            return
        if not CFG["input_device"]:
            self._no_input("No input device chosen", now)
            return
        w, ep = ring.written, ring.epoch
        if self.ptr is None or ep != self.epoch or w < self.ptr:
            self.ptr, self.epoch = w, ep                   # a (re)opened device: start from the newest audio
            self.pend = np.zeros((0, ring.nch), dtype=np.int16)
            self.last_w, self.last_move = w, now
        if w != self.last_w:
            self.last_w, self.last_move = w, now
        if self.status.get("state") != "ok":
            if self.status.get("fault") == "channels" and self.status.get("channels"):
                self._fallback(int(self.status["channels"]))
            elif self.switching and self.status_at > self.restart_at and self.status.get("reason") not in ("", "starting"):
                self.switching = False                      # the new capture really failed (not just starting): say why instead of "Switching…"
            self._no_input(self.status.get("reason") or "No audio from the input device", now)
            return
        if now - self.last_move > STALL_S:
            self._no_input("No audio is arriving from the input device", now)
            return
        self.alive, self.why, self.switching = True, "", False
        self.last_idle = now
        self.ptr, data, lost = ring.read(self.ptr)
        if lost:
            self.pend = self.pend[:0]
        if len(data):
            buf = np.concatenate([self.pend, data]) if len(self.pend) and self.pend.shape[1] == data.shape[1] else data
            levels, used = input_blocks(buf, BLOCK)
            self.pend = buf[used:]
            for lv in levels:
                self._step(lv, BLOCK / RATE)
        self._finish()

    def channels(self):
        """The chosen channels, [n] or [n, n+1]."""
        try:
            return clean_channels(CFG.get("input_channels") or [CFG.get("input_channel") or 1])
        except ValueError:
            return [1]

    def _fallback(self, n):
        """The device has `n` channels and the saved choice does not fit: use the first valid choice of the menu (the first stereo pair, or channel 1 of
        a one-channel device), say so plainly on the card, and restart the capture. Not an error."""
        old = self.channels()
        new = [1, 2] if n >= 2 else [1]
        if new == old:
            return
        names = self.status.get("names") or []
        self.note = (f"{channel_label(old, names)} is not on {CFG['input_device'] or 'this device'} (it has {n} channel{'s' if n != 1 else ''}); "
                     f"using {channel_label(new, names)} instead.")
        CFG["input_channels"], CFG["input_channel"] = new, new[0]
        save_state()
        note = self.note
        self.restart_helper()
        self.note = note

    def watchdog(self):
        """Called from the player's 50 ms tick: if the 10 ms detector task has not run for DETECTOR_STALL_S (it died, or the loop was blocked and is
        only now catching up) the input ducking is ramped off and the chip says "Detector stalled". A stale detector can never leave the music ducked."""
        now = clock.monotonic()
        if self.ring is None or now - self.last_poll <= DETECTOR_STALL_S:
            return
        self.stalled = True
        self._no_input("The input detector stalled", now)

    # ------------------------------------------------------------ what the page / Companion see
    def signal(self):
        return bool(self.alive and self.audio_t - self.last_signal <= SIGNAL_WINDOW)

    def ducking(self):
        return bool(self.gr > 0.5)

    def reason(self):
        if self.alive:
            return ""
        w = self.why or ""
        if CFG["input_device"] and "saved" not in w and "not found" in w and "channel" not in w.lower():
            return w + ". It is retried every few seconds and picked up when it appears."
        return w

    def is_stalled(self):
        return bool(self.stalled or (self.ring is not None and clock.monotonic() - self.last_poll > DETECTOR_STALL_S))

    def info(self):
        sig = self.signal()
        stalled = self.is_stalled()
        chs = self.channels()
        names = self.status.get("names") or []
        stereo = len(chs) == 2
        return {"mode": "duck", "device": CFG["input_device"], "channel": chs[0], "channel_list": chs, "stereo": stereo, "channel_label": channel_label(chs, names),
                "choices": channel_choices(self.status.get("channels") or 0, names, chs), "note": self.note,
                "levels_db": [round(v, 1) for v in self.levels_db] if self.alive else None, "switching": bool(self.switching and not self.alive),
                "gain_db": CFG["input_gain_db"],
                "armed": bool(CFG["input_armed"]), "duck_now": bool(self.duck_now), "solo": self.solo,
                "present": bool(self.alive), "signal": sig,
                "chip": "Detector stalled" if stalled else ("Signal present" if sig else "No signal") if self.alive else "Switching…" if self.switching else "No input",
                "reason": "The input detector has not run for a moment; the input ducking is off until it does" if stalled else "Switching the input…" if (self.switching and not self.alive) else self.reason(),
                "level_db": round(self.level_db, 1) if self.alive else None, "threshold_db": float(CFG["input_threshold_db"]),
                "threshold_default": THR_DEFAULT, "threshold_min": THR_MIN, "threshold_max": THR_MAX,
                "gr": round(self.gr, 1), "ducking": self.ducking(), "channels": int(self.status.get("channels") or 0),
                "gain_min": GAIN_MIN, "gain_max": GAIN_MAX, "channel_max": CHANNEL_MAX}


LI = LiveInput()


def start():
    """Called once the event loop runs: clean the saved settings, create the ring and start the loop that polls and supervises the helper."""
    sanitize_config()
    try:
        LI.attach(RING_FILE, create=True)
    except OSError as e:
        LI.why = f"could not create the input buffer ({e})"
        log_once("inring", "Live input: could not create the capture buffer", e)
        return None
    LI.started = True
    return spawn(loop())


async def loop():
    n = 0
    while True:
        try:
            LI.poll()
            n += 1
            if n % 25 == 0:
                LI.supervise()
        except Exception as e:                       # the input must never stop the player
            log_once("inloop", "Live input: error in the detector (the input is ignored until it works again)", e)
            try:
                LI._no_input("The input detector hit an error", clock.monotonic())
            except Exception:
                pass
        await asyncio.sleep(BLOCK / RATE)
