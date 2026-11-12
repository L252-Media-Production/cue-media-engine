#!/usr/bin/env python3
"""Clicking the playing title in the one-line bar (2.7.5 preview-rc2, Fix 3): it is the same handler as the full panel's title (liveGo), so it shows the playing item in its playlist, with the same
"show me" flash; not hidden under the bar or the header; keyboard (Enter, Space), an accessible name; it triggers nothing else (no play, pause or seek); the pause button and the progress keep
their own behaviour.  Desktop bar and phone strip.    python tests/test_strip_title.py      (needs playwright; own disposable player)"""
import os
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from harness import client                       # noqa: E402
from harness.instance import Instance, PROJECT   # noqa: E402

FAILS = []


def check(name, ok, info=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"   {info}"))
    if not ok:
        FAILS.append(name)


def main():
    from playwright.sync_api import sync_playwright
    with Instance(wav_only=True, project_dir=os.environ.get("PP_PROJECT") or PROJECT) as inst, sync_playwright() as p:
        api = client.Api(inst.base_url, osc_port=inst.osc_port)
        for i in range(6):
            api.post("/api/playlists", {"name": f"List {i}"})
            api.post(f"/api/playlists/{i}/add", {"files": ["tone_a.wav", "tone_b.wav", "tone_c.wav", "long_120s.wav", "short_1s.wav", "short_2s.wav"]})
        br = p.chromium.launch()
        for label, vp, touch in (("desktop bar", (1280, 800), False), ("phone strip", (390, 844), True)):
            for key in ("click", "Enter", "Space"):
                api.cmd("stop"); api.cmd("5/3"); api.wait_playing("5/3")           # the last playlist's long track is live
                c = br.new_context(viewport={"width": vp[0], "height": vp[1]}, has_touch=touch, is_mobile=touch)
                c.add_init_script("localStorage.setItem('cp_tour','1');localStorage.removeItem('cp_coll');localStorage.setItem('cp_coll',JSON.stringify(['List 5']))")
                pg = c.new_page(); errs = []
                pg.on("pageerror", lambda e: errs.append(str(e)))
                pg.goto(inst.base_url); pg.wait_for_selector("li.t"); time.sleep(1.2)
                tag = f"{label} {key}"
                pg.evaluate("window.scrollTo(0,0)"); time.sleep(0.3)
                pg.evaluate("window.scrollTo(0,document.getElementById('cl').getBoundingClientRect().bottom+scrollY-4)"); time.sleep(0.5)       # the panel is gone: the bar shows
                check(f"{tag}: the bar is showing", not pg.evaluate("ms.hidden"))
                st = pg.evaluate("({role:ms_name.getAttribute('role'),tab:ms_name.tabIndex,name:ms_name.getAttribute('aria-label'),cursor:getComputedStyle(ms_name).cursor,lk:ms_name.classList.contains('lk')})")
                check(f"{tag}: the title looks and acts like a link (role, focusable, pointer, accessible name)", st["role"] == "link" and st["tab"] == 0 and st["lk"] and st["cursor"] == "pointer" and "playlist" in (st["name"] or ""), st)
                before = {k: api.state()[k] for k in ("state", "live_id", "live_volume")}
                pos0 = api.state()["live_pos"]
                same = pg.evaluate("ms_name.onclick===livenm.onclick||String(ms_name.getAttribute('onclick'))===String(livenm.getAttribute('onclick'))")
                check(f"{tag}: it calls the very same handler as the full panel's title (liveGo)", same)
                pg.evaluate("window.scrollTo(0,0)"); time.sleep(0.2)
                pg.evaluate("window.scrollTo(0,document.getElementById('cl').getBoundingClientRect().bottom+scrollY-4)"); time.sleep(0.5)
                if key == "click":
                    (pg.tap if touch else pg.click)("#ms_name")
                else:
                    pg.focus("#ms_name"); pg.keyboard.press("Enter" if key == "Enter" else " ")
                time.sleep(1.8)
                r = pg.evaluate("""()=>{const li=document.querySelector('li.t.live'),b=li.getBoundingClientRect(),m=ms.getBoundingClientRect(),h=document.documentElement.clientHeight;
                    return {top:b.top,bottom:b.bottom,msBottom:m.bottom,vh:h,flash:li.classList.contains('flash'),coll:li.closest('.pl').classList.contains('coll'),hidden:ms.hidden}}""")
                check(f"{tag}: the playing item is in view and not covered by the bar", r["top"] >= r["msBottom"] + 2 and r["bottom"] <= r["vh"] + 1, r)
                check(f"{tag}: the playlist was opened and the item flashes (same as the full view)", not r["coll"] and r["flash"], r)
                after = {k: api.state()[k] for k in before}
                check(f"{tag}: nothing else happened: no play, pause, stop, volume or seek", after == before and api.state()["live_pos"] >= pos0 - 0.1 and api.state()["live_pos"] < pos0 + 4, (before, after, pos0, api.state()["live_pos"]))
                check(f"{tag}: no page errors", not errs, errs)
                c.close()
        # the pause button of the bar keeps its own behaviour
        c = br.new_context(viewport={"width": 1280, "height": 800}); c.add_init_script("localStorage.setItem('cp_tour','1')")
        pg = c.new_page(); pg.goto(inst.base_url); pg.wait_for_selector("li.t"); time.sleep(1.0)
        pg.evaluate("window.scrollTo(0,document.getElementById('cl').getBoundingClientRect().bottom+scrollY-4)"); time.sleep(0.5)
        pg.click("#ms_pp"); time.sleep(0.8)
        check("the bar's pause button still pauses", api.state()["state"] == "paused")
        pg.click("#ms_pp"); time.sleep(0.6)
        check("... and resumes", api.state()["state"] == "playing")
        api.cmd("stop"); c.close(); br.close()
    print(f"\n{len(FAILS)} failure(s)")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
