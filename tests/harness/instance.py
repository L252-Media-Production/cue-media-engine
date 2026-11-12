"""Start a separate, disposable player instance from a COPY of player.py, with its own folder, ports, config, state, test library and a
silent audio driver; tear it down afterwards.

It cannot touch production: the player reads config.json, state and media from the folder its own script is in, and this copy lives in a
fresh temp folder (cptest-*). The ports are picked at random from 18200-18999 (never 8080/9000), and OSC output goes to a local sink the
harness owns, never to a real Companion. After start-up the harness asks the instance where its config file is and aborts if it is not
the copy.

Stand-alone use (to test from another machine):
    python tests/harness/instance.py start [--port 18200] [--keep]     # prints the base URL, runs until Ctrl-C, then removes everything
"""
import argparse, atexit, json, os, random, shutil, signal, socket, subprocess, sys, tempfile, threading, time, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent.parent
sys.path.insert(0, str(HERE.parent))
from harness import libgen, safety                   # noqa: E402
from harness.appcopy import copy_app                 # noqa: E402


def free_port(kind=socket.SOCK_STREAM, lo=18200, hi=18999, avoid=()):
    for _ in range(200):
        p = random.randint(lo, hi)
        if p in avoid or p in safety.PRODUCTION_PORTS:
            continue
        s = socket.socket(socket.AF_INET, kind)
        try:
            s.bind(("0.0.0.0", p))
            return p
        except OSError:
            continue
        finally:
            s.close()
    raise RuntimeError("no free port")


class OscSink(threading.Thread):
    """Stands in for Companion's OSC listener: receives what the player sends and records it."""
    def __init__(self, port):
        super().__init__(daemon=True)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("127.0.0.1", port))
        self.sock.settimeout(0.2)
        self.port, self.msgs, self.lock, self.stop_flag = port, [], threading.Lock(), False

    def run(self):
        from pythonosc.osc_message import OscMessage
        while not self.stop_flag:
            try:
                data, _ = self.sock.recvfrom(65535)
            except socket.timeout:
                continue
            except OSError:
                return
            try:
                m = OscMessage(data)
                with self.lock:
                    self.msgs.append((time.time(), m.address, list(m.params)))
            except Exception:
                pass

    def since(self, t0):
        with self.lock:
            return [m for m in self.msgs if m[0] >= t0]

    def close(self):
        self.stop_flag = True
        try:
            self.sock.close()
        except OSError:
            pass


