"""Playback commands: play / take / cut / xfade / toggle / stop / pause / seek / fade out / focus (the cue)."""
import time
import pytest


def play_and_wait(api, path, live_id):
    assert api.res(path) == "ok"
    return api.wait_playing(live_id)


@pytest.mark.sev(1)
@pytest.mark.covers("cmd.track.play")
def test_play_track_by_address(std):
    api = std
    s = play_and_wait(api, "0/1", "0/1")
    assert s["live_name"] == "tone_b" and s["live_fid"] == "tone_b.wav"
    assert 2.9 < s["live_dur"] < 3.1
    assert s["remaining"] in ("00:03", "00:02")
    p1 = api.state()["live_pos"]
    time.sleep(0.5)
    assert api.state()["live_pos"] > p1 + 0.3, "position does not advance"


@pytest.mark.sev(1)
@pytest.mark.covers("cmd.track.play")
@pytest.mark.parametrize("path", ["9/9", "0/99", "99/0", "0/-1", "-1/0", "a/b", "0/1.5", "0/%20"])
def test_play_bad_address_does_nothing(std, path):
    api = std
    r = api.res(path)
    assert r in ("invalid", "unknown"), r
    time.sleep(0.2)
    assert api.state()["state"] == "stopped"


@pytest.mark.sev(1)
@pytest.mark.covers("cmd.take", "cmd.cut", "cmd.track.focus")
def test_take_plays_the_cue_and_cut_equals_take(std):
    api = std
    api.cmd("0/2/focus")
    assert api.state()["focus_id"] == "0/2" and api.state()["focus_name"] == "tone_c"
    assert api.res("take") == "ok"
    api.wait_playing("0/2")
    api.cmd("stop")
    api.cmd("0/1/focus")
    assert api.res("cut") == "ok"
    api.wait_playing("0/1")


@pytest.mark.sev(1)
@pytest.mark.covers("cmd.stop", "cmd.stopall", "cmd.clear")
def test_stop_stopall_and_cleared_cue(std):
    api = std
    play_and_wait(api, "0/0", "0/0")
    assert api.res("stop") == "ok"
    s = api.wait_state("stopped")
    assert s["live_id"] == "-" and s["live_name"] == "-" and s["remaining"] == "--:--"
    assert s["focus_id"] != "-", "stop must keep the cue"
    play_and_wait(api, "0/0", "0/0")
    assert api.res("stopall") == "ok"
    s = api.wait_state("stopped")
    assert s["focus_id"] == "-" and s["focus_name"] == "-", "stopall clears the cue"
    for c in ("take", "xfade", "cut", "toggle", "top"):
        assert api.res(c) == "no cue", c
    assert api.state()["state"] == "stopped"
    api.cmd("0/1/focus")
    assert api.state()["focus_id"] == "0/1"
    assert api.res("clear") == "ok"
    assert api.state()["focus_id"] == "-"


@pytest.mark.sev(1)
@pytest.mark.covers("cmd.pause", "cmd.resume", "cmd.playpause")
def test_pause_resume_playpause(std):
    api = std
    play_and_wait(api, "1/2", "1/2")
    assert api.res("pause") == "ok"
    s = api.wait_state("paused")
    pos = s["live_pos"]
    time.sleep(0.6)
    assert abs(api.state()["live_pos"] - pos) < 0.15, "position moves while paused"
    assert api.res("resume") == "ok"
    api.wait_state("playing")
    time.sleep(0.5)
    assert api.state()["live_pos"] > pos + 0.3
    api.cmd("playpause")
    api.wait_state("paused")
    api.cmd("playpause")
    api.wait_state("playing")


@pytest.mark.sev(1)
@pytest.mark.covers("cmd.fadeout")
def test_fadeout_with_and_without_ms(std):
    api = std
    play_and_wait(api, "1/2", "1/2")
    assert api.res("fadeout", ms=1500) == "ok"
    api.wait_state("fading", 2)
    api.wait_state("stopped", 4)
    play_and_wait(api, "1/2", "1/2")
    t0 = time.time()
    api.cmd("fadeout", ms=200)
    api.wait_state("stopped", 3)
    assert time.time() - t0 < 1.5
    # fade out while paused stops at once
    play_and_wait(api, "1/2", "1/2")
    api.cmd("pause")
    api.wait_state("paused")
    api.cmd("fadeout")
    api.wait_state("stopped", 3)


