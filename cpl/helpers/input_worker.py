"""Helper process (python player.py --input <json>): owns the Live input's capture device and writes ONE channel, or a stereo pair, of it into the shared ring
(cpl/helpers/ring.py). Nothing else lives here: no analysis, no playback. If this process stalls, crashes or loses the device, the player sees
the ring stop moving (and the status lines say why) and releases the ducking; Live playback never waits for it.
It retries to open the device every RETRY_S, forever, so a device that comes back is picked up by itself. It stops when the player closes our stdin.
Argument: JSON {"device": name|null, "channels": [1-based channel] or [a, a+1] (a stereo pair), "ring": path}. Status: one JSON line on stdout 4 times a second:
{"state": "ok"|"error", "reason": str, "channels": int (what the device really has, 0 = unknown), "names": [the device's own channel names, [] when it reports none],
"fault": "channels" when the chosen channels are not on the device, "device": name, "opens": n, "frames": n}.
Imports only stdlib, numpy, pygame and the helper modules."""
import json, math, os, sys, threading, time
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import numpy as np
from cpl.helpers.common import test_input_dir as _test_input_dir
from cpl.helpers.ring import RATE, Ring

RETRY_S = 2.0                   # between attempts to (re)open the device
STALL_S = 1.5                   # no audio callback for this long: the device is considered gone and is reopened
CHUNK = 480                     # frames per callback request (10 ms)

_arg = json.loads(sys.argv[2])
DEVICE = _arg.get("device")
SEL = [max(1, int(c)) for c in (_arg.get("channels") or [_arg.get("channel") or 1])][:2]       # 1-based channels to capture: one, or a stereo pair
ring = Ring(_arg["ring"], writer=True)
ST = {"state": "error", "reason": "starting", "channels": 0, "names": [], "fault": "", "device": DEVICE, "opens": 0}
_lock = threading.Lock()
_last_cb = [time.monotonic()]
_dev = [None]
_td = _test_input_dir()


def _set(state, reason="", channels=None, names=None, fault=""):
    with _lock:
        ST["state"], ST["reason"], ST["fault"] = state, reason, fault
        if channels is not None:
            ST["channels"] = channels
        if names is not None:
            ST["names"] = names


def _status():
    while True:
        with _lock:
            out = dict(ST, frames=ring.written)
        try:
            print(json.dumps(out), flush=True)
        except (BrokenPipeError, ValueError, OSError):
            os._exit(0)
        time.sleep(0.25)


# ---------------------------------------------------------------- the real device (pygame / SDL capture)
class _Fault(RuntimeError):
    """The chosen channels are not on the device: the player falls back to the first valid choice (it knows `channels`)."""
    def __init__(self, msg, channels):
        super().__init__(msg)
        self.channels = channels


def _real_names():
    from pygame._sdl2 import audio as A
    return A.get_audio_device_names(True)


