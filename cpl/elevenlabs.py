"""ElevenLabs client (2.9.0): the API key on disk, and every HTTP call to ElevenLabs.

This is the ONE module that talks to ElevenLabs. Everything goes through `transport()`, which tests replace, so no test
reaches the network. Direct REST with aiohttp (already a dependency), no SDK: nothing new to install on the Pi.

API facts (read from the docs, 2026-11-23; see docs/api-reference.md "ElevenLabs"):
  header xi-api-key; GET /v2/voices (page_size <= 100, next_page_token); GET /v1/user/subscription (character_count,
  character_limit, next_character_count_reset_unix); GET /v1/models (can_do_text_to_speech); POST /v1/text-to-speech/{voice_id}
  ?output_format=mp3_44100_128 with {"text", "model_id"?, "voice_settings"?} -> the audio bytes. Errors: {"detail": {"status",
  "message"}} with status invalid_api_key, quota_exceeded, max_character_limit_exceeded, voice_not_found, too_many_concurrent_requests,
  system_busy. With no model_id the API uses its default model (eleven_multilingual_v2, 10,000 characters per request).

The key: kept only in BASE/elevenlabs.key (mode 0600; on Windows icacls limits it to the account running the player), never in
CFG, config.json or state.json, never returned by a route (the page gets "set" and the last four characters), never logged:
every error text that leaves this module goes through redact().
"""
import asyncio, email.utils, json, os, re, subprocess, sys

import aiohttp

from cpl import clock
from cpl.config import BASE

API = "https://api.elevenlabs.io"
KEY_FILE = BASE / "elevenlabs.key"
OUTPUT_FORMAT = "mp3_44100_128"        # the API default; available on every plan (192 kbps needs Creator, 44.1 kHz WAV/PCM needs Pro)
DEFAULT_MODEL_LIMIT = 10000            # characters per request of the API's default model (eleven_multilingual_v2), used only while no model is chosen
TEXT_MAX = 100000                      # never send more than this, whatever a model claims
TTS_TIMEOUT_S = 90.0                   # one generation
CALL_TIMEOUT_S = 10.0                  # every other call
CACHE_S = 300.0                        # voices and models are kept in memory this long
AUDIO_MAX = 64 << 20                   # refuse an answer larger than this (a 10,000-character mp3 is a few MB)

PERMS = {"voices": "voices_read", "usage": "user_read", "speech": "text_to_speech", "models": "models_read"}
WHAT = {"voices": "list your voices", "usage": "read your usage", "speech": "generate speech", "models": "list the models"}


# ---------------------------------------------------------------- the key on disk
_K = {"v": None, "read": False, "note": ""}       # the key in memory (read once from the file); note = the amber protection note, if any


def _clean_key(k):
    """A key as typed: surrounding spaces dropped. None when it cannot be a key (empty, spaces or control characters inside, too long)."""
    k = str(k or "").strip()
    if not 8 <= len(k) <= 256 or re.search(r"[\s\x00-\x1f\x7f]", k):
        return None
    return k


def key():
    """The key, or None. Read from the file the first time."""
    if not _K["read"]:
        _K["read"] = True
        try:
            _K["v"] = _clean_key(KEY_FILE.read_text(encoding="utf-8"))
            if _K["v"] and os.name != "nt" and (KEY_FILE.stat().st_mode & 0o077):
                os.chmod(KEY_FILE, 0o600)            # someone loosened it: tighten it again
        except FileNotFoundError:
            _K["v"] = None
        except OSError as e:
            print("WARNING: ElevenLabs: could not read the key file:", redact(str(e)), flush=True)
            _K["v"] = None
    return _K["v"]


def key_info():
    """What the page may know about the key: whether one is set and its last four characters. Never the key."""
    k = key()
    return {"set": bool(k), "last4": k[-4:] if k else "", "note": _K["note"] if k else ""}


