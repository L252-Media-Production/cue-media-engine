"""The 'i' popover: file facts measured on demand.

Moved verbatim from cpl/legacy.py in split step P5/P6 (docs/split-plan.md 2.1); nothing here imports cpl.legacy.
"""
import asyncio, os
from pathlib import Path

from cpl.cache import decode_in_child
from cpl.config import LIB
from cpl.dsp import lufs_from_pcm, np
from cpl.ffmpeg import ff_check, ff_loudness, ff_probe, ff_volume
from cpl.formats import FMT
from cpl.infostore import INFO, info_entry, info_store
from cpl.loudness import LOUD, _loud_save, _scipy_ok, apply_gain_live
from cpl.state import DURS, bump
from cpl.util import log_once, spawn


_info_jobs = {}


def _wav_basic(path):
    """What the WAV header says, for when ffprobe is not installed. None for anything else."""
    if not path.lower().endswith((".wav", ".wave")):
        return None
    try:
        import wave
        with wave.open(path, "rb") as w:
            rate, ch, bits, n = w.getframerate(), w.getnchannels(), w.getsampwidth() * 8, w.getnframes()
        return {"container": "wav", "codec": "pcm", "rate": rate, "ch": ch, "bits": bits, "dur": n / float(rate) if rate else 0.0, "br": rate * ch * bits}
    except Exception:
        return None


async def _info_job(fid):
    """Measure what the popover still lacks, one step at a time through the shared low-priority ffmpeg runner."""
    loop = asyncio.get_running_loop()
    path = str(LIB / fid)
    try:
        st = os.stat(path)
        size, mt = st.st_size, st.st_mtime_ns
        e = info_entry(fid, st)
        ff = await loop.run_in_executor(None, ff_check)
        if ff and "probe" not in e:
            try:
                pr = await ff_probe(path)
                info_store(fid, size, mt, "probe", pr if pr is not None else {"error": "ffprobe was not found (it comes with ffmpeg)", "noprobe": True})
            except Exception as ex:
                info_store(fid, size, mt, "probe", {"error": str(ex)[:160]})
        pr = INFO.get(fid, {}).get("probe") or {}
        unreadable = bool(pr.get("error")) and not pr.get("noprobe")
        if unreadable:
            return
        if "loud" not in INFO.get(fid, {}):
            m = None
            if ff:
                try:
                    m = {**(await ff_loudness(path)), "src": "ffmpeg"}
                except Exception as ex:
                    print("file info: ffmpeg loudness failed for", fid, "-", ex)
            if m is None and np is not None and await loop.run_in_executor(None, _scipy_ok):
                try:
                    raw = await decode_in_child(path)
                    m = {"lufs": await loop.run_in_executor(None, lufs_from_pcm, raw), "lra": None, "tp": None, "src": "builtin"}
                    del raw
                except Exception as ex:
                    print("file info: built-in loudness failed for", fid, "-", ex)
            if m is None:
                m = {"lufs": None, "lra": None, "tp": None, "src": "failed"}
            info_store(fid, size, mt, "loud", m)
            if m["src"] != "failed" and LOUD.get(fid, (0, 0))[:2] != (size, mt):          # level matching can use it too
                LOUD[fid] = (size, mt, m["lufs"])
                _loud_save()
                apply_gain_live()
                bump()
        if ff and "vol" not in INFO.get(fid, {}):
            try:
                info_store(fid, size, mt, "vol", await ff_volume(path))
            except Exception as ex:
                info_store(fid, size, mt, "vol", {"max": None, "rms": None, "error": str(ex)[:160]})
    except Exception as ex:
        log_once("info:" + fid, f"file information for {fid} could not be measured", ex)
    finally:
        _info_jobs.pop(fid, None)


def info_response(fid, st, ff, can_builtin):
    e = info_entry(fid, st)
    job = _info_jobs.get(fid)
    running = bool(job and not job.done())
    pr = e.get("probe")
    lo, vo = e.get("loud"), e.get("vol")
    unreadable = bool(pr and pr.get("error") and not pr.get("noprobe"))
    need = (("probe" not in e and ff) or ("loud" not in e and (ff or can_builtin)) or ("vol" not in e and ff)) and not unreadable
    if need and not running:
        _info_jobs[fid] = spawn(_info_job(fid))
        running = True
    basic = None if (pr and not pr.get("error")) else _wav_basic(str(LIB / fid))
    good = pr if (pr and not pr.get("error")) else (basic or {})
    d = DURS.get(fid)
    dur = good.get("dur") or (d[2] if d and d[0] == st.st_size and d[2] > 0 else None)

    def pending():                          # why a value is missing: still being measured, or it cannot be
        if unreadable:
            return "unavailable"
        return "measuring" if running else ("needs ffmpeg" if not ff else "unavailable")

    if pr and not pr.get("error"):
        probe_s = "ok"
    elif unreadable:
        probe_s = "failed"
    elif running and not pr:
        probe_s = "measuring"
    else:
        probe_s = "needs ffmpeg" if not ff or (pr and pr.get("noprobe")) else "unavailable"
    if lo:
        loud_s = "failed" if lo.get("src") == "failed" else "ok"
        peak_s = "failed" if lo.get("src") == "failed" else "ok" if lo.get("src") == "ffmpeg" else "needs ffmpeg"    # the built-in measurement has no peak or range
    else:
        loud_s = "measuring" if running and not unreadable else "unavailable" if unreadable else ("needs ffmpeg" if not ff and not can_builtin else "unavailable")
        peak_s = pending()
    vol_s = ("failed" if vo.get("error") else "ok") if vo else pending()
    r1 = lambda v: None if v is None else round(v, 1)
    chk = FMT.get(fid)
    return {
        "id": fid, "name": Path(fid).name, "folder": fid.rsplit("/", 1)[0] if "/" in fid else "", "size": st.st_size,
        "format": (good.get("container") or "").upper() or None, "format_long": good.get("format_long") or None,
        "codec": good.get("codec") or None, "codec_long": good.get("codec_long") or None,
        "dur": dur, "bitrate": round(good["br"] / 1000) if good.get("br") else None, "rate": good.get("rate") or None,
        "channels": good.get("ch") or None, "bits": good.get("bits") or None, "score": good.get("score"),
        "lufs": r1(lo.get("lufs")) if lo else None, "tp": r1(lo.get("tp")) if lo else None, "lra": r1(lo.get("lra")) if lo else None,
        "max": r1(vo.get("max")) if vo else None, "rms": r1(vo.get("rms")) if vo else None,
        "status": {"probe": probe_s, "loud": loud_s, "peak": peak_s, "vol": vol_s},
        "error": pr.get("error") if unreadable else None, "ffmpeg": ff,
        "check": {"lv": chk["lv"], "msg": chk["msg"]} if chk and chk.get("s") == st.st_size and chk.get("lv") in ("warn", "error") else None}