@pytest.mark.sev(1)
@pytest.mark.covers("cmd.track.toggle", "cmd.toggle")
def test_toggle_on_off(std):
    api = std
    assert api.res("0/1/toggle") == "ok"
    api.wait_playing("0/1")
    assert api.res("0/1/toggle") == "ok"
    api.wait_state("stopped", 3)
    api.cmd("0/2/focus")
    api.cmd("toggle")
    api.wait_playing("0/2")
    api.cmd("0/1/toggle")                    # another track: switches to it
    api.wait_playing("0/1")


@pytest.mark.sev(1)
@pytest.mark.covers("cmd.track.cut", "cmd.track.xfade", "cmd.xfade")
def test_cut_and_crossfade_switch_the_track(std):
    api = std
    play_and_wait(api, "0/0", "0/0")
    assert api.res("0/1/cut") == "ok"
    api.wait_playing("0/1")
    assert api.res("0/2/xfade", ms=400) == "ok"
    api.wait_playing("0/2")
    time.sleep(0.6)
    s = api.state()
    assert s["live_id"] == "0/2" and s["state"] == "playing"
    api.cmd("0/1/focus")
    assert api.res("xfade", ms=300) == "ok"
    api.wait_playing("0/1")
    assert api.res("0/0/crossfade", ms=300) == "ok"           # alias
    api.wait_playing("0/0")


@pytest.mark.sev(1)
@pytest.mark.covers("cmd.seek")
def test_seek(std):
    api = std
    play_and_wait(api, "1/2", "1/2")
    assert api.res("seek/60") == "ok"
    p = api.state()["live_pos"]
    assert 59.5 < p < 62, p
    assert api.res("seek/-5") == "ok"
    assert api.state()["live_pos"] < 2
    assert api.res("seek/500") == "ok"
    assert 118 < api.state()["live_pos"] < 120.5
    for bad in ("abc", ""):
        assert api.res("seek/" + bad if bad else "seek") == "invalid"
    api.cmd("pause")
    api.wait_state("paused")
    assert api.res("seek/30") == "ok"
    assert api.state()["state"] == "paused"
    assert 29 < api.state()["live_pos"] < 31


@pytest.mark.sev(2)
@pytest.mark.covers("cmd.seek")
def test_seek_with_nothing_playing_is_invalid(std):
    assert std.res("seek/10") == "invalid"


@pytest.mark.sev(2)
@pytest.mark.covers("cmd.next", "cmd.prev", "cmd.nextlist", "cmd.prevlist")
def test_cue_navigation_wraps(std):
    api = std
    api.cmd("0/0/focus")
    api.cmd("next")
    assert api.state()["focus_id"] == "0/1"
    api.cmd("next"); api.cmd("next")
    assert api.state()["focus_id"] == "0/0", "next must wrap"
    api.cmd("prev")
    assert api.state()["focus_id"] == "0/2", "prev must wrap"
    assert api.res("previous") == "ok"                         # alias
    assert api.state()["focus_id"] == "0/1"
    api.cmd("nextlist")
    s = api.state()
    assert s["focus_id"] == "1/0" and s["focus_playlist"] == "B" and s["focus_playlist_num"] == "1"
    api.cmd("nextlist")
    assert api.state()["focus_id"] == "0/0"
    api.cmd("prevlist")
    assert api.state()["focus_id"] == "1/0"
    api.cmd("clear")
    api.cmd("next")
    assert api.state()["focus_id"] != "-", "next brings the cue back"


@pytest.mark.sev(2)
@pytest.mark.covers("cmd.next", "cmd.nextlist")
def test_navigation_with_no_playlists_is_safe(api):
    for c in ("next", "prev", "nextlist", "prevlist", "take", "toggle", "xfade", "cut", "top"):
        assert api.res(c) in ("ok", "invalid", "no cue"), c
    assert api.state()["state"] == "stopped"


