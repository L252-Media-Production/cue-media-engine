"""Output-device tests with a mocked device list (double-spaced DVS names, duplicates, natural order).
Stand-alone like test_triggers.py:  python tests/test_devices.py   (needs pygame, aiohttp, python-osc, numpy, playwright).
It copies the app into a temp folder, sets CP_TEST_DEVICES (a test-only hook in player.py: device list from mock_devices.json), logs what reaches
pygame.mixer.init / the --preview worker, and never touches the real project folder, config or service."""
import json, math, os, shutil, socket, struct, subprocess, sys, tempfile, time, urllib.request, wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from harness.appcopy import copy_app   # noqa: E402

PROJECT = Path(__file__).resolve().parent.parent
DVS = [f"DVS Transmit {'' if i >= 6 else ' '}{2*i-1}-{2*i} (Dante Virtual Soundcard)" for i in range(1, 9)]   # 1-2 .. 9-10 double-spaced
DEVICES = ["System Audio"] + DVS + ["Out 10", "Out 2", "Speakers (Realtek)", "Speakers (Realtek)"]
FAILS = []


def check(name, ok, info=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"   {info}"))
    if not ok:
        FAILS.append(name)


def free_port(kind=socket.SOCK_STREAM):
    """An OS-assigned free port of the given kind (the OSC input is UDP: ask for a UDP port, a free TCP number can be taken as UDP)."""
    with socket.socket(socket.AF_INET, kind) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Box:
    """A disposable player with a mocked device list."""
    def __init__(self, state=None, devices=DEVICES, root=None):
        self.dir = Path(root or tempfile.mkdtemp(prefix="cptest-dev-"))
        (self.dir / "media/library").mkdir(parents=True, exist_ok=True)
        self.port = free_port()
        copy_app(self.dir, PROJECT)
        (self.dir / "config.json").write_text(json.dumps({"http_port": self.port, "osc_in_port": free_port(socket.SOCK_DGRAM)}))
        for n in "abc":
            lib = self.dir / "media/library" / f"{n}.wav"
            if not lib.exists():
                with wave.open(str(lib), "wb") as w:
                    w.setnchannels(2); w.setsampwidth(2); w.setframerate(48000)
                    w.writeframes(b"".join(struct.pack("<hh", int(3000 * math.sin(i / 20)), 0) for i in range(48000 * 2)))
        self.set_devices(devices)
        if state is not None:
            (self.dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
        self.proc = None

    def set_devices(self, devices):
        (self.dir / "mock_devices.json").write_text(json.dumps(devices), encoding="utf-8")

    def start(self):
        env = dict(os.environ, SDL_AUDIODRIVER="dummy", CP_TEST_DEVICES=str(self.dir))
        self.proc = subprocess.Popen([sys.executable, "-u", "-I", "player.py"], cwd=self.dir, env=env,
                                     stdout=open(self.dir / "out.log", "w"), stderr=subprocess.STDOUT)
        for _ in range(100):
            try:
                self.get("/api/devices")
                return self
            except Exception:
                time.sleep(0.2)
        raise RuntimeError("player did not start:\n" + (self.dir / "out.log").read_text())

    def stop(self):
        if self.proc:
            self.proc.kill(); self.proc.wait()
            self.proc = None

    def get(self, path):
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}{path}", timeout=5) as r:
            return json.loads(r.read())

    def post(self, path, obj):
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", json.dumps(obj).encode(), {"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())

    def log(self, name):
        f = self.dir / name
        return [json.loads(x) for x in f.read_text(encoding="utf-8").splitlines()] if f.exists() else []

    def state(self):
        f = self.dir / "state.json"
        return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}

    def url(self):
        return f"http://127.0.0.1:{self.port}/"

    def cleanup(self):
        self.stop(); shutil.rmtree(self.dir, ignore_errors=True)


def page_values(pg, sel):
    return pg.eval_on_selector(sel, "e=>[...e.options].map(o=>[o.value,o.textContent])")


