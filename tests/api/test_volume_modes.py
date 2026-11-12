"""Master volume, playlist play modes, per-track end actions (and what really happens when a track ends)."""
import time
import pytest
from conftest import make_playlist


def vol(api):
    return int(api.state()["live_volume"])


def audible(api):
    return api.get("/api/monitor").json["decks"]


@pytest.mark.sev(2)
@pytest.mark.covers("cmd.volume")
def test_volume_set_up_down_clamp(api):
    assert api.res("volume/80") == "ok" and vol(api) == 80
    assert api.res("volume/up") == "ok" and vol(api) == 85
    assert api.res("volume/up/10") == "ok" and vol(api) == 95
    api.cmd("volume/up/10")
    assert vol(api) == 100, "up must stop at 100"
    api.cmd("volume/down")
    assert vol(api) == 95
    api.cmd("volume/down/50")
    assert vol(api) == 45
    api.cmd("volume/down/50")
    assert vol(api) == 0, "down must stop at 0"
    assert api.res("volume/150") == "ok" and vol(api) == 100, "above 100 is clamped"
    assert api.res("vol/30") == "ok" and vol(api) == 30                    # alias
    assert api.res("volume/0") == "ok" and vol(api) == 0


@pytest.mark.sev(2)
@pytest.mark.covers("cmd.volume")
@pytest.mark.parametrize("bad", ["volume", "volume/abc", "volume/-5", "volume/1.5", "volume/up/x/y/z/w"])
def test_volume_bad_values(api, bad):
    api.cmd("volume/60")
    r = api.res(bad)
    assert r in ("invalid", "ok"), r
    if r == "invalid":
        assert vol(api) == 60, "an invalid volume command must not change the volume"


@pytest.mark.sev(2)
@pytest.mark.covers("cmd.volume")
def test_volume_mute_toggle_restores_the_level(api):
    api.cmd("volume/70")
    assert api.res("volume/mute") == "ok" and vol(api) == 0
    assert api.res("volume/mute") == "ok" and vol(api) == 70
    api.cmd("volume/0")
    api.cmd("volume/mute")
    assert vol(api) == 100, "unmuting from a manual 0 goes to full"


@pytest.mark.sev(1)
@pytest.mark.covers("cmd.volume", "http.GET /api/monitor")
def test_master_volume_reaches_the_audible_level(std):
    api = std
    api.cmd("0/0")
    api.wait_playing("0/0")
    v100 = audible(api)[0]["vol"]
    api.cmd("volume/50")
    time.sleep(0.2)
    d = audible(api)
    assert d and abs(d[0]["vol"] - v100 * 0.5) < 0.02, (v100, d)
    api.cmd("volume/mute")
    time.sleep(0.2)
    assert audible(api) == [], "muted: no deck is audible"
    api.cmd("volume/mute")
    time.sleep(0.2)
    assert audible(api)[0]["vol"] > 0.4


@pytest.mark.sev(2)
@pytest.mark.covers("cmd.playlist.mode", "cmd.mode")
@pytest.mark.parametrize("word,expect", [("stop", "stop"), ("loop_playlist", "loop_playlist"), ("next_playlist", "next_playlist"), ("shuffle", "shuffle"),
                                          ("off", "stop"), ("once", "stop"), ("playlist", "loop_playlist"), ("loopall", "loop_playlist"),
                                          ("all", "loop_playlist"), ("random", "shuffle"), ("continue", "next_playlist"), ("chain", "next_playlist"),
                                          ("nextplaylist", "next_playlist"), ("next_list", "next_playlist")])
def test_play_mode_words_and_aliases(std, word, expect):
    api = std
    assert api.res(f"1/mode/{word}") == "ok"
    assert api.playlists()[1]["mode"] == expect
    assert api.playlists()[0]["mode"] == "stop", "another playlist must not change"
    api.cmd("1/0/focus")
    assert api.state()["play_mode"] == expect


@pytest.mark.sev(2)
@pytest.mark.covers("cmd.playlist.mode", "cmd.mode")
def test_mode_next_cycles_and_focus_mode(std):
    api = std
    order = ["loop_playlist", "next_playlist", "shuffle", "stop"]
    for want in order:
        assert api.res("0/mode/next") == "ok"
        assert api.playlists()[0]["mode"] == want
    api.cmd("1/1/focus")
    api.cmd("mode/shuffle")
    assert api.playlists()[1]["mode"] == "shuffle" and api.playlists()[0]["mode"] == "stop"
    assert api.res("mode/next") == "ok" and api.playlists()[1]["mode"] == "stop"
    assert api.res("mode/bogus") == "invalid"


@pytest.mark.sev(2)
@pytest.mark.covers("cmd.playlist.mode")
@pytest.mark.parametrize("bad", ["0/mode/bogus", "9/mode/stop", "0/mode/", "0/mode"])
def test_mode_bad_values(std, bad):
    api = std
    api.cmd("0/mode/shuffle")
    r = api.res(bad)
    assert r in ("invalid", "unknown"), r
    assert api.playlists()[0]["mode"] == "shuffle"


@pytest.mark.sev(2)
@pytest.mark.covers("cmd.track.end", "cmd.track.loop", "cmd.loop")
def test_end_action_cycle_and_values(std):
    api = std

    def end():
        return api.playlists()[0]["tracks"][1]["end"]
    assert end() == "default"
    seq = []
    for _ in range(4):
        assert api.res("0/1/end") == "ok"
        seq.append(end())
    assert seq == ["once", "loop", "stop", "default"]
    for v in ("once", "loop", "stop", "default"):
        assert api.res(f"0/1/end/{v}") == "ok" and end() == v
    assert api.res("0/1/end/next") == "ok" and end() == "once"
    for bad in ("bogus", "LOOP2"):
        assert api.res(f"0/1/end/{bad}") == "invalid"
    assert end() == "once"
    assert api.playlists()[0]["tracks"][0]["end"] == "default" and api.playlists()[0]["tracks"][2]["end"] == "default"
    assert api.res("0/9/end/loop") == "invalid" and api.res("9/0/end/loop") == "invalid"


