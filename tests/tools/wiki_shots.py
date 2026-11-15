#!/usr/bin/env python3
"""Screenshots for the GitHub wiki (see docs/wiki-screenshots.md). Stand-alone: not part of tests/run.py.
Starts a disposable player (generated library, dummy audio, simulated Live input), drives the page with Playwright and writes cropped PNGs.
A file is only rewritten when its pixels changed, so a re-run after an unrelated change leaves the wiki repo clean.

    python tests/tools/wiki_shots.py [--out DIR] [--only a,b] [--phone] [--list]

Needs: the player's requirements, tests/requirements.txt, playwright (+ `playwright install chromium`) and pillow.
To add a shot: write a function `shot_<name>(pg, ctx)` that leaves the page in the wanted state and returns the CSS selector to crop
(or None for the whole viewport), then add it to SHOTS with its viewport."""
import argparse, io, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent)); sys.path.insert(0, str(HERE.parent / "api"))
from harness import client                       # noqa: E402
from harness.instance import Instance, PROJECT   # noqa: E402
from test_live_input import make_env, set_feed   # noqa: E402

DESKTOP = {"width": 1280, "height": 900}
PHONE = {"width": 390, "height": 844}
FREEZE_CSS = "*,*::before,*::after{animation:none!important;transition:none!important;caret-color:transparent!important}"
LIB = {  # a readable demo set: playlist name -> library files (generated tones; names only matter on screen)
    "Pre-show": ["tone_a.wav", "tone_b.wav", "tone_c.wav", "long_120s.wav"],
    "Walk-in": ["short_2s.wav", "loud.wav", "quiet.wav"],
}


class Ctx:
    def __init__(self, inst, api, feed_dir):
        self.inst, self.api, self.feed_dir = inst, api, feed_dir


# --- shots: each prepares the page and returns the selector to crop -------------------------------------------------------------

def shot_trim_dialog(pg, c):
    pg.evaluate("openTrim(0,3)")                       # long_120s.wav
    pg.wait_for_selector("#trdlg[open]")
    pg.wait_for_function("typeof TR!=='undefined'&&TR.full>0")
    pg.evaluate("TR.inn=8;TR.out=96;TR.end='fade';TR.fade=3000;TR.start='fade';TR.fadeIn=1500;trUpd()")
    pg.wait_for_timeout(600)
    return "#trdlg"


def shot_live_input_card(pg, c):
    set_feed(c.feed_dir, state="run", db=-24.0, hz=500, channels=2)
    pg.wait_for_function("document.getElementById('inp_chip').textContent!=='No input'", timeout=10000)
    if pg.get_attribute("#inp_t", "aria-expanded") != "true":
        pg.click("#inp_t")
    c.api.cmd("input/ducknow/off")
    pg.wait_for_timeout(1200)
    set_feed(c.feed_dir, state="run", db=-24.0, hz=500, channels=2)
    pg.wait_for_timeout(800)
    return "#inpc"


def _play_paused(c, pl, tr, at):
    c.api.cmd(f"{pl}/{tr}")
    c.api.wait_playing()
    c.api.cmd(f"seek/{at}")
    c.api.cmd("pause")
    time.sleep(0.8)


def shot_live_card(pg, c):
    _play_paused(c, 0, 3, 41)
    pg.wait_for_timeout(1200)
    return "#cl"


def shot_playlists(pg, c):
    c.api.post("/api/playlists/0/trim", {"track": 3, "in": 8, "out": 96, "end": "fade"})
    _play_paused(c, 0, 1, 1)
    pg.reload(); pg.wait_for_selector("#lists li.t")
    pg.add_style_tag(content=FREEZE_CSS)
    pg.wait_for_timeout(1200)
    return "#plcol"


def shot_layout_edit(pg, c):
    pg.evaluate("layEdit()")
    pg.wait_for_selector("body.ledit")
    pg.wait_for_timeout(800)
    return None


SHOTS = {  # name -> (function, viewport, also on phone?)
    "trim-dialog": (shot_trim_dialog, DESKTOP, False),
    "live-input-card": (shot_live_input_card, DESKTOP, False),
    "live-card": (shot_live_card, DESKTOP, True),
    "playlists": (shot_playlists, DESKTOP, True),
    "layout-edit": (shot_layout_edit, DESKTOP, False),
}


def write_if_changed(path, png):
    from PIL import Image, ImageChops
    new = Image.open(io.BytesIO(png)).convert("RGBA")
    if path.exists():
        old = Image.open(path).convert("RGBA")
        if old.size == new.size and ImageChops.difference(old, new).getbbox() is None:
            return False
    path.write_bytes(png)
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(PROJECT.parent / "cue-media-engine.wiki" / "images"))
    ap.add_argument("--only", default="")
    ap.add_argument("--phone", action="store_true", help="also take the 390 px variants (suffix -phone) of the shots that have one")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()
    if a.list:
        for n, (_, vp, ph) in SHOTS.items():
            print(n, f"{vp['width']}px", "(+phone)" if ph else "")
        return
    names = [n for n in a.only.split(",") if n] or list(SHOTS)
    bad = [n for n in names if n not in SHOTS]
    if bad:
        sys.exit("unknown shot: " + ", ".join(bad))
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    from playwright.sync_api import sync_playwright
    d, env = make_env()
    set_feed(d, state="run", db=-90.0, channels=2)
    cfg = {"input_device": "Fake input", "input_armed": True, "preview_device": "Mock out 1", "duck_threshold_db": -30}
    changed, same = [], []
    with Instance(wav_only=True, extra_config=cfg, extra_env=env) as inst, sync_playwright() as p:
        api = client.Api(inst.base_url, osc_port=inst.osc_port)
        api.cmd("rescan")
        for i, (name, files) in enumerate(LIB.items()):
            api.post("/api/playlists", {"name": name})
            api.post(f"/api/playlists/{i}/add", {"files": files})
        time.sleep(2)
        ctx = Ctx(inst, api, d)
        br = p.chromium.launch()
        for name in names:
            fn, vp, has_phone = SHOTS[name]
            variants = [("", vp)] + ([("-phone", PHONE)] if a.phone and has_phone else [])
            for suffix, size in variants:
                api.cmd("stopall")
                set_feed(d, state="run", db=-90.0, channels=2)
                c = br.new_context(viewport=size, device_scale_factor=1, reduced_motion="reduce", has_touch=bool(suffix), is_mobile=bool(suffix))
                c.add_init_script("localStorage.setItem('cp_tour','1');localStorage.setItem('cp_theme','dark');localStorage.removeItem('cp_layout')")
                pg = c.new_page()
                pg.goto(inst.base_url); pg.wait_for_selector("#lists li.t")
                pg.add_style_tag(content=FREEZE_CSS)
                sel = fn(pg, ctx)
                png = pg.locator(sel).screenshot() if sel else pg.screenshot()
                f = out / f"{name}{suffix}.png"
                (changed if write_if_changed(f, png) else same).append(f.name)
                print(("wrote   " if f.name in changed else "same    ") + f.name, f"{f.stat().st_size // 1024} KB")
                c.close()
        br.close()
    print(f"\n{len(changed)} changed, {len(same)} unchanged")


if __name__ == "__main__":
    main()