def _real_open():
    """Open the chosen capture device and start delivering its channel into the ring. Raises with a plain reason."""
    import pygame
    from pygame._sdl2 import audio as A, sdl2
    try:
        sdl2.init_subsystem(sdl2.INIT_AUDIO)
    except Exception:
        pygame.mixer.init()
    names = _real_names()
    if DEVICE:
        if DEVICE not in names:
            raise RuntimeError(f"the input device \"{DEVICE}\" was not found (unplugged, or not running)")
        name = DEVICE
    elif names:
        name = names[0]
    else:
        raise RuntimeError("no input device was found")
    top = max(SEL)
    want = max(2, top + (top & 1))                       # an even number at least as large as the highest chosen channel
    holder = []
    cols = [c - 1 for c in SEL]

    def cb(dev, mv):
        _last_cb[0] = time.monotonic()
        n = dev.numchannels
        a = np.frombuffer(mv, dtype=np.int16)
        a = a[:len(a) // n * n]
        if top <= n and len(a):
            ring.write(np.ascontiguousarray(a.reshape(-1, n)[:, cols]))

    try:
        d = A.AudioDevice(devicename=name, iscapture=True, frequency=RATE, audioformat=pygame.AUDIO_S16SYS, numchannels=want,
                          chunksize=CHUNK, allowed_changes=pygame.AUDIO_ALLOW_CHANNELS_CHANGE, callback=cb)
    except Exception as e:
        raise RuntimeError(f"could not open the input device ({e})")
    holder.append(d)
    if top > d.numchannels:
        n = d.numchannels
        d.close()
        raise _Fault(f"channel {top} does not exist: the device has {n} channel{'s' if n != 1 else ''}", n)
    _last_cb[0] = time.monotonic()
    ring.new_epoch(len(SEL))
    d.pause(0)
    _dev[0] = d
    return {"channels": d.numchannels, "name": name, "names": []}          # (SDL does not report channel names: the player says "Channel n")


def _real_close():
    d, _dev[0] = _dev[0], None
    if d is not None:
        try:
            d.close()
        except Exception:
            pass


def _real_alive():
    if time.monotonic() - _last_cb[0] > STALL_S:
        return "the input device stopped delivering audio"
    if DEVICE:
        try:
            if DEVICE not in _real_names():
                return f"the input device \"{DEVICE}\" disappeared (unplugged?)"
        except Exception:
            pass
    return None


# ---------------------------------------------------------------- test source (CP_TEST_INPUT): feed.json decides what the "device" does
# {"state": "run" | "stop" | "error" | "gone", "db": RMS of the tone in dBFS, "hz": tone, "channels": n, "ch_db": {"2": -10} per-channel overrides, "reason": text}
# run = delivers audio; stop = the device stays open but delivers nothing (a stall); error = the stream fails; gone = the device is not there.
_fake = {"t": 0.0, "phase": 0.0, "thread": None, "run": False}


def _feed():
    try:
        return json.loads((_td / "feed.json").read_text(encoding="utf-8"))
    except Exception:
        return {"state": "run", "db": -90.0}


def _fake_loop():
    last = time.monotonic()
    cols = [c - 1 for c in SEL]
    while _fake["run"]:
        time.sleep(0.005)
        now = time.monotonic()
        n = int((now - last) * RATE)
        if n < 48:
            continue
        last += n / RATE
        f = _feed()
        if f.get("state", "run") != "run":
            continue
        _last_cb[0] = now
        chans = int(f.get("channels", 2))
        if max(SEL) > chans:
            continue
        hz = float(f.get("hz", 440.0))
        ph = _fake["phase"] + 2 * math.pi * hz / RATE * np.arange(n)
        _fake["phase"] = float((_fake["phase"] + 2 * math.pi * hz / RATE * n) % (2 * math.pi))
        sine = np.sin(ph)
        dev = np.zeros((n, chans), dtype=np.int16)                 # the whole fake device: every channel at its own level (ch_db {"2": -10}), then the chosen ones are taken
        for c in range(chans):
            db = float((f.get("ch_db") or {}).get(str(c + 1), f.get("db", -90.0)))
            dev[:, c] = (sine * (10.0 ** (db / 20.0) * math.sqrt(2.0) * 32767.0)).astype(np.int16)
        ring.write(np.ascontiguousarray(dev[:, cols]))


def _fake_open():
    f = _feed()
    st = f.get("state", "run")
    if st == "gone":
        raise RuntimeError(f.get("reason") or (f"the input device \"{DEVICE}\" was not found (unplugged, or not running)" if DEVICE else "no input device was found"))
    if st == "error":
        raise RuntimeError(f.get("reason") or "could not open the input device (test error)")
    chans = int(f.get("channels", 2))
    if max(SEL) > chans:
        raise _Fault(f"channel {max(SEL)} does not exist: the device has {chans} channel{'s' if chans != 1 else ''}", chans)
    _last_cb[0] = time.monotonic()
    ring.new_epoch(len(SEL))
    _fake["run"] = True
    _fake["thread"] = threading.Thread(target=_fake_loop, daemon=True)
    _fake["thread"].start()
    return {"channels": chans, "name": DEVICE, "names": list(f.get("names") or [])}


def _fake_close():
    _fake["run"] = False


def _fake_alive():
    f = _feed()
    if f.get("state", "run") == "gone":
        return f.get("reason") or "the input device disappeared (unplugged?)"
    if f.get("state") == "error":
        return f.get("reason") or "the input stream failed (test error)"
    if time.monotonic() - _last_cb[0] > STALL_S:
        return "the input device stopped delivering audio"
    return None


OPEN, CLOSE, ALIVE = (_fake_open, _fake_close, _fake_alive) if _td else (_real_open, _real_close, _real_alive)


def _keeper():
    """Open the device; while it is open, watch it; when it fails, close it and try again every RETRY_S. Never raises."""
    while True:
        try:
            info = OPEN()
        except _Fault as e:
            _set("error", str(e), e.channels, [], "channels")
            time.sleep(RETRY_S)
            continue
        except Exception as e:
            _set("error", str(e), 0)
            time.sleep(RETRY_S)
            continue
        with _lock:
            ST["opens"] += 1
        _set("ok", "", info["channels"], info.get("names") or [])
        while True:
            time.sleep(0.1)
            why = None
            try:
                why = ALIVE()
            except Exception as e:
                why = f"the input check failed ({e})"
            if why:
                CLOSE()
                _set("error", why, 0)
                time.sleep(RETRY_S)
                break


threading.Thread(target=_status, daemon=True).start()
threading.Thread(target=_keeper, daemon=True).start()
for _line in sys.stdin:                                  # the player closes our stdin (or dies) to stop us
    if '"quit"' in _line:
        break
os._exit(0)
