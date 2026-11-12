"""Helper process (python player.py --preview DEVICE): the preview / mirror / solo-monitor mixer on a second output.
Runs when this module is imported by the launcher (player.py); imports only cpl.dsp (numpy) and the test hook."""
import json, os, sys, threading, time
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")      # as at the top of the old player.py: a pygame banner on stdout would corrupt the child's output

import numpy as np                              # (already needed by cpl.dsp) for the Loop A-B fades
from cpl.dsp import METER_WIN, compute_env      # numpy-only module: no config, no aiohttp, no python-osc
from cpl.helpers.common import test_dev_dir as _test_dev_dir
from cpl.helpers.ring import Ring

# Preview worker: its own mixer on a second output device (e.g. the Pi's headphone jack), controlled by
# JSON lines on stdin; it reports {"state","pos","dur","error"} as JSON lines on stdout ten times a second.
import pygame
_dev = sys.argv[2] or None
_td = _test_dev_dir()
if _td:
    open(_td / "worker.log", "a", encoding="utf-8").write(json.dumps(_dev) + "\n")
    _dev = None   # the dummy audio driver cannot open a named device; the log above is what is checked
pygame.mixer.pre_init(48000, -16, 2, 1024)
try:
    pygame.mixer.init(devicename=_dev) if _dev else pygame.mixer.init()
except Exception as _e:
    print(json.dumps({"state": "error", "pos": 0, "dur": 0, "error": f"could not open {_dev!r}: {_e}"}), flush=True)
    sys.exit(2)
pygame.mixer.set_num_channels(5)                       # 0 = preview, 1-3 = live monitor (solo), 4 = the Live input (Solo listening)
_BPS = 48000 * 2 * 2                                   # bytes per second of decoded audio
W = {"state": "stopped", "base": 0.0, "t0": 0.0, "dur": 0.0, "err": "", "gen": 0, "vol": 1.0, "mute": False,
     "raw": None, "path": None, "ch": None, "pausepos": 0.0, "env": None, "lidx": 0, "solo": False, "loop": None}
_lock = threading.Lock()

def _ev():
    """The preview output's own level: the preview volume, or 0 while the preview output is muted (a Mute that is not the volume, so unmuting brings the same level back)."""
    return 0.0 if W["mute"] else W["vol"]

def _pos():
    if W["state"] == "playing" and W["loop"]:          # Loop A-B: the position wraps inside [A, B)
        a, b = W["loop"]
        return a + (W["base"] - a + time.monotonic() - W["t0"]) % (b - a)
    if W["state"] == "playing":
        return min(W["dur"], W["base"] + time.monotonic() - W["t0"])
    if W["state"] == "paused":
        return W["pausepos"]
    return 0.0

def _play_from(pos):                                   # caller holds _lock
    pos = max(0.0, min(pos, max(0.0, W["dur"] - 0.05)))
    off = int(pos * _BPS) // 4 * 4
    if W["ch"]:
        W["ch"].stop()
    snd = pygame.mixer.Sound(buffer=W["raw"][off:])
    ch = pygame.mixer.Channel(0)                       # the preview always uses channel 0; the monitor uses 1-3
    ch.play(snd)
    ch.set_volume(0.0 if W["solo"] else _ev())      # muted (but still running) while the live audio is soloed
    W["ch"], W["snd"] = ch, snd
    W["base"], W["t0"], W["state"], W["err"] = pos, time.monotonic(), "playing", ""
    W["lidx"] = int(pos / METER_WIN)
    W["loop"] = None

