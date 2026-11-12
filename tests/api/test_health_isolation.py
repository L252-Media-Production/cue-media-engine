"""2.8.0: computing the health report and running the watchdog (silent heartbeat on a reserved channel) must not change the Live audio.

The real rendered output is captured with SDL's disk driver (the pattern of test_audio_capture.py). While the 1 kHz bed plays, a thread asks
/api/state (which builds the health report) and /api/settings/health every second; the bed must hold its level without a single dropout, and the
ducking depth of a Play on Top must still be the one the settings give. The watchdog must not have restarted anything."""
import sys
import threading
import time
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_audio_capture import FS, amp, disk_ok, quiet, rig            # noqa: E402,F401  (fixtures and helpers of the capture tests)


@pytest.mark.sev(2)
def test_health_and_watchdog_leave_the_live_audio_untouched(quiet):
    rig = quiet
    api = rig.api
    stop = threading.Event()
    seen = {"n": 0, "states": set()}

    def poll():
        while not stop.is_set():
            st = api.state()
            seen["n"] += 1
            seen["states"].add(st["health"]["state"])
            api.get("/api/settings/health")
            api.get("/api/health/report")                       # a forced health refresh every second as well (no device enumeration while playing)
            stop.wait(1.0)

    th = threading.Thread(target=poll, daemon=True)
    th.start()
    try:
        assert api.res("0/0") == "ok"                        # background: 1 kHz at 0.5
        time.sleep(3.0)
        assert api.res("1/0/top") == "ok"                    # the 3 s voice-over: 2 kHz at 0.5
        time.sleep(7.0)
    finally:
        stop.set()
        th.join(5)
    L, _ = rig.samples()
    bg, top = amp(L, 1000), amp(L, 2000)
    assert seen["n"] >= 8 and seen["states"] <= {"starting", "ready", "degraded", "problem"}
    steady = bg[4:50]                                         # the first 3 s: nothing but the bed
    assert float(steady.min()) > 0.49 and float(steady.max()) < 0.51, f"the bed moved while health was computed: {steady.min():.3f}..{steady.max():.3f}"
    base = float(np.mean(steady))
    t_start = int(np.argmax(top > 0.25))
    t_end = len(top) - 1 - int(np.argmax(top[::-1] > 0.25))
    assert t_end - t_start + 1 >= 40
    want = (20 * np.log10(0.5 / np.sqrt(2)) + 30) * (1 - 1 / 6)
    depth = 20 * np.log10(float(np.mean(bg[t_start + 8:t_end - 4])) / base)
    assert abs(depth + want) < 1.0, f"ducking depth {-depth:.2f} dB, expected {want:.2f} dB"
    info = api.get("/api/settings/health").json
    assert info["restarts"] == 0 and not info["stalled"]
    assert info["beats"] >= 8, f"the heartbeat counted only {info['beats']} finished half-seconds in 10 s of playing: the stall signal does not move on a working output"
