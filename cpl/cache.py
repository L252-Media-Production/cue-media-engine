"""The decoded-sound cache: LRU of whole tracks and of trimmed cuts, the decode helper process, load and ensure_loaded.

Moved verbatim from cpl/legacy.py in split step P5/P6 (docs/split-plan.md 2.1); nothing here imports cpl.legacy.
"""
import asyncio, os, sys, threading
from collections import OrderedDict
from pathlib import Path

import pygame

from cpl.config import BASE, CFG, LAUNCHER, LIB, MEDIA
from cpl.dsp import compute_env, duck_key, np
from cpl.util import log_once, spawn


# ---------------------------------------------------------------- sound cache
# A track must be decoded into RAM before it can play. Decoding compressed files inside this process freezes
# the audio output for seconds (measured: ~2.8 s for a 12-minute MP3), so MP3/OGG/FLAC are decoded in a helper
# process and handed over as raw PCM. The tracks around the focus are warmed ahead of time, and a trigger for a
# track that isn't ready yet waits in the background while whatever is playing carries on undisturbed.
_cache = OrderedDict()          # path -> (Sound, size in bytes)
_cache_lock = threading.Lock()
_loading = {}                   # path -> future of a load in progress
_gen = 0                        # bumped when the output device changes: cached sounds are then invalid


def resolve_path(p):
    """Used for paths from older versions: relative to this folder, or ./media/<same filename>."""
    q = Path(p)
    if not q.is_absolute():
        q = BASE / q
    if q.exists():
        return str(q)
    alt = MEDIA / q.name
    return str(alt) if alt.exists() else str(q)


_env = {}                                   # path -> level envelope of a cached track (see compute_env)


def cached(path):
    with _cache_lock:
        if path in _cache:
            _cache.move_to_end(path)
            return _cache[path][0]
    return None


_tcache = {}                    # (path, lo, hi) -> (Sound, bytes): a track already cut to its In/Out, so a cue is just play()
_key = {}                       # path -> per-10 ms level used to work out ducking (see duck_key); settings independent


def _cache_total():             # caller holds _cache_lock
    return sum(v[1] for v in _cache.values()) + sum(v[1] for v in _tcache.values())


def cache_bytes():
    with _cache_lock:
        return _cache_total()


def ram_snapshot():
    """For the page's RAM indicator: (paths decoded in RAM, paths being decoded, bytes used by sounds and trimmed cuts).
    Read-only: it does not call move_to_end, so looking never changes which track is dropped first."""
    with _cache_lock:
        return set(_cache), set(_loading), _cache_total()


def cache_drop(path):
    """Forget everything derived from one file (its decoded sound, trimmed copies, meter and ducking data)."""
    with _cache_lock:
        _cache.pop(path, None)
        for k in [k for k in _tcache if k[0] == path]:
            del _tcache[k]
    _env.pop(path, None)
    _key.pop(path, None)


def cache_put(path, snd):
    freq, fmt, chans = pygame.mixer.get_init()
    nbytes = int(snd.get_length() * freq) * chans * (abs(fmt) // 8)
    budget = max(64.0, float(CFG["cache_mb"])) * 1048576
    with _cache_lock:
        _cache[path] = (snd, nbytes)
        _cache.move_to_end(path)
        while len(_cache) > 1 and _cache_total() > budget:
            old, _ = _cache.popitem(last=False)       # drop the least recently used track
            for k in [k for k in _tcache if k[0] == old]:
                del _tcache[k]
            _env.pop(old, None)
            _key.pop(old, None)


def cut_sound(snd, start, hi):
    """A Sound holding seconds start..hi of snd. memoryview avoids copying the slice a second time."""
    freq, fmt, chans = pygame.mixer.get_init()
    frame = chans * (abs(fmt) // 8)
    return pygame.mixer.Sound(buffer=memoryview(snd.get_raw())[int(start * freq) * frame:int(hi * freq) * frame])


def trimmed_cached(path, lo, hi):
    with _cache_lock:
        v = _tcache.get((path, round(lo, 3), round(hi, 3)))
    return v[0] if v else None


def trimmed_put(path, lo, hi, snd):
    freq, fmt, chans = pygame.mixer.get_init()
    nbytes = int(snd.get_length() * freq) * chans * (abs(fmt) // 8)
    with _cache_lock:
        if path in _cache:                             # only while the whole track is still cached
            _tcache[(path, round(lo, 3), round(hi, 3))] = (snd, nbytes)


def mem_info():
    """RAM figures for the header readout: whole machine, this player process, and the decoded-track cache."""
    total = avail = rss = 0
    try:
        if os.name == "nt":
            import ctypes
            from ctypes import wintypes

            class MS(ctypes.Structure):
                _fields_ = [("dwLength", wintypes.DWORD), ("dwMemoryLoad", wintypes.DWORD), ("ullTotalPhys", ctypes.c_ulonglong),
                            ("ullAvailPhys", ctypes.c_ulonglong), ("ullTotalPageFile", ctypes.c_ulonglong),
                            ("ullAvailPageFile", ctypes.c_ulonglong), ("ullTotalVirtual", ctypes.c_ulonglong),
                            ("ullAvailVirtual", ctypes.c_ulonglong), ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
            ms = MS()
            ms.dwLength = ctypes.sizeof(MS)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(ms))
            total, avail = ms.ullTotalPhys, ms.ullAvailPhys

            class PM(ctypes.Structure):
                _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD), ("PeakWorkingSetSize", ctypes.c_size_t),
                            ("WorkingSetSize", ctypes.c_size_t), ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaPagedPoolUsage", ctypes.c_size_t), ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaNonPagedPoolUsage", ctypes.c_size_t), ("PagefileUsage", ctypes.c_size_t),
                            ("PeakPagefileUsage", ctypes.c_size_t)]
            pm = PM()
            pm.cb = ctypes.sizeof(PM)
            k32 = ctypes.windll.kernel32
            k32.GetCurrentProcess.restype = wintypes.HANDLE
            ctypes.windll.psapi.GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(pm), pm.cb)
            rss = pm.WorkingSetSize
        else:
            with open("/proc/meminfo") as f:
                mi = {l.split(":")[0]: int(l.split()[1]) * 1024 for l in f if ":" in l}
            total, avail = mi.get("MemTotal", 0), mi.get("MemAvailable", mi.get("MemFree", 0))
            with open("/proc/self/status") as f:
                for l in f:
                    if l.startswith("VmRSS:"):
                        rss = int(l.split()[1]) * 1024
    except Exception:
        pass
    with _cache_lock:
        n = len(_cache)
        cb = _cache_total()
    return {"ram_total": total, "ram_used": max(0, total - avail), "proc": rss,
            "cache": cb, "cache_budget": int(float(CFG["cache_mb"]) * 1048576), "cache_tracks": n}


