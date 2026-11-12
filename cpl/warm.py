"""Warm-up policy: which tracks to decode ahead.

Moved verbatim from cpl/legacy.py in split step P5/P6 (docs/split-plan.md 2.1); nothing here imports cpl.legacy.
"""
import asyncio
from pathlib import Path

from cpl import clock
from cpl import state as S
from cpl.cache import _cache_lock, _tcache, cache_bytes, cached, cut_sound, ensure_loaded, ram_snapshot, trimmed_cached, trimmed_put
from cpl.config import CFG, LIB
from cpl.playlists import trim_of, trim_range
from cpl.state import focus, library, playlists
from cpl.triggers_data import trigger_targets
from cpl.util import log_once


_warm = {"task": None, "again": False}


def request_warm():
    """Keep the tracks from the focus onwards decoded in RAM (within the cache budget)."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return
    if _warm["task"] and not _warm["task"].done():
        _warm["again"] = True                  # focus moved: start the warm-up order again
        return
    _warm["task"] = asyncio.ensure_future(_warm_loop())


S.on_change.append(request_warm)       # bump() runs it (split step P4, F2): the lists changed, so keep the tracks around the focus decoded


async def _warm_loop():
    while True:
        _warm["again"] = False
        p, t = focus
        order = trigger_targets()               # what the live track's trigger points will play comes first
        ids = list(playlists[p]["tracks"]) if 0 <= p < len(playlists) else []   # then the focus playlist from the cue onwards, then the others (the next one first)
        order += [ids[(t + k) % len(ids)] for k in range(len(ids))]
        for q in list(range(p + 1, len(playlists))) + list(range(0, p)):
            order += playlists[q]["tracks"]
        todo, seen = [], set()
        for fid in order:
            if fid in seen or fid not in library:
                continue
            seen.add(fid)
            if cached(str(LIB / fid)) is None:
                todo.append(str(LIB / fid))
        i = 0
        while i < len(todo) and not _warm["again"]:
            if cache_bytes() > 0.8 * float(CFG["cache_mb"]) * 1048576:
                break
            batch = todo[i:i + 2]               # two at a time: the player has cores to spare, and a cold start waits less
            i += 2
            res = await asyncio.gather(*(ensure_loaded(x) for x in batch), return_exceptions=True)
            for r in res:
                if isinstance(r, Exception):
                    print("warm-up:", r)
        await _warm_trims()
        if not _warm["again"]:
            return


async def _warm_trims():
    """Cut each trimmed track to its In/Out ahead of time (off the event loop), and drop copies nobody asks for any more."""
    loop = asyncio.get_running_loop()
    want = []                                           # (path, lo, hi) in cue order: focus playlist first
    order = [focus[0]] + [q for q in range(len(playlists)) if q != focus[0]] if 0 <= focus[0] < len(playlists) else range(len(playlists))
    for p in order:
        for t, fid in enumerate(playlists[p]["tracks"]):
            if fid not in library or "out" not in trim_of(p, t) and trim_of(p, t).get("in", 0) <= 0.05:
                continue
            snd = cached(str(LIB / fid))
            if snd is None:
                continue
            lo, hi, _tm = trim_range(p, t, snd.get_length())
            if lo > 0.05 or hi < snd.get_length() - 0.01:
                want.append((str(LIB / fid), round(lo, 3), round(hi, 3)))
    keep = set(want)
    with _cache_lock:
        for k in [k for k in _tcache if k not in keep]:
            del _tcache[k]
    for path, lo, hi in want:
        if _warm["again"] or cache_bytes() > 0.9 * float(CFG["cache_mb"]) * 1048576:
            return
        snd = cached(path)
        if snd is None or trimmed_cached(path, lo, hi) is not None:
            continue
        try:
            cut = await loop.run_in_executor(None, cut_sound, snd, lo, hi)
        except Exception as e:
            log_once("cut:" + path, f"could not prepare the trimmed copy of {Path(path).name}", e)
            continue
        if cached(path) is snd:
            trimmed_put(path, lo, hi, cut)


# ---------------------------------------------------------------- RAM indicator (web page only: not in snapshot() / command(), nothing goes to Companion)
# What "in RAM" means: a track is `in` when its whole decoded sound is in the cache. A trimmed cut (_tcache) is only ever kept while the whole sound
# is cached too (trimmed_put, and the LRU drops both together), so a cut alone never exists: `play` starts without a decode exactly when the whole sound
# is cached. `loading` = a decode is in flight (_loading); everything else is `out` (starts after a decode).
# Computed from existing structures with set lookups (one pass over the playlists), cached for 1 s, read-only (no LRU "touch").
_ram = {"t": None, "states": {}, "info": {}, "rev": 0, "sig": None}


def _ram_compute():
    in_set, loading, used = ram_snapshot()
    states, total, n_in, missing_out = {}, 0, 0, False
    for pl in playlists:
        for fid in pl["tracks"]:
            if fid in states or fid not in library:
                continue
            path = str(LIB / fid)
            st = "in" if path in in_set else "loading" if path in loading else "out"
            states[fid] = st
            total += 1
            n_in += st == "in"
            missing_out = missing_out or st != "in"
    budget = int(float(CFG["cache_mb"]) * 1048576)
    busy = bool(loading) or bool(_warm["task"] and not _warm["task"].done())
    sig = (n_in, tuple(sorted(f for f, v in states.items() if v != "out")), busy)
    if sig != _ram["sig"]:
        _ram["sig"] = sig
        _ram["rev"] += 1
    _ram["states"] = states
    _ram["info"] = {"used_mb": round(used / 1048576, 1), "budget_mb": round(budget / 1048576, 1), "tracks_total": total, "tracks_in_ram": n_in,
                    "loading": busy, "full": bool(budget and used >= 0.95 * budget and missing_out), "rev": _ram["rev"]}
    _ram["t"] = clock.monotonic()


def _ram_fresh():
    if _ram["t"] is None or clock.monotonic() - _ram["t"] >= 1.0:
        _ram_compute()


def ram_info():
    """The `ram` block of /api/state."""
    _ram_fresh()
    return dict(_ram["info"])


def ram_states():
    """file id -> "in" | "loading" | "out" for every library file used by a playlist (/api/playlists: `ram`, `ram_in`, `ram_total`)."""
    _ram_fresh()
    return _ram["states"]
