#!/usr/bin/env python3
"""The one-line Live bar appears when MORE THAN HALF of the full panel is out of view (2.7.5 preview-rc2, Fix 2): scroll in steps and check it is hidden up to 46 % out and shown from 54 % out,
no flicker around 50 % (a few % of hysteresis), no layout shift (the content below the panel does not move when the bar appears or goes), it never overlaps the page header (it is fixed at the top
with a higher z-order), at 100 / 125 / 150 % zoom and on a phone, with the pin and shrink options in every combination.    python tests/test_strip_threshold.py   (needs playwright; own player)"""
import os
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from harness.instance import Instance, PROJECT   # noqa: E402

FAILS = []


def check(name, ok, info=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"   {info}"))
    if not ok:
        FAILS.append(name)


def main():
    from playwright.sync_api import sync_playwright
    with Instance(wav_only=True, project_dir=os.environ.get("PP_PROJECT") or PROJECT) as inst, sync_playwright() as p:
        br = p.chromium.launch()
        for label, vp, touch, zoom in (("desktop 100%", (1280, 800), False, 1), ("desktop 125%", (1280, 800), False, 1.25), ("desktop 150%", (1280, 800), False, 1.5), ("phone", (390, 844), True, 1)):
            for pin, mini in ((True, True), (True, False), (False, True), (False, False)):
                tag = f"{label} pin={'on' if pin else 'off'} shrink={'on' if mini else 'off'}"
                c = br.new_context(viewport={"width": int(vp[0] / zoom), "height": int(vp[1] / zoom)}, device_scale_factor=zoom, has_touch=touch, is_mobile=touch)
                c.add_init_script(f"localStorage.setItem('cp_tour','1');localStorage.setItem('cp_pin','{1 if pin else 0}');localStorage.setItem('cp_pinmini','{1 if mini else 0}')")
                pg = c.new_page(); errs = []
                pg.on("pageerror", lambda e: errs.append(str(e)))
                pg.goto(inst.base_url); pg.wait_for_selector("#cl"); time.sleep(0.8)
                pg.evaluate("document.body.style.minHeight='4000px'")
                time.sleep(0.2)
                geo = pg.evaluate("(()=>{const r=cl.getBoundingClientRect();return {top:r.top+scrollY,h:r.height,below:cuerow.getBoundingClientRect().top+scrollY}})()")
                shows = pin and mini
                seen = []
                step = max(4, int(geo["h"] / 40))
                y = 0
                while y < geo["top"] + geo["h"] + 40:
                    pg.evaluate(f"window.scrollTo(0,{y})"); time.sleep(0.12)
                    out = (y - geo["top"]) / geo["h"]
                    hidden = pg.evaluate("ms.hidden")
                    seen.append((round(out, 3), hidden))
                    y += step
                early = [s for s in seen if s[0] <= 0.46 and not s[1]]
                late = [s for s in seen if s[0] >= 0.54 and s[1]]
                if shows:
                    check(f"{tag}: hidden up to 46 % out", not early, early[:3])
                    check(f"{tag}: shown from 54 % out", not late, late[:3])
                    first = next((s[0] for s in seen if not s[1]), None)
                    check(f"{tag}: it first appears just past 50 % out ({first})", first is not None and 0.46 < first <= 0.60, first)
                else:
                    check(f"{tag}: the bar never shows", all(s[1] for s in seen), [s for s in seen if not s[1]][:3])
                # no flicker: wiggle around the threshold
                mid = geo["top"] + 0.5 * geo["h"]
                flips = 0
                last = None
                for k in range(40):
                    yy = mid + (-0.012 * geo["h"] if k % 2 == 0 else 0.012 * geo["h"])
                    pg.evaluate(f"window.scrollTo(0,{yy})"); time.sleep(0.07)
                    h = pg.evaluate("ms.hidden")
                    if last is not None and h != last:
                        flips += 1
                    last = h
                if shows:
                    check(f"{tag}: no flicker when the scroll position wiggles by +-1.2 % of the panel height around 50 % ({flips} changes)", flips <= 2, flips)
                # no layout shift and no overlap with the page header
                if shows:
                    pg.evaluate(f"window.scrollTo(0,{geo['top'] + 0.3 * geo['h']})"); time.sleep(0.3)
                    b1 = pg.evaluate("cuerow.getBoundingClientRect().top+scrollY")
                    pg.evaluate(f"window.scrollTo(0,{geo['top'] + 0.3 * geo['h']})"); time.sleep(0.1)
                    pg.evaluate(f"window.scrollTo(0,{geo['top'] + 0.7 * geo['h']})"); time.sleep(0.4)
                    shown = not pg.evaluate("ms.hidden")
                    b2 = pg.evaluate("cuerow.getBoundingClientRect().top+scrollY")
                    check(f"{tag}: the bar is visible at 70 % and the content below the panel did not move ({b1:.1f} -> {b2:.1f})", shown and abs(b1 - b2) < 0.6, (shown, b1, b2))
                    z = pg.evaluate("(()=>{const r=ms.getBoundingClientRect(),cs=getComputedStyle(ms);return {top:r.top,pos:cs.position,z:+cs.zIndex,hz:Math.max(0,...[...document.querySelectorAll('.top,header,#cl')].map(e=>+getComputedStyle(e).zIndex||0))}})()")
                    check(f"{tag}: it is fixed at the top of the view with a higher z-order than the page content", abs(z["top"]) < 1.5 and z["pos"] == "fixed" and z["z"] > z["hz"], z)
                check(f"{tag}: no page errors", not errs, errs)
                c.close()
        br.close()
    print(f"\n{len(FAILS)} failure(s)")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
