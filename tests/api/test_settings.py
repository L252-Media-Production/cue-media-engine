"""Settings endpoints, time warnings, devices, downloads (input checks only)."""
import json
import pytest


@pytest.fixture()
def keep_companion_target(api):
    """/api/settings repoints the OSC output; put it back afterwards."""
    s = api.get("/api/settings").json
    yield s
    api.post("/api/settings", {"companion_host": s["companion_host"], "companion_osc_port": s["companion_osc_port"]})


@pytest.mark.sev(2)
@pytest.mark.covers("http.GET /api/settings", "http.POST /api/settings")
def test_companion_target_settings(api, keep_companion_target):
    orig = keep_companion_target
    assert set(orig) >= {"companion_host", "companion_osc_port", "config_file"}
    r = api.post("/api/settings", {"companion_host": "127.0.0.1", "companion_osc_port": orig["companion_osc_port"]})
    assert r.status == 200 and r.json["ok"] and r.json["target"] == f"127.0.0.1:{orig['companion_osc_port']}"
    assert api.state()["feedback"] == r.json["target"]
    r = api.post("/api/settings", {"companion_host": " localhost ", "companion_osc_port": str(orig["companion_osc_port"])})
    assert r.status == 200 and api.get("/api/settings").json["companion_host"] == "localhost"


@pytest.mark.sev(2)
@pytest.mark.covers("http.POST /api/settings")
@pytest.mark.parametrize("bad", [{}, {"companion_host": ""}, {"companion_host": "bad host!"}, {"companion_host": "a;b"}, {"companion_host": "x", "companion_osc_port": 0},
                                 {"companion_host": "x", "companion_osc_port": 65536}, {"companion_host": "x", "companion_osc_port": "abc"},
                                 {"companion_host": "x", "companion_osc_port": -1}, {"companion_host": "x"}, {"companion_host": "<script>", "companion_osc_port": 1},
                                 {"companion_host": "x" * 5000, "companion_osc_port": 1}])
def test_companion_target_rejects_bad_input_and_keeps_the_old_one(api, keep_companion_target, bad):
    before = api.get("/api/settings").json
    r = api.post("/api/settings", bad)
    assert r.status == 400, (bad, r.status, r.text[:100])
    assert api.get("/api/settings").json == before


@pytest.mark.sev(2)
@pytest.mark.covers("http.POST /api/settings", "http.POST /api/settings/companion/test")
def test_well_formed_unresolvable_host_is_saved_and_send_test_says_host_not_found(api, keep_companion_target):
    r = api.post("/api/settings", {"companion_host": "no-such-host.invalid", "companion_osc_port": 12321})
    assert r.status == 200 and r.json["ok"] and r.json["target"] == "no-such-host.invalid:12321" and r.json["host_found"] is False, r.text[:200]
    s = api.get("/api/settings").json
    assert s["companion_host"] == "no-such-host.invalid" and s["host_found"] is False
    assert api.state()["feedback"] == "no-such-host.invalid:12321"
    t = api.post("/api/settings/companion/test").json
    assert t["ok"] is False and t["error"] == "Host not found" and t["sent_to"] == "no-such-host.invalid:12321", t
    assert api.get("/api/state").status == 200, "the player is fine"


@pytest.mark.sev(2)
@pytest.mark.covers("http.POST /api/settings")
def test_a_resolvable_host_after_an_unresolvable_one_works_again(api, keep_companion_target, sink):
    import time
    assert api.post("/api/settings", {"companion_host": "no-such-host.invalid", "companion_osc_port": 12321}).status == 200
    s = keep_companion_target
    r = api.post("/api/settings", {"companion_host": s["companion_host"], "companion_osc_port": s["companion_osc_port"]})
    assert r.status == 200 and r.json["host_found"] is True
    t0 = time.time()
    t = api.post("/api/settings/companion/test").json
    assert t["ok"] is True
    api.get("/api/resend")
    deadline = time.time() + 4
    while time.time() < deadline and not [m for m in sink.since(t0) if m[1] == "/custom-variable/mp_live_name/value"]:
        time.sleep(0.1)
    assert [m for m in sink.since(t0) if m[1] == "/custom-variable/mp_live_name/value"]


