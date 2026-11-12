"""Pages, state and read-only endpoints."""
import json, socket, urllib.parse
import pytest

STATE_KEYS = ["focus_id", "focus_name", "focus_playlist", "focus_playlist_num", "focus_is_live", "live_id", "live_name", "remaining", "state",
              "play_mode", "go_transition", "preview_volume", "status", "on_top", "duck_gr", "duck_threshold", "duck_ratio", "duck_attack",
              "duck_release", "duck_hold", "top_level", "live_volume", "preview_state", "output", "rev", "health", "mem", "preview", "warning",
              "live_pos", "live_dur", "live_in", "live_out", "live_fid", "trim_fade_ms", "live_end", "live_pass", "live_passes"]


@pytest.mark.covers("http.GET /", "http.GET /variables", "http.GET /help", "http.GET /stage", "http.GET /stage/", "http.GET /stage/{v}")
@pytest.mark.parametrize("path", ["/", "/variables", "/help", "/stage", "/stage/", "/stage/a", "/stage/b", "/stage/c"])
def test_pages_served(api, path):
    r = api.get(path)
    assert r.status == 200 and "<html" in r.text.lower() or "<!doctype" in r.text.lower()
    assert len(r.text) > 500


@pytest.mark.sev(3)
def test_stage_unknown_variant_is_404(api):
    assert api.get("/stage/zzz").status == 404


@pytest.mark.covers("http.GET /api/state")
def test_state_has_all_fields(api):
    s = api.state()
    missing = [k for k in STATE_KEYS if k not in s]
    assert not missing, missing
    assert s["state"] == "stopped" and s["live_id"] == "-" and s["remaining"] == "--:--"


@pytest.mark.covers("http.GET /api/variables", "var.*")
def test_variables_shape_and_values(api, std):
    d = api.get("/api/variables").json
    assert d["prefix"] == "mp_" and "vars" in d
    byname = {v["name"]: v for v in d["vars"]}
    for k in ("state", "live_name", "live_volume", "focus_name", "pl0_name", "pl0_count", "pl0_t0", "focus_t0", "focus_count", "live_fader_l"):
        assert k in byname, k
    assert byname["pl0_name"]["value"] == "A" and byname["pl0_count"]["value"] == "3" and byname["pl0_t1"]["value"] == "tone_b"
    assert byname["focus_count"]["value"] == "3" and byname["focus_t2"]["value"] == "tone_c" and byname["focus_t3"]["value"] == "-"
    s = api.state()
    for k in ("state", "live_volume", "focus_name", "duck_ratio", "play_mode"):
        assert byname[k]["value"] == s[k], k


@pytest.mark.sev(4)
def test_variable_descriptions_are_complete(api, std):
    bad = []
    for v in api.get("/api/variables").json["vars"]:
        info = v.get("info") or ""
        if not info.strip():
            bad.append(f"{v['name']}: no description")
        elif "  " in info:
            bad.append(f"{v['name']}: {info!r} (a word is missing)")
    assert not bad, bad[:5]


@pytest.mark.covers("http.GET /api/playlists", "http.GET /api/meters", "http.GET /api/devices", "http.GET /api/storage", "http.GET /api/ffmpeg",
                    "http.GET /api/formats", "http.GET /api/scan", "http.GET /api/monitor", "http.GET /api/settings", "http.GET /api/settings/warning",
                    "http.GET /api/settings/transition", "http.GET /api/settings/top", "http.GET /api/settings/folders", "http.GET /api/triggers",
                    "http.GET /api/preview", "http.GET /api/library")
@pytest.mark.parametrize("path", ["/api/playlists", "/api/meters", "/api/devices", "/api/storage", "/api/ffmpeg", "/api/formats", "/api/scan",
                                  "/api/monitor", "/api/settings", "/api/settings/warning", "/api/settings/transition", "/api/settings/top",
                                  "/api/settings/folders", "/api/triggers", "/api/preview", "/api/library"])
def test_read_only_endpoints_return_json(api, path):
    r = api.get(path)
    assert r.status == 200, r
    assert r.json is not None


@pytest.mark.covers("http.GET /api/{tail}")
def test_unknown_api_command_is_reported_not_crashed(api):
    c = api.cmd("definitely_not_a_command")
    assert c["result"] == "unknown"
    assert "state" in c


@pytest.mark.covers("http.GET /api/live")
def test_live_stream_sends_meter_events(target):
    base = target["api"].base
    u = urllib.parse.urlparse(base)
    s = socket.create_connection((u.hostname, u.port), timeout=5)
    s.sendall(b"GET /api/live HTTP/1.1\r\nHost: x\r\n\r\n")
    buf = b""
    s.settimeout(5)
    while b"data: " not in buf or buf.count(b"\n\n") < 2:
        buf += s.recv(4096)
    s.close()
    ev = [l for l in buf.decode().split("\n") if l.startswith("data: ")][0][6:]
    d = json.loads(ev)
    assert "m" in d and "pv" in d


@pytest.mark.sev(2)
def test_live_stream_limit_is_16(target):
    import time
    u = urllib.parse.urlparse(target["api"].base)
    socks = []

    def open_stream():
        s = socket.create_connection((u.hostname, u.port), timeout=5)
        s.sendall(b"GET /api/live HTTP/1.1\r\nHost: x\r\n\r\n")
        s.settimeout(5)
        return s, s.recv(200).split(b"\r\n")[0]
    try:
        for attempt in range(25):                       # the slot of a stream closed a moment ago is released within ~0.1 s
            ok = True
            for _ in range(16):
                s, head = open_stream()
                socks.append(s)
                if b"200" not in head:
                    ok = False
                    break
            if ok:
                break
            for s in socks:
                s.close()
            socks.clear()
            time.sleep(0.2)
        assert len(socks) == 16, "could not open 16 live streams"
        s, head = open_stream()
        socks.append(s)
        assert b"429" in head, head
    finally:
        for s in socks:
            s.close()
        time.sleep(0.6)


@pytest.mark.sev(2)
def test_cross_site_requests_are_refused(api):
    r = api.request("GET", "/api/stopall", headers={"Sec-Fetch-Site": "cross-site"})
    assert r.status == 403
    r = api.request("POST", "/api/settings/top", body={"ratio": 6}, headers={"Origin": "http://evil.example"})
    assert r.status == 403
    r = api.request("GET", "/api/state", headers={"Sec-Fetch-Site": "same-origin"})
    assert r.status == 200