def _protect_windows(path):
    """Limit the file to the account running the player (no inherited access). True when icacls succeeded."""
    user = os.environ.get("USERNAME") or ""
    if not user:
        return False
    try:
        r = subprocess.run(["icacls", str(path), "/inheritance:r", "/grant:r", f"{user}:F"], capture_output=True, timeout=15,
                           creationflags=0x08000000)       # CREATE_NO_WINDOW
        return r.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def save_key(raw):
    """Store a new key. Returns (ok, error text). The file is written 0600 from the start (never readable by others, not even briefly)."""
    k = _clean_key(raw)
    if not k:
        return False, "That doesn't look like an API key. Paste the whole key from ElevenLabs."
    tmp = KEY_FILE.with_name(KEY_FILE.name + ".tmp")
    try:
        try:
            tmp.unlink()
        except FileNotFoundError:
            pass
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(k + "\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, KEY_FILE)
    except OSError as e:
        try:
            tmp.unlink()
        except OSError:
            pass
        print("WARNING: ElevenLabs: could not save the key file:", redact(str(e), k), flush=True)
        return False, "Couldn't save the key on the player (the folder is not writable)."
    note = ""
    if os.name == "nt":
        if not _protect_windows(KEY_FILE):
            note = "Couldn't restrict the key file to your account. It is saved, but other accounts on this computer may be able to read it."
            print("WARNING: ElevenLabs: could not restrict the key file to the current account (icacls failed); the key is saved", flush=True)
    else:
        os.chmod(KEY_FILE, 0o600)
    _K.update(v=k, read=True, note=note)
    forget_cache()
    return True, ""


def remove_key():
    try:
        KEY_FILE.unlink()
    except FileNotFoundError:
        pass
    _K.update(v=None, read=True, note="")
    forget_cache()


def redact(text, extra=None):
    """Text with the key (and anything that looks like an xi-api-key header) replaced, for logs and messages."""
    s = str(text)
    for k in (extra, _K["v"]):
        if k:
            s = s.replace(k, "[key hidden]")
    return re.sub(r"(?i)(xi-api-key['\"]?\s*[:=]\s*['\"]?)[^\s'\",}]+", r"\1[key hidden]", s)


# ---------------------------------------------------------------- errors
class ElError(Exception):
    """A failed ElevenLabs call, in plain words. kind: no_key, invalid_key, permission, network, quota, rate, too_long, timeout,
    voice_gone, unexpected. level: "bad" (red) or "warn" (amber), the same boxes as Settings."""

    def __init__(self, kind, message, level="bad", retry_s=None, perm=None, status=None):
        super().__init__(message)
        self.kind, self.message, self.level, self.retry_s, self.perm, self.status = kind, message, level, retry_s, perm, status

    def json(self):
        return {"kind": self.kind, "error": self.message, "level": self.level, "retry_s": self.retry_s, "perm": self.perm}


def no_key():
    return ElError("no_key", "No ElevenLabs key is set. Add one in Settings › System › ElevenLabs.", "warn")


def permission_error(what):
    return ElError("permission", f"This key can't {WHAT[what]}. Give it the {PERMS[what]} permission in ElevenLabs › API keys.", "bad", perm=PERMS[what])


def retry_after(headers):
    """Seconds from a Retry-After header (a number of seconds or an HTTP date), or None when there is none."""
    v = (headers or {}).get("retry-after")
    if not v:
        return None
    v = str(v).strip()
    if v.isdigit():
        return int(v)
    try:
        when = email.utils.parsedate_to_datetime(v).timestamp()
        return max(0, int(round(when - clock.time())))
    except (TypeError, ValueError, OverflowError):
        return None


def _detail(body):
    """(status string, message) from an error body {"detail": {"status", "message"}} (or a 422 list, or plain text)."""
    try:
        d = json.loads(body.decode("utf-8", "replace")) if body else {}
    except ValueError:
        return "", ""
    det = d.get("detail", d) if isinstance(d, dict) else d
    if isinstance(det, dict):
        return str(det.get("status") or det.get("code") or det.get("type") or ""), str(det.get("message") or "")
    if isinstance(det, list) and det and isinstance(det[0], dict):
        return "validation", str(det[0].get("msg") or "")
    if isinstance(det, str):
        return "", det
    return "", ""


def map_error(status, headers, body, what, limit=None):
    """An ElError for a non-2xx answer. `what` is the call ("voices", "usage", "speech", "models"); it names the missing permission."""
    st, msg = _detail(body)
    low = (st + " " + msg).lower()
    if st == "invalid_api_key":
        return ElError("invalid_key", "ElevenLabs doesn't accept this key. Check it, or create a new one in ElevenLabs › API keys.", status=status)
    if "permission" in low or (status == 403 and "quota" not in low):
        return permission_error(what)
    if "quota" in low or st in ("insufficient_credits", "credits_exhausted"):       # documented with 400/401: checked before a bare 401
        return ElError("quota", "Your ElevenLabs character quota is used up for this period. Nothing was generated.", "warn", status=status)
    if st == "max_character_limit_exceeded" or "character limit" in low:
        lim = f" (at most {limit:,} characters for this model)" if limit else ""
        return ElError("too_long", f"The text is too long for one request{lim}. Shorten it or split it into two tracks.", "warn", status=status)
    if status == 401:
        return ElError("invalid_key", "ElevenLabs doesn't accept this key. Check it, or create a new one in ElevenLabs › API keys.", status=status)
    if status == 429 or st in ("too_many_concurrent_requests", "system_busy", "rate_limit_exceeded"):
        sec = retry_after(headers)
        when = f"Try again in {sec} s." if sec is not None else "Try again in a moment."
        return ElError("rate", f"ElevenLabs is busy or too many requests are running on this account. {when}", "warn", retry_s=sec, status=status)
    if st == "voice_not_found" or (status == 404 and what == "speech"):
        return ElError("voice_gone", "That voice is no longer in your account. Press Refresh and pick another.", "warn", status=status)
    extra = f": {redact(msg)[:200]}" if msg else ""
    return ElError("unexpected", f"Unexpected answer from ElevenLabs (HTTP {status}){extra}.", status=status)


# ---------------------------------------------------------------- the one network function (tests replace it)
async def transport(method, path, api_key, params=None, body=None, timeout=CALL_TIMEOUT_S):
    """One HTTP call to ElevenLabs. Returns (status, headers with lower-case names, body bytes). Raises ElError for no network,
    a DNS failure or a timeout. Runs on the event loop without blocking it (aiohttp)."""
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as s:
            async with s.request(method, API + path, params=params, json=body,
                                 headers={"xi-api-key": api_key, "User-Agent": "CueMediaEngine"}) as r:
                buf = bytearray()
                async for chunk in r.content.iter_chunked(1 << 16):      # the whole body (a single read() may stop after the first chunk)
                    buf += chunk
                    if len(buf) > AUDIO_MAX:
                        raise ElError("unexpected", "ElevenLabs sent an answer that is far too large; it was not kept.")
                return r.status, {k.lower(): v for k, v in r.headers.items()}, bytes(buf)
    except asyncio.TimeoutError:
        raise ElError("timeout", f"ElevenLabs didn't answer within {int(timeout)} seconds. Nothing was saved; try again.", "warn") from None
    except aiohttp.ClientConnectorError:
        raise ElError("network", "Can't reach ElevenLabs. Check this player's internet connection and DNS.") from None
    except (aiohttp.ClientError, OSError) as e:
        raise ElError("network", "Can't reach ElevenLabs (" + redact(e.__class__.__name__) + "). Check this player's internet connection.") from None



_TEST = os.environ.get("CP_TEST_ELEVENLABS")      # test hook, inert unless set: a folder with fake.json; the network is never used then
if _TEST:
    async def transport(method, path, api_key, params=None, body=None, timeout=CALL_TIMEOUT_S):      # noqa: F811 (replaces the real one)
        """A fake ElevenLabs for the instance and Playwright tests. fake.json: {"key": the accepted key, "voices" | "usage" | "models"
        | "speech": {"status", "body" (JSON) or "file" (a file in the folder), "headers", "delay"}}. Each call is appended to
        calls.jsonl WITHOUT the key (whether the right key was sent is recorded as key_ok)."""
        from pathlib import Path as _P
        folder = _P(_TEST)
        try:
            spec = json.loads((folder / "fake.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            spec = {}
        what = "voices" if path.startswith("/v2/voices") else "usage" if path == "/v1/user/subscription" else "models" if path == "/v1/models" else "speech"
        good = api_key == spec.get("key")
        with open(folder / "calls.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps({"what": what, "method": method, "path": path, "params": params, "body": body, "key_ok": good}) + "\n")
        r = spec.get(what) or {"status": 200, "body": {}}
        if r.get("delay"):
            await asyncio.wait_for(asyncio.sleep(float(r["delay"])), timeout)
        if r.get("network"):
            raise ElError("network", "Can't reach ElevenLabs. Check this player's internet connection and DNS.")
        if not good:
            return 401, {}, json.dumps({"detail": {"status": "invalid_api_key", "message": "Invalid API key"}}).encode()
        data = (folder / r["file"]).read_bytes() if r.get("file") else json.dumps(r.get("body", {})).encode()
        headers = {k.lower(): str(v) for k, v in (r.get("headers") or {}).items()}
        headers.setdefault("content-type", "audio/mpeg" if r.get("file") else "application/json")
        return int(r.get("status", 200)), headers, data

async def _call(what, method, path, params=None, body=None, timeout=CALL_TIMEOUT_S, api_key=None, limit=None):
    k = api_key or key()
    if not k:
        raise no_key()
    status, headers, data = await transport(method, path, k, params=params, body=body, timeout=timeout)
    if not 200 <= status < 300:
        raise map_error(status, headers, data, what, limit)
    return headers, data


def _json(data):
    try:
        return json.loads(data.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        raise ElError("unexpected", "Unexpected answer from ElevenLabs (not JSON).") from None


# ---------------------------------------------------------------- voices, usage, models
_C = {"voices": None, "models": None}       # {"t": monotonic, "v": value}


def cached_models():
    """The model list from the last /v1/models call (None when not fetched yet or the key can't read models)."""
    c = _C["models"]
    return c["v"] if c else None


def forget_cache():
    _C["voices"] = _C["models"] = None


def kind_of(v):
    """own / cloned / library, from the voice's category and is_owner."""
    cat = str(v.get("category") or "")
    if cat in ("cloned", "professional"):
        return "cloned"
    if v.get("is_owner") is True or cat == "generated":
        return "own"
    return "library"


def parse_voices(d):
    """[{id, name, kind, preview}] from one /v2/voices page; entries without an id are skipped. preview only for an https URL."""
    out = []
    for v in (d.get("voices") if isinstance(d, dict) else None) or []:
        if not isinstance(v, dict) or not isinstance(v.get("voice_id"), str) or not v["voice_id"]:
            continue
        pv = v.get("preview_url")
        out.append({"id": v["voice_id"][:64], "name": str(v.get("name") or v["voice_id"])[:80], "kind": kind_of(v),
                    "preview": pv if isinstance(pv, str) and pv.startswith("https://") else None})
    return out


async def list_voices(refresh=False):
    """Every voice of the account (up to 10 pages of 100), cached for CACHE_S."""
    c = _C["voices"]
    if c and not refresh and clock.monotonic() - c["t"] < CACHE_S:
        return c["v"]
    voices, token = [], None
    for _ in range(10):
        params = {"page_size": "100", **({"next_page_token": token} if token else {})}
        _, data = await _call("voices", "GET", "/v2/voices", params=params)
        d = _json(data)
        voices += parse_voices(d)
        token = d.get("next_page_token") if isinstance(d, dict) and d.get("has_more") else None
        if not token:
            break
    seen, uniq = set(), []
    for v in voices:
        if v["id"] not in seen:
            seen.add(v["id"])
            uniq.append(v)
    uniq.sort(key=lambda v: ({"own": 0, "cloned": 1, "library": 2}[v["kind"]], v["name"].lower()))
    _C["voices"] = {"t": clock.monotonic(), "v": uniq}
    return uniq


def parse_usage(d):
    """{used, limit, left, reset} from /v1/user/subscription, or None when the numbers are missing."""
    if not isinstance(d, dict):
        return None
    used, lim = d.get("character_count"), d.get("character_limit")
    if not all(isinstance(x, int) and not isinstance(x, bool) for x in (used, lim)):
        return None
    reset = d.get("next_character_count_reset_unix")
    return {"used": used, "limit": lim, "left": max(0, lim - used), "reset": reset if isinstance(reset, int) else None}


async def usage():
    """The character quota (never cached: it changes with every generation)."""
    _, data = await _call("usage", "GET", "/v1/user/subscription")
    return parse_usage(_json(data))


def parse_models(d):
    """[{id, name, limit}] of the text-to-speech models in /v1/models. limit only when the answer carries a whole number for it."""
    out = []
    for m in d if isinstance(d, list) else []:
        if not isinstance(m, dict) or not isinstance(m.get("model_id"), str) or m.get("can_do_text_to_speech") is False:
            continue
        lim = m.get("maximum_text_length_per_request")
        out.append({"id": m["model_id"][:64], "name": str(m.get("name") or m["model_id"])[:80],
                    "limit": lim if isinstance(lim, int) and not isinstance(lim, bool) and lim > 0 else None})
    return out


async def list_models():
    """The models the key may read, or None when it lacks models_read (the page then shows only "Default model")."""
    c = _C["models"]
    if c and clock.monotonic() - c["t"] < CACHE_S:
        return c["v"]
    try:
        _, data = await _call("models", "GET", "/v1/models")
        v = parse_models(_json(data))
    except ElError as e:
        if e.kind != "permission":
            raise
        v = None
    _C["models"] = {"t": clock.monotonic(), "v": v}
    return v


async def test_key():
    """The Test key result: {"level": ok|warn|bad, "title", "msg", "usage"}. voices_read decides valid or not; user_read only adds the usage."""
    if not key():
        return {"level": "bad", "title": "No key", "msg": "Save a key first.", "usage": None}
    try:
        await _call("voices", "GET", "/v2/voices", params={"page_size": "1"})
    except ElError as e:
        if e.kind in ("network", "timeout"):
            return {"level": "warn", "title": "Can't reach ElevenLabs", "msg": e.message, "usage": None}
        if e.kind == "rate":
            return {"level": "warn", "title": "ElevenLabs is busy", "msg": e.message, "usage": None}
        title = "Key lacks a permission" if e.kind == "permission" else "Key not valid" if e.kind == "invalid_key" else "Test failed"
        return {"level": "bad", "title": title, "msg": e.message, "usage": None}
    try:
        u = await usage()
    except ElError as e:
        if e.kind == "permission":
            return {"level": "ok", "title": "Key works", "msg": "Usage isn't shown because the key lacks the usage permission (user_read).", "usage": None}
        return {"level": "ok", "title": "Key works", "msg": "Voices can be listed. The usage could not be read just now.", "usage": None}
    return {"level": "ok", "title": "Key works", "msg": "Voices can be listed and the usage read.", "usage": u}


async def speech(voice_id, text, model_id=None, voice_settings=None, limit=None):
    """Generate speech. Returns the audio (mp3 bytes). Raises ElError."""
    body = {"text": text}
    if model_id:
        body["model_id"] = model_id
    if voice_settings:
        body["voice_settings"] = voice_settings
    headers, data = await _call("speech", "POST", "/v1/text-to-speech/" + voice_id, params={"output_format": OUTPUT_FORMAT},
                                body=body, timeout=TTS_TIMEOUT_S, limit=limit)
    ctype = headers.get("content-type", "")
    if not data or "json" in ctype or "text/" in ctype:
        raise ElError("unexpected", "Unexpected answer from ElevenLabs (no audio came back).")
    return data
