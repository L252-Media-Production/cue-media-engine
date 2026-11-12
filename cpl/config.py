"""Paths, the CFG dict and the config.json / state.json overlay (docs/split-plan.md 2.1). Importing this module reads config.json and
state.json and creates media/library, exactly as the top of the old player.py did. BASE is the folder of the launcher (player.py).
Moved verbatim from cpl/legacy.py in split step P3. The child-process helpers must not import it (gate 10)."""
import json, re, sys
from pathlib import Path

from cpl.util import atomic_write

APP_VERSION = "2.8.0"       # the one product version: Settings footer, /api/state "version", the player_version variable (the Companion module compares major.minor)


# ---------------------------------------------------------------- config
BASE = Path(__file__).resolve().parent.parent      # the folder of the launcher (player.py), which also holds static/, config.json, media/ ...
LAUNCHER = BASE / "player.py"                           # what the child processes (--decode, --preview, --probe, --dl) are started from
MEDIA = BASE / "media"
LIB = MEDIA / "library"
DATA = BASE / "playlists.json"
CFG = {
    "osc_in_port": 9000,
    "http_port": 8080,
    "companion_host": "127.0.0.1",
    "companion_osc_port": 12321,     # Companion > Settings > OSC listen port
    "var_prefix": "mp_",             # custom variables: mp_focus_name, ...
    "default_transition": "cut",     # what /0/1 and /take do: "cut" or "crossfade"
    "go_transition": "cut",          # what the Go button of the web page does: "cut" (take) or "crossfade" (xfade); kept in state.json, shared by every page. Companion's Take / Crossfade are not affected
    "crossfade_ms": 3000,
    "top_track_pct": 100,            # Play on Top: level of the track played on top (the background goes to top_level_pct)
    "top_fade_ms": 1500,             # Play on Top: fade used when a second top track replaces the first
    "triggers_armed": True,          # Trigger points: when off, no trigger fires (the live track just plays); set from the page or /api/triggers/arm, never from Companion
    "top_level_pct": 10,             # (only used when numpy is missing) background level while a track plays on top
    "duck_threshold_db": -30.0,      # Play on Top ducking: the background is turned down while the top track is louder than this (dBFS)
    "duck_ratio": 6.0,               # ... by (dB over the threshold) x (1 - 1/ratio)
    "duck_attack_ms": 10,            # ... going down this fast
    "duck_release_ms": 500,          # ... and coming back up this fast
    "default_folder_icon": "",       # icon given to folders created from now on ("" = the plain circle); chosen in Settings
    "duck_hold": True,               # stay ducked from the first loud moment until the top track ends
    "input_device": None,            # Live input (Duck only): the capture device, null = none chosen. Kept in state.json
    "input_channel": 1,              # ... and the 1-based channel of it that is listened to (kept: written for older versions, and read when "input_channels" is absent)
    "input_channels": None,          # ... the channels listened to: [n] (one channel) or [n, n+1] (a stereo pair, the louder channel ducks); null = derive from "input_channel"
    "input_gain_db": 0.0,            # ... gain applied to that channel before the ducking threshold (-12..+24 dB)
    "input_threshold_db": None,      # ... the level (dBFS, after the gain, -60..0) above which the input ducks. null = not set yet: the first start copies the Play on Top threshold (what the detector used before), then it is its own setting. Kept in state.json
    "input_armed": False,            # ... when on, speech on the input ducks the playlist audio (same threshold / ratio / attack / release / hold as Play on Top). Off at first start
    "fadeout_ms": 2000,
    "trim_fade_ms": 1500,            # DEFAULT length of the fade at a track's Out point (when its end is set to fade); a track can override it (trim "fade_ms"); Settings > Transitions
    "trim_fadein_ms": 0,             # DEFAULT length of the fade-in at a track's In point (only used when the track's start edge is set to Fade in; 0 = no default); a track can override it (trim "fade_in_ms"); Settings > Transitions
    "toggle_off_fade_ms": 0,         # fade used when a toggle switches the live track off
    "audio_device": None,            # exact device name; devices are printed at startup
    "download_folder": "Downloads",  # library folder that "Download from a link" saves into
    "download_format": "flac",       # flac | mp3 | wav
    "cache_mb": 768,                 # RAM for decoded tracks (a stereo minute is ~11 MB); the focus playlist is kept warm
    "storage_limit": None,           # cap on the library size: "10GB", "500MB" or "50%" of the disk. null = no cap
    "storage_reserve": "1GB",        # always keep this much of the disk free (uploads are refused below it)
    "mirror_enabled": False,         # the mirror output is off unless this is switched on (Settings)
    "mirror_device": None,           # second output that plays a copy of the live audio (headphones, a second Dante adapter); null = off
    "output_aliases": None,          # labels / groups / hidden / live-only flags for output names (cpl/outalias.py); null = never saved, the built-in default applies; a saved list replaces it. Kept in state.json
    "preview_device": None,          # second output for previewing tracks (e.g. the Pi's headphone jack); null = off
    "preview_volume": 1.0,
    "live_volume": 1.0,              # master volume of the main (live) output, 0..1; also set from the web page and Companion
    "meter_rate_hz": 4,              # how often level meters are sent to Companion (0 = don't send; the web page is unaffected)
    "resume_on_start": True,         # after a restart, carry on with the track that was playing, from where it left off
    "resume_save_s": 5,              # how often the position is saved while playing (seconds)
    "resume_max_age_s": 1800,        # ...but only if the player was last seen playing within this many seconds
    "play_mode": "stop",             # default for playlists with no mode of their own: stop | loop_playlist | next_playlist | shuffle
    "ffmpeg_path": "",               # leave empty to find ffmpeg and ffprobe on the PATH; or the full path of ffmpeg
    "ffmpeg_cores": 2,               # ffmpeg may use at most this many CPU cores (Linux), one job at a time, at low priority
    "ffmpeg_nice": 10,               # ...and this much lower priority than the audio (0-19, Linux)
    "import_convert": True,          # upload m4a, aiff, wma, opus, video files ... by converting them with ffmpeg (to 48 kHz FLAC)
    "time_warning": None,            # Time warning (Settings): {"warnings": [{"t","c"}, ...]}, always on; null until set. Kept in state.json, shared by every page and the stage page
    "watchdog": True,                # restart the audio engine (only) when the output stops moving for 10 s while playing (Settings > System > Health and alerts)
    "push_enabled": False,           # Push on state change (Settings > System > Health and alerts): a webhook message when the health state changes
    "push_url": "",                  # the webhook address (http or https); a secret: never logged or sent to the page in full
    "push_events": {"problem": True, "recovered": True, "degraded_long": True, "watchdog": True},
    "push_hold": False,              # queue messages while something is playing and send them together when nothing is
    "player_name": "",               # the name this player uses in push messages and the health report; empty = the machine's host name
    "health_preview_amber": True,    # Health panel: a configured Preview output that is missing makes the dot amber (Settings > System > Health and alerts)
    "import_normalise": True,        # wav/flac uploads with another sample rate, more than 16 bits or more than 2 channels are converted to 48 kHz 16-bit stereo
}
cfg_file = BASE / "config.json"