class Instance:
    def __init__(self, port=None, keep=False, project_dir=PROJECT, extra_config=None, wav_only=False, extra_env=None):
        self.project = Path(project_dir).resolve()
        self.keep, self.proc, self.sink, self.log = keep, None, None, None
        self.port = port or free_port()
        self.osc_port = free_port(socket.SOCK_DGRAM, avoid=(self.port,))
        self.sink_port = free_port(socket.SOCK_DGRAM, avoid=(self.port, self.osc_port))
        self.extra = extra_config or {}
        self.extra_env = extra_env or {}          # e.g. SDL_AUDIODRIVER=disk for the audio-capture tests
        self.wav_only = wav_only
        self.manifest = {}
        self.workdir = None

    @property
    def base_url(self):
        return f"http://127.0.0.1:{self.port}"

    def start(self, timeout=90):
        if self.port in safety.PRODUCTION_PORTS:
            raise safety.Refused(f"port {self.port} is a production port")
        self.workdir = Path(tempfile.mkdtemp(prefix=safety.MARKER)).resolve()
        w = self.workdir
        if w == self.project or self.project in w.parents or w in self.project.parents:
            raise safety.Refused("the test folder overlaps the project folder")
        copy_app(w, self.project)
        (w / "media" / "library").mkdir(parents=True)
        self.manifest = libgen.generate(w / "media" / "library", ffmpeg_files=not self.wav_only)
        cfg = {"http_port": self.port, "osc_in_port": self.osc_port, "companion_host": "127.0.0.1", "companion_osc_port": self.sink_port,
               "resume_on_start": False, "storage_limit": None, "storage_reserve": "100MB", "cache_mb": 256}
        cfg.update(self.extra)
        cfg.update(json.loads(os.environ.get("CPTEST_EXTRA_CONFIG") or "{}"))         # e.g. CPTEST_EXTRA_CONFIG='{"ffmpeg_path": "/nope/ffmpeg"}' runs the whole suite without ffmpeg (CLAUDE.md Testing step 5)
        (w / "config.json").write_text(json.dumps(cfg, indent=1), encoding="utf-8")
        self.sink = OscSink(self.sink_port)
        self.sink.start()
        env = {**os.environ, "SDL_AUDIODRIVER": "dummy", "PYGAME_HIDE_SUPPORT_PROMPT": "1", "PYTHONUNBUFFERED": "1", **self.extra_env}
        self.log = open(w / "player.log", "wb")
        self.proc = self._spawn(env)
        atexit.register(self.stop)
        t0 = time.time()
        while time.time() - t0 < timeout:
            if self.proc.poll() is not None:
                self.stop()
                raise RuntimeError("the player exited during start-up:\n" + self.log_text()[-2000:])
            try:
                with urllib.request.urlopen(self.base_url + "/api/settings", timeout=2) as r:
                    cf = json.loads(r.read()).get("config_file", "")
                if Path(cf).resolve() != (w / "config.json").resolve():                     # something else answered on that port
                    self.stop()
                    raise safety.Refused(f"the instance on port {self.port} is not the test copy (config {cf})")
                break
            except (OSError, ValueError):
                time.sleep(0.3)
        else:
            self.stop()
            raise RuntimeError("the player did not start in %d s:\n%s" % (timeout, self.log_text()[-2000:]))
        self.wait_library()
        return self

    def _spawn(self, env):
        kw = {"creationflags": getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)} if os.name == "nt" else {"start_new_session": True}
        return subprocess.Popen([sys.executable, "-u", "-I", str(self.workdir / "player.py")], cwd=str(self.workdir), env=env, stdout=self.log,
                                stderr=subprocess.STDOUT, **kw)

    def _signal(self, sig_name):
        """Signal the player and its helper processes (POSIX: the whole process group)."""
        if not self.proc or self.proc.poll() is not None and os.name == "nt":
            return
        try:
            if os.name == "nt":
                (self.proc.terminate if sig_name == "TERM" else self.proc.kill)()
            else:
                os.killpg(self.proc.pid, getattr(signal, "SIG" + sig_name))
        except (ProcessLookupError, PermissionError, OSError):
            pass

    def restart(self, timeout=60):
        """Start the same player again (same folder, ports and sink) after it was killed."""
        env = {**os.environ, "SDL_AUDIODRIVER": "dummy", "PYGAME_HIDE_SUPPORT_PROMPT": "1", "PYTHONUNBUFFERED": "1", **self.extra_env}
        self.log = open(self.workdir / "player.log", "ab")
        self.proc = self._spawn(env)
        t0 = time.time()
        while time.time() - t0 < timeout:
            try:
                urllib.request.urlopen(self.base_url + "/api/state", timeout=2).read()
                return self
            except OSError:
                time.sleep(0.3)
        raise RuntimeError("the player did not come back")

    def wait_library(self, timeout=90):
        """Until every library file has a measured length and the player reports ready (the start-up scan has finished)."""
        t0 = time.time()
        while time.time() - t0 < timeout:
            try:
                with urllib.request.urlopen(self.base_url + "/api/library", timeout=5) as r:
                    files = json.loads(r.read())["files"]
                with urllib.request.urlopen(self.base_url + "/api/state", timeout=5) as r:
                    ready = json.loads(r.read()).get("status") == "ready"
                if files and ready and all(f.get("dur") is not None for f in files):
                    return
            except OSError:
                pass
            time.sleep(0.4)

    def log_text(self):
        try:
            self.log.flush()
            return (self.workdir / "player.log").read_text("utf-8", "replace")
        except Exception:
            return ""

    def stop(self):
        if self.proc:
            self._signal("TERM")
            try:
                self.proc.wait(8)
            except subprocess.TimeoutExpired:
                self._signal("KILL")
                try:
                    self.proc.wait(5)
                except subprocess.TimeoutExpired:
                    pass
            self._signal("KILL")                       # anything of the group that outlived the main process
        if self.sink:
            self.sink.close()
        if self.log:
            try:
                self.log.close()
            except Exception:
                pass
        if self.workdir and not self.keep:
            shutil.rmtree(self.workdir, ignore_errors=True)
        self.proc = None

    def __enter__(self):
        return self.start()

    def __exit__(self, *a):
        self.stop()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("action", choices=["start"])
    ap.add_argument("--port", type=int)
    ap.add_argument("--keep", action="store_true", help="keep the temp folder (config, library, player.log) after stopping")
    a = ap.parse_args()
    inst = Instance(port=a.port, keep=a.keep)
    inst.start()
    print(f"test instance ready: {inst.base_url}   (OSC in :{inst.osc_port}, folder {inst.workdir})", flush=True)
    print("run the tests against it with:  python tests/run.py --base-url %s [--allow-remote --confirm-target HOST:%d]" % (inst.base_url, inst.port), flush=True)
    stop = threading.Event()
    for s in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(s, lambda *_: stop.set())
        except (ValueError, OSError):
            pass
    try:
        while not stop.is_set() and inst.proc.poll() is None:
            time.sleep(0.5)
    finally:
        inst.stop()
        print("test instance stopped" + (f"; kept {inst.workdir}" if a.keep else " and removed"))


if __name__ == "__main__":
    main()