@pytest.mark.sev(2)
@pytest.mark.covers("http.POST /api/settings/companion/test")
def test_test_message_is_reported_with_its_time_and_goes_stale(api):
    t = api.post("/api/settings/companion/test").json
    st = api.state()
    assert st["test_message"] == t["at"] and isinstance(st["test_sent_at"], float)
@pytest.mark.sev(2)
def test_settings_are_written_to_config_json(api, managed, keep_companion_target):
    api.post("/api/settings/top", {"ratio": 9})
    api.post("/api/settings/transition", {"default": "crossfade", "crossfade_s": 4})
    cfg = json.loads((managed.workdir / "config.json").read_text("utf-8"))
    assert cfg["duck_ratio"] == 9.0 and cfg["default_transition"] == "crossfade" and cfg["crossfade_ms"] == 4000
    assert cfg["http_port"] == managed.port, "other keys in config.json must survive"
    api.post("/api/settings/transition", {"default": "cut", "crossfade_s": 3})


@pytest.mark.sev(2)
@pytest.mark.covers("http.GET /api/settings/warning", "http.POST /api/settings/warning")
def test_time_warning_settings(api):
    d = api.get("/api/settings/warning").json
    assert d["on"] is True and [w["t"] for w in d["warnings"]] == [60, 30]
    r = api.post("/api/settings/warning", {"warnings": [{"t": 10, "c": "#FF0000"}, {"t": 120.4, "c": "#00ff00"}, {"t": 45, "c": "#0000ff"}]})
    assert r.status == 200
    d = api.get("/api/settings/warning").json
    assert d["set"] is True and d["warnings"] == [{"t": 120, "c": "#00ff00"}, {"t": 45, "c": "#0000ff"}, {"t": 10, "c": "#ff0000"}], "sorted longest first, colours lower-cased"
    assert (d["t1"], d["t2"], d["c1"], d["c2"]) == (120, 10, "#00ff00", "#ff0000")
    assert api.state()["warning"]["warnings"] == d["warnings"]
    assert api.post("/api/settings/warning", {"t1": 90, "c1": "#111111"}).status == 200, "the older two-warning shape is still accepted"
    assert api.get("/api/settings/warning").json["warnings"][0] == {"t": 90, "c": "#111111"}


@pytest.mark.sev(2)
@pytest.mark.covers("http.POST /api/settings/warning")
@pytest.mark.parametrize("bad", [{"warnings": []}, {"warnings": [{"t": -1, "c": "#000000"}]},
                                 {"warnings": [{"t": 400000, "c": "#000000"}]}, {"warnings": [{"t": 5, "c": "red"}]}, {"warnings": [{"t": "5", "c": "#000000"}]},
                                 {"warnings": [{"t": True, "c": "#000000"}]}, {"warnings": [5]}, {"warnings": "x"}, {"warnings": [{"t": 5}]}])
def test_time_warning_rejects_bad_lists(api, bad):
    before = api.get("/api/settings/warning").json
    r = api.post("/api/settings/warning", bad)
    assert r.status == 400, (bad, r.status)
    assert api.get("/api/settings/warning").json == before


@pytest.mark.sev(3)
@pytest.mark.covers("http.POST /api/settings/warning")
def test_time_warning_non_object_body(api):
    for raw in ("[1,2]", "null", "5", "not json", ""):
        r = api.request("POST", "/api/settings/warning", raw=raw, headers={"Content-Type": "application/json"})
        assert r.status == 400, (raw, r.status)


