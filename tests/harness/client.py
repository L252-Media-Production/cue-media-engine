"""HTTP/OSC client for the tests. Every HTTP call is timed and recorded in CALLS (the report shows the timings per endpoint)."""
import json, re, time, urllib.error, urllib.parse, urllib.request

CALLS = []            # {test, method, path, status, ms}
CURRENT = [None]      # nodeid of the running test


class Resp:
    def __init__(self, status, body, ms, headers=None):
        self.status, self.body, self.ms, self.headers = status, body, ms, headers or {}

    @property
    def text(self):
        return self.body.decode("utf-8", "replace")

    @property
    def json(self):
        try:
            return json.loads(self.body.decode("utf-8", "replace"))
        except ValueError:
            return None

    def __repr__(self):
        return f"<{self.status} {self.text[:200]!r}>"


def norm_path(path):
    """Group calls by endpoint: numbers become {n}, command words after /api/ stay."""
    p = path.split("?")[0]
    return re.sub(r"/\d+(?=/|$)", "/{n}", p)


class Api:
    def __init__(self, base, osc_port=None, sink=None):
        self.base = base.rstrip("/")
        self.osc_port, self.sink, self._osc = osc_port, sink, None

    # ---- raw
    def request(self, method, path, query=None, body=None, raw=None, headers=None, timeout=30):
        url = self.base + path
        if query:
            url += "?" + urllib.parse.urlencode(query)
        data, h = None, dict(headers or {})
        if body is not None:
            data = json.dumps(body).encode()
            h.setdefault("Content-Type", "application/json")
        elif raw is not None:
            data = raw if isinstance(raw, bytes) else raw.encode()
        req = urllib.request.Request(url, data=data, method=method, headers=h)
        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                resp = Resp(r.status, r.read(), (time.perf_counter() - t0) * 1000, dict(r.headers))
        except urllib.error.HTTPError as e:
            resp = Resp(e.code, e.read(), (time.perf_counter() - t0) * 1000, dict(e.headers))
        CALLS.append({"test": CURRENT[0], "method": method, "path": norm_path(path), "status": resp.status, "ms": round(resp.ms, 2)})
        return resp

    def get(self, _path, **q):
        return self.request("GET", _path, query=q or None)

    def post(self, path, body=None, **kw):
        return self.request("POST", path, body={} if body is None and "raw" not in kw else body, **kw)

    def delete(self, _path, **q):
        return self.request("DELETE", _path, query=q or None)

    def upload(self, filename, content, folder=None, playlist=None, field="file"):
        """POST /api/library/upload as multipart. content is bytes."""
        b = "----cptest%d" % int(time.time() * 1000000)
        data = (f'--{b}\r\nContent-Disposition: form-data; name="{field}"; filename="{filename}"\r\nContent-Type: application/octet-stream\r\n\r\n').encode() \
            + content + f"\r\n--{b}--\r\n".encode()
        q = {}
        if folder:
            q["folder"] = folder
        if playlist is not None:
            q["playlist"] = playlist
        return self.request("POST", "/api/library/upload", query=q or None, raw=data, headers={"Content-Type": f"multipart/form-data; boundary={b}"}, timeout=120)

    # ---- commands (GET /api/<path>): returns the parsed JSON {"result":..., **snapshot}
    def cmd(self, path, ms=None):
        path = "/".join(urllib.parse.quote(x, safe="") for x in path.strip("/").split("/"))
        r = self.request("GET", "/api/" + path, query={"ms": ms} if ms is not None else None)
        assert r.status == 200, f"/api/{path} -> HTTP {r.status}: {r.text[:200]}"
        return r.json

    def res(self, path, ms=None):
        """The command's result word ("ok", "invalid", "unknown", "no cue" ...)."""
        return self.cmd(path, ms)["result"]

    # ---- state
    def state(self):
        r = self.get("/api/state")
        assert r.status == 200
        return r.json

    def playlists(self):
        return self.get("/api/playlists").json

    def library(self):
        return self.get("/api/library").json

    def wait_for(self, pred, timeout=8.0, interval=0.08, desc="condition"):
        t0, last = time.time(), None
        while time.time() - t0 < timeout:
            last = self.state()
            v = pred(last)
            if v:
                return last
            time.sleep(interval)
        raise AssertionError(f"timed out after {timeout}s waiting for {desc}; last state={ {k: last.get(k) for k in ('state','live_id','live_name','live_pos','focus_id','loading')} if last else None }")

    def wait_state(self, name, timeout=8.0):
        return self.wait_for(lambda s: s["state"] == name, timeout, desc=f"state {name!r}")

    def wait_playing(self, live_id=None, timeout=8.0):
        return self.wait_for(lambda s: s["state"] == "playing" and (live_id is None or s["live_id"] == live_id), timeout,
                             desc=f"playing {live_id or ''}")

    # ---- OSC
    def osc(self, address, *args):
        from pythonosc.udp_client import SimpleUDPClient
        if self._osc is None:
            self._osc = SimpleUDPClient("127.0.0.1" if "127.0.0.1" in self.base or "localhost" in self.base else urllib.parse.urlparse(self.base).hostname, self.osc_port)
        self._osc.send_message(address, list(args) if args else [])
        CALLS.append({"test": CURRENT[0], "method": "OSC", "path": address, "status": 0, "ms": 0})

    def osc_raw(self, data: bytes):
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        host = urllib.parse.urlparse(self.base).hostname
        s.sendto(data, (host, self.osc_port))
        s.close()
