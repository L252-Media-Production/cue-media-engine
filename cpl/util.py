"""Small helpers with no knowledge of the player (docs/split-plan.md 2.1): atomic file writes, log_once, spawn, request-body and
number parsing, byte formatting. Moved verbatim from cpl/legacy.py in split step P3."""
import asyncio, json, math, os, re

from aiohttp import web

from cpl import clock


def atomic_write(path, text):
    """Write a file so a power cut leaves either the old or the new content, never a half-written file."""
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


_log_seen = {}


_tasks = set()                      # background tasks started by spawn(); asyncio itself only holds weak references


def log_once(key, msg, exc=None):
    """Print a problem at most once a minute per key, so a failure that repeats every tick cannot flood the log."""
    now = clock.monotonic()
    if now - _log_seen.get(key, -1e9) >= 60:
        _log_seen[key] = now
        print(f"{msg}: {exc}" if exc is not None else msg, flush=True)


def spawn(coro):
    """Start a background task and keep it referenced until it finishes (a bare ensure_future can be garbage-collected
    mid-flight). A failure is logged instead of surfacing only when the task is collected."""
    task = asyncio.ensure_future(coro)
    _tasks.add(task)

    def done(t):
        _tasks.discard(t)
        if not t.cancelled() and t.exception() is not None:
            log_once("task:" + repr(t.exception())[:60], "background task failed", t.exception())
    task.add_done_callback(done)
    return task


def is_uint(s):
    """True for a string of ASCII digits only (and short enough for int()). str.isdigit() also accepts characters like '\u00b2' that int() then rejects."""
    return isinstance(s, str) and s.isascii() and s.isdigit() and len(s) <= 4000


def route_int(req, key):
    """The integer in the URL part {key} (a playlist or track number); anything else is an unknown address: 404 instead of a 500."""
    try:
        return int(req.match_info[key])
    except ValueError:
        raise web.HTTPNotFound(text=json.dumps({"ok": False, "error": "no such " + ("track" if key == "t" else "playlist")}), content_type="application/json")


def finite_float(v):
    """float(v), or None when v is not a number or is not finite (inf, -inf, nan, 1e999)."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


async def body(req):
    """The JSON object of a request, or {} when the body is missing or is not a JSON object."""
    try:
        b = await req.json()
    except Exception:
        return {}
    return b if isinstance(b, dict) else {}


def fmt(sec):
    sec = max(0, int(math.ceil(sec - 0.001)))
    return f"{sec // 60:02d}:{sec % 60:02d}"


def fmt_bytes(n):
    n = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit in ("B", "KB") else f"{n:.1f} {unit}"
        n /= 1024


# ---------------------------------------------------------------- storage limits
_UNITS = {"": 1024 ** 3, "b": 1, "k": 1024, "kb": 1024, "m": 1024 ** 2, "mb": 1024 ** 2,
          "g": 1024 ** 3, "gb": 1024 ** 3, "t": 1024 ** 4, "tb": 1024 ** 4}


_warned = set()


def parse_size(v, total):
    """'10GB' -> bytes, '50%' -> half of `total`. A bare number means GB. None/'' -> None."""
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return int(v * 1024 ** 3)
    s = str(v).strip().lower().replace(" ", "").replace("ib", "b")
    m = re.fullmatch(r"(\d+(?:\.\d+)?)(%|[a-z]*)", s)
    if not m or (m.group(2) != "%" and m.group(2) not in _UNITS):
        if v not in _warned:
            _warned.add(v)
            print(f"config: could not understand size {v!r} (use e.g. \"10GB\", \"500MB\" or \"50%\") - ignored")
        return None
    num = float(m.group(1))
    return int(total * num / 100) if m.group(2) == "%" else int(num * _UNITS[m.group(2)])


_sc = {"t": 0.0, "v": None}
