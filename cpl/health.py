"""The health model (2.8.0): turns facts about the player into a list of checks and one overall state.

Pure: `evaluate()` takes plain inputs and returns plain data, so tests feed it fake inputs and a fake clock. Nothing here touches the
audio device, the disk or the network; `cpl/legacy.py` gathers the facts (cheaply, off the event loop where they cost anything)
and calls it. A check has an id, a status (ok | warn | bad | unknown), a short title and one sentence in words.
"""

OK, WARN, BAD, UNKNOWN = "ok", "warn", "bad", "unknown"
STATES = ("starting", "ready", "degraded", "problem")

COMPANION_SILENT_S = 30            # the Companion module polls /api/state four times a second; silent for longer than this = not answering
DISK_WARN_PCT, DISK_WARN_BYTES, DISK_BAD_BYTES = 10.0, 5 * 1024 ** 3, 1 * 1024 ** 3
GB = 1024 ** 3
PROC_STATUS, PROC_FD = "/proc/self/status", "/proc/self/fd"

TITLES = {
    "live_output": "Live output",
    "preview_output": "Preview output",
    "audio_engine": "Audio engine",
    "companion": "Companion",
    "disk": "Media drive space",
    "cache": "Track cache",
    "uptime": "Player uptime",
}
ORDER = tuple(TITLES)


def uptime_text(seconds):
    s = max(0, int(seconds))
    d, rest = divmod(s, 86400)
    h, rest = divmod(rest, 3600)
    m = rest // 60
    if d:
        return f"Up {d} d {h} h"
    if h:
        return f"Up {h} h {m} min"
    return f"Up {m} min"


def _chk(cid, status, text=""):
    return {"id": cid, "status": status, "title": TITLES[cid], "text": text}


def check_live(x):
    name = x.get("shown") or x.get("name") or "system default"       # "shown" = the alias label with the raw name in brackets; the checks themselves use "name"
    if x.get("present", True) and x.get("open", True):
        return _chk("live_output", OK)
    if x.get("present", True):
        return _chk("live_output", BAD, f"The live output ({name}) is not open. Check the audio device, then choose it again in Settings > Audio.")
    return _chk("live_output", BAD, f"The live output ({name}) is not available. Start or plug in the device, then press Refresh devices and choose it again.")


def check_preview(x):
    if not x.get("configured") or x.get("browser"):
        return _chk("preview_output", OK)
    if x.get("present", True):
        return _chk("preview_output", OK)
    name = x.get("shown") or x.get("name") or "the saved device"
    if not x.get("amber", True):
        return _chk("preview_output", OK)
    return _chk("preview_output", WARN, f"The preview output ({name}) is not available. Plug it in and press Refresh devices; Live is not affected.")


def restarts_note(n):
    n = int(n or 0)
    return f"Restarted {n} time{'s' if n != 1 else ''} since start"


def check_engine(x):
    c = _check_engine(x)
    c["note"] = restarts_note(x.get("restarts"))       # always shown on this row (a long soak test reads it)
    return c


def _check_engine(x):
    if x.get("gave_up"):
        return _chk("audio_engine", BAD, "The audio output stalled and the watchdog has restarted the engine too often. Check the audio device, then restart the player.")
    if x.get("stalled"):
        return _chk("audio_engine", BAD, "The audio output has stopped moving. The watchdog is restarting the audio engine.")
    return _chk("audio_engine", OK)


def check_companion(x):
    if x.get("host_found") is False:
        return _chk("companion", WARN, "The Companion address cannot be found. Check the address in Settings > Companion.")
    if not x.get("polled"):
        return _chk("companion", UNKNOWN, "Companion has not asked for anything since the player started.")
    silent = x.get("silent_s", 0)
    if silent > COMPANION_SILENT_S:
        return _chk("companion", WARN, f"Companion has not answered for {int(silent)} s. Check that Companion is running and the module is connected.")
    return _chk("companion", OK)


def pct_text(free, total):
    """The free share as text for a person: a whole number, never below 0 or above 100, "less than 1 %" when there is some space but under 1 %,
    and None (leave it out) when the total is not known. Never prints "0 %" for space that is there."""
    try:
        if not total or total <= 0 or free is None:
            return None
        v = min(100.0, max(0.0, 100.0 * free / total))
    except (TypeError, ValueError):
        return None
    if 0 < v < 1:
        return "less than 1 %"
    return f"{int(v + 0.5)} %"


