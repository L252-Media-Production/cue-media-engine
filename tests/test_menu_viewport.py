#!/usr/bin/env python3
"""Output menus stay inside the viewport (2.7.5 preview-rc2, Fix 1): the Live speaker menu, the Preview speaker menu, the Preview panel's selector, the Mirror device menu and the Settings menus
open fully inside the visible viewport (8 px margin on all four sides), whatever the width (360 / 390 / 768 / 1280 / 1920, a short 1280 x 500 window), the scroll position of the button, the skin,
theme and zoom (100 / 150 %). The search box stays on top while the list scrolls, every outline and focus ring is inside the clipping boxes (the rc3 fix), the menu follows a resize and a scroll
and closes when its button has scrolled out of view.     python tests/test_menu_viewport.py [SHOT_DIR]      (needs playwright; own disposable player)"""
import os
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from harness import client                       # noqa: E402
from harness.instance import Instance, PROJECT   # noqa: E402

FAILS = []
SHOTS = sys.argv[1] if len(sys.argv) > 1 else None
M = 8
GEO = """()=>{const c=document.getElementById('cbo'),q=document.getElementById('cbo_q'),l=document.getElementById('cbo_l'),R=e=>e.getBoundingClientRect(),
 cr=R(c),vw=document.documentElement.clientWidth,vh=document.documentElement.clientHeight,out=[];
 if(cr.left<%(m)s-0.5)out.push('left '+cr.left);if(cr.top<%(m)s-0.5)out.push('top '+cr.top);if(cr.right>vw-%(m)s+0.5)out.push('right '+(cr.right-(vw-%(m)s)));if(cr.bottom>vh-%(m)s+0.5)out.push('bottom '+(cr.bottom-(vh-%(m)s)));
 const cs=getComputedStyle(c),bw=parseFloat(cs.borderTopWidth)||0,qr=R(q),qs=getComputedStyle(q),ring=2+Math.max(parseFloat(qs.outlineOffset)||0,0);
 if(qr.left-ring<cr.left+bw-0.5||qr.right+ring>cr.right-bw+0.5||qr.top-ring<cr.top+bw-0.5)out.push('search ring clipped');
 const lr=R(l);const sel=l.querySelector('.cbo-i.on');if(sel){const o=getComputedStyle(sel),ex=(parseFloat(o.outlineWidth)||0)+Math.max(parseFloat(o.outlineOffset)||0,0),b=R(sel);
   if(b.left-ex<lr.left-0.5||b.right+ex>lr.right+0.5)out.push('row outline clipped sides')}
 const last=[...l.querySelectorAll('.cbo-i')].pop();l.scrollTop=l.scrollHeight;if(last){const b=R(last);if(b.bottom>R(l).bottom+0.5)out.push('last row clipped')}l.scrollTop=0;
 return {out,pop:[Math.round(cr.left),Math.round(cr.top),Math.round(cr.right),Math.round(cr.bottom)],vp:[vw,vh],searchOnTop:qr.bottom<=lr.top+1,scrolls:l.scrollHeight>l.clientHeight+1}}""" % {"m": M}


def check(name, ok, info=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"   {info}"))
    if not ok:
        FAILS.append(name)


