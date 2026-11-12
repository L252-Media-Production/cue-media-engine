"""All ffmpeg / ffprobe use in one place: measurement, waveform, conversion, one job at a time at low priority.

Moved verbatim from cpl/legacy.py in split step P5/P6 (docs/split-plan.md 2.1); nothing here imports cpl.legacy.
"""
import asyncio, json, math, os, re, shutil
from pathlib import Path

from cpl import clock
from cpl.cache import _env, decode_in_child
from cpl.config import CFG, LIB
from cpl.dsp import METER_WIN, compute_env, np


def _num(txt):
    """A number from ffmpeg's text output, or None for -inf / nothing."""
    try:
        v = float(txt)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


async def ff_loudness(path):
    """One ffmpeg ebur128 pass: {"lufs": integrated loudness or None (silent / too short), "lra": loudness range (LU) or None,
    "tp": true peak (dBTP) or None}. Raises when ffmpeg fails, so the caller can use the built-in measurement instead."""
    for flt in ("ebur128=framelog=quiet:peak=true", "ebur128=framelog=quiet"):         # (an old ffmpeg has no true-peak option)
        rc, _o, err = await ff_run(["-v", "info", "-nostats", "-i", path, "-vn", "-af", flt, "-f", "null", "-"], timeout=3600)
        m = re.findall(r"I:\s+(-?[\d.]+|-inf)\s+LUFS", err)
        if rc == 0 and m:
            break
        if "peak" not in err.lower():
            break
    if rc != 0 or not m:
        raise RuntimeError((err.strip().splitlines() or ["no loudness result"])[-1][:160])
    lufs = _num(m[-1])
    lra = re.findall(r"LRA:\s+(-?[\d.]+|-inf)\s+LU", err)
    tp = re.findall(r"True peak:\s*\n\s*Peak:\s+(-?[\d.]+|-inf)\s+dBFS", err)
    return {"lufs": None if lufs is None or lufs <= -69.9 else lufs,
            "lra": _num(lra[-1]) if lra else None, "tp": _num(tp[-1]) if tp else None}


async def ff_lufs(path):
    """Integrated loudness (LUFS) measured by ffmpeg. None for silent or very short files. Raises when ffmpeg fails."""
    return (await ff_loudness(path))["lufs"]


async def ff_volume(path):
    """One quick ffmpeg volumedetect pass: {"max": loudest sample (dB), "rms": average level (dB)}; None where it gives nothing."""
    rc, _o, err = await ff_run(["-v", "info", "-nostats", "-i", path, "-vn", "-af", "volumedetect", "-f", "null", "-"], timeout=3600)
    mx = re.findall(r"max_volume:\s+(-?[\d.]+|-inf)\s+dB", err)
    mean = re.findall(r"mean_volume:\s+(-?[\d.]+|-inf)\s+dB", err)
    if rc != 0 and not (mx or mean):
        raise RuntimeError((err.strip().splitlines() or ["no volume result"])[-1][:160])
    return {"max": _num(mx[-1]) if mx else None, "rms": _num(mean[-1]) if mean else None}


_wave = {}                                  # (path, mtime) -> {"peaks": [0..255 x WAVE_BINS], "dur": seconds}
WAVE_BINS = 600
_wave_lock = [None]