@pytest.mark.sev(3)
@pytest.mark.covers("http.GET /api/settings/folders", "http.POST /api/settings/folders")
def test_default_folder_icon(api):
    assert api.post("/api/settings/folders", {"default_icon": "music"}).status == 200
    assert api.get("/api/settings/folders").json == {"default_icon": "music"}
    assert api.post("/api/settings/folders", {"default_icon": "Bad Icon!"}).status == 400
    assert api.get("/api/settings/folders").json == {"default_icon": "music"}
    assert api.post("/api/settings/folders", {"default_icon": ""}).status == 200
    assert api.get("/api/settings/folders").json == {"default_icon": ""}


@pytest.mark.sev(2)
@pytest.mark.covers("http.GET /api/devices", "http.POST /api/device", "cmd.device")
def test_output_device_selection(api):
    d = api.get("/api/devices").json
    assert isinstance(d["devices"], list) and "current" in d
    assert api.post("/api/device", {"name": "No Such Device"}).status == 400
    assert api.post("/api/device", {"name": None}).status == 200
    assert api.get("/api/devices").json["current"] is None
    assert api.state()["output"] == "System default"
    if d["devices"]:
        assert api.post("/api/device", {"name": d["devices"][0]}).status == 200
        assert api.get("/api/devices").json["current"] == d["devices"][0]
        assert api.state()["output"] == d["devices"][0]
        assert api.res("device/default") == "ok" and api.get("/api/devices").json["current"] is None
        assert api.res("device/0") == "ok" and api.get("/api/devices").json["current"] == d["devices"][0]
        assert api.res("device/next") == "ok"
        api.cmd("device/default")
    for bad in ("device/99", "device/abc", "device", "device/-1"):
        assert api.res(bad) == "invalid", bad
    assert api.get("/api/devices").json["current"] is None


@pytest.mark.sev(1)
@pytest.mark.covers("http.POST /api/device")
def test_switching_the_output_device_keeps_the_live_track_going(std):
    api = std
    devs = api.get("/api/devices").json["devices"]
    if not devs:
        pytest.skip("no output device listed")
    api.cmd("1/2")
    api.wait_playing("1/2")
    api.cmd("seek/40")
    assert api.post("/api/device", {"name": devs[0]}).status == 200
    s = api.wait_playing("1/2", 8)
    assert s["live_pos"] >= 39, f"the track must carry on from where it was, not restart ({s['live_pos']})"
    api.post("/api/device", {"name": None})
    s = api.wait_playing("1/2", 8)
    assert s["live_pos"] >= 39


@pytest.mark.sev(3)
@pytest.mark.covers("http.POST /api/download", "http.GET /api/download", "http.POST /api/download/clear")
def test_download_input_checks(api):
    assert api.get("/api/download").json["state"] == "idle"
    for bad in ({}, {"url": ""}, {"url": "ftp://x/y"}, {"url": "javascript:alert(1)"}, {"url": "http://"}, {"url": "not a url"}, {"url": 5}, {"url": "https://a b"}):
        r = api.post("/api/download", bad)
        assert r.status == 400, (bad, r.status, r.text[:100])
    assert api.post("/api/download/clear", {}).json["ok"] is True
    assert api.get("/api/download").json["state"] == "idle"


@pytest.mark.sev(3)
def test_unsupported_methods_are_not_server_errors(api):
    for m, p in (("PUT", "/api/state"), ("POST", "/api/state"), ("DELETE", "/api/state"), ("POST", "/"), ("DELETE", "/api/settings"), ("PATCH", "/api/playlists")):
        r = api.request(m, p)
        assert r.status in (200, 404, 405), (m, p, r.status)


# ---- 2.7.5 Settings rework -------------------------------------------------------------------------------------------------
@pytest.mark.sev(2)
@pytest.mark.covers("http.POST /api/settings")
@pytest.mark.parametrize("half", ["192.168.1.", "192.168.1", "192.168", "999.1.1.1", "1.2.3.4.5", ".local", "host..x", "-x", "x."])
def test_incomplete_companion_address_is_refused_and_the_old_one_stays(api, keep_companion_target, half):
    before = api.get("/api/settings").json
    r = api.post("/api/settings", {"companion_host": half, "companion_osc_port": 12321})
    assert r.status == 400 and r.json["ok"] is False and r.json["error"], (half, r.status, r.text[:120])
    after = api.get("/api/settings").json
    assert after == before and after["target"] == f"{before['companion_host']}:{before['companion_osc_port']}"
    assert api.state()["feedback"] == after["target"], "the address in use did not change"