def read_config_file():
    """config.json as a dict. A trailing comma (easy to leave behind when editing by hand) is forgiven;
    any other mistake stops the player with a message that says where it is, instead of a traceback."""
    text = cfg_file.read_text(encoding="utf-8-sig")
    try:
        return json.loads(text)
    except ValueError as e:
        try:
            fixed = json.loads(re.sub(r",(\s*[}\]])", r"\1", text))
            print(f"Note: config.json has a trailing comma ({e}). It was ignored; remove it when you next edit the file.")
            return fixed
        except ValueError:
            print(f"\nconfig.json could not be read: {e}\nFile: {cfg_file}\n"
                  "Fix it (every setting needs a comma after it except the last one) or delete the file to use the defaults.")
            sys.exit(1)


if cfg_file.exists():
    CFG.update(read_config_file())
RESUME = BASE / "resume.json"        # what was playing, so a restart can carry on
STATE = BASE / "state.json"          # remembers the output device chosen in the web UI
if STATE.exists():
    try:
        CFG.update({k: v for k, v in json.loads(STATE.read_text()).items() if k != "play_mode"})   # play mode is per playlist now
    except Exception:
        pass
if CFG.get("go_transition") not in ("cut", "crossfade"):
    CFG["go_transition"] = "cut"
CFG["triggers_armed"] = CFG.get("triggers_armed") not in (False, 0, "0", "false", "off", "no")
WARN_DEFAULT = {"warnings": [{"t": 60, "c": "#f97316"}, {"t": 30, "c": "#ef4444"}]}


def _warn_item(d):
    t, c = d.get("t"), d.get("c")
    if isinstance(t, bool) or not isinstance(t, (int, float)) or not 0 <= t <= 359999:
        raise ValueError("a warning time must be a number of seconds from 0 to 359999")
    if not isinstance(c, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", c):
        raise ValueError("a warning colour must look like #f97316")
    return {"t": int(round(t)), "c": c.lower()}


def warn_clean(d, base=None):
    """Time warning settings, checked: {"warnings": [{"t": seconds left, "c": "#rrggbb"}, ...]}, at least one, any number, longest
    time first. The warning is always on. Also accepts the older shape {t1, c1, t2, c2[, on]} (first and final warning).
    Returns None if d is not a dict; raises ValueError for a bad value."""
    if not isinstance(d, dict):
        return None
    cur = (base or WARN_DEFAULT)["warnings"]
    if "warnings" in d:
        items = d["warnings"]
        if not isinstance(items, list) or not items:
            raise ValueError("send at least one warning")
        new = [_warn_item(it) if isinstance(it, dict) else _warn_item({}) for it in items]
    elif any(k in d for k in ("t1", "c1", "t2", "c2")):
        new = [_warn_item({"t": d.get("t1", cur[0]["t"]), "c": d.get("c1", cur[0]["c"])}),
               _warn_item({"t": d.get("t2", cur[-1]["t"]), "c": d.get("c2", cur[-1]["c"])})]
    else:
        new = [dict(w) for w in cur]
    new.sort(key=lambda w: -w["t"])                      # longest first (a stable sort: equal times keep their order)
    return {"warnings": new}


try:
    CFG["time_warning"] = warn_clean(CFG.get("time_warning"))
except ValueError:
    CFG["time_warning"] = None
for _k in ("watchdog", "health_preview_amber"):
    CFG[_k] = CFG.get(_k) not in (False, 0, "0", "false", "off", "no")
PLAY_MODES = ("stop", "loop_playlist", "next_playlist", "shuffle")      # what a track does when it ends is per track (playlist["end_actions"])
if CFG["play_mode"] not in PLAY_MODES:
    CFG["play_mode"] = "stop"
LIB.mkdir(parents=True, exist_ok=True)
AUDIO_EXT = {".wav", ".mp3", ".ogg", ".flac"}


def save_config_keys(updates):
    """Merge `updates` into config.json (keeping every other setting) and write it atomically."""
    data = read_config_file() if cfg_file.exists() else {}
    data.update(updates)
    atomic_write(cfg_file, json.dumps(data, indent=2) + "\n")