async def ff_wave(path):
    """Waveform through ffmpeg: decodes to 8 kHz stereo and keeps the loudest sample of each bin. Returns None when
    ffmpeg is missing or fails, so the caller falls back to the built-in decoder."""
    if np is None or not ff_check():
        return None
    try:
        info = await ff_probe(path)
        if not info or info.get("error"):
            return None
        ch = 1 if int(info.get("ch") or 2) == 1 else 2          # keep mono as mono (ffmpeg's upmix would lose 3 dB)
        rc, out, _err = await ff_run(["-i", path, "-vn", "-map", "0:a:0", "-ac", str(ch), "-ar", "8000", "-f", "s16le", "-"])
    except Exception:
        return None
    if rc != 0 or len(out) < 8:
        return None
    a = np.frombuffer(out, dtype=np.int16)
    a = np.abs(a[: len(a) // ch * ch].reshape(-1, ch).astype(np.int32)).max(axis=1)
    bins = min(WAVE_BINS, len(a))
    idx = np.linspace(0, len(a), bins + 1).astype(int)
    peaks = [int(min(1.0, int(a[idx[i]:max(idx[i + 1], idx[i] + 1)].max()) / 32768.0) ** 0.6 * 255) for i in range(bins)]
    return {"peaks": peaks, "dur": round(len(a) / 8000.0, 2)}


async def get_wave(fid):
    """Down-sampled waveform of a library file for the web page. Uses the level envelope when the track is cached,
    otherwise decodes it once in a helper process (one at a time)."""
    path = str(LIB / fid)
    key = (path, (LIB / fid).stat().st_mtime)
    if key in _wave:
        return _wave[key]
    if np is None:
        return {"peaks": [], "dur": 0}
    env = _env.get(path)
    if env is None:
        out = await ff_wave(path)
        if out:
            if len(_wave) > 300:
                _wave.pop(next(iter(_wave)))
            _wave[key] = out
            return out
    if env is None:
        if _wave_lock[0] is None:
            _wave_lock[0] = asyncio.Lock()
        async with _wave_lock[0]:
            raw = await decode_in_child(path)
            env = await asyncio.get_running_loop().run_in_executor(None, compute_env, raw)
            del raw
    if env is None or len(env) == 0:
        return {"peaks": [], "dur": 0}
    mono = env.max(axis=1)
    bins = min(WAVE_BINS, len(mono))
    idx = np.linspace(0, len(mono), bins + 1).astype(int)
    peaks = [int(min(1.0, float(mono[idx[i]:max(idx[i + 1], idx[i] + 1)].max())) ** 0.6 * 255) for i in range(bins)]
    out = {"peaks": peaks, "dur": round(len(mono) * METER_WIN, 2)}
    if len(_wave) > 300:
        _wave.pop(next(iter(_wave)))
    _wave[key] = out
    return out


# ---------------------------------------------------------------- ffmpeg (optional helper)
# ffmpeg and ffprobe are used when they are installed: importing more file types, normalising uploads, waveforms,
# level measurement and format checks. Every one of those has a built-in fallback, so the player works without them.
# ffmpeg is always run one job at a time, at low priority and on at most "ffmpeg_cores" cores, so it never starves playback.
CONVERT_EXT = {".m4a", ".aac", ".aif", ".aiff", ".aifc", ".caf", ".wma", ".opus", ".oga", ".mp2", ".ac3", ".wv",
               ".mp4", ".m4v", ".mov", ".mkv", ".webm", ".avi", ".3gp"}
FF = {"exe": None, "probe": None, "ver": "", "ok": False, "checked": 0.0, "err": "ffmpeg has not been looked for yet"}
_ff_sem = [None]


def ff_check(force=False):
    """True when ffmpeg and ffprobe work. Looked up again at most once a minute, so installing ffmpeg needs no restart."""
    now = clock.monotonic()
    if not force and FF["checked"] and now - FF["checked"] < 60:
        return FF["ok"]
    FF["checked"] = now
    FF.update(ok=False, exe=None, probe=None, ver="")
    want = str(CFG.get("ffmpeg_path") or "").strip()
    exe = want if want and Path(want).is_file() else shutil.which(want or "ffmpeg")
    if not exe:
        FF["err"] = "ffmpeg was not found (install it, e.g. sudo apt install ffmpeg)"
        return False
    sib = Path(exe).with_name("ffprobe" + (".exe" if os.name == "nt" else ""))
    probe = str(sib) if sib.is_file() else shutil.which("ffprobe")
    try:
        import subprocess
        r = subprocess.run([exe, "-version"], capture_output=True, text=True, timeout=10)
        if r.returncode != 0:
            raise OSError(r.stderr.strip()[-120:] or "ffmpeg did not start")
        FF["ver"] = (r.stdout.splitlines() or [""])[0].replace("ffmpeg version", "").strip().split(" Copyright")[0]
    except Exception as e:
        FF["err"] = f"ffmpeg does not run: {e}"
        return False
    FF.update(ok=True, exe=exe, probe=probe, err="")
    return True


def ff_prefix():
    """Wrapper that keeps ffmpeg low priority and on the last few CPU cores (Linux)."""
    pre = []
    if os.name != "nt":
        try:
            if CFG["ffmpeg_nice"] and shutil.which("nice"):
                pre += ["nice", "-n", str(max(0, min(19, int(CFG["ffmpeg_nice"]))))]
            cpus = sorted(os.sched_getaffinity(0))
            n = max(1, int(CFG["ffmpeg_cores"]))
            if shutil.which("taskset") and len(cpus) > n:
                pre += ["taskset", "-c", ",".join(str(c) for c in cpus[-n:])]
        except Exception:
            pass
    return pre


async def ff_run(args, probe=False, timeout=900):
    """Run ffmpeg (or ffprobe) with limited CPU, one at a time. Returns (exit code, stdout bytes, stderr text);
    raises RuntimeError when ffmpeg is missing, cannot start or takes too long."""
    if not await asyncio.get_running_loop().run_in_executor(None, ff_check):          # (it may run ffmpeg -version: not on the event loop)
        raise RuntimeError(FF["err"])
    exe = FF["probe"] if probe else FF["exe"]
    if not exe:
        raise RuntimeError("ffprobe was not found (it comes with ffmpeg)")
    n = max(1, int(CFG["ffmpeg_cores"]))
    cmd = ff_prefix() + [exe, "-v", "error"] + ([] if probe else ["-hide_banner", "-nostdin", "-threads", str(n), "-filter_threads", "1"]) + args
    if _ff_sem[0] is None:
        _ff_sem[0] = asyncio.Semaphore(1)
    async with _ff_sem[0]:
        try:
            proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                                                        **({"creationflags": 0x4000} if os.name == "nt" else {}))
        except OSError as e:
            FF["checked"] = 0.0                       # look again next time
            raise RuntimeError(f"ffmpeg could not start: {e}")
        try:
            out, err = await asyncio.wait_for(proc.communicate(), timeout)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            raise RuntimeError("ffmpeg took too long")
        except asyncio.CancelledError:
            proc.kill()
            raise
    return proc.returncode, out, err.decode(errors="replace")


async def ff_probe(path):
    """Facts about an audio file from ffprobe: {"codec", "rate", "ch", "bits", "br", "dur", "container"}.
    None when ffprobe is not available; {"error": ...} when the file cannot be read."""
    try:
        rc, out, err = await ff_run(["-select_streams", "a:0", "-show_entries",
                                     "stream=codec_name,codec_long_name,sample_rate,channels,sample_fmt,bits_per_sample,bits_per_raw_sample,bit_rate,duration:format=duration,bit_rate,format_name,format_long_name,probe_score",
                                     "-of", "json", str(path)], probe=True, timeout=60)
    except RuntimeError:
        return None
    if rc != 0:
        return {"error": (err.replace(str(path) + ": ", "").strip().splitlines() or ["the file cannot be read"])[-1][:160]}
    try:
        d = json.loads(out.decode() or "{}")
        st = (d.get("streams") or [None])[0]
        fm = d.get("format") or {}
        if not st:
            return {"error": "no audio found in the file"}
        bits = int(st.get("bits_per_raw_sample") or st.get("bits_per_sample") or 0)
        dur = float(st.get("duration") or fm.get("duration") or 0)
        return {"codec": st.get("codec_name", "?"), "rate": int(st.get("sample_rate") or 0), "ch": int(st.get("channels") or 0),
                "bits": bits, "fmt": st.get("sample_fmt", ""), "br": int(st.get("bit_rate") or fm.get("bit_rate") or 0),
                "dur": dur, "container": (fm.get("format_name") or "").split(",")[0],
                "codec_long": st.get("codec_long_name", ""), "format_long": fm.get("format_long_name", ""),
                "score": fm.get("probe_score") if isinstance(fm.get("probe_score"), int) else None}
    except Exception:
        return {"error": "ffprobe gave an answer that could not be understood"}


async def ff_convert(src, dest, kind):
    """Convert any audio (or the audio of a video) to 48 kHz 16-bit stereo: kind "flac" or "wav". Returns None or an error text."""
    part = Path(dest).with_name("." + Path(dest).name + ".part")
    codec = ["-c:a", "flac", "-sample_fmt", "s16"] if kind == "flac" else ["-c:a", "pcm_s16le"]
    try:
        rc, _, err = await ff_run(["-y", "-i", str(src), "-vn", "-map", "0:a:0", "-map_metadata", "-1", "-ar", "48000", "-ac", "2",
                                   *codec, "-f", kind, str(part)])
    except RuntimeError as e:
        part.unlink(missing_ok=True)
        return str(e)
    if rc != 0 or not part.exists() or part.stat().st_size == 0:
        part.unlink(missing_ok=True)
        return (err.strip().splitlines() or ["the file could not be converted"])[-1][:200]
    os.replace(part, dest)
    return None


def needs_normalising(info):
    """wav/flac the mixer would have to resample, or that has more than 16 bits or 2 channels."""
    return bool(info) and "error" not in info and (info["rate"] != 48000 or info["bits"] > 16 or info["ch"] > 2 or info["ch"] < 1)
