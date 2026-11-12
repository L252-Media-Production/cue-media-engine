"""Level match: measurement queue, gain, per-playlist settings.

Moved verbatim from cpl/legacy.py in split step P5/P6 (docs/split-plan.md 2.1); nothing here imports cpl.legacy.
"""
import asyncio, json, math, os

from cpl import state as S
from cpl.cache import decode_in_child
from cpl.config import BASE, LIB
from cpl.dsp import lufs_from_pcm, np
from cpl.ffmpeg import ff_check, ff_loudness
from cpl.infostore import info_store
from cpl.persist import save
from cpl.playlists import valid
from cpl.state import ISSUES, bump, decks, library, playlists
from cpl.util import atomic_write


# ---------------------------------------------------------------- level matching (per playlist, only ever turns down)
LOUDFILE = BASE / "loudness.json"      # {id: [size, mtime_ns, LUFS or null]} measured once per file version
LOUD = {}
_loud = {"task": None, "again": False}
NORM_DEFAULT = {"mode": "off", "ref": None, "lufs": -18.0}      # mode: off | track | lufs


def _loud_load():
    try:
        for k, v in json.loads(LOUDFILE.read_text()).items():
            if isinstance(v, list) and len(v) == 3:
                LOUD[k] = (int(v[0]), int(v[1]), None if v[2] is None else float(v[2]))
    except FileNotFoundError:
        pass
    except Exception as e:
        print("could not read loudness.json (it will be measured again):", e)


def _loud_save():
    try:
        atomic_write(LOUDFILE, json.dumps({k: list(v) for k, v in LOUD.items() if k in library}))
    except Exception as e:
        print("could not save loudness.json:", e)


def norm_cfg(p):
    c = dict(NORM_DEFAULT)
    if isinstance(p, int) and 0 <= p < len(playlists):
        c.update({k: v for k, v in (playlists[p].get("norm") or {}).items() if k in c})
    return c


def _lufs_of(fid):
    v = LOUD.get(fid)
    return v[2] if v else None


def norm_gain_db(p, t):
    """dB to apply to track t of playlist p (0 or negative), or None when level matching does not apply to it."""
    c = norm_cfg(p)
    if c["mode"] == "off" or not valid(p, t):
        return None
    mine = _lufs_of(playlists[p]["tracks"][t])
    if mine is None:
        return None
    if c["mode"] == "track":
        target = _lufs_of(c["ref"]) if c["ref"] in playlists[p]["tracks"] else None
    else:
        target = float(c["lufs"])
    if target is None:
        return None
    return min(0.0, target - mine)                      # never boost


def norm_gain(p, t):
    db = norm_gain_db(p, t)
    return 1.0 if not db else 10 ** (db / 20.0)


def apply_gain_live():
    for d in decks:
        d.gain = norm_gain(*d.pt) if d.pt else 1.0
        d.set_vol(d.vol)


def _scipy_ok():
    try:
        import scipy.signal  # noqa: F401
        return True
    except Exception:
        return False


def loud_pending():
    need = []
    seen = set()
    for pi, pl in enumerate(playlists):
        c = norm_cfg(pi)
        if c["mode"] == "off":
            continue
        for fid in pl["tracks"]:
            if fid in library and fid not in seen:
                seen.add(fid)
                try:
                    st = os.stat(LIB / fid)
                except OSError:
                    continue
                cur = LOUD.get(fid)
                if not cur or cur[0] != st.st_size or cur[1] != st.st_mtime_ns:
                    need.append((fid, st.st_size, st.st_mtime_ns))
    return need


def request_loudness():
    """Measure the files that level-matched playlists need (one at a time, in a low-priority helper process)."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    if _loud["task"] and not _loud["task"].done():
        _loud["again"] = True
        return
    if not loud_pending():
        ISSUES.pop("loudness", None)
        return
    if not ff_check() and (np is None or not _scipy_ok()):
        ISSUES["loudness"] = "level matching needs ffmpeg or scipy (pip install scipy)"
        return
    ISSUES.pop("loudness", None)
    _loud["task"] = loop.create_task(_loud_worker())


S.on_save.append(request_loudness)    # save() runs it after bump() (split step P4, F3)


async def _loud_worker():
    loop = asyncio.get_running_loop()
    while True:
        todo = loud_pending()
        if not todo:
            break
        fid, size, mt = todo[0]
        try:
            v, done = None, False
            if ff_check():                      # ffmpeg first: any codec, no decoded copy in RAM
                try:
                    m = await ff_loudness(str(LIB / fid))
                    v, done = m["lufs"], True
                    info_store(fid, size, mt, "loud", {**m, "src": "ffmpeg"})      # the same pass also answers the File information popover
                except Exception as e:
                    print("loudness: ffmpeg failed for", fid, "-", e, "(using the built-in measurement)")
            if not done:
                raw = await decode_in_child(str(LIB / fid))
                v = await loop.run_in_executor(None, lufs_from_pcm, raw)
                del raw
        except Exception as e:
            print("loudness:", fid, e)
            v = None
        LOUD[fid] = (size, mt, v)
        _loud_save()
        apply_gain_live()
        bump()
        S.notify()
        await asyncio.sleep(0.3)


def set_norm(p, mode=None, ref=None, lufs=None):
    if not (isinstance(p, int) and 0 <= p < len(playlists)):
        return False
    c = norm_cfg(p)
    if mode is not None:
        mode = {"track": "track", "match": "track", "lufs": "lufs", "fixed": "lufs", "off": "off", "none": "off"}.get(str(mode).lower())
        if mode is None:
            return False
        c["mode"] = mode
    if ref is not None:
        if isinstance(ref, int) and 0 <= ref < len(playlists[p]["tracks"]):
            ref = playlists[p]["tracks"][ref]
        if ref not in playlists[p]["tracks"]:
            return False
        c["ref"] = ref
    if lufs is not None:
        try:
            if not math.isfinite(float(lufs)):
                return False
            c["lufs"] = max(-60.0, min(0.0, round(float(lufs), 1)))
        except (TypeError, ValueError):
            return False
    if c["mode"] == "track" and c["ref"] not in playlists[p]["tracks"]:
        c["ref"] = playlists[p]["tracks"][0] if playlists[p]["tracks"] else None
    playlists[p]["norm"] = c
    save()
    request_loudness()
    apply_gain_live()
    S.notify()
    return True