def check_disk(x):
    if not x or x.get("free") is None:
        return _chk("disk", UNKNOWN, "The free space could not be read.")
    free, total = x["free"], x.get("total")
    pct = (100.0 * free / total) if total and total > 0 else None       # None = total unknown: only the absolute limits apply
    shown = pct_text(free, total)
    amount = f"{free / GB:.1f} GB free" + (f" ({shown})" if shown else "")
    if free < DISK_BAD_BYTES:
        return _chk("disk", BAD, f"Only {free / GB:.1f} GB is free on the media drive. Delete files or add space before uploading or downloading.")
    if (pct is not None and pct < DISK_WARN_PCT) or free < DISK_WARN_BYTES:
        return _chk("disk", WARN, f"The media drive is running low: {amount}. Delete files you no longer need.")
    return _chk("disk", OK)


def check_cache(x):
    if not x or not x.get("measured", True):
        return _chk("cache", UNKNOWN, "")
    if x.get("failing"):
        return _chk("cache", WARN, "A track could not be loaded into memory. See the track list for the file.")
    if x.get("full"):
        return _chk("cache", WARN, "The track cache is full, so some tracks load when they start. Raise the cache size in Settings or shorten the playlists.")
    return _chk("cache", OK)


def evaluate(inp):
    """inp: {starting, live, preview, engine, companion, disk, cache, uptime_s}. -> {state, summary, checks, uptime}."""
    checks = [check_live(inp.get("live") or {}), check_preview(inp.get("preview") or {}), check_engine(inp.get("engine") or {}),
              check_companion(inp.get("companion") or {}), check_disk(inp.get("disk")), check_cache(inp.get("cache")),
              _chk("uptime", OK, uptime_text(inp.get("uptime_s", 0)))]
    bad = [c for c in checks if c["status"] == BAD]
    warn = [c for c in checks if c["status"] == WARN]
    if inp.get("starting") and not bad:
        state = "starting"
    elif bad:
        state = "problem"
    elif warn:
        state = "degraded"
    else:
        state = "ready"
    first = (bad or warn or [None])[0]
    issues = inp.get("issues")                        # the older red-dot reasons (a library folder that is missing, a failed start-up step ...)
    if issues and not bad:
        return {"state": "problem", "summary": str(issues)[:80], "checks": checks}
    summary = SUMMARY.get(first["id"], first["title"]) if first else ""
    if first and first["id"] == "disk":
        summary = "Disk space critical" if first["status"] == BAD else "Disk space low"
    return {"state": state, "summary": summary, "checks": checks}


SUMMARY = {"live_output": "Live output problem", "preview_output": "Preview output missing", "audio_engine": "Audio engine stalled",
           "companion": "Companion not answering", "cache": "Track cache full"}


def compact(h):
    """The small object for /api/state: the overall state, the summary and the checks without the always-present titles' repeats."""
    return {"state": h["state"], "summary": h["summary"], "checks": [({"id": c["id"], "status": c["status"], "title": c["title"], "text": c["text"]} | ({"note": c["note"]} if c.get("note") else {})) for c in h["checks"]]}


# ---- soak lines of the report (2.8.0 follow-up 3): read-only, plain facts about this process, with no effect on any check
def process_memory_text(status_path=PROC_STATUS, platform=None, rusage=None):
    """"Process memory: 412 MB" = the resident set size of the player (VmRSS on Linux; on macOS the getrusage figure, which is the peak), or "not available"."""
    import sys
    plat = platform or sys.platform
    try:
        if plat.startswith("linux"):
            with open(status_path, encoding="utf-8", errors="replace") as f:
                for line in f:
                    if line.startswith("VmRSS:"):
                        return f"Process memory: {int(line.split()[1]) / 1024:.0f} MB"
            return "Process memory: not available"
        if plat == "darwin":
            if rusage is None:
                import resource
                rusage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            return f"Process memory: {int(rusage) / 1048576:.0f} MB"        # macOS reports bytes
    except Exception:
        pass
    return "Process memory: not available"


def open_files_text(fd_dir=PROC_FD, platform=None, own_fd=1):
    """"Open files: 57" = the entries of /proc/self/fd (Linux only), less the one the listing itself holds open; "not available" elsewhere."""
    import os, sys
    if not (platform or sys.platform).startswith("linux"):
        return "Open files: not available"
    try:
        return f"Open files: {max(0, len(os.listdir(fd_dir)) - own_fd)}"
    except Exception:
        return "Open files: not available"
