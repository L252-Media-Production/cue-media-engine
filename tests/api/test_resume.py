"""Resume on start (gap 1 of docs/split-plan.md 5.4): after a restart the player carries on with the track that was live, near the saved position.

The harness config switches resume_on_start off, so these tests start their OWN instance (resume_on_start true, resume_save_s 1) and kill / restart it.
Tolerances (resume_save_s = 1): resume.json is written when the live track changes and then about once per second, so after a hard kill the saved
position is at most resume_save_s + 1.5 s behind the true position; the restarted track begins at the saved position and then runs on, so when it is
first observed it is at most (time since the restart came back) + 1.5 s ahead of it (load time and polling)."""
import json, os, signal, sys, time
import pytest

from harness import client
from harness.instance import Instance

pytestmark = pytest.mark.noreset           # no reset of the shared instance: these tests have their own
SAVE_S = 1


@pytest.fixture()
def rinst(request):
    if sys.platform == "win32":
        pytest.skip("process signals / os.execv are not supervised on Windows")
    inst = Instance(project_dir=request.config.getoption("--project"), wav_only=True, extra_config={"resume_on_start": True, "resume_save_s": SAVE_S})
    inst.start()
    api = client.Api(inst.base_url, osc_port=inst.osc_port)
    api.post("/api/playlists", {"name": "R"})
    assert api.post("/api/playlists/0/add", {"files": ["long_120s.wav", "tone_a.wav"]}).status == 200
    yield inst, api
    inst.stop()


def resume_file(inst):
    return inst.workdir / "resume.json"


def wait_resume(inst, pred=lambda d: True, timeout=10):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            d = json.loads(resume_file(inst).read_text())
            if pred(d):
                return d
        except (OSError, ValueError):
            pass
        time.sleep(0.1)
    raise AssertionError("resume.json did not reach the expected content within %s s (last: %s)" % (timeout, resume_file(inst).read_text() if resume_file(inst).exists() else "missing"))


def kill_and_restart(inst, how="KILL"):
    inst._signal(how)
    inst.proc.wait(10)
    t0 = time.time()
    inst.restart()
    return time.time() - t0


@pytest.mark.sev(1)
def test_hard_kill_then_restart_carries_on_with_the_same_track_near_the_saved_position(rinst):
    inst, api = rinst
    assert api.res("0/0") == "ok"
    api.wait_playing("0/0")
    time.sleep(3.0)
    saved = wait_resume(inst, lambda d: d["pos"] >= 2.0 and not d["paused"])
    true_pos = api.state()["live_pos"]
    assert saved["pt"] == [0, 0] and saved["id"] == "long_120s.wav"
    assert 0 <= true_pos - saved["pos"] <= SAVE_S + 1.5, f"the saved position is {true_pos - saved['pos']:.2f} s behind the true one"
    t_kill = time.time()
    kill_and_restart(inst, "KILL")
    t_back = time.time()
    s = api.wait_for(lambda s: s["state"] == "playing", 20, desc="resumed playing")
    waited = time.time() - t_back
    assert s["live_id"] == "0/0" and s["live_name"] == "long_120s"
    # resumed from the SAVED position: not from 0, not from the true position at the kill
    final = json.loads(resume_file(inst).read_text())["pos"]
    assert s["live_pos"] >= saved["pos"] - 0.1, f"resumed at {s['live_pos']:.2f}, saved was {saved['pos']:.2f}"
    assert s["live_pos"] <= saved["pos"] + waited + 1.5, f"resumed at {s['live_pos']:.2f}: too far ahead of the saved {saved['pos']:.2f} (+{waited:.1f} s since restart)"
    assert abs(final - s["live_pos"]) < 3.0


@pytest.mark.sev(1)
def test_paused_track_resumes_paused_at_the_same_position(rinst):
    inst, api = rinst
    api.res("0/0")
    api.wait_playing("0/0")
    time.sleep(2.0)
    assert api.res("pause") == "ok"
    saved = wait_resume(inst, lambda d: d["paused"], 10)
    time.sleep(1.2)                                     # the position of a paused track must not move
    again = wait_resume(inst)
    assert abs(again["pos"] - saved["pos"]) < 0.2
    kill_and_restart(inst, "KILL")
    s = api.wait_for(lambda s: s["state"] in ("paused", "playing"), 20, desc="resumed")
    assert s["state"] == "paused", f"a paused track must come back paused, got {s['state']}"
    assert s["live_id"] == "0/0"
    assert abs(s["live_pos"] - saved["pos"]) < 0.5
    p1 = api.state()["live_pos"]
    time.sleep(1.0)
    assert abs(api.state()["live_pos"] - p1) < 0.05, "a resumed paused track must stay where it is"


@pytest.mark.sev(1)
def test_a_deliberate_stop_is_not_resumed(rinst):
    inst, api = rinst
    api.res("0/0")
    api.wait_playing("0/0")
    wait_resume(inst, lambda d: d["pos"] > 0.5)
    assert api.res("stop") == "ok"
    t0 = time.time()
    while resume_file(inst).exists() and time.time() - t0 < 5:
        time.sleep(0.1)
    assert not resume_file(inst).exists(), "a deliberate stop must remove resume.json"
    kill_and_restart(inst, "KILL")
    time.sleep(2.5)
    s = api.state()
    assert s["state"] == "stopped" and s["live_id"] == "-", f"nothing may start after a restart that follows a stop: {s['state']} {s['live_id']}"


@pytest.mark.sev(1)
def test_a_finished_fade_out_is_not_resumed(rinst):
    inst, api = rinst
    api.res("0/0")
    api.wait_playing("0/0")
    wait_resume(inst, lambda d: d["pos"] > 0.5)
    api.cmd("fadeout", ms=300)
    api.wait_state("stopped", 6)
    t0 = time.time()
    while resume_file(inst).exists() and time.time() - t0 < 5:
        time.sleep(0.1)
    assert not resume_file(inst).exists()
    kill_and_restart(inst, "KILL")
    time.sleep(2.0)
    assert api.state()["state"] == "stopped"


@pytest.mark.sev(2)
def test_a_service_stop_records_the_exact_position_and_the_restart_continues_from_it(rinst):
    inst, api = rinst
    api.res("0/0")
    api.wait_playing("0/0")
    time.sleep(3.5)
    true_pos = api.state()["live_pos"]
    inst._signal("TERM")                                  # what systemd does: the handler writes resume.json once more, with the exact position
    inst.proc.wait(10)
    saved = json.loads(resume_file(inst).read_text())
    assert saved["id"] == "long_120s.wav"
    assert 0 <= saved["pos"] - true_pos <= 0.8, f"saved {saved['pos']:.2f}, position a moment before the stop {true_pos:.2f}"
    t0 = time.time()
    inst.restart()
    s = api.wait_for(lambda s: s["state"] == "playing", 20, desc="resumed playing")
    assert s["live_id"] == "0/0" and saved["pos"] - 0.1 <= s["live_pos"] <= saved["pos"] + (time.time() - t0) + 1.5