@pytest.mark.sev(2)
@pytest.mark.covers("http.POST /api/settings")
@pytest.mark.parametrize("ok", ["192.168.1.50", "127.0.0.1", "localhost", "::1", "companion.local", "my-host"])
def test_complete_companion_addresses_are_accepted(api, keep_companion_target, ok):
    r = api.post("/api/settings", {"companion_host": ok, "companion_osc_port": 12321})
    assert r.status == 200 and api.get("/api/settings").json["companion_host"] == ok


@pytest.mark.sev(2)
@pytest.mark.covers("http.POST /api/settings/warning")
def test_time_warnings_have_no_limit_on_count(api):
    ws = [{"t": 600 - 10 * i, "c": "#%02x%02x%02x" % (i, i, i)} for i in range(40)]
    assert api.post("/api/settings/warning", {"warnings": ws}).status == 200
    got = api.get("/api/settings/warning").json["warnings"]
    assert len(got) == 40 and [w["t"] for w in got] == sorted((w["t"] for w in ws), reverse=True)
    assert [w["t"] for w in api.state()["warning"]["warnings"]] == [w["t"] for w in got]


@pytest.mark.sev(2)
@pytest.mark.covers("http.POST /api/settings/companion/test")
def test_send_test_goes_to_the_address_in_use_and_only_mp_test(api, sink):
    import re, time
    t0 = time.time()
    r = api.post("/api/settings/companion/test")
    s = api.get("/api/settings").json
    assert r.status == 200 and r.json["ok"] is True and r.json["sent_to"] == s["target"]
    assert re.fullmatch(r"\d\d:\d\d:\d\d", r.json["at"])
    deadline = time.time() + 3
    while time.time() < deadline and not [m for m in sink.since(t0) if m[1] == "/custom-variable/mp_test/value"]:
        time.sleep(0.05)
    got = [m for m in sink.since(t0) if m[1] == "/custom-variable/mp_test/value"]
    assert got and got[-1][2] == [r.json["at"]], got
    assert api.state()["test_message"] == r.json["at"]
    assert "test_message" not in api.get("/api/variables").text, "the test value is not a variable the player keeps pushing"


@pytest.mark.sev(2)
@pytest.mark.covers("cmd.resend")
def test_resend_does_not_send_mp_test(api, sink):
    import time
    api.post("/api/settings/companion/test")
    t0 = time.time()
    api.get("/api/resend")
    time.sleep(1.0)
    seen = {m[1] for m in sink.since(t0)}
    assert "/custom-variable/mp_live_name/value" in seen and "/custom-variable/mp_test/value" not in seen


@pytest.mark.sev(2)
@pytest.mark.covers("http.POST /api/settings/companion/test")
def test_send_test_ignores_an_address_that_was_refused(api, keep_companion_target, sink):
    import time
    s = api.get("/api/settings").json
    assert api.post("/api/settings", {"companion_host": "192.168.1.", "companion_osc_port": 12321}).status == 400
    r = api.post("/api/settings/companion/test").json
    assert r["ok"] and r["sent_to"] == s["target"]


# ---- 2.7.5 rc3: configurable variable prefix -------------------------------------------------------------------------------
@pytest.fixture()
def keep_prefix(api):
    old = api.get("/api/settings").json["variable_prefix"]
    yield old
    api.post("/api/settings/prefix", {"prefix": old, "confirm": True})


