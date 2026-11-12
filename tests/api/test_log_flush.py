"""The player flushes its own log lines (player.py switches stdout/stderr to line buffering), so a service without PYTHONUNBUFFERED=1 still logs promptly.
Starts the real launcher as a subprocess with a PIPE for stdout and no PYTHONUNBUFFERED; the start-up "Audio devices:" line must arrive without the
buffer having to fill. The read has a timeout (a thread + queue), no sleep."""
import json, os, queue, socket, subprocess, sys, tempfile, threading
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from harness.appcopy import copy_app      # noqa: E402


def _port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


@pytest.mark.sev(3)
def test_startup_log_line_arrives_through_a_pipe_without_pythonunbuffered():
    d = Path(tempfile.mkdtemp(prefix="cptest-logflush-"))
    copy_app(d)
    (d / "media" / "library").mkdir(parents=True)
    (d / "config.json").write_text(json.dumps({"http_port": _port(), "osc_in_port": _port()}))
    env = {k: v for k, v in os.environ.items() if k != "PYTHONUNBUFFERED"}
    env.update(SDL_AUDIODRIVER="dummy")
    p = subprocess.Popen([sys.executable, "-I", str(d / "player.py")], cwd=str(d), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    q = queue.Queue()
    threading.Thread(target=lambda: [q.put(l) for l in p.stdout], daemon=True).start()
    seen = []
    try:
        while True:
            try:
                line = q.get(timeout=30)
            except queue.Empty:
                pytest.fail("no 'Audio devices:' line within 30 s; seen: %r" % seen)
            seen.append(line)
            if line.startswith("Audio devices:"):
                break
    finally:
        p.kill()
        p.wait()
