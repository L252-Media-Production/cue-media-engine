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
_big = {}                       # path -> decoded bytes of a track larger than the whole limit: played without caching (2.8.1), never warmed


# ---------------------------------------------------------------- the limit (2.8.1)
# What the cache may hold is the SMALLEST of: the cache_mb setting, 25 % of the machine's RAM, and the RAM minus 1 GB (so something always
# stays for the system). The machine's RAM is MemTotal of /proc/meminfo (Linux), else os.sysconf (macOS), else unknown: then only cache_mb counts.
MIB, GIB = 1048576, 1024 ** 3
BPS = 48000 * 2 * 2                             # decoded bytes per second at the mixer's fixed format (cpl/devices.py: 48 kHz, 16-bit, stereo)
RAM_SHARE, RAM_RESERVE, LIMIT_FLOOR = 0.25, GIB, 64 * MIB
MEMINFO = "/proc/meminfo"
_mach = {"path": MEMINFO, "sysconf": True}     # tests point "path" at a fake meminfo file (set_machine); "total" is read once


def read_meminfo(path=MEMINFO):
    """{field: bytes} of a /proc/meminfo file, or {} when there is none (macOS, Windows) or it cannot be read."""
    try:
        with open(path) as f:
            return {l.split(":")[0]: int(l.split()[1]) * 1024 for l in f if ":" in l and len(l.split()) >= 2}
    except (OSError, ValueError, IndexError):
        return {}


def machine_total(path=MEMINFO, sysconf=True):
    """Bytes of RAM in the machine, or None when it cannot be found."""
    t = read_meminfo(path).get("MemTotal")
    if t:
        return t
    if sysconf:
        try:
            v = os.sysconf("SC_PHYS_PAGES") * os.sysconf("SC_PAGE_SIZE")
            return v if v > 0 else None
        except (ValueError, OSError, AttributeError):
            pass
    return None


def limit_parts(setting_mb, total):
    """The three rules and the result: {setting, share, spare, limit, by}. share / spare are None when the RAM is not known."""
    try:
        setting = int(max(64.0, float(setting_mb)) * MIB)
    except (TypeError, ValueError):
        setting = 768 * MIB
    share = int(total * RAM_SHARE) if total else None
    spare = int(total - RAM_RESERVE) if total else None
    cands = [("setting", setting)] + ([("share", share), ("spare", spare)] if total else [])
    by, lim = min(cands, key=lambda c: c[1])
    return {"setting": setting, "share": share, "spare": spare, "limit": max(LIMIT_FLOOR, lim), "by": by}


def set_machine(path=MEMINFO, sysconf=True):
    """Tests: read the machine's RAM from another meminfo file (a missing file + sysconf=False = no machine rule)."""
    _mach.clear()
    _mach.update({"path": path, "sysconf": sysconf})


def machine_ram():
    if "total" not in _mach:
        _mach["total"] = machine_total(_mach["path"], _mach["sysconf"])
    return _mach["total"]


def limit_bytes():
    """The most the track cache holds (bytes)."""
    return limit_parts(CFG["cache_mb"], machine_ram())["limit"]


def mem_available():
    """MemAvailable of the machine in bytes (Linux), or None where it is not known."""
    return read_meminfo(_mach["path"]).get("MemAvailable")


def fill_bytes(lim=None):
    """How far the warm-up fills the cache ahead: 80 % of the limit, or the limit less 512 MB when that is more (a big machine keeps
    more of its playlists decoded); the rest is room for what is played on demand without dropping warm tracks."""
    lim = limit_bytes() if lim is None else lim
    return max(0.8 * lim, lim - 512 * MIB)


# ---------------------------------------------------------------- what is never dropped
# Callables that return paths the LRU must keep: the tracks playing (and fading, under a crossfade or a Play on Top), the track that follows the
# live one, the cue, the live track's trigger targets (cpl/warm.py) and the track on the Preview output (cpl/legacy.py). Only asked when over the limit.
keepers = []


def kept():
    out = set()
    for f in keepers:
        try:
            out.update(p for p in (f() or ()) if p)
        except Exception as e:
            log_once("cache-keep", "track cache: could not work out which tracks are in use", e)
    return out


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


def has(path):
    """Is the whole decoded track in the cache? Read-only: unlike cached() it does not count as a use."""
    with _cache_lock:
        return path in _cache