async def decode_in_child(path):
    freq, fmt, chans = pygame.mixer.get_init()
    proc = await asyncio.create_subprocess_exec(
        sys.executable, str(LAUNCHER), "--decode", path, str(freq), str(fmt), str(chans),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        env={**os.environ, "PYGAME_HIDE_SUPPORT_PROMPT": "1"})
    try:
        data, err = await asyncio.wait_for(proc.communicate(), 120)
    except (asyncio.TimeoutError, asyncio.CancelledError) as e:
        proc.kill()                                # a stuck decode must not wedge the load queue
        await proc.wait()
        if isinstance(e, asyncio.TimeoutError):
            raise RuntimeError(f"decoding {Path(path).name} took too long")
        raise
    if proc.returncode != 0 or not data:
        raise RuntimeError(f"could not decode {Path(path).name}: "
                           + (err.decode(errors="replace").strip()[-200:] or f"exit code {proc.returncode}"))
    return data


async def _load(path):
    gen = _gen
    if not Path(path).exists():
        raise FileNotFoundError(f"file is missing: {path}")
    loop = asyncio.get_running_loop()
    if path.lower().endswith(".wav"):          # plain WAV loads without a decoder, so it can't stall the audio
        snd = await loop.run_in_executor(None, pygame.mixer.Sound, path)
        raw = await loop.run_in_executor(None, snd.get_raw) if np is not None else None
    else:
        raw = await decode_in_child(path)
        if gen != _gen:
            raise RuntimeError("the output device changed while loading")
        snd = pygame.mixer.Sound(buffer=raw)
    if gen != _gen:
        raise RuntimeError("the output device changed while loading")
    cache_put(path, snd)                       # the track can start now; the meter envelope is worked out in the background
    if raw is not None:
        async def _env_job():
            try:
                e = await loop.run_in_executor(None, compute_env, raw)
                if e is not None and cached(path) is snd:
                    _env[path] = e
                k = await loop.run_in_executor(None, duck_key, raw)
                if k is not None and cached(path) is snd:
                    _key[path] = k
            except Exception as ex:
                log_once("env:" + path, f"level meter data for {Path(path).name} could not be worked out (its meter stays flat)", ex)
        spawn(_env_job())
    return snd


async def ensure_loaded(path):
    snd = cached(path)
    if snd is not None:
        return snd
    fut = _loading.get(path)
    if fut is None:
        fut = asyncio.ensure_future(_load(path))
        _loading[path] = fut

        def done(f, p=path):
            if _loading.get(p) is f:
                del _loading[p]
            if not f.cancelled():
                f.exception()                  # mark as retrieved; waiters report the error themselves
        fut.add_done_callback(done)
    return await asyncio.shield(fut)


def invalidate_all():
    """The output device changed (set_device): everything decoded belongs to the old mixer instance. Statements moved from set_device, same order."""
    global _gen
    _gen += 1                          # loads still in flight were decoded for the old output: discard them
    _loading.clear()
    with _cache_lock:
        _cache.clear()                 # decoded sounds belong to the old mixer instance
        _tcache.clear()


def rename_path(m):
    """lib_rename: re-key the cache after a rename / move. `m` maps an old library id to the new one (the function lib_rename built).
    Statements moved from lib_rename, same order and same locking."""
    with _cache_lock:
        items = list(_cache.items())
        _cache.clear()
        for k, v in items:
            try:
                _cache[str(LIB / m(Path(k).relative_to(LIB).as_posix()))] = v
            except ValueError:
                _cache[k] = v
    for store in (_env, _key):
        for k in list(store):
            try:
                store[str(LIB / m(Path(k).relative_to(LIB).as_posix()))] = store.pop(k)
            except ValueError:
                pass
    with _cache_lock:
        _tcache.clear()                                # rebuilt by the warm-up under the new names