def main():
    from playwright.sync_api import sync_playwright
    box = Box().start()
    try:
        with sync_playwright() as p:
            br = p.chromium.launch()
            pg = br.new_page(viewport={"width": 1400, "height": 900}); pg.add_init_script("localStorage.setItem('cp_tour','1')")
            pg.goto(box.url()); pg.wait_for_function("document.querySelector('#dev') && document.querySelector('#dev').options.length>1")

            # --- order and duplicates (server + page)
            api = box.get("/api/devices")["devices"]
            want = DVS + ["Out 2", "Out 10", "Speakers (Realtek)", "Speakers (Realtek)", "System Audio"]
            check("server sorts naturally (1-2 before 11-12, Out 2 before Out 10, double spaces ignored in the key)", api == want, api)
            opts = page_values(pg, "#dev")
            check("System default stays first", opts[0] == ["", "System default"], opts[0])
            check("option values are the exact names (double spaces kept)", [o[0] for o in opts[1:]] == api, opts)
            check("duplicate display names are told apart", [o[1] for o in opts if o[1].startswith("Speakers")] == ["Speakers (Realtek)", "Speakers (Realtek) (2)"], opts)
            check("Mirror and preview lists have the same exact values", [o[0] for o in page_values(pg, "#mdev")[1:]] == api)

            # --- each DVS pair: select in the page, check config, mixer init and reload
            for n in DVS:
                pg.select_option("#dev", value=n, force=True)
                for _ in range(40):
                    if box.state().get("audio_device") == n:
                        break
                    time.sleep(0.1)
                check(f"stores exact name: {n!r}", box.state().get("audio_device") == n, box.state())
                check(f"  pygame.mixer.init got it: {n!r}", box.log("init.log")[-1] == n, box.log("init.log")[-3:])
                pg.reload(); pg.wait_for_function("document.querySelector('#dev').options.length>1")
                check(f"  selection survives reload: {n!r}", pg.eval_on_selector("#dev", "e=>e.value") == n)

            # --- mirror + preview: exact name to the worker
            for pair in (DVS[0], DVS[4]):
                box.post("/api/mirror/enable", {"on": True})
                pg.reload(); pg.wait_for_function("document.querySelector('#mdev').options.length>1")
                pg.select_option("#mdev", value=pair); time.sleep(1.5)
                check(f"mirror stores exact name {pair!r}", box.state().get("mirror_device") == pair, box.state())
                check("  mirror worker started with the exact name", pair in box.log("worker.log"), box.log("worker.log"))
            pg.click("#setbtn"); pg.wait_for_selector("#settings[open]"); pg.click("#set_tabs [data-tab=audio]")
            pg.wait_for_function("document.querySelector('#set_pv').options.length>1")
            check("Settings preview select has exact values", [o[0] for o in page_values(pg, "#set_pv")[1:]] == api)
            pg.select_option("#set_pv", value=DVS[1]); time.sleep(1.5)
            check("preview stores exact name", box.state().get("preview_device") == DVS[1], box.state())
            check("  preview worker started with the exact name", DVS[1] in box.log("worker.log"), box.log("worker.log"))

            # --- refresh: a device that appears later
            late = "DVS Transmit  17-18 (Dante Virtual Soundcard)"
            box.set_devices(DEVICES + [late])
            check("late device not listed before the menu is opened", late not in [o[0] for o in page_values(pg, "#set_pv")])
            pg.click("#set_pv_cb"); time.sleep(0.8); pg.keyboard.press("Escape")
            vals = [o[0] for o in page_values(pg, "#set_pv")]
            check("opening the Settings output menu lists the late device, in order", late in vals and vals.index(late) == vals.index(DVS[-1]) + 1, vals)
            check("  the output menu got it too", late in [o[0] for o in page_values(pg, "#dev")])
            box.set_devices(DEVICES + [late, "Zeta Out"])
            pg.keyboard.press("Escape"); pg.click("#dev_out"); time.sleep(0.8); pg.keyboard.press("Escape")
            check("opening an output menu re-reads the list", "Zeta Out" in [o[0] for o in page_values(pg, "#dev")])
            box.set_devices(DEVICES + [late, "Zeta Out", "Late Settings Dev"])
            br.close()
    finally:
        box.cleanup()

    # --- a saved device that is not there at start-up
    gone = "DVS Transmit  1-2 (Dante Virtual Soundcard)"
    box = Box(state={"audio_device": gone, "preview_device": "Gone preview"}, devices=["Other Out"]).start()
    try:
        out = (box.dir / "out.log").read_text()
        d = box.get("/api/devices")
        check("missing saved output: logged clearly", "No current device has exactly that name" in out and repr(gone) in out, out[-400:])
        check("missing saved output: notice in /api/devices", gone in d["notices"].get("output", "") and "Gone preview" in d["notices"].get("preview", ""), d)
        check("missing saved output: system default used", d["current"] is None)
        check("missing saved output: state.json keeps the name", box.state().get("audio_device") == gone, box.state())
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            br = p.chromium.launch(); pg = br.new_page(viewport={"width": 1400, "height": 900}); pg.add_init_script("localStorage.setItem('cp_tour','1')")
            pg.goto(box.url()); pg.wait_for_selector("#devnote:not([hidden])")
            check("page shows the notice", gone in pg.text_content("#devnote"), pg.text_content("#devnote"))
            br.close()
        box.set_devices([gone, "Other Out"])
        r = box.post("/api/device", {"name": gone})
        check("choosing it once it exists works and clears the notice", r.get("ok") and "output" not in box.get("/api/devices")["notices"], r)
    finally:
        box.cleanup()
    print("\n%d failure(s)" % len(FAILS))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
