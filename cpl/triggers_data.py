"""Trigger points, data side.

Moved verbatim from cpl/legacy.py in split step P5/P6 (docs/split-plan.md 2.1); nothing here imports cpl.legacy.
"""
import os
from pathlib import Path

from cpl import state as S
from cpl.config import LIB
from cpl.persist import save
from cpl.playlists import _file_len, trim_range, valid
from cpl.state import decks, library, playlists


# ---------------------------------------------------------------- trigger points
# A playlist entry can carry trigger points: when the live track reaches `at` (seconds of the file), the player plays the
# library file `file` on top of it (the same Play on Top as the button, with the same ducking). Stored like the trim, per
# playlist and keyed by file id: playlists[p]["triggers"] = {file_id: [{id, at, file, once, enabled}, ...]} (sorted by at).
TRIG_MAX = 16
TRIG = {"seq": 0, "notice": None}       # notice: the latest thing that happened {seq, kind: fired|skipped|failed, text, t}


def _truthy(v):
    return v.strip().lower() in ("1", "true", "on", "yes") if isinstance(v, str) else bool(v)


def triggers_of(p, t):
    """The trigger points of track t in playlist p (a list of dicts sorted by time), or []."""
    if not (isinstance(p, int) and isinstance(t, int) and 0 <= p < len(playlists) and 0 <= t < len(playlists[p]["tracks"])):
        return []
    return playlists[p].get("triggers", {}).get(playlists[p]["tracks"][t], [])


def trigger_json(p, t):
    """Triggers of one track for the API, with `missing` (the target left the library) and `outside` (not inside the trimmed region)."""
    if not (isinstance(p, int) and isinstance(t, int) and 0 <= p < len(playlists) and 0 <= t < len(playlists[p]["tracks"])):
        return []
    full = _file_len(playlists[p]["tracks"][t])
    lo, hi, _tm = trim_range(p, t, full) if full else (0.0, None, {})
    return [{**tg, "name": Path(tg["file"]).stem, "missing": not trigger_target_ok(tg["file"]),
             "outside": tg["at"] < lo - 1e-6 or (hi is not None and tg["at"] >= hi - 1e-6)} for tg in triggers_of(p, t)]


def trigger_target_ok(fid):
    return isinstance(fid, str) and fid in library and (LIB / fid).exists()


def _trig_clean(raw, base=None):
    """(trigger, error) from user input merged over `base`."""
    tg = dict(base or {})
    try:
        if "at" in raw:
            at = float(raw["at"])
            if not 0 <= at <= 86400:
                return None, "the time must be between 0 and 86400 seconds"
            tg["at"] = round(at, 3)
        if "file" in raw and raw["file"] != tg.get("file"):
            f = str(raw["file"] or "").strip("/")
            if not f or ".." in f.split("/") or f not in library:
                return None, "the track to play on top is not in the library"
            tg["file"] = f
        for k in ("once", "enabled"):
            if k in raw:
                tg[k] = _truthy(raw[k])
    except (TypeError, ValueError):
        return None, "not a number"
    if "at" not in tg or "file" not in tg:
        return None, "a trigger needs a time and a track"
    tg.setdefault("once", False)
    tg.setdefault("enabled", True)
    tg["id"] = str(tg.get("id") or os.urandom(4).hex())
    return {k: tg[k] for k in ("id", "at", "file", "once", "enabled")}, None


def set_triggers(p, t, action, data):
    """Change the trigger points of track t in playlist p. action: add | update | delete | set (replace the whole list with
    data["triggers"]). Returns (list, None) or (None, error text)."""
    if not (isinstance(p, int) and isinstance(t, int) and 0 <= p < len(playlists) and 0 <= t < len(playlists[p]["tracks"])):
        return None, "no such track"
    fid = playlists[p]["tracks"][t]
    cur = [dict(x) for x in triggers_of(p, t)]
    full = _file_len(fid)
    if action == "add":
        tg, err = _trig_clean(data)
        if err:
            return None, err
        cur.append(tg)
    elif action in ("update", "delete"):
        i = next((k for k, x in enumerate(cur) if x["id"] == str(data.get("id"))), None)
        if i is None:
            return None, "no such trigger"
        if action == "delete":
            cur.pop(i)
        else:
            tg, err = _trig_clean(data, cur[i])
            if err:
                return None, err
            cur[i] = tg
    elif action == "set":
        lst = data.get("triggers")
        if not isinstance(lst, list):
            return None, "triggers must be a list"
        old = {x["id"]: x for x in cur}
        cur = []
        for raw in lst:
            if not isinstance(raw, dict):
                return None, "each trigger must be an object"
            tg, err = _trig_clean(raw, old.get(str(raw.get("id"))))
            if err:
                return None, err
            cur.append(tg)
    else:
        return None, "unknown action"
    if len(cur) > TRIG_MAX:
        return None, f"at most {TRIG_MAX} triggers per track"
    if full and any(x["at"] > full + 0.01 for x in cur):
        return None, "a trigger is after the end of the file"
    cur.sort(key=lambda x: x["at"])
    trs = dict(playlists[p].get("triggers", {}))
    if cur:
        trs[fid] = cur
    else:
        trs.pop(fid, None)
    if trs:
        playlists[p]["triggers"] = trs
    else:
        playlists[p].pop("triggers", None)
    save()
    return cur, None


def trig_deck():
    """The deck whose trigger points are being watched: the live one, or the track under a Play on Top."""
    d = S.live_deck
    if d is not None and d.top:
        d = d.under if d.under in decks else None
    return d if d is not None and d.pt and valid(*d.pt) else None


def trigger_targets():
    """Library ids that the watched track's trigger points will play (so the warm-up decodes them first)."""
    d = trig_deck()
    if d is None:
        return []
    out = []
    for tg in triggers_of(*d.pt):
        if tg.get("enabled", True) and tg["file"] in library and tg["file"] not in out:
            out.append(tg["file"])
    return out
