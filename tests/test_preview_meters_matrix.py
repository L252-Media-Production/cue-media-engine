#!/usr/bin/env python3
"""Preview meters / pinned Live panel across skins and themes (2.7.5 rc1): Console, Studio, Stage x light, dark x desktop, phone, in the states idle, previewing, scrolled (one line)
and the output menu open. Geometry checks (nothing of the Live card sticks out of it or off the page, the strip fits the viewport, the menu is inside the viewport) and screenshots.
    python tests/test_preview_meters_matrix.py [SHOT_DIR]      (needs playwright; own disposable player)"""
import os
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from harness.instance import Instance, PROJECT   # noqa: E402

FAILS = []
SHOTS = sys.argv[1] if len(sys.argv) > 1 else None
GEO = """()=>{const c=document.querySelector('#cl').getBoundingClientRect(),vw=innerWidth,out=[];
 document.querySelectorAll('#cl *').forEach(e=>{const r=e.getBoundingClientRect();if(!r.width||!r.height||e.closest('[hidden]'))return;const cs=getComputedStyle(e);if(cs.display==='none'||cs.visibility==='hidden')return;
  if(e.closest('canvas'))return;if(r.right>c.right+1||r.left<c.left-1)out.push((e.id||e.className||e.tagName)+' '+Math.round(r.right-c.right))});
 const btn=['#mutebtn','#pvsolo','#dev_out','#pvmute','#pv_out'].map(s=>document.querySelector(s)).filter(e=>e&&e.getBoundingClientRect().width>0).map(e=>{const r=e.getBoundingClientRect();return [e.id,r.left>=c.left-0.5&&r.right<=c.right+0.5&&r.bottom<=c.bottom+0.5]});
 return {out:out.slice(0,5),btn:btn.filter(b=>!b[1]).map(b=>b[0]),page:document.documentElement.scrollWidth>vw+1}}"""
STRIP = """()=>{const r=document.getElementById('ms').getBoundingClientRect(),o=[];document.querySelectorAll('#ms *').forEach(e=>{const q=e.getBoundingClientRect();if(q.width&&!e.closest('[hidden]')&&(q.right>r.right+1||q.left<r.left-1))o.push(e.id||e.className)});return {inView:r.left>=-0.5&&r.right<=innerWidth+0.5&&r.top>=-0.5,out:o.slice(0,4),h:r.height}}"""


def check(name, ok, info=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"   {info}"))
    if not ok:
        FAILS.append(name)


def main():
    from playwright.sync_api import sync_playwright
    if SHOTS:
        os.makedirs(SHOTS, exist_ok=True)
    with Instance(wav_only=True, project_dir=os.environ.get("PP_PROJECT") or PROJECT) as inst, sync_playwright() as p:
        br = p.chromium.launch()
        for skin in ("console", "studio", "stage"):
            for theme in ("light", "dark"):
                for wn, vp, touch in (("desktop", {"width": 1280, "height": 800}, False), ("phone", {"width": 390, "height": 844}, True)):
                    tag = f"{skin}/{theme}/{wn}"
                    c = br.new_context(viewport=vp, has_touch=touch, is_mobile=touch)
                    c.add_init_script(f"localStorage.setItem('cp_tour','1');localStorage.setItem('cp_skin','{skin}');localStorage.setItem('cp_theme','{theme}')")
                    pg = c.new_page(); errs = []
                    pg.on("pageerror", lambda e: errs.append(str(e)))
                    pg.goto(inst.base_url); pg.wait_for_selector("#setbtn"); time.sleep(0.9)
                    pg.evaluate("document.body.style.minHeight='3200px'")
                    shot = lambda n: pg.screenshot(path=f"{SHOTS}/{skin}-{theme}-{wn}-{n}.png") if SHOTS else None   # noqa: E731
                    g = pg.evaluate(GEO); check(f"{tag} idle: nothing sticks out of the Live card or the page", not g["out"] and not g["btn"] and not g["page"], g); shot("1-idle")
                    row = pg.locator(".lt", has_text="long_120s").first.locator(".ib.pv")
                    (row.tap if touch else row.click)(); pg.wait_for_function("PVCUR.state==='playing'", timeout=8000); time.sleep(0.6)
                    pg.evaluate("window.scrollTo(0,0)"); time.sleep(0.4)
                    g = pg.evaluate(GEO); check(f"{tag} previewing: nothing sticks out (the pair, its buttons, the card)", not g["out"] and not g["btn"] and not g["page"], g); shot("2-previewing")
                    pg.click("#dev_out"); pg.wait_for_selector("#cbo:popover-open"); time.sleep(0.2)
                    mg = pg.evaluate("(()=>{const r=cbo.getBoundingClientRect();return r.left>=-0.5&&r.right<=innerWidth+0.5&&r.top>=-0.5&&r.bottom<=innerHeight+0.5})()")
                    check(f"{tag} output menu open: inside the viewport", mg); shot("3-output-menu"); pg.keyboard.press("Escape")
                    pg.evaluate("window.scrollTo(0,1400)"); time.sleep(0.7)
                    s = pg.evaluate(STRIP); check(f"{tag} scrolled: the one-line strip fits the viewport", s["inView"] and not s["out"], s); shot("4-scrolled-one-line")
                    check(f"{tag}: no page errors", not errs, errs)
                    c.close()
        br.close()
    print(f"\n{len(FAILS)} failure(s)")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
