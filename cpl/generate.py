"""Generate audio with ElevenLabs (2.9.0): one generation at a time, its temporary file, and Save / Replace / Discard.

The flow: start() runs one request in a background task (aiohttp, so the event loop, OSC, the watchdog and the health push carry
on); the audio lands in _import/ (emptied at every start) as a temporary file the operator previews; save_new() moves it into a
library folder through upload.import_path (the same steps as an upload), replace() puts it in place of a generated track.
Nothing here goes near the Live output, and no failure touches the player's health (ISSUES is never written).
The metadata of a generated track (text, voice, model, date; never the key) is GENERATED[file id], saved in playlists.json.
"""
import asyncio, os, re, secrets, shutil, time
from datetime import datetime, timezone
from pathlib import Path

from cpl import clock, elevenlabs as el, upload
from cpl.cache import cache_drop
from cpl.config import LIB
from cpl.library import _safe_rel, invalidate_storage
from cpl.persist import save
from cpl.state import DURS, GENERATED, library, playlists

DEFAULT_FOLDER = "Generated"
NAME_MAX = 80
TOKEN_S = 60.0                     # a browser-preview link is good for one fetch within this many seconds
VOICE_RE = re.compile(r"[A-Za-z0-9_-]{1,64}")
MODEL_RE = re.compile(r"[A-Za-z0-9_.-]{1,64}")

JOB = {"state": "idle", "n": 0, "started": 0.0, "error": None, "result": None}     # idle | running | done | error | cancelled
_T = {"task": None, "path": None, "meta": None, "token": None, "token_t": 0.0}


def clean_name(name):
    """A track name typed in the dialog as a file name stem: path separators and characters that are not allowed in a library
    name become _, spaces are collapsed, no leading dot or underscore, at most NAME_MAX characters. "" when nothing is left."""
    s = re.sub(r"[^\w.\- ]", "_", str(name or ""))
    s = re.sub(r"\s+", " ", s).strip(" .")
    s = s.lstrip("._ ").strip()
    return s[:NAME_MAX].rstrip(" .")


def limit_for(model):
    """Characters per request: the default model's 10,000 when no model is chosen; a chosen model's limit from /v1/models when
    the answer had one (else None: the API's max_character_limit_exceeded error decides)."""
    if not model:
        return el.DEFAULT_MODEL_LIMIT
    for m in el.cached_models() or []:
        if m["id"] == model:
            return m["limit"]
    return None


def _unit(v):
    if v is None or v == "":
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        raise ValueError("stability and similarity are numbers from 0 to 1")
    if not 0.0 <= f <= 1.0:
        raise ValueError("stability and similarity are numbers from 0 to 1")
    return round(f, 2)


def check(b):
    """The dialog's fields, checked. Returns a dict, or raises el.ElError / ValueError with a plain message."""
    name = clean_name(b.get("name"))
    if not name:
        raise ValueError("Give the track a name.")
    text = str(b.get("text") or "").strip()
    if not text:
        raise ValueError("Type the text to speak.")
    voice = str(b.get("voice_id") or "")
    if not VOICE_RE.fullmatch(voice):
        raise ValueError("Pick a voice.")
    model = str(b.get("model") or "") or None
    if model and not MODEL_RE.fullmatch(model):
        raise ValueError("That model name is not valid.")
    lim = limit_for(model)
    if len(text) > min(lim or el.TEXT_MAX, el.TEXT_MAX):
        raise el.ElError("too_long", f"The text is too long for one request ({len(text):,} characters; at most {min(lim or el.TEXT_MAX, el.TEXT_MAX):,}). "
                         "Shorten it or split it into two tracks.", "warn")
    vs = {}
    for k, api in (("stability", "stability"), ("similarity", "similarity_boost")):
        v = _unit(b.get(k))
        if v is not None:
            vs[api] = v
    return {"name": name, "text": text, "voice_id": voice, "voice_name": str(b.get("voice_name") or voice)[:80], "model": model,
            "settings": vs or None, "limit": lim}


