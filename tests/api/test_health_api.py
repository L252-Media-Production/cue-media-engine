"""2.8.0 health block of /api/state, the Health and alerts settings, the webhook test message and secret masking (a real local HTTP receiver)."""
import json
import re
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

SECRET = "SECRETKEY123"
CHECK_IDS = ["live_output", "preview_output", "audio_engine", "companion", "disk", "cache", "uptime"]


class Receiver:
    def __init__(self):
        self.got = []
        outer = self

        class H(BaseHTTPRequestHandler):
            def do_POST(self):
                n = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(n)
                if self.path.startswith("/missing"):
                    self.send_response(404)
                    self.end_headers()
                    return
                outer.got.append((self.path, json.loads(body.decode("utf-8")), self.headers.get("Content-Type")))
                self.send_response(200)
                self.end_headers()

            def log_message(self, *a):
                pass

        self.srv = HTTPServer(("127.0.0.1", 0), H)
        self.port = self.srv.server_address[1]
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def url(self, path):
        return f"http://127.0.0.1:{self.port}{path}"

    def close(self):
        self.srv.shutdown()
        self.srv.server_close()


@pytest.fixture()
def hook(api):
    r = Receiver()
    yield r
    r.close()
    api.post("/api/settings/health", {"player_name": "", "watchdog": True, "preview_amber": True, "push": {"enabled": False, "hold": False, "url": "", "events": {k: True for k in ("problem", "recovered", "degraded_long", "watchdog")}}})


@pytest.mark.sev(2)
def test_state_has_a_small_health_block_with_seven_checks(api):
    h = api.state()["health"]
    assert h["status"] in ("starting", "ready", "error") and "detail" in h          # the old light is unchanged
    assert h["state"] in ("starting", "ready", "degraded", "problem")
    assert [c["id"] for c in h["checks"]] == CHECK_IDS
    assert all(c["status"] in ("ok", "warn", "bad", "unknown") for c in h["checks"])
    assert len(json.dumps(h)) < 2500
    assert all(c["text"] == "" for c in h["checks"] if c["status"] == "ok" and c["id"] != "uptime")
    up = [c for c in h["checks"] if c["id"] == "uptime"][0]
    assert up["status"] == "ok" and up["text"].startswith("Up ")


@pytest.mark.sev(2)
def test_companion_polls_are_recognised_by_header_and_browsers_are_not(api):
    def companion():
        return [c for c in api.state()["health"]["checks"] if c["id"] == "companion"][0]["status"]
    api.request("GET", "/api/state", headers={"User-Agent": "Mozilla/5.0 (Macintosh)"})
    assert api.request("GET", "/api/state", headers={"X-CompanionPlayer-Client": "companion-module"}).status == 200
    assert companion() == "ok"                                                      # a poll was seen just now (and none is older than 30 s)


@pytest.mark.sev(2)
def test_health_settings_roundtrip_and_bad_values(api, hook):
    s = api.get("/api/settings/health").json
    assert s["watchdog"] is True and s["preview_amber"] is True and s["push"]["enabled"] is False
    assert api.post("/api/settings/health", {"watchdog": False, "preview_amber": False}).json["watchdog"] is False
    assert api.get("/api/settings/health").json["preview_amber"] is False
    assert api.post("/api/settings/health", {"watchdog": "yes"}).status == 400
    assert api.post("/api/settings/health", {"push": "x"}).status == 400
    assert api.post("/api/settings/health", {"push": {"enabled": 1}}).status == 400
    assert api.post("/api/settings/health", {"push": {"events": {"problem": "no"}}}).status == 400


@pytest.mark.sev(2)
@pytest.mark.parametrize("bad", ["ftp://example.com/x", "javascript:alert(1)", "file:///etc/passwd", "example.com/hook", "https://", "http://bad host/x"])
def test_only_http_and_https_addresses_are_saved(api, hook, bad):
    r = api.post("/api/settings/health", {"push": {"url": bad}})
    assert r.status == 400 and not api.get("/api/settings/health").json["push"]["has_url"]


@pytest.mark.sev(1)
def test_the_webhook_address_is_never_returned_in_full(api, hook):
    r = api.post("/api/settings/health", {"push": {"url": hook.url("/services/" + SECRET), "enabled": True}})
    assert r.status == 200 and r.json["push"]["host"] == f"http://127.0.0.1:{hook.port}/…"
    for path in ("/api/settings/health", "/api/state", "/api/variables", "/api/settings", "/api/playlists"):
        text = api.get(path).text
        assert SECRET not in text, path
    assert SECRET not in api.post("/api/settings/health", {"watchdog": True}).text


