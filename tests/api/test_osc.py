"""OSC input (commands over UDP, malformed packets) and OSC output (variables pushed to Companion, captured by the harness sink)."""
import struct, time
import pytest


def pad(b):
    return b + b"\x00" * (4 - len(b) % 4)


def packet(addr, *ints):
    return pad(addr.encode()) + pad(("," + "i" * len(ints)).encode()) + b"".join(struct.pack(">i", i) for i in ints)


@pytest.mark.sev(2)
@pytest.mark.covers("osc.command", "cmd.volume")
def test_osc_volume_and_playback(std, needs_osc):
    api = std
    api.osc("/volume/40")
    api.wait_for(lambda s: s["live_volume"] == "40", 3, desc="volume over OSC")
    api.osc("/0/1")
    api.wait_playing("0/1")
    api.osc("/pause")
    api.wait_state("paused")
    api.osc("/resume")
    api.wait_state("playing")
    api.osc("/stop")
    api.wait_state("stopped")
    api.osc("/mode/shuffle")
    api.wait_for(lambda s: s["play_mode"] == "shuffle", 3, desc="mode over OSC")


@pytest.mark.sev(2)
@pytest.mark.covers("osc.ms_argument")
def test_osc_first_numeric_argument_is_the_fade_time(std, needs_osc):
    api = std
    api.cmd("1/2")
    api.wait_playing("1/2")
    api.osc("/fadeout", 300)
    t0 = time.time()
    api.wait_state("stopped", 3)
    assert time.time() - t0 < 1.5, "a 300 ms fade out was sent"
    api.cmd("0/2")
    api.wait_playing("0/2")
    api.osc("/1/2/xfade", 1500)
    time.sleep(0.5)
    assert len(api.get("/api/monitor").json["decks"]) == 2
    api.osc("/volume/55.0")                                   # a float argument is not a command value but must not break anything
    api.osc("/volume/55", "text", 1.5, True)                   # odd argument types: ignored
    api.wait_for(lambda s: s["live_volume"] == "55", 3, desc="volume")


@pytest.mark.sev(2)
@pytest.mark.covers("osc.command")
@pytest.mark.parametrize("addr", ["/nonsense/zzz", "/", "/VOLUME/10", "/0/1/in/abc", "/seek", "/a" * 300, "/0/é/1"])
def test_osc_unknown_or_odd_addresses_change_nothing(std, needs_osc, addr):
    api = std
    api.cmd("volume/62")
    before = api.state()
    api.osc(addr)
    time.sleep(0.3)
    s = api.state()
    assert s["state"] == "stopped" and s["live_volume"] == "62"
    api.osc("/volume/63")
    api.wait_for(lambda s: s["live_volume"] == "63", 3, desc="the server still answers OSC")


@pytest.mark.sev(1)
@pytest.mark.covers("osc.malformed")
def test_malformed_osc_packets_do_not_stop_the_server(std, needs_osc):
    api = std
    junk = [b"", b"\x00", b"\xff" * 5, b"garbage", b"/volume/50", b"/volume/50\x00\x00,i\x00\x00", b"/volume/50\x00\x00,i\x00\x00\x00\x00",
            b"#bundle\x00", b"#bundle\x00" + b"\x00" * 8 + b"\xff\xff\xff\xff" + b"x" * 8, pad(b"/x") + pad(b",") , pad(b"/x") + pad(b",s") + b"abc",
            pad(b"/x") + pad(b",[[[["), pad(b"/x") + pad(b",f") + b"\x01", b"\x00" * 1000, b"/" + b"a" * 8000, bytes(range(256)) * 20,
            pad(b"/volume/70") + pad(b",i") + struct.pack(">i", 2 ** 31 - 1), pad(b"/0/1/xfade") + pad(b",i") + struct.pack(">i", -1),
            pad(b"/fadeout") + pad(b",i") + struct.pack(">i", -2 ** 31)]
    for k, j in enumerate(junk):
        api.osc_raw(j)
        time.sleep(0.03)
    time.sleep(0.4)
    api.osc("/volume/41")
    api.wait_for(lambda s: s["live_volume"] == "41", 3, desc="the server still answers after junk")
    assert api.state()["status"] in ("ready", "starting")
    assert api.get("/api/state").status == 200


@pytest.mark.sev(3)
@pytest.mark.covers("osc.command")
def test_osc_extra_slashes_are_ignored(std, needs_osc):
    api = std
    api.osc("//0//1//")
    api.wait_playing("0/1")
    api.osc("/stop/")
    api.wait_state("stopped")


