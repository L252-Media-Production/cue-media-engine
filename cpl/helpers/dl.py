"""Helper process (python player.py --dl JSON): download one link with yt-dlp, progress as JSON lines on stdout.
Runs when this module is imported by the launcher (player.py); imports nothing of the app."""
import json, os, re, shutil, sys, time
from pathlib import Path
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")      # as at the top of the old player.py: a pygame banner on stdout would corrupt the child's output

# Helper process: download the audio of one link with yt-dlp. The player starts it under nice / taskset (and Windows'
# low priority), so the extraction and the ffmpeg conversion it launches never compete with the live audio.
# Progress goes to stdout as JSON lines: {"t":"p",...} while running and one {"t":"done","err":...,"playlist":bool}.
_a = json.loads(sys.argv[2])
_out, sys.stdout = sys.stdout, sys.stderr            # anything a library prints must not corrupt the protocol

def _say(**kw):
    _out.write(json.dumps(kw) + "\n")
    _out.flush()

try:
    try:
        import yt_dlp as _mod
    except ImportError:
        import youtube_dl as _mod
except ImportError:
    _say(t="done", err="The downloader is not installed. On the player run: pip install -r requirements.txt, then restart it.", playlist=False)
    sys.exit(0)

class _Log:
    def debug(self, m): pass
    def info(self, m): pass
    def warning(self, m): pass
    def error(self, m): pass

_last = [0.0]
_title = [""]

def _hook(d):
    t = (d.get("info_dict") or {}).get("title")
    if t:
        _title[0] = t
    if d.get("status") == "downloading":
        if time.monotonic() - _last[0] < 0.25:
            return
        _last[0] = time.monotonic()
        tot = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
        _say(t="p", title=_title[0], msg="Downloading...",
             pct=round(min(99.0, 100.0 * (d.get("downloaded_bytes") or 0) / tot), 1) if tot else None)
    elif d.get("status") == "finished":
        _say(t="p", title=_title[0], msg="Converting to " + _a["codec"].upper() + "...", pct=100.0)

_name = "%(playlist_title)s/%(playlist_index)02d - %(title).110s.%(ext)s" if _a["whole"] else "%(title).120s.%(ext)s"
_opts = {
    "format": "bestaudio/best", "outtmpl": str(Path(_a["tmp"]) / _name), "noplaylist": not _a["whole"],
    "quiet": True, "no_warnings": True, "noprogress": True, "no_color": True, "logger": _Log(),
    "progress_hooks": [_hook], "socket_timeout": 20, "retries": 3, "windowsfilenames": True,
    "postprocessors": [dict({"key": "FFmpegExtractAudio", "preferredcodec": _a["codec"]},
                            **({"preferredquality": _a["quality"]} if _a["quality"] else {}))],
}
if _a.get("ffmpeg"):
    _opts["ffmpeg_location"] = _a["ffmpeg"]
if _a["codec"] in ("flac", "wav") and _a["normalise"]:       # lossless downloads match the rest of the library: 48 kHz, 16-bit, stereo
    _opts["postprocessor_args"] = {"extractaudio": ["-ar", "48000", "-ac", "2", "-sample_fmt", "s16"]}
if _a["whole"]:
    _opts["playlistend"] = 100                 # a safety limit
else:
    _opts["playlist_items"] = "1"              # a link to a whole playlist gives just its first track
_rts = {n: {} for n in ("deno", "node", "bun", "quickjs") if shutil.which(n)}
if _rts and _mod.__name__ == "yt_dlp":
    _opts["js_runtimes"] = _rts                 # YouTube needs one of these to solve its checks
try:
    with _mod.YoutubeDL(_opts) as _ydl:
        _info = _ydl.extract_info(_a["url"], download=True)
    _say(t="done", err=None, playlist=isinstance(_info, dict) and _info.get("_type") == "playlist")
except Exception as _e:
    _msg = re.sub(r"\x1b\[[0-9;]*m", "", str(_e)).replace("ERROR: ", "").strip()
    _say(t="done", err=_msg or _e.__class__.__name__, playlist=False)
sys.exit(0)
