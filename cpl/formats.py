"""Format checks.

Moved verbatim from cpl/legacy.py in split step P5/P6 (docs/split-plan.md 2.1); nothing here imports cpl.legacy.
"""
import asyncio, json, os

from cpl.config import BASE, LIB
from cpl.ffmpeg import ff_check, ff_probe, ff_run
from cpl.state import library
from cpl.util import atomic_write


FMTFILE = BASE / "formats.json"   # format check results, remembered between runs: {id: {s, m, lv, msg, tip, deep}}
FMT = {}
FMT_STATE = {"running": False, "deep": False, "done": 0, "total": 0, "task": None}


def _fmt_load():
    try:
        d = json.loads(FMTFILE.read_text())
        if isinstance(d, dict):
            FMT.update({k: v for k, v in d.items() if isinstance(v, dict) and "s" in v and "m" in v})
    except FileNotFoundError:
        pass
    except Exception as e:
        print("could not read formats.json (files will be checked again):", e)


def _fmt_save():
    try:
        atomic_write(FMTFILE, json.dumps({k: v for k, v in list(FMT.items()) if k in library}))
    except Exception as e:
        print("could not save formats.json:", e)


def fmt_judge(info):
    """ffprobe facts -> (level, message, tooltip). Levels: ok, info, warn, error."""
    if info.get("error"):
        return "error", "Cannot be read: " + info["error"], ""
    kind = {"mp3": "MP3", "vorbis": "OGG", "opus": "Opus", "flac": "FLAC", "aac": "AAC", "alac": "ALAC"}.get(info["codec"], "WAV" if info["codec"].startswith("pcm") else info["codec"].upper())
    chn = {1: "mono", 2: "stereo"}.get(info["ch"], f"{info['ch']} channels")
    parts = [kind, f"{info['rate'] / 1000:g} kHz", chn]
    if info["bits"]:
        parts.append(f"{info['bits']}-bit")
    if info["br"] and kind in ("MP3", "OGG", "Opus", "AAC"):
        parts.append(f"{round(info['br'] / 1000)} kbps")
    tip = " · ".join(parts)
    if info["dur"] <= 0.05:
        return "error", "Contains no audio (zero length)", tip
    if info["ch"] > 2:
        return "warn", f"{info['ch']} channels: only stereo plays correctly, the rest is mixed down", tip
    if info["dur"] < 0.5:
        return "warn", f"Very short ({info['dur']:.2f} s)", tip
    if info["rate"] and info["rate"] != 48000:
        return "info", f"{info['rate'] / 1000:g} kHz: resampled to 48 kHz when it loads", tip
    if info["ch"] == 1:
        return "info", "Mono: played on both sides", tip
    return "ok", "", tip


async def _fmt_run(deep):
    st = FMT_STATE
    st.update(running=True, deep=deep, done=0, total=len(library))
    try:
        n = 0
        for fid in list(library):
            try:
                fs = os.stat(LIB / fid)
            except OSError:
                continue
            cur = FMT.get(fid)
            fresh = cur and cur["s"] == fs.st_size and cur["m"] == fs.st_mtime_ns
            if fresh and (not deep or cur.get("deep")):
                st["done"] += 1
                continue
            info = await ff_probe(LIB / fid)
            if info is None:                                  # no ffprobe: nothing more to do
                break
            lv, msg, tip = fmt_judge(info)
            if deep and lv != "error":
                try:
                    _rc, _o, err = await ff_run(["-i", str(LIB / fid), "-vn", "-f", "null", "-"])
                    bad = [x for x in err.splitlines() if x.strip()]
                    if _rc != 0 or bad:
                        lv, msg = "warn", "Decode problems: " + (bad[0] if bad else "failed")[:140]
                except RuntimeError:
                    pass
            FMT[fid] = {"s": fs.st_size, "m": fs.st_mtime_ns, "lv": lv, "msg": msg, "tip": tip, "deep": bool(deep)}
            st["done"] += 1
            n += 1
            if n % 20 == 0:
                _fmt_save()
            await asyncio.sleep(0.2)                          # gaps, so playback is never starved
        _fmt_save()
    except Exception as e:
        print("format check stopped:", e)
    finally:
        st["running"] = False


def fmt_kick(deep=False):
    """Start the background check when there is something new to look at (or when a deep scan is asked for)."""
    if FMT_STATE["running"] or not ff_check():
        return
    pending = deep or any((FMT.get(f) or {}).get("s") != sz for f, sz in library.items())
    if pending:
        FMT_STATE.update(running=True, deep=deep, done=0, total=len(library))
        FMT_STATE["task"] = asyncio.get_running_loop().create_task(_fmt_run(deep))
