"""The playlist model: modes, end actions, crossfade and trim per track, track lookup, add / remove / move, next in order.

Moved verbatim from cpl/legacy.py in split step P5/P6 (docs/split-plan.md 2.1); nothing here imports cpl.legacy.
"""
import random
from pathlib import Path

from cpl.config import CFG, LIB, PLAY_MODES
from cpl.persist import save
from cpl.state import DURS, decks, focus, library, playlists


def pl_mode(p):
    """What happens when a track of playlist p ends by itself."""
    if isinstance(p, int) and 0 <= p < len(playlists) and playlists[p].get("mode") in PLAY_MODES:
        return playlists[p]["mode"]
    return CFG["play_mode"]


END_ACTIONS = ("default", "once", "loop", "stop")   # per track: follow the playlist | play twice | repeat forever | stop at its natural end


def end_of(p, t):
    """What track t of playlist p does when it ends: "default" (follow the playlist behavior), "once" (loop once: two passes
    in all), "loop" (repeat until stopped) or "stop" (playback stops, whatever the playlist behavior is)."""
    if not (isinstance(p, int) and isinstance(t, int) and 0 <= p < len(playlists) and 0 <= t < len(playlists[p]["tracks"])):
        return "default"
    v = playlists[p].get("end_actions", {}).get(playlists[p]["tracks"][t])
    return v if v in ("once", "loop", "stop") else "default"


def is_loop(p, t):
    """True when track t of playlist p is switched to loop forever (it repeats until stopped or another track is played)."""
    return end_of(p, t) == "loop"


def set_end(p, t, val=None):
    """Set the end action of one track (val None = next in the cycle default > once > loop > stop). The setting belongs to the
    file within that playlist."""
    if not (0 <= p < len(playlists) and 0 <= t < len(playlists[p]["tracks"])):
        return False
    fid = playlists[p]["tracks"][t]
    if val is None or val == "next":
        val = END_ACTIONS[(END_ACTIONS.index(end_of(p, t)) + 1) % len(END_ACTIONS)]
    if val not in END_ACTIONS:
        return False
    ea = dict(playlists[p].get("end_actions", {}))
    if val == "default":
        ea.pop(fid, None)
    else:
        ea[fid] = val
    if ea:
        playlists[p]["end_actions"] = ea
    else:
        playlists[p].pop("end_actions", None)
    save()
    return True


def set_loop(p, t, val=None):
    """Switch looping forever of one track on or off (val None = toggle). Off only clears a loop: a track set to once or stop stays so."""
    if not (0 <= p < len(playlists) and 0 <= t < len(playlists[p]["tracks"])):
        return False
    on = (not is_loop(p, t)) if val is None else bool(val)
    if on:
        return set_end(p, t, "loop")
    return set_end(p, t, "default") if is_loop(p, t) else True


