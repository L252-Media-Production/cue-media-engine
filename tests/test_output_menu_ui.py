#!/usr/bin/env python3
"""Output menu (#cbo, 2.7.5 rc3): every outline and focus ring (the highlighted row, the first row, the search box) is fully inside the box that clips it, the last row
is reachable, the popover stays in the viewport: Live output, Mirror device, Settings > Audio menus, 3 skins x light / dark x desktop / phone.
python tests/test_output_menu_ui.py [SHOT_DIR]    (needs playwright; own disposable player)"""
import sys, os, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from harness import client
from harness.instance import Instance, PROJECT
from playwright.sync_api import sync_playwright
SH = sys.argv[1] if len(sys.argv) > 1 else None
GEO = """()=>{const q=document.getElementById('cbo_q'),l=document.getElementById('cbo_l'),c=document.getElementById('cbo'),it=[...l.querySelectorAll('.cbo-i')];
 const R=e=>e.getBoundingClientRect(),cr=R(c),lr=R(l),qr=R(q),vw=innerWidth,vh=innerHeight,out=[];
 const cs=getComputedStyle(c),bw=parseFloat(cs.borderTopWidth)||0;
 // the search box + its focus ring (2px + offset) inside the popover's padding box
 const q2=getComputedStyle(q);const off=parseFloat(q2.outlineOffset)||0,ring=2+Math.max(off,0);
 if(qr.left-ring<cr.left+bw-0.5||qr.right+ring>cr.right-bw+0.5||qr.top-ring<cr.top+bw-0.5)out.push('search ring clipped');
 // rows: bottom of the last row inside the list box once scrolled to the end; every row's outline (inside, offset -1) inside the list
 l.scrollTop=l.scrollHeight;const last=it[it.length-1];if(last){const b=R(last);if(b.bottom>R(l).bottom+0.5||b.top<R(l).top-0.5)out.push('last row clipped')}
 for(const e of it){const b=R(e);if(b.left<lr.left-0.5||b.right>lr.right+0.5)out.push('row wider than list');
   const o=getComputedStyle(e);if(o.outlineStyle!=='none'){const ex=(parseFloat(o.outlineWidth)||0)+Math.max(parseFloat(o.outlineOffset)||0,0);
    l.scrollTop=0;const c1=R(l);const bb=R(e);
    if(bb.left-ex<c1.left-0.5||bb.right+ex>c1.right+0.5)out.push('row outline clipped at the sides')}}
 for(const e of [it[0]]){if(!e)continue;const o=getComputedStyle(e);const ex=o.outlineStyle==='none'?0:(parseFloat(o.outlineWidth)||0)+Math.max(parseFloat(o.outlineOffset)||0,0);if(R(e).top-ex<R(l).top-0.5)out.push('first row outline clipped at the top')}
 {const hl=l.querySelector('.cbo-i.on');if(hl){const o=getComputedStyle(hl);const ex=(parseFloat(o.outlineWidth)||0)+Math.max(parseFloat(o.outlineOffset)||0,0);l.scrollTop=l.scrollHeight;const b=R(hl),c1=R(l);if(b.left-ex<c1.left-0.5||b.right+ex>c1.right+0.5)out.push('highlighted outline clipped (sides)');l.scrollTop=0}}
 if(lr.bottom>cr.bottom-bw+0.5)out.push('list taller than popover');
 if(cr.left<-0.5||cr.right>vw+0.5||cr.top<-0.5||cr.bottom>vh+0.5)out.push('popover outside viewport');
 l.scrollTop=0;return {out,rows:it.length,pop:[Math.round(cr.left),Math.round(cr.top),Math.round(cr.right),Math.round(cr.bottom)],vp:[vw,vh]}}"""
fails = []
def chk(n, ok, info=""):
    print(("PASS " if ok else "FAIL ") + n + ("" if ok else "   " + str(info)))
    if not ok: fails.append(n)
with Instance(wav_only=True, project_dir=PROJECT) as inst, sync_playwright() as p:
    api = client.Api(inst.base_url, osc_port=inst.osc_port)
    api.post("/api/mirror/enable", {"on": True})
    br = p.chromium.launch()
    for skin in ("console", "studio", "stage"):
        for theme in ("light", "dark"):
            for wname, vp, touch in (("desktop", {"width": 1280, "height": 800}, False), ("phone", {"width": 390, "height": 760}, True)):
                c = br.new_context(viewport=vp, has_touch=touch, is_mobile=touch)
                c.add_init_script(f"localStorage.setItem('cp_tour','1');localStorage.setItem('cp_skin','{skin}');localStorage.setItem('cp_theme','{theme}')")
                pg = c.new_page(); tag = f"{skin}/{theme}/{wname}"
                pg.goto(inst.base_url); pg.wait_for_selector("#setbtn"); time.sleep(0.8)
                # main-page menus: Live output and Mirror device
                for sel in ("#dev_out", "#mdev_cb"):
                    if not pg.is_visible(sel): continue
                    pg.click(sel); pg.wait_for_selector("#cbo:popover-open"); time.sleep(0.2)
                    pg.keyboard.press("ArrowDown"); pg.keyboard.press("End"); time.sleep(0.1)
                    g = pg.evaluate(GEO); chk(f"{tag} {sel}", not g["out"], g)
                    if SH and sel == "#dev_out": pg.screenshot(path=f"{SH}/{skin}-{theme}-{wname}-live-output-menu.png")
                    pg.keyboard.press("Escape")
                # Settings > Audio: preview target + player output
                pg.click("#setbtn"); pg.wait_for_selector("#settings[open]")
                if wname == "desktop": pg.click("#set_tabs [data-tab=audio]")
                else: pg.click("[data-sec=audio] .sh")
                for sel in ("#set_pvt_cb", "#set_pv_cb", "#set_mdev_cb"):
                    if not pg.is_visible(sel): continue
                    pg.click(sel); pg.wait_for_selector("#cbo:popover-open"); time.sleep(0.2)
                    pg.keyboard.press("ArrowDown"); time.sleep(0.1)
                    g = pg.evaluate(GEO); chk(f"{tag} {sel}", not g["out"], g)
                    pg.keyboard.press("End"); time.sleep(0.1); g = pg.evaluate(GEO); chk(f"{tag} {sel} (last row highlighted)", not g["out"], g)
                    if SH and sel == "#set_pv_cb": pg.screenshot(path=f"{SH}/{skin}-{theme}-{wname}-preview-player-output-menu.png")
                    pg.keyboard.press("Escape")
                c.close()
    br.close()
print(f"\n{len(fails)} failed")
sys.exit(1 if fails else 0)