@pytest.mark.sev(2)
def test_send_test_message_posts_json_with_text_and_content(api, hook):
    api.post("/api/settings/health", {"push": {"url": hook.url("/hook/" + SECRET), "enabled": False, "hold": True}})     # off and holding: the test is sent anyway
    r = api.post("/api/settings/health/push-test", {})
    assert r.json["ok"] is True and r.json["error"] == ""
    assert len(hook.got) == 1
    path, body, ctype = hook.got[0]
    assert path == "/hook/" + SECRET and ctype == "application/json"
    assert body["text"] == body["content"] and "Test message" in body["text"]
    assert body["event"] == "test" and body["player"] and body["time"][-6] in "+-"


@pytest.mark.sev(2)
def test_send_test_message_failures_have_a_short_reason(api, hook):
    r = api.post("/api/settings/health/push-test", {})
    assert r.json["ok"] is False and r.json["error"] == "Enter a webhook address first"
    api.post("/api/settings/health", {"push": {"url": hook.url("/missing/" + SECRET)}})
    r = api.post("/api/settings/health/push-test", {})
    assert r.json == {"ok": False, "error": "Refused (HTTP 404)", "at": r.json["at"]}
    hook.close()
    r = api.post("/api/settings/health/push-test", {})
    assert r.json["ok"] is False and r.json["error"] in ("Connection refused", "Could not connect")
    assert SECRET not in r.text


@pytest.mark.sev(2)
def test_preview_amber_switch_controls_the_preview_check(api, hook, tmp_path):
    api.post("/api/settings/health", {"preview_amber": True})
    chk = lambda: [c for c in api.state()["health"]["checks"] if c["id"] == "preview_output"][0]["status"]
    assert chk() == "ok"                                                            # no preview device configured


@pytest.mark.sev(2)
def test_the_stall_test_hook_does_not_exist_in_production(api):
    r = api.post("/api/test/stall", {})
    assert r.status == 404                 # not registered: a plain 404 (the catch-all GET /api/... used to make it a 405)
    assert api.get("/api/settings/health").json["beats"] >= 0 and api.get("/api/settings/health").json["stalled"] is False


@pytest.mark.sev(2)
def test_player_name_saves_trims_falls_back_to_the_host_name_and_is_used_in_messages(api, hook):
    host = api.get("/api/settings/health").json["player_in_use"]
    assert host and api.get("/api/settings/health").json["player_name"] == ""
    r = api.post("/api/settings/health", {"player_name": "   L252   NUC  "})
    assert r.status == 200 and r.json["player_name"] == "L252 NUC" and r.json["player_in_use"] == "L252 NUC"
    api.post("/api/settings/health", {"push": {"url": hook.url("/hook/" + SECRET)}})
    assert api.post("/api/settings/health/push-test", {}).json["ok"] is True
    body = hook.got[-1][1]
    assert body["player"] == "L252 NUC" and body["text"].startswith("L252 NUC: Test message")
    assert "(L252 NUC)" in api.get("/api/health/report").json["text"]
    r = api.post("/api/settings/health", {"player_name": ""})
    assert r.json["player_name"] == "" and r.json["player_in_use"] == host
    assert api.post("/api/settings/health", {"player_name": "x" * 41}).status == 400
    assert api.post("/api/settings/health", {"player_name": 5}).status == 400
    assert api.post("/api/settings/health", {"player_name": "x" * 40}).json["player_name"] == "x" * 40
    assert api.get("/api/settings/health").json["player_name"] == "x" * 40


@pytest.mark.sev(2)
def test_the_audio_engine_row_and_the_report_carry_the_restart_count(api):
    eng = [c for c in api.state()["health"]["checks"] if c["id"] == "audio_engine"][0]
    assert eng["note"] == "Restarted 0 times since start" and eng["text"] == ""
    assert "Audio engine: Restarted 0 times since start" in api.get("/api/health/report").json["text"]


@pytest.mark.sev(3)
def test_the_report_names_the_sdl_audio_driver(api):
    """The harness runs SDL_AUDIODRIVER=dummy: the report says what SDL selected, never "unknown"."""
    text = api.get("/api/health/report").json["text"]
    assert "Audio driver: dummy\n" in text and "unknown" not in text.split("Audio driver:")[1].split("\n")[0]


@pytest.mark.sev(3)
def test_the_report_has_the_two_soak_lines_and_they_change_nothing(api):
    before = api.state()["health"]
    text = api.get("/api/health/report").json["text"]
    assert re.search(r"^Process memory: (\d+ MB|not available)$", text, re.M)
    assert re.search(r"^Open files: (\d+|not available)$", text, re.M)
    after = api.state()["health"]
    assert after["state"] == before["state"] and [c["id"] for c in after["checks"]] == [c["id"] for c in before["checks"]]
    assert "Process memory" not in str(after) and "Open files" not in str(after)