def _load_and_play(path, start, gen):
    try:
        if W["path"] != path:
            raw = pygame.mixer.Sound(path).get_raw()
        else:
            raw = W["raw"]
    except Exception as e:
        with _lock:
            if gen == W["gen"]:
                W["state"], W["err"] = "error", f"could not load: {e}"
        return
    with _lock:
        if gen != W["gen"]:                            # stopped, or another track was requested meanwhile
            return
        W["raw"], W["path"], W["dur"] = raw, path, len(raw) / _BPS
    env = compute_env(raw) if W["path"] != W.get("envpath") else W["env"]          # (outside the lock: can take a moment)
    with _lock:
        if gen != W["gen"]:
            return
        W["env"], W["envpath"] = env, path
        _play_from(start)

def _loop_play(a, b, fin, fout, gen):
    """Loop A-B (the trim dialog): [A, B) of the decoded file as ONE buffer with an equal-power fade-in at A and fade-out at B, played with loops=-1,
    so the wrap is sample-accurate and every lap carries both fades (the same sin / cos curves as the live fades). Built off the command thread."""
    with _lock:
        raw, dur = W["raw"], W["dur"]
    if raw is None or dur <= 0:
        return
    a = max(0.0, min(a, dur - 0.1))
    b = max(a + 0.1, min(b, dur))
    x = np.frombuffer(raw, dtype=np.int16)[int(a * 48000) * 2:int(b * 48000) * 2].reshape(-1, 2).astype(np.float32)
    n = len(x)
    k = min(n // 2, int(fin / 1000.0 * 48000))
    if k > 0:
        x[:k] *= np.sin(np.arange(k, dtype=np.float32) / k * (np.pi / 2))[:, None]
    m = min(n // 2, int(fout / 1000.0 * 48000))
    if m > 0:
        x[n - m:] *= np.cos(np.arange(1, m + 1, dtype=np.float32) / m * (np.pi / 2))[:, None]
    snd = pygame.mixer.Sound(buffer=x.astype(np.int16).tobytes())
    with _lock:
        if gen != W["gen"]:                            # stopped, or something else was started meanwhile
            return
        if W["ch"]:
            W["ch"].stop()
        ch = pygame.mixer.Channel(0)
        ch.play(snd, loops=-1)
        ch.set_volume(0.0 if W["solo"] else _ev())
        W["ch"], W["snd"], W["loop"] = ch, snd, (a, n / 48000.0 + a)
        W["base"], W["t0"], W["state"], W["err"] = a, time.monotonic(), "playing", ""
        W["lidx"] = int(a / METER_WIN)

MON, MRAW, MLOAD = {}, {}, set()                      # live monitor: deck id -> playing channel; decoded files

def _mon_load(path):
    try:
        raw = pygame.mixer.Sound(path).get_raw()
    except Exception:
        raw = None
    with _lock:
        MLOAD.discard(path)
        if raw is not None:
            MRAW[path] = raw
            while len(MRAW) > 4:
                MRAW.pop(next(iter(MRAW)))

def _mon_stop():
    for m in MON.values():
        m["ch"].stop()
    MON.clear()

def _mon_apply(decks):                                 # caller holds _lock
    now = time.monotonic()
    keep = set()
    for d in decks[:3]:
        i = d["id"]
        keep.add(i)
        raw = MRAW.get(d["path"])
        if raw is None:
            if d["path"] not in MLOAD:
                MLOAD.add(d["path"])
                threading.Thread(target=_mon_load, args=(d["path"],), daemon=True).start()
            continue
        pos, v = float(d["pos"]), max(0.0, min(1.0, float(d["vol"]) * _ev()))
        m = MON.get(i)
        if m is not None and (m["path"] != d["path"] or not m["ch"].get_busy() or abs(m["base"] + now - m["t0"] - pos) > 0.3):
            m["ch"].stop()
            del MON[i]
            m = None
        if m is None:
            used = {x["slot"] for x in MON.values()}
            slot = next((k for k in (1, 2, 3) if k not in used), None)
            off = int(pos * _BPS) // 4 * 4
            if slot is None or off >= len(raw) - 4:
                continue
            ch = pygame.mixer.Channel(slot)
            ch.play(pygame.mixer.Sound(buffer=raw[off:]))
            m = MON[i] = {"ch": ch, "slot": slot, "path": d["path"], "base": pos, "t0": now}
        m["dv"] = float(d["vol"])                      # the live deck's own level; the preview volume multiplies it
        m["ch"].set_volume(v)
    for i in list(MON):
        if i not in keep:
            MON[i]["ch"].stop()
            del MON[i]

# ---- Live input, Solo listening: this process is a READER of the capture ring, with its own read pointer. It only plays what it reads on
# channel 4 of THIS (preview) mixer; it opens the ring read-only and sends nothing back, so it cannot affect the player's detector or Live.
IN = {"on": False, "gain": 1.0, "thread": None, "gen": 0, "played": 0, "nch": 0, "diff": 0}
_IN_CHUNK = 4800                                      # 100 ms per queued buffer

def _in_loop(path, gen):
    ring = Ring(path)
    ptr, ep = None, None
    pend = np.zeros((0, 1), dtype=np.int16)
    ch = pygame.mixer.Channel(4)
    while IN["on"] and IN["gen"] == gen:
        time.sleep(0.02)
        w, e = ring.written, ring.epoch
        if ptr is None or e != ep or w < ptr:
            ptr, ep, pend = w, e, np.zeros((0, ring.nch), dtype=np.int16)
        ptr, data, lost = ring.read(ptr)
        if lost:
            pend = pend[:0]
        if len(data):
            pend = np.concatenate([pend, data]) if pend.shape[1] == data.shape[1] else data
        if len(pend) > 48000:                          # never let the tap fall more than a second behind
            pend = pend[-_IN_CHUNK * 2:]
        while len(pend) >= _IN_CHUNK and ch.get_queue() is None:
            x = np.clip(pend[:_IN_CHUNK].astype(np.float32) * IN["gain"], -32768, 32767).astype(np.int16)
            pend = pend[_IN_CHUNK:]
            st = np.repeat(x, 2, axis=1) if x.shape[1] == 1 else x      # a single channel plays to both ears, a stereo pair as stereo
            snd = pygame.mixer.Sound(buffer=np.ascontiguousarray(st).tobytes())
            IN["played"] += len(x)
            IN["nch"] = int(x.shape[1])
            IN["diff"] += int(np.abs(st[:, 0].astype(np.int32) - st[:, 1].astype(np.int32)).sum())
            with _lock:
                ch.set_volume(_ev())
            if ch.get_busy():
                ch.queue(snd)
            else:
                ch.play(snd)
    ch.stop()
    ring.close()

def _in_set(c):                                        # caller holds _lock
    IN["gain"] = 10.0 ** (float(c.get("gain_db", 0.0)) / 20.0)
    on = bool(c.get("on")) and bool(c.get("ring"))
    if on and not IN["on"]:
        IN["on"], IN["gen"], IN["played"], IN["diff"], IN["nch"] = True, IN["gen"] + 1, 0, 0, 0
        IN["thread"] = threading.Thread(target=_in_loop, args=(c["ring"], IN["gen"]), daemon=True)
        IN["thread"].start()
    elif not on:
        IN["on"], IN["gen"] = False, IN["gen"] + 1

def _status():
    while True:
        with _lock:
            if W["state"] == "playing" and W["ch"] is not None and not W["ch"].get_busy():
                W["state"] = "stopped"
            lv = (0.0, 0.0)
            if W["state"] == "playing" and W["env"] is not None:
                idx = min(len(W["env"]) - 1, int(_pos() / METER_WIN))
                seg = W["env"][min(W["lidx"], idx):idx + 1]
                W["lidx"] = idx
                lv = (float(seg[:, 0].max()) * _ev(), float(seg[:, 1].max()) * _ev())
            else:
                W["lidx"] = int(_pos() / METER_WIN)
            out = {"state": W["state"], "pos": round(_pos(), 2), "dur": round(W["dur"], 2), "error": W["err"],
                   "l": round(lv[0], 4), "r": round(lv[1], 4), "solo": W["solo"], "mute": W["mute"], "mon": len(MON), "inmon": IN["on"], "inframes": IN["played"], "inch": IN["nch"], "indiff": IN["diff"],
                   "mv": round(max((m["ch"].get_volume() for m in MON.values()), default=0.0), 3)}
        try:
            print(json.dumps(out), flush=True)
        except (BrokenPipeError, ValueError, OSError):      # the player closed the pipe (it is stopping): stop quietly
            try:
                sys.stdout = open(os.devnull, "w")           # so the flush at exit does not complain either
            except Exception:
                pass
            return
        time.sleep(0.1)

threading.Thread(target=_status, daemon=True).start()
for _line in sys.stdin:
    try:
        c = json.loads(_line)
    except Exception:
        continue
    with _lock:
        op = c.get("cmd")
        if op == "play":
            W["loop"] = None
            W["gen"] += 1
            if W["ch"]:
                W["ch"].stop()
            W["state"], W["err"] = "loading", ""
            threading.Thread(target=_load_and_play, args=(c["path"], float(c.get("start", 0)), W["gen"]),
                             daemon=True).start()
        elif op == "loop" and W["raw"] is not None:    # Loop A-B: {a, b, fin, fout} (seconds, milliseconds); a stop, play or seek ends it
            W["gen"] += 1
            threading.Thread(target=_loop_play, args=(float(c.get("a", 0)), float(c.get("b", 0)), float(c.get("fin", 0)), float(c.get("fout", 0)), W["gen"]), daemon=True).start()
        elif op == "stop":
            W["loop"] = None
            W["gen"] += 1
            if W["ch"]:
                W["ch"].stop()
            W["state"] = "stopped"
        elif op == "pause" and W["state"] == "playing":
            W["pausepos"] = _pos()
            W["ch"].pause()
            W["state"] = "paused"
        elif op == "resume" and W["state"] == "paused":
            W["base"], W["t0"], W["state"] = W["pausepos"], time.monotonic(), "playing"
            W["ch"].unpause()
        elif op == "seek" and W["raw"] is not None and W["state"] in ("playing", "paused", "stopped"):
            was_paused = W["state"] == "paused"
            _play_from(float(c.get("pos", 0)))
            if was_paused and W["state"] == "playing":
                W["pausepos"] = W["base"]
                W["ch"].pause()
                W["state"] = "paused"
        elif op == "vol":
            W["vol"] = max(0.0, min(1.0, float(c.get("v", 1))))
            if W["ch"]:
                W["ch"].set_volume(0.0 if W["solo"] else _ev())
            for m in MON.values():                     # the soloed live audio follows the preview volume at once
                m["ch"].set_volume(max(0.0, min(1.0, m.get("dv", 1.0) * _ev())))
            pygame.mixer.Channel(4).set_volume(_ev())
        elif op == "mute":                             # mute the preview output (the preview track and the soloed live audio on it); the volume is kept
            W["mute"] = bool(c.get("on"))
            if W["ch"]:
                W["ch"].set_volume(0.0 if W["solo"] else _ev())
            for m in MON.values():
                m["ch"].set_volume(max(0.0, min(1.0, m.get("dv", 1.0) * _ev())))
            pygame.mixer.Channel(4).set_volume(_ev())
        elif op == "solo":                             # hear the live audio here; the preview keeps running, muted
            W["solo"] = bool(c.get("on"))
            if W["ch"]:
                W["ch"].set_volume(0.0 if W["solo"] else _ev())
            if not W["solo"]:
                _mon_stop()
        elif op == "inmon":                            # Solo listening to the Live input {on, ring, gain_db}
            _in_set(c)
        elif op == "mon" and W["solo"]:
            _mon_apply(c.get("decks", []))
        elif op == "quit":
            break
sys.exit(0)