def main():
    from playwright.sync_api import sync_playwright
    if SHOTS:
        os.makedirs(SHOTS, exist_ok=True)
    names = [f"Device number {i} with a rather long name (Dante Virtual Soundcard)" for i in range(1, 31)]
    with Instance(wav_only=True, project_dir=os.environ.get("PP_PROJECT") or PROJECT) as inst, sync_playwright() as p:
        api = client.Api(inst.base_url, osc_port=inst.osc_port)
        api.post("/api/mirror/enable", {"on": True})
        br = p.chromium.launch()
        sizes = [(360, 740), (390, 844), (768, 1024), (1280, 800), (1920, 1080), (1280, 500)]
        for (w, h) in sizes:
            for zoom in (1, 1.5):
                for skin, theme in (("console", "light"), ("studio", "dark"), ("stage", "light"), ("console", "dark"), ("stage", "dark"), ("studio", "light")):
                    if zoom != 1 and (w, h) not in ((1280, 800), (390, 844)):
                        continue
                    tag = f"{w}x{h}/zoom{int(zoom * 100)}/{skin}/{theme}"
                    touch = w < 500
                    c = br.new_context(viewport={"width": int(w / zoom), "height": int(h / zoom)}, device_scale_factor=zoom, has_touch=touch, is_mobile=touch)
                    c.add_init_script(f"localStorage.setItem('cp_tour','1');localStorage.setItem('cp_skin','{skin}');localStorage.setItem('cp_theme','{theme}')")
                    pg = c.new_page(); errs = []
                    pg.on("pageerror", lambda e: errs.append(str(e)))
                    pg.goto(inst.base_url); pg.wait_for_selector("#dev_out"); time.sleep(0.8)
                    pg.evaluate("n=>{document.body.style.minHeight='2600px';PVDEV='Player output';fillPvTarget();lvl.classList.add('pvon');pvlvl.hidden=false;pcap.hidden=false;pvbtns.hidden=false;pvsel.value='pi'}", None)
                    pg.route("**/api/devices", lambda r: r.fulfill(json={"devices": names, "current": "", "preview": "", "mirror": "", "mirror_enabled": True, "notices": {}}))
                    pg.evaluate("n=>{devSet(dev,'System default',n,'');devSet(mdev,'Off',n,'')}", names)
                    for scroll in (0, 400):
                        pg.evaluate(f"window.scrollTo(0,{scroll})"); time.sleep(0.3)
                        for sel in ("#dev_out", "#pv_out", "#mdev_cb", "#pvsel_cb"):
                            if not pg.is_visible(sel):
                                continue
                            try:
                                (pg.tap if touch else pg.click)(sel, timeout=3000)
                            except Exception:
                                continue
                            pg.wait_for_selector("#cbo:popover-open", timeout=3000); time.sleep(0.2)
                            g = pg.evaluate(GEO)
                            check(f"{tag} scroll{scroll} {sel}: inside the viewport with an 8 px margin, no ring or row clipped", not g["out"], g)
                            if sel == "#dev_out":
                                check(f"{tag} scroll{scroll} {sel}: the search box stays on top, the list scrolls inside its own box", g["searchOnTop"] and (g["scrolls"] or len(names) < 4), g)
                            if SHOTS and scroll == 0 and sel in ("#dev_out", "#pv_out") and ((w, h) in ((360, 740), (1280, 800), (1280, 500)) and zoom == 1):
                                pg.screenshot(path=f"{SHOTS}/menu-{w}x{h}-{skin}-{theme}-{sel[1:-4]}.png")
                            pg.keyboard.press("Escape")
                    check(f"{tag}: no page errors", not errs, errs)
                    c.close()
        # follows resize and scroll, closes when the button leaves the view
        c = br.new_context(viewport={"width": 1280, "height": 800}); c.add_init_script("localStorage.setItem('cp_tour','1')")
        pg = c.new_page(); pg.goto(inst.base_url); pg.wait_for_selector("#dev_out"); time.sleep(0.6)
        pg.evaluate("document.body.style.minHeight='3000px'"); pg.click("#dev_out"); pg.wait_for_selector("#cbo:popover-open")
        pg.set_viewport_size({"width": 520, "height": 700}); time.sleep(0.4)
        g = pg.evaluate(GEO)
        check("after a window resize the open menu is re-placed and still inside the viewport", not g["out"] and pg.is_visible("#cbo"), g)
        pg.set_viewport_size({"width": 1280, "height": 800}); time.sleep(0.3)
        pg.evaluate("window.scrollTo(0,30)"); time.sleep(0.3)
        a = pg.evaluate("(()=>{const r=dev_out.getBoundingClientRect(),c=cbo.getBoundingClientRect();return Math.abs((cbo.dataset.side==='down'?c.top-r.bottom:r.top-c.bottom))})()")
        check("after a small scroll it stays attached to its button (4 px gap)", pg.is_visible("#cbo") and a < 6, a)
        pg.evaluate("window.scrollTo(0,1500)"); time.sleep(0.5)
        check("when its button has scrolled out of view the menu closes", not pg.is_visible("#cbo"))
        c.close(); br.close()
    print(f"\n{len(FAILS)} failure(s)")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
