"""Track lengths, remembered in durations.json; one worker thread measures the files.

Moved verbatim from cpl/legacy.py in split step P5/P6 (docs/split-plan.md 2.1); nothing here imports cpl.legacy.
"""
import json, os, sys, threading

from cpl import clock
from cpl.config import BASE, LAUNCHER, LIB
from cpl.state import DURS, library
from cpl.util import atomic_write


DURFILE = BASE / "durations.json"  # track lengths, remembered between runs: {id: [size, mtime_ns, seconds]}
_dur_busy = False
_dur_booted = False               # the start-up check of every file has finished


def _dur_load():
    try:
        for k, v in json.loads(DURFILE.read_text()).items():
            if isinstance(v, list) and len(v) == 3:
                DURS[k] = (int(v[0]), int(v[1]), float(v[2]))
    except FileNotFoundError:
        pass
    except Exception as e:
        print("could not read durations.json (lengths will be measured again):", e)


def _dur_save():
    try:
        data = {k: list(v) for k, v in list(DURS.items()) if k in library}
        atomic_write(DURFILE, json.dumps(data))
    except Exception as e:
        print("could not save durations.json:", e)


def _probe_dur(fid):
    path = LIB / fid
    try:
        if path.suffix.lower() in (".wav", ".wave"):
            import wave
            with wave.open(str(path), "rb") as w:
                return w.getnframes() / float(w.getframerate())
    except Exception:
        pass
    try:                              # not WAV: measure in a low-priority child process, never inside the player
        import subprocess
        r = subprocess.run([sys.executable, str(LAUNCHER), "--probe", str(path)],
                           capture_output=True, text=True, timeout=120,
                           env={**os.environ, "PYGAME_HIDE_SUPPORT_PROMPT": "1"})
        return float(r.stdout.strip().splitlines()[-1])
    except Exception:
        return 0.0


def _dur_worker():
    global _dur_busy, _dur_booted
    try:
        n = 0
        for fid in list(library):
            try:
                st = os.stat(LIB / fid)
            except OSError:
                continue
            cur = DURS.get(fid)
            if cur and cur[0] == st.st_size and cur[1] == st.st_mtime_ns:
                continue                   # unchanged since last time: nothing to measure
            DURS[fid] = (st.st_size, st.st_mtime_ns, round(_probe_dur(fid), 2))
            n += 1
            if n % 20 == 0:
                _dur_save()
            clock.sleep(0.5)                # one file at a time, with gaps, so playback is never starved
        _dur_save()
    finally:
        _dur_busy = False
        _dur_booted = True


def durations(force=False):
    global _dur_busy
    if not _dur_busy and (force or any(DURS.get(f, (None,))[0] != s for f, s in library.items())):
        _dur_busy = True
        threading.Thread(target=_dur_worker, daemon=True).start()
    return DURS


def status():
    """(busy, booted) for health(): the flags stay private to this module; each is a plain bool written by the one worker thread (or by durations())."""
    return _dur_busy, _dur_booted