@pytest.mark.sev(2)
@pytest.mark.covers("http.POST /api/settings/prefix")
@pytest.mark.parametrize("bad", ["", "1abc", "_x", "a b", "a-b", "x" * 17, "é", None, 5, ["a"]])
def test_variable_prefix_rejects_bad_values_and_keeps_the_old_one(api, keep_prefix, bad):
    r = api.post("/api/settings/prefix", {"prefix": bad, "confirm": True})
    assert r.status == 400 and r.json["ok"] is False and r.json["error"], (bad, r.status, r.text[:100])
    assert api.get("/api/settings").json["variable_prefix"] == keep_prefix and api.state()["variable_prefix"] == keep_prefix


@pytest.mark.sev(2)
@pytest.mark.covers("http.POST /api/settings/prefix")
@pytest.mark.parametrize("good", ["a", "mp", "Show_1", "x" * 16, "foh_"])
def test_variable_prefix_accepts_valid_values_as_typed(api, keep_prefix, good):
    r = api.post("/api/settings/prefix", {"prefix": good, "confirm": True})
    assert r.status == 200 and r.json["ok"] and r.json["prefix"] == good and r.json["example"] == good + "remaining", r.text[:150]
    assert api.state()["variable_prefix"] == good, "no underscore is added or removed"


@pytest.mark.sev(2)
@pytest.mark.covers("http.POST /api/settings/prefix")
def test_changing_the_prefix_needs_a_confirmation_and_changes_nothing_without_it(api, keep_prefix):
    r = api.post("/api/settings/prefix", {"prefix": "zz_"})
    assert r.status == 409 and r.json["needs_confirm"] is True and r.json["old"] == keep_prefix and r.json["new"] == "zz_" and "old variable" in r.json["message"], r.text[:200]
    assert api.state()["variable_prefix"] == keep_prefix
    assert api.post("/api/settings/prefix", {"prefix": "zz_", "confirm": "yes"}).status == 409, "only true confirms"
    assert api.post("/api/settings/prefix", {"prefix": keep_prefix}).json["changed"] is False, "the same prefix needs no confirmation"


@pytest.mark.sev(2)
@pytest.mark.covers("http.POST /api/settings/prefix", "http.GET /api/variables")
def test_variables_are_sent_under_the_new_prefix_and_resent_at_once(api, sink, keep_prefix, managed):
    import time
    t0 = time.time()
    r = api.post("/api/settings/prefix", {"prefix": "zz_", "confirm": True})
    assert r.status == 200 and r.json["changed"] is True and r.json["old"] == keep_prefix
    deadline = time.time() + 4
    names = set()
    while time.time() < deadline and "/custom-variable/zz_live_name/value" not in names:
        names = {m[1] for m in sink.since(t0)}
        time.sleep(0.1)
    assert "/custom-variable/zz_live_name/value" in names and "/custom-variable/zz_remaining/value" in names, sorted(names)[:8]
    assert api.get("/api/variables").json["prefix"] == "zz_"
    assert json.loads((managed.workdir / "config.json").read_text("utf-8"))["var_prefix"] == "zz_"
    t1 = time.time()
    api.post("/api/settings/companion/test")
    time.sleep(0.6)
    assert any(m[1] == "/custom-variable/zz_test/value" for m in sink.since(t1)), "Send test uses the prefix too"
    t2 = time.time(); api.get("/api/volume/41"); time.sleep(0.8)
    assert not [m for m in sink.since(t2) if m[1].startswith(f"/custom-variable/{keep_prefix}live_volume")], "nothing is sent under the old name any more"