@pytest.mark.sev(1)
@pytest.mark.covers("cmd.playlist.play")
def test_playlist_play_button_command(std):
    api = std
    assert api.res("1/play") == "ok"
    api.wait_playing("1/0")
    api.cmd("stop")
    assert api.res("9/play") == "invalid"
    api.post("/api/playlists", {"name": "empty"})
    assert api.res("2/play") == "invalid"


@pytest.mark.sev(2)
@pytest.mark.covers("cmd.playlist.play", "cmd.playlist.mode")
def test_playlist_play_in_shuffle_picks_a_track_of_that_playlist(std):
    api = std
    assert api.res("0/mode/shuffle") == "ok"
    seen = set()
    for _ in range(6):
        assert api.res("0/play") == "ok"
        s = api.wait_for(lambda s: s["state"] == "playing" and s["live_id"].startswith("0/"), 5, desc="shuffle play")
        seen.add(s["live_id"])
        api.cmd("stop")
        api.wait_state("stopped")
    assert seen <= {"0/0", "0/1", "0/2"}


@pytest.mark.sev(1)
@pytest.mark.covers("cmd.track.top", "cmd.top")
def test_play_on_top(std):
    api = std
    assert api.res("0/0/top") == "ok"                         # nothing playing: it just plays
    api.wait_playing("0/0")
    assert api.state()["on_top"] == "0"
    assert api.res("1/0/top") == "ok"                         # now over the live track
    s = api.wait_for(lambda s: s["on_top"] == "1", 5, desc="on_top")
    assert s["live_id"] == "1/0"
    api.cmd("0/1/focus")
    assert api.res("top") == "ok"
    api.cmd("stopall")
    api.wait_state("stopped")
    assert api.state()["on_top"] == "0"


@pytest.mark.sev(1)
def test_stop_while_a_track_is_still_loading_leaves_it_stopped(std):
    """A stop that arrives while the track is being decoded must not let it start afterwards (wrong track on air)."""
    api = std
    api.cmd("1/2")                                            # the 120 s file, not cached yet on a fresh instance
    api.cmd("stop")
    time.sleep(1.5)
    assert api.state()["state"] == "stopped" and api.state()["live_id"] == "-"
    api.cmd("0/2")
    api.cmd("stopall")
    time.sleep(1.5)
    assert api.state()["state"] == "stopped"


@pytest.mark.sev(1)
def test_last_command_wins_under_rapid_fire(std):
    api = std
    for i in range(12):
        api.cmd(f"0/{i % 3}")
    api.cmd("0/1")
    s = api.wait_playing("0/1", 6)
    time.sleep(0.5)
    assert api.state()["live_id"] == "0/1"
    for i in range(10):
        api.cmd("pause"); api.cmd("resume")
    api.cmd("resume")
    api.wait_state("playing")


@pytest.mark.sev(3)
def test_playing_by_address_moves_the_cue_the_same_way_every_time(std):
    """play() moves the cue only when the track had to be decoded first; a cached track leaves it where it was."""
    api = std
    api.cmd("0/0/focus")
    api.cmd("0/2")                                            # decoded for the first time
    api.wait_playing("0/2")
    first = api.state()["focus_id"]
    api.cmd("stop")
    api.cmd("0/0/focus")
    api.cmd("0/2")                                            # already in the cache
    api.wait_playing("0/2")
    second = api.state()["focus_id"]
    assert first == second, f"cue after the first play: {first}, after playing the cached track: {second}"


@pytest.mark.sev(2)
@pytest.mark.covers("cmd.track.focus")
def test_focus_and_cue_alias(std):
    api = std
    assert api.res("1/1/focus") == "ok" and api.state()["focus_id"] == "1/1"
    assert api.res("0/2/cue") == "ok" and api.state()["focus_id"] == "0/2"
    assert api.res("5/5/focus") == "invalid" and api.state()["focus_id"] == "0/2"
    assert api.state()["state"] == "stopped"


@pytest.mark.sev(2)
def test_unknown_command_words_do_not_change_anything(std):
    api = std
    for c in ("0/1/bogus", "bogus", "bogus/1/2", "0/bogus", "0/1/loop/maybe/extra"):
        r = api.res(c)
        assert r in ("unknown", "invalid", "ok"), (c, r)
    assert api.state()["state"] == "stopped"
