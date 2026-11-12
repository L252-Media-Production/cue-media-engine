"""Golden page / API capture: fetch the pages and API outputs of a test instance and normalise what legitimately varies between runs.

Used by tests/golden/capture.py (writes tests/golden/*) and tests/test_pages_equal.py (compares sha256). What is normalised is documented in
tests/golden/README.md; keep both in step.
"""
import hashlib, json, re, time, urllib.request

# (name, path). HTML pages are compared as raw bytes; JSON outputs after normalisation.
TARGETS = [("root.html", "/"), ("help.html", "/help"), ("stage.html", "/stage"), ("variables.html", "/variables"),
           ("api_state.json", "/api/state"), ("api_playlists.json", "/api/playlists"), ("api_variables.json", "/api/variables"),
           ("api_library.json", "/api/library")]
# keys removed at any depth (values depend on the machine, the clock or on start-up timing)
DROP_KEYS = {"mem", "rev", "storage", "disk_free", "allowance", "storage_free", "storage_library"}
# keys kept but with the value replaced by "<varies>": the RAM indicator depends on how far the background warm-up has got when the page is fetched (2.7.3)
MASK_KEYS = {"ram", "ram_in"}
DROP_VARS = {"storage_free", "storage_library"}            # entries of /api/variables "vars" with these names
PORT_RE = re.compile(r"127\.0\.0\.1:\d+")


def setup(api):
    """Fixed content for the playlist outputs: two playlists, a loop end action and a track crossfade time (all WAV files of libgen)."""
    api.post("/api/playlists", {"name": "Golden A"})
    api.post("/api/playlists", {"name": "Golden B"})
    api.post("/api/playlists/0/add", {"files": ["tone_a.wav", "tone_b.wav", "Sub/tone_d.wav"]})
    api.post("/api/playlists/1/add", {"files": ["short_1s.wav", "Name with spaces & ünï.wav"]})
    api.cmd("0/1/end/loop")
    api.cmd("0/0/xftime/2")
    time.sleep(0.5)


def _scrub(x):
    if isinstance(x, dict):
        if "checks" in x and "summary" in x and "status" in x:        # the 2.8.0 health block: status / detail are the old light; the checks depend on the machine's disk, devices and uptime
            return {k: (v if k in ("status", "detail") else "<varies>") for k, v in x.items()}
        return {k: ("<varies>" if k in MASK_KEYS else _scrub(v)) for k, v in x.items() if k not in DROP_KEYS}
    if isinstance(x, list):
        return [_scrub(v) for v in x if not (isinstance(v, dict) and v.get("name") in DROP_VARS)]
    if isinstance(x, str):
        return PORT_RE.sub("127.0.0.1:PORT", x)
    return x


def normalise(name, data: bytes) -> bytes:
    if name.endswith(".json"):
        return json.dumps(_scrub(json.loads(data)), indent=1, sort_keys=True, ensure_ascii=False).encode("utf-8") + b"\n"
    return data


def fetch(base_url, path):
    with urllib.request.urlopen(base_url + path, timeout=20) as r:
        return r.read()


def capture(base_url):
    """-> {name: normalised bytes}"""
    return {name: normalise(name, fetch(base_url, path)) for name, path in TARGETS}


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()