def busy():
    return JOB["state"] == "running"


def _drop_temp():
    p = _T["path"]
    _T.update(path=None, meta=None, token=None, token_t=0.0)
    if p:
        try:
            Path(p).unlink()
        except FileNotFoundError:
            pass
        except OSError as e:
            print("WARNING: ElevenLabs: could not delete a temporary file:", e, flush=True)


def start(b):
    """Start one generation. Returns (dict, http status)."""
    if busy():
        return {"ok": False, "kind": "busy", "error": "A generation is already running. Wait for it or press Cancel.", "level": "warn"}, 409
    if not el.key():
        return {"ok": False, **el.no_key().json()}, 400
    try:
        req = check(b)
    except el.ElError as e:
        return {"ok": False, **e.json()}, 400
    except ValueError as e:
        return {"ok": False, "kind": "input", "error": str(e), "level": "warn"}, 400
    _drop_temp()                                          # a new generation replaces an unsaved one
    JOB.update(state="running", n=JOB["n"] + 1, started=clock.monotonic(), error=None, result=None)
    _T["task"] = asyncio.ensure_future(_run(req, JOB["n"]))
    return {"ok": True, "n": JOB["n"]}, 200


async def _run(req, n):
    tmp = None
    try:
        audio = await asyncio.wait_for(el.speech(req["voice_id"], req["text"], req["model"], req["settings"], req["limit"]), el.TTS_TIMEOUT_S + 10)
        upload.IMPORT_DIR.mkdir(exist_ok=True)
        tmp = upload.IMPORT_DIR / f"gen-{os.getpid()}-{time.time_ns()}.mp3"
        await asyncio.get_running_loop().run_in_executor(None, tmp.write_bytes, audio)
        if JOB["n"] != n:                                  # cancelled meanwhile and another one started
            tmp.unlink(missing_ok=True)
            return
        meta = {"text": req["text"], "voice_id": req["voice_id"], "voice_name": req["voice_name"], "model": req["model"] or "",
                "created": datetime.now(timezone.utc).replace(microsecond=0).isoformat()}
        _T.update(path=str(tmp), meta=meta, token=None, token_t=0.0)
        JOB.update(state="done", result={"name": req["name"], "voice_name": req["voice_name"], "chars": len(req["text"]),
                                         "size": len(audio), "model": req["model"] or ""})
    except asyncio.CancelledError:
        if tmp:
            tmp.unlink(missing_ok=True)
        if JOB["n"] == n:
            JOB.update(state="cancelled", error=None)
        raise
    except asyncio.TimeoutError:
        JOB.update(state="error", error=el.ElError("timeout", "ElevenLabs didn't answer in time. Nothing was saved; try again.", "warn").json())
    except el.ElError as e:
        JOB.update(state="error", error=e.json())
    except Exception as e:                                 # never let it escape: log without the key, tell the page plainly
        print("WARNING: ElevenLabs: generation failed:", el.redact(f"{e.__class__.__name__}: {e}"), flush=True)
        JOB.update(state="error", error=el.ElError("unexpected", "Something went wrong while generating. Nothing was saved.").json())
    finally:
        if JOB["n"] == n:
            _T["task"] = None


def cancel():
    t = _T["task"]
    if t and not t.done():
        t.cancel()
        JOB.update(state="cancelled", error=None, result=None)
        _T["task"] = None
        return True
    return False


def state():
    out = {k: JOB[k] for k in ("state", "n", "error", "result")}
    if JOB["state"] == "running":
        out["elapsed"] = round(clock.monotonic() - JOB["started"], 1)
    out["has_temp"] = bool(_T["path"])
    return out


def temp_path():
    return _T["path"] if _T["path"] and Path(_T["path"]).exists() else None