def touch(paths):
    """Count these as used, the FIRST one last: after the warm-up, the tracks nearest the cue are the last to be dropped."""
    with _cache_lock:
        for p in reversed(list(paths)):
            if p in _cache:
                _cache.move_to_end(p)


def is_oversize(path):
    return path in _big


def is_loading(path):
    return path in _loading


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
    _big.pop(path, None)


def sound_bytes(snd):
    freq, fmt, chans = pygame.mixer.get_init()
    return int(snd.get_length() * freq) * chans * (abs(fmt) // 8)


def _evict_locked(limit, keep):
    """Drop least recently used tracks (never one in `keep`) until the cache is within `limit`. Caller holds _cache_lock. Returns the paths dropped."""
    total, gone = _cache_total(), []
    for old in list(_cache):                           # oldest first
        if total <= limit:
            break
        if old in keep:
            continue
        total -= _cache.pop(old)[1]
        for k in [k for k in _tcache if k[0] == old]:
            total -= _tcache.pop(k)[1]
        _env.pop(old, None)
        _key.pop(old, None)
        gone.append(old)
    return gone


def cache_put(path, snd):
    nbytes = sound_bytes(snd)
    limit = limit_bytes()
    with _cache_lock:
        _cache[path] = (snd, nbytes)
        _cache.move_to_end(path)
        over = _cache_total() > limit
    if over:
        keep = kept() | {path}                         # outside the lock: the keepers read the decks and the playlists
        with _cache_lock:
            _evict_locked(limit, keep)


def shed():
    """Out of memory: drop every cached track that is not in use. Returns how many were dropped."""
    keep = kept()
    with _cache_lock:
        return len(_evict_locked(0, keep))


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
            "cache": cb, "cache_budget": limit_bytes(), "cache_tracks": n}


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


async def _decode(path, gen):
    loop = asyncio.get_running_loop()
    if path.lower().endswith(".wav"):          # plain WAV loads without a decoder, so it can't stall the audio
        snd = await loop.run_in_executor(None, pygame.mixer.Sound, path)
        try:
            raw = await loop.run_in_executor(None, snd.get_raw) if np is not None else None
        except MemoryError:
            raw = None                         # only the meter and ducking data need it: the track itself is decoded
    else:
        raw = await decode_in_child(path)
        if gen != _gen:
            raise RuntimeError("the output device changed while loading")
        snd = pygame.mixer.Sound(buffer=raw)
    return snd, raw


async def _load(path):
    gen = _gen
    if not Path(path).exists():
        raise FileNotFoundError(f"file is missing: {path}")
    loop = asyncio.get_running_loop()
    try:
        snd, raw = await _decode(path, gen)
    except MemoryError:                        # 2.8.1: never crash or restart the audio for memory: drop what is not in use and try once more
        n = shed()
        print(f"WARNING: out of memory while loading {Path(path).name}; dropped {n} cached track(s) that were not in use and trying again", flush=True)
        try:
            snd, raw = await _decode(path, gen)
        except MemoryError:
            raise RuntimeError(f"not enough memory to load {Path(path).name}") from None
    if gen != _gen:
        raise RuntimeError("the output device changed while loading")
    nbytes, limit = sound_bytes(snd), limit_bytes()
    big = nbytes > limit
    if big:                                    # larger than the whole cache: play it without keeping it (decoded again next time)
        if path not in _big:
            print(f"WARNING: {Path(path).name} needs {nbytes / MIB:,.0f} MB decoded, more than the track cache limit of {limit / MIB:,.0f} MB; "
                  "it plays without being kept in the cache", flush=True)
        _big[path] = nbytes
    else:
        _big.pop(path, None)
        cache_put(path, snd)                   # the track can start now; the meter envelope is worked out in the background
    if raw is not None:
        def mine():                            # read-only: working out the meter data is not a use of the track (it must not reorder the LRU)
            with _cache_lock:
                held = _cache.get(path)
            return (held is not None and held[0] is snd) or (big and path in _big)

        async def _env_job():
            try:
                e = await loop.run_in_executor(None, compute_env, raw)
                if e is not None and mine():
                    _env[path] = e
                k = await loop.run_in_executor(None, duck_key, raw)
                if k is not None and mine():
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
    _big.clear()


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