# ---- 2.7.5 rc4: prefix edge cases ---------------------------------------------------------------------------------------------
@pytest.mark.sev(2)
@pytest.mark.covers("http.POST /api/settings/prefix")
def test_prefix_change_while_a_track_plays_switches_cleanly(std, sink, keep_prefix):
    import time
    api = std
    api.cmd("1/2"); api.wait_playing("1/2")                # the 120 s file: a 3 s track ended inside the window and its `--:--` / full-resend gap (1.4-1.5 s) looked like a stall (also on v2.7.5)
    time.sleep(1.5)
    t_change = time.time()
    r = api.post("/api/settings/prefix", {"prefix": "zq_", "confirm": True})
    t_done = time.time()
    assert r.status == 200 and r.json["sending"] is True
    time.sleep(3.0)
    msgs = sink.since(t_change - 0.001)
    new = [m for m in msgs if m[1].startswith("/custom-variable/zq_")]
    old = [m for m in msgs if m[1].startswith(f"/custom-variable/{keep_prefix}") and m[0] > t_done + 0.3]
    assert not old, f"still sent under the old names after the change: {[m[1] for m in old[:4]]}"
    for var in ("live_name", "remaining", "live_fader_l", "state"):
        ts = sorted(m[0] for m in new if m[1] == f"/custom-variable/zq_{var}/value")
        assert ts and ts[0] - t_change < 0.5, f"{var} did not go out at once under the new name"
    # the remaining time changes every second: no gap longer than one send interval (1 s, plus the tick) once it runs under the new name
    ts = sorted(m[0] for m in new if m[1] == "/custom-variable/zq_remaining/value")
    gaps = [b - a for a, b in zip(ts, ts[1:])]
    assert len(ts) >= 3 and max(gaps) < 1.3, f"gap {max(gaps) if gaps else None}"
    assert [m for m in new if m[1] == "/custom-variable/zq_live_name/value"][-1][2] == [api.state()["live_name"]]


@pytest.mark.sev(2)
@pytest.mark.covers("http.POST /api/settings/prefix")
def test_prefix_change_while_companion_cannot_be_reached_is_saved_and_says_so(api, sink, keep_prefix, keep_companion_target):
    import time
    s = keep_companion_target
    assert api.post("/api/settings", {"companion_host": "no-such-host.invalid", "companion_osc_port": 12321}).status == 200
    r = api.post("/api/settings/prefix", {"prefix": "off_", "confirm": True})
    assert r.status == 200 and r.json["ok"] and r.json["prefix"] == "off_" and r.json["sending"] is False, r.text[:200]
    assert api.state()["variable_prefix"] == "off_"
    t0 = time.time()
    assert api.post("/api/settings", {"companion_host": s["companion_host"], "companion_osc_port": s["companion_osc_port"]}).json["host_found"] is True
    deadline = time.time() + 4
    while time.time() < deadline and not [m for m in sink.since(t0) if m[1] == "/custom-variable/off_live_name/value"]:
        time.sleep(0.1)
    assert [m for m in sink.since(t0) if m[1] == "/custom-variable/off_live_name/value"], "the sender recovers and sends under the new prefix"
    assert not [m for m in sink.since(t0) if m[1].startswith(f"/custom-variable/{keep_prefix}live_name")]


@pytest.mark.sev(2)
@pytest.mark.covers("http.POST /api/settings/prefix", "http.POST /api/restart")
def test_prefix_survives_a_restart(std, managed, keep_prefix):
    import sys, time, urllib.error
    if sys.platform == "win32":
        pytest.skip("os.execv on Windows starts a new process")
    api = std
    assert api.post("/api/settings/prefix", {"prefix": "rs_", "confirm": True}).status == 200
    assert api.post("/api/restart").status == 200
    time.sleep(1.0)
    deadline = time.time() + 30
    while time.time() < deadline:
        try:
            if api.state()["status"] in ("ready", "starting"):
                break
        except (urllib.error.URLError, OSError, AssertionError, ValueError):
            pass
        time.sleep(0.3)
    api.wait_for(lambda s: s["status"] == "ready", 40, desc="ready after restart")
    assert api.state()["variable_prefix"] == "rs_" and api.get("/api/variables").json["prefix"] == "rs_" and api.get("/api/settings").json["variable_prefix"] == "rs_"
    assert json.loads((managed.workdir / "config.json").read_text("utf-8"))["var_prefix"] == "rs_"