def xfade_of(p, t):
    """The crossfade time (ms) set for track t of playlist p, used when this track is crossfaded into; None = the master time (crossfade_ms)."""
    if not (isinstance(p, int) and isinstance(t, int) and 0 <= p < len(playlists) and 0 <= t < len(playlists[p]["tracks"])):
        return None
    v = playlists[p].get("xfades", {}).get(playlists[p]["tracks"][t])
    return int(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and 0 <= v <= 30000 else None


def xfade_ms(p, t, ms=None):
    """Crossfade time for a crossfade into track t: an explicit ms (?ms=) first, then the track's own time, then the master time."""
    if ms is not None:
        return ms
    own = xfade_of(p, t)
    return CFG["crossfade_ms"] if own is None else own


def set_xfade(p, t, seconds):
    """Set (seconds 0-30) or clear (None) the crossfade time of one track. It belongs to the file within that playlist."""
    if not (0 <= p < len(playlists) and 0 <= t < len(playlists[p]["tracks"])):
        return False
    fid = playlists[p]["tracks"][t]
    xf = dict(playlists[p].get("xfades", {}))
    if seconds is None:
        xf.pop(fid, None)
    else:
        try:
            ms = int(round(float(seconds) * 1000))
        except (TypeError, ValueError, OverflowError):          # OverflowError: inf, -inf, 1e999
            return False
        if not 0 <= ms <= 30000:
            return False
        xf[fid] = ms
    if xf:
        playlists[p]["xfades"] = xf
    else:
        playlists[p].pop("xfades", None)
    save()
    return True


def _file_len(fid):
    """Length of a library file in seconds (0 when not known yet)."""
    v = DURS.get(fid)
    return float(v[2]) if v and v[2] > 0 else 0.0


def trim_of(p, t):
    """The In/Out trim of track t in playlist p: {"in": s, "out": s, "end": "fade"|"cut", "fade_ms": ms, "start": "fade", "fade_in_ms": ms} (only what is set), or {}.
    start/fade_in_ms is the fade-in at A (2.7.4): start is stored only as "fade" (Cut is the default); fade_in_ms is kept while the edge is Cut."""
    if not (isinstance(p, int) and isinstance(t, int) and 0 <= p < len(playlists) and 0 <= t < len(playlists[p]["tracks"])):
        return {}
    return playlists[p].get("trims", {}).get(playlists[p]["tracks"][t], {})


FADE_MIN_MS, FADE_MAX_MS = 100, 10000


def fade_default_ms():
    """The default fade-out length at B (config key trim_fade_ms, kept for compatibility), ms."""
    try:
        return max(0, int(CFG["trim_fade_ms"]))
    except (TypeError, ValueError):
        return 1500


def fade_ms_of(p, t):
    """The fade-out length that applies at B for track t of playlist p: its own `fade_ms`, else the default."""
    own = trim_of(p, t).get("fade_ms")
    return int(own) if own else fade_default_ms()


def fade_in_default_ms():
    """The default fade-in length at A (config key trim_fadein_ms; 0 = none), ms."""
    try:
        return max(0, min(FADE_MAX_MS, int(CFG["trim_fadein_ms"])))
    except (TypeError, ValueError):
        return 0


def fade_in_ms_of(p, t):
    """The fade-in length for track t of playlist p: its own `fade_in_ms`, else the default (0 = none). Whether it is applied is the start edge's job (fade_in_start_ms)."""
    own = trim_of(p, t).get("fade_in_ms")
    return int(own) if own else fade_in_default_ms()


def fade_in_start_ms(p, t):
    """The fade-in that is really applied when the track starts at A: 0 while the start edge is Cut (the default), else the effective length."""
    return fade_in_ms_of(p, t) if trim_of(p, t).get("start") == "fade" else 0


def trim_range(p, t, full):
    """(lo, hi, trim) in file seconds for a file `full` seconds long: where the track starts and where it ends."""
    tm = trim_of(p, t)
    lo = max(0.0, min(float(tm.get("in", 0.0)), max(0.0, full - 0.5)))
    hi = float(tm.get("out", full)) if tm.get("out") is not None else full
    hi = min(full, hi)
    if hi < lo + 0.5:
        hi = full
    return lo, hi, tm


def set_trim(p, t, fields):
    """Set or clear the In/Out of one track within one playlist. fields: {"in": s|None, "out": s|None, "end": "fade"|"cut"}.
    None removes a point. The trim belongs to the file within that playlist, like the end action."""
    if not (0 <= p < len(playlists) and 0 <= t < len(playlists[p]["tracks"])):
        return False
    fid = playlists[p]["tracks"][t]
    tm = dict(playlists[p].get("trims", {}).get(fid, {}))
    full = _file_len(fid)
    try:
        for k in ("in", "out"):
            if k in fields:
                v = fields[k]
                if v is None or v == "":
                    tm.pop(k, None)
                else:
                    v = round(max(0.0, float(v)), 2)       # nan counts as 0 and inf as "the end" (clipped to the file below), as before
                    if v == float("inf") and not full:     # ... but the end is unknown: never store infinity
                        return False
                    if full and v > full:
                        v = round(full, 2)
                    tm[k] = v
        if "fade_ms" in fields:
            f = fields["fade_ms"]
            if f is None or f == "":
                tm.pop("fade_ms", None)
            else:
                f = int(round(float(f)))              # OverflowError for inf is caught below
                if not (FADE_MIN_MS <= f <= FADE_MAX_MS):
                    return False
                tm["fade_ms"] = f
        if "fade_in_ms" in fields:
            f = fields["fade_in_ms"]
            if f is None or f == "":
                tm.pop("fade_in_ms", None)
            else:
                f = int(round(float(f)))
                if not (FADE_MIN_MS <= f <= FADE_MAX_MS):
                    return False
                tm["fade_in_ms"] = f
        if "start" in fields:
            e = fields["start"]
            if e == "fade":
                tm["start"] = "fade"
            elif e in ("cut", None):
                tm.pop("start", None)                  # Cut is the default: only a fade-in is stored
            else:
                return False
        if "end" in fields:
            e = fields["end"]
            if e in ("fade", "cut"):
                tm["end"] = e
            elif e is None:
                tm.pop("end", None)
            else:
                return False
    except (TypeError, ValueError, OverflowError):
        return False
    if tm.get("in", 0) <= 0.01:
        tm.pop("in", None)
    if full and tm.get("out", full) >= full - 0.01:
        tm.pop("out", None)
    if "in" in tm and "out" in tm and tm["out"] < tm["in"] + 0.5:
        return False                                  # the region must be at least half a second
    if tm.get("end") == "fade":
        tm.pop("end")                                 # fade is the default: only a cut is stored
    if "out" not in tm:
        tm.pop("fade_ms", None)                       # the fade belongs to B: no B, no fade length
    if "fade_ms" in tm:                               # the fade can never be longer than the part that plays (B - A)
        tm["fade_ms"] = max(FADE_MIN_MS, min(tm["fade_ms"], int((tm["out"] - tm.get("in", 0.0)) * 1000)))
    if "fade_in_ms" in tm:                            # the fade-in can never be longer than the part that plays (B - A, or the rest of the file when there is no B)
        top = tm.get("out", full) if (tm.get("out") is not None or full) else None
        if top:
            tm["fade_in_ms"] = max(FADE_MIN_MS, min(tm["fade_in_ms"], int((top - tm.get("in", 0.0)) * 1000)))
    if not any(k in tm for k in ("in", "out", "start", "fade_in_ms")):
        tm = {}
    trims = dict(playlists[p].get("trims", {}))
    if tm:
        trims[fid] = tm
    else:
        trims.pop(fid, None)
    if trims:
        playlists[p]["trims"] = trims
    else:
        playlists[p].pop("trims", None)
    save()
    return True


def valid(p, t):
    return 0 <= p < len(playlists) and 0 <= t < len(playlists[p]["tracks"])


def track(p, t):
    if not valid(p, t):
        return None
    fid = playlists[p]["tracks"][t]
    return {"id": fid, "name": Path(fid).stem, "path": str(LIB / fid)}


# ---------------------------------------------------------------- playlist editing
def clamp_focus():
    if not playlists:
        focus[:] = [0, 0]
        return
    focus[0] = max(0, min(focus[0], len(playlists) - 1))
    n = len(playlists[focus[0]]["tracks"])
    focus[1] = max(0, min(focus[1], n - 1)) if n else 0


def remap_all(fn):
    """Apply fn(pt) -> pt | None to the focus cursor and every playing deck, so they stay on the same
    tracks when a list changes. None means that track left the list (its deck keeps playing)."""
    nf = fn(list(focus))
    for d in decks:
        if d.pt:
            d.pt = fn(d.pt)
    if nf:
        focus[:] = nf


def add_to_playlist(p, ids, index=None):
    if not 0 <= p < len(playlists):
        return "invalid"
    ids = [i for i in ids if isinstance(i, str) and i in library]
    if not ids:
        return "invalid"
    tr = playlists[p]["tracks"]
    idx = len(tr) if index is None else max(0, min(int(index), len(tr)))

    def fn(pt):
        return [p, pt[1] + len(ids)] if pt[0] == p and pt[1] >= idx else pt

    remap_all(fn)
    tr[idx:idx] = ids
    save()
    return "ok"


def remove_from_playlist(p, t, save_now=True):
    """Remove a track from ONE playlist. The file stays in the library."""
    if not valid(p, t):
        return "invalid"

    def fn(pt):
        if pt == [p, t]:
            return None
        return [p, pt[1] - 1] if pt[0] == p and pt[1] > t else pt

    remap_all(fn)
    playlists[p]["tracks"].pop(t)
    clamp_focus()
    if save_now:
        save()
    return "ok"


def move_track(fp, ft, tp, ti):
    """Move a playlist entry to index ti (index in the final list) of playlist tp."""
    if not valid(fp, ft) or not 0 <= tp < len(playlists):
        return "invalid"
    ti = max(0, min(ti, len(playlists[tp]["tracks"]) - (1 if fp == tp else 0)))
    if fp == tp and ti == ft:
        return "ok"

    def remap(pt):
        if pt == [fp, ft]:
            return [tp, ti]
        p, t = pt
        if p == fp and t > ft:
            t -= 1
        if p == tp and t >= ti:
            t += 1
        return [p, t]

    new_focus = remap(list(focus))
    for d in decks:
        if d.pt:
            d.pt = remap(d.pt)
    fid = playlists[fp]["tracks"].pop(ft)
    playlists[tp]["tracks"].insert(ti, fid)
    if fp != tp and fid in playlists[fp].get("trims", {}) and fid not in playlists[tp].get("trims", {}) \
            and fid not in playlists[fp]["tracks"]:
        playlists[tp].setdefault("trims", {})[fid] = playlists[fp]["trims"].pop(fid)
        if not playlists[fp]["trims"]:
            playlists[fp].pop("trims")
    if fp != tp and fid in playlists[fp].get("end_actions", {}) and fid not in playlists[tp].get("end_actions", {}) \
            and fid not in playlists[fp]["tracks"]:          # the end action goes with the track, like its trim
        playlists[tp].setdefault("end_actions", {})[fid] = playlists[fp]["end_actions"].pop(fid)
        if not playlists[fp]["end_actions"]:
            playlists[fp].pop("end_actions")
    if fp != tp and fid in playlists[fp].get("xfades", {}) and fid not in playlists[tp].get("xfades", {}) \
            and fid not in playlists[fp]["tracks"]:          # the crossfade time goes with the track
        playlists[tp].setdefault("xfades", {})[fid] = playlists[fp]["xfades"].pop(fid)
        if not playlists[fp]["xfades"]:
            playlists[fp].pop("xfades")
    if fp != tp and fid in playlists[fp].get("triggers", {}) and fid not in playlists[tp].get("triggers", {}) \
            and fid not in playlists[fp]["tracks"]:          # the trigger points go with the track too
        playlists[tp].setdefault("triggers", {})[fid] = playlists[fp]["triggers"].pop(fid)
        if not playlists[fp]["triggers"]:
            playlists[fp].pop("triggers")
    focus[:] = new_focus
    save()
    return "ok"


def move_focus(delta):
    p, t = focus
    if not playlists or p >= len(playlists) or not playlists[p]["tracks"]:
        return
    focus[1] = (t + delta) % len(playlists[p]["tracks"])


def move_playlist(delta):
    if not playlists:
        return
    focus[0] = (focus[0] + delta) % len(playlists)
    focus[1] = 0


_bag = {}                              # shuffle: library ids not yet played, per playlist


def set_play_mode(p, mode):
    """Set the end-of-track behaviour of playlist p."""
    if not (0 <= p < len(playlists)):
        return False
    if mode == "next":
        mode = PLAY_MODES[(PLAY_MODES.index(pl_mode(p)) + 1) % len(PLAY_MODES)]
    if mode in ("track", "loop", "repeat", "loop_track"):    # old name: now toggles looping of the focused track of this playlist
        return focus[0] == p and set_loop(p, focus[1])
    mode = {"off": "stop", "once": "stop", "playlist": "loop_playlist", "loopall": "loop_playlist", "all": "loop_playlist",
            "random": "shuffle", "continue": "next_playlist", "chain": "next_playlist", "nextplaylist": "next_playlist",
            "next_list": "next_playlist"}.get(mode, mode)
    if mode not in PLAY_MODES:
        return False
    playlists[p]["mode"] = mode
    _bag.pop(p, None)
    save()
    return True


def shuffle_left(p):
    """Shuffle: library ids of playlist p still to come in the current round (read-only; the page uses it for its progress display)."""
    ids = playlists[p]["tracks"] if 0 <= p < len(playlists) else []
    return [x for x in _bag.get(p, []) if x in ids]


def dur_eff(p, t):
    """Seconds that one pass of track t of playlist p plays: its A-to-B window (the whole file when there is no trim); None while the file's length is unknown."""
    d = DURS.get(playlists[p]["tracks"][t])
    if not d or not d[2]:
        return None
    lo, hi, _tm = trim_range(p, t, float(d[2]))
    return round(hi - lo, 2)


def next_in_order(p, t):
    """Indices to try (best first) for what follows track t of playlist p, or [] when nothing should follow."""
    ids = playlists[p]["tracks"] if 0 <= p < len(playlists) else []
    n, mode = len(ids), pl_mode(p)
    if n and is_loop(p, t):
        return [t]
    if not n or mode == "stop":
        return []
    if mode == "loop_playlist":
        return [(t + 1 + k) % n for k in range(n)]
    cur = ids[t] if t < n else None                       # shuffle: every track once before any repeats
    bag = [x for x in _bag.get(p, []) if x in ids and x != cur]
    if not bag:
        bag = [x for x in ids if x != cur] or list(ids)
        random.shuffle(bag)
    pick = bag.pop()
    _bag[p] = bag
    first = ids.index(pick)
    return [first] + [i for i in range(n) if i != first]