@pytest.mark.sev(2)
@pytest.mark.covers("osc.command")
def test_osc_command_is_logged(std, needs_osc, managed):
    std.osc("/volume/44")
    std.wait_for(lambda s: s["live_volume"] == "44", 3, desc="volume")
    assert "OSC /volume/44" in managed.log_text() and "-> ok" in managed.log_text()


@pytest.mark.sev(1)
@pytest.mark.covers("osc.command")
def test_osc_flood_leaves_the_player_responsive(std, needs_osc):
    api = std
    api.cmd("0/2")
    api.wait_playing("0/2")
    for i in range(400):
        api.osc("/volume/%d" % (i % 100))
    time.sleep(0.5)
    t0 = time.perf_counter()
    assert api.state()["state"] == "playing"
    assert time.perf_counter() - t0 < 1.0
    api.osc("/volume/50")
    api.wait_for(lambda s: s["live_volume"] == "50", 3, desc="final volume")


# ------------------------------------------------------------------ OSC out
def wait_msgs(sink, t0, pred, timeout=4.0):
    end = time.time() + timeout
    while time.time() < end:
        m = [x for x in sink.since(t0) if pred(x)]
        if m:
            return m
        time.sleep(0.05)
    return []


@pytest.mark.sev(2)
@pytest.mark.covers("osc.out.variables", "cmd.volume")
def test_changed_variables_are_pushed_to_companion(api, sink):
    t0 = time.time()
    api.cmd("volume/47")
    m = wait_msgs(sink, t0, lambda x: x[1] == "/custom-variable/mp_live_volume/value")
    assert m and m[-1][2] == ["47"], m


@pytest.mark.sev(2)
@pytest.mark.covers("osc.out.variables", "cmd.resend", "var.*")
def test_resend_pushes_every_variable(std, sink):
    api = std
    t0 = time.time()
    assert api.res("resend") == "ok"
    time.sleep(1.0)
    names = {m[1] for m in sink.since(t0)}
    assert len(names) > 60, len(names)
    for n in ("state", "live_name", "live_volume", "focus_name", "pl0_name", "pl1_count", "focus_t2", "duck_ratio", "preview_state", "live_fader_l", "live_db_r"):
        assert f"/custom-variable/mp_{n}/value" in names, n
    vals = {m[1]: m[2] for m in sink.since(t0)}
    assert vals["/custom-variable/mp_pl0_name/value"] == ["A"] and vals["/custom-variable/mp_pl0_count/value"] == ["3"]
    assert all(isinstance(v[0], str) for k, v in vals.items() if "level" not in k), "variables are sent as text"


@pytest.mark.sev(2)
@pytest.mark.covers("osc.out.variables")
def test_full_resend_every_5_seconds(api, sink):
    t0 = time.time()
    m = wait_msgs(sink, t0, lambda x: x[1] == "/custom-variable/mp_state/value", 7.5)
    assert m, "no unchanged variable was re-sent within 7.5 s (the player sends everything every 5 s)"


@pytest.mark.sev(2)
@pytest.mark.covers("osc.out.variables")
def test_removed_playlist_variables_are_blanked(api, sink):
    api.post("/api/playlists", {"name": "Zed"})
    t0 = time.time()
    api.post(f"/api/playlists/{len(api.playlists()) - 1}/rename", {"name": "Zed2"})
    assert wait_msgs(sink, t0, lambda x: x[1] == "/custom-variable/mp_pl0_name/value" and x[2] == ["Zed2"])
    t0 = time.time()
    api.delete("/api/playlists/0")
    assert wait_msgs(sink, t0, lambda x: x[1] == "/custom-variable/mp_pl0_name/value" and x[2] == ["-"]), "a removed playlist's variable must be blanked once"


@pytest.mark.sev(2)
@pytest.mark.covers("osc.out.variables")
def test_playing_updates_state_variables(std, sink):
    api = std
    t0 = time.time()
    api.cmd("0/1")
    api.wait_playing("0/1")
    assert wait_msgs(sink, t0, lambda x: x[1] == "/custom-variable/mp_state/value" and x[2] == ["playing"])
    assert wait_msgs(sink, t0, lambda x: x[1] == "/custom-variable/mp_live_name/value" and x[2] == ["tone_b"])
    assert wait_msgs(sink, t0, lambda x: x[1] == "/custom-variable/mp_live_id/value" and x[2] == ["0/1"])
