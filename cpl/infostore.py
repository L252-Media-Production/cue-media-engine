"""The file-information store (fileinfo.json).

Moved verbatim from cpl/legacy.py in split step P5/P6 (docs/split-plan.md 2.1); nothing here imports cpl.legacy.
"""
import asyncio, json

from cpl.config import BASE
from cpl.state import library
from cpl.util import atomic_write, spawn


# ---------------------------------------------------------------- file information (the "i" popover in the library)
INFOFILE = BASE / "fileinfo.json"   # measurements per file, remembered between runs: {id: {s, m, probe, loud, vol}}
INFO = {}


def _info_load():
    try:
        d = json.loads(INFOFILE.read_text())
        if isinstance(d, dict):
            INFO.update({k: v for k, v in d.items() if isinstance(v, dict) and "s" in v and "m" in v})
    except FileNotFoundError:
        pass
    except Exception as e:
        print("could not read fileinfo.json (files will be measured again when opened):", e)


def _info_save():
    try:
        atomic_write(INFOFILE, json.dumps({k: v for k, v in list(INFO.items()) if k in library}))
    except Exception as e:
        print("could not save fileinfo.json:", e)


_info_pending = [None]


def info_save_soon():
    """Write fileinfo.json half a second from now in a worker thread (the write waits for the disk, which is busy while ffmpeg reads):
    many measurements finishing together make one write, and the event loop is never held up by it."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        _info_save()
        return
    if _info_pending[0] and not _info_pending[0].done():
        return                                           # one is already waiting: it writes the newest state

    async def go():
        await asyncio.sleep(0.5)
        await loop.run_in_executor(None, _info_save)
    _info_pending[0] = spawn(go())


def info_entry(fid, st):
    """The cached measurements of a file, started afresh when the file has changed since (size or modified time)."""
    e = INFO.get(fid)
    if e is None or e.get("s") != st.st_size or e.get("m") != st.st_mtime_ns:
        e = INFO[fid] = {"s": st.st_size, "m": st.st_mtime_ns}
    return e


def info_store(fid, size, mt, key, val):
    """Remember one measurement of file version (size, mt)."""
    e = INFO.get(fid)
    if e is None or e.get("s") != size or e.get("m") != mt:
        e = INFO[fid] = {"s": size, "m": mt}
    e[key] = val
    info_save_soon()