@pytest.mark.sev(2)
@pytest.mark.covers("cmd.track.loop", "cmd.loop")
def test_loop_commands(std):
    api = std
    t = lambda k: api.playlists()[0]["tracks"][k]
    assert api.res("0/1/loop") == "ok" and t(1)["loop"] is True and t(1)["end"] == "loop"
    assert api.res("0/1/loop") == "ok" and t(1)["loop"] is False
    assert api.res("0/1/loop/1") == "ok" and t(1)["loop"] is True
    assert api.res("0/1/loop/0") == "ok" and t(1)["loop"] is False and t(1)["end"] == "default"
    api.cmd("0/1/end/stop")
    api.cmd("0/1/loop/0")
    assert t(1)["end"] == "stop", "loop off must not clear a 'stop'"
    api.cmd("0/2/focus")
    assert api.res("loop/1") == "ok" and t(2)["loop"] is True
    assert api.res("loop") == "ok" and t(2)["loop"] is False
    assert api.res("loop/on") == "ok" and t(2)["loop"] is True
    assert api.res("0/9/loop") == "invalid"


@pytest.mark.sev(2)
@pytest.mark.covers("cmd.playlist.mode")
def test_mode_track_alias_toggles_loop_of_the_focused_track(std):
    api = std
    api.cmd("0/1/focus")
    assert api.res("0/mode/loop") == "ok"
    assert api.playlists()[0]["tracks"][1]["loop"] is True
    assert api.res("1/mode/loop") == "invalid", "only the focused playlist can toggle"


def short_list(api, files, name="S"):
    idx = make_playlist(api, name, files)
    return idx


@pytest.mark.sev(1)
def test_mode_stop_stops_at_the_end(api):
    p = short_list(api, ["short_1s.wav", "short_1s_b.wav"])
    api.cmd(f"{p}/0")
    api.wait_playing(f"{p}/0")
    api.wait_state("stopped", 4)


@pytest.mark.sev(1)
def test_mode_loop_playlist_goes_on_and_wraps(api):
    p = short_list(api, ["short_1s.wav", "short_1s_b.wav"])
    api.cmd(f"{p}/mode/loop_playlist")
    api.cmd(f"{p}/0")
    api.wait_playing(f"{p}/0")
    api.wait_playing(f"{p}/1", 4)
    api.wait_playing(f"{p}/0", 4)


@pytest.mark.sev(1)
def test_mode_next_playlist_continues_into_the_next_playlist(api):
    p = short_list(api, ["short_1s.wav"], "first")
    q = short_list(api, ["short_1s_b.wav"], "second")
    api.cmd(f"{p}/mode/next_playlist")
    api.cmd(f"{p}/0")
    api.wait_playing(f"{p}/0")
    api.wait_playing(f"{q}/0", 5)


@pytest.mark.sev(1)
def test_mode_shuffle_plays_each_track_once_before_repeating(api):
    p = short_list(api, ["short_1s.wav", "short_1s_b.wav", "short_1s_c.wav"])
    api.cmd(f"{p}/mode/shuffle")
    api.cmd(f"{p}/0")
    api.wait_playing(f"{p}/0")
    seen = [f"{p}/0"]
    for _ in range(2):
        s = api.wait_for(lambda s: s["state"] == "playing" and s["live_id"] != seen[-1], 4, desc="the next shuffled track")
        seen.append(s["live_id"])
    assert len(set(seen)) == 3, seen


@pytest.mark.sev(1)
def test_end_action_loop_repeats_until_stopped(api):
    p = short_list(api, ["short_1s.wav", "short_1s_b.wav"])
    api.cmd(f"{p}/mode/loop_playlist")
    api.cmd(f"{p}/0/end/loop")
    api.cmd(f"{p}/0")
    api.wait_playing(f"{p}/0")
    time.sleep(2.6)
    s = api.state()
    assert s["state"] == "playing" and s["live_id"] == f"{p}/0", "a looped track must stay live, whatever the playlist mode"
    api.cmd("stop")


@pytest.mark.sev(1)
@pytest.mark.covers("cmd.track.end")
def test_end_action_once_plays_two_passes(api):
    p = short_list(api, ["short_1s.wav"])
    api.cmd(f"{p}/0/end/once")
    api.cmd(f"{p}/0")
    s = api.wait_playing(f"{p}/0")
    assert s["live_end"] == "once" and s["live_passes"] == 2 and s["live_pass"] == 1
    time.sleep(1.35)
    s = api.state()
    assert s["state"] == "playing" and s["live_pass"] == 2, s
    api.wait_state("stopped", 3)


@pytest.mark.sev(1)
def test_end_action_stop_overrides_the_playlist_mode(api):
    p = short_list(api, ["short_1s.wav", "short_1s_b.wav"])
    api.cmd(f"{p}/mode/loop_playlist")
    api.cmd(f"{p}/0/end/stop")
    api.cmd(f"{p}/0")
    api.wait_playing(f"{p}/0")
    api.wait_state("stopped", 4)


@pytest.mark.sev(2)
def test_state_reports_the_live_tracks_end_action(std):
    api = std
    api.cmd("0/1/end/loop")
    api.cmd("0/1")
    s = api.wait_playing("0/1")
    assert s["live_end"] == "loop" and s["live_passes"] == 1
    api.cmd("0/1/end/stop")
    assert api.state()["live_end"] == "stop"