def new_token():
    """A one-use link for the browser preview of the temporary file, good for TOKEN_S. None when there is no file."""
    if not temp_path():
        return None
    _T.update(token=secrets.token_urlsafe(24), token_t=clock.monotonic())
    return _T["token"]


def take_token(tok):
    """The temporary file for a valid token (the token is used up), else None."""
    good = bool(_T["token"]) and isinstance(tok, str) and secrets.compare_digest(tok, _T["token"]) and clock.monotonic() - _T["token_t"] <= TOKEN_S
    _T.update(token=None, token_t=0.0)
    return temp_path() if good else None


def discard():
    cancel()
    had = bool(_T["path"])
    _drop_temp()
    if JOB["state"] in ("done", "error", "cancelled"):
        JOB.update(state="idle", error=None, result=None)
    return had


async def save_new(name, folder):
    """Save the temporary file as a new library track. Returns (dict, http status)."""
    src = temp_path()
    if not src:
        return {"ok": False, "error": "There is nothing to save. Generate first."}, 409
    stem = clean_name(name)
    if not stem:
        return {"ok": False, "error": "Give the track a name."}, 400
    folder = _safe_rel(str(folder or "").strip() or DEFAULT_FOLDER, True)
    if not folder:
        return {"ok": False, "error": "That folder name is not allowed."}, 400
    meta = dict(_T["meta"])
    res = await upload.import_path(src, folder, stem)
    if "error" in res:
        return {"ok": False, "error": res["error"]}, res["status"]
    _drop_temp()                                           # moved (or deleted as a duplicate): forget it
    JOB.update(state="idle", error=None, result=None)
    if not res["duplicate"]:
        GENERATED[res["id"]] = meta
    save()
    return {"ok": True, "id": res["id"], "duplicate": res["duplicate"], "folder": folder}, 200


def replace(fid, in_use):
    """Put the temporary file in place of generated track `fid`, keeping its playlist entries. Everything derived from the old
    audio is dropped: the decoded sound (RAM cache), the measured length; the waveform, format check, loudness and file information
    are keyed by size and modification time and are measured again; A/B points and trigger points on that track are cleared (their
    times belonged to the old audio). Refused while the track is playing, cued to start or previewing (`in_use`)."""
    src = temp_path()
    if not src:
        return {"ok": False, "error": "There is nothing to save. Generate first."}, 409
    if fid not in library or fid not in GENERATED:
        return {"ok": False, "error": "That track is not a generated track in the library."}, 404
    if Path(fid).suffix.lower() != Path(src).suffix.lower():
        return {"ok": False, "error": "That track has another file type; save as a new track instead."}, 409
    if in_use:
        return {"ok": False, "error": "That track is playing or about to play. Stop it first, or save as a new track."}, 409
    dest = LIB / fid
    size = Path(src).stat().st_size
    cache_drop(str(dest))
    try:
        shutil.move(src, str(dest) + ".new")
        os.replace(str(dest) + ".new", dest)               # atomic on one disk: never a half-written track
    except OSError as e:
        print("WARNING: ElevenLabs: could not replace", fid, "-", e, flush=True)
        return {"ok": False, "error": "Couldn't replace the file on the player."}, 500
    cache_drop(str(dest))
    library[fid] = size
    DURS.pop(fid, None)
    cleared = 0
    for pl in playlists:
        for k in ("trims", "triggers"):
            if fid in (pl.get(k) or {}):
                pl[k].pop(fid)
                cleared += 1
                if not pl[k]:
                    pl.pop(k)
    GENERATED[fid] = dict(_T["meta"])
    _T.update(path=None, meta=None, token=None, token_t=0.0)
    JOB.update(state="idle", error=None, result=None)
    invalidate_storage()
    save()
    return {"ok": True, "id": fid, "cleared": cleared}, 200


def meta_of(fid):
    """What the page needs to regenerate a track (text, voice, model, date); never the key."""
    g = GENERATED.get(fid)
    return dict(g) if g else None
