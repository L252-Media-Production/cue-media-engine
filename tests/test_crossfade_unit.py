#!/usr/bin/env python3
"""Cue panel crossfade field (#foc_xf, 2.7.2-rc4): the unit "s" is inside the field's box, to the right of the number; the number is not covered or clipped
(0.5, 3, 10, 2.5); typing and saving work as before; the Go column and the Cue panel keep their size; the field dims when Go is on Cut and focusing/clicking the "s" focuses it.
3 skins x dark/light x desktop / phone / touch.    python tests/test_crossfade_unit.py     (needs playwright; starts its own disposable player)"""
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from harness import client                       # noqa: E402
from harness.instance import Instance, PROJECT   # noqa: E402

FAILS = []
# Measured at v2.7.2-rc3 (0cae9e8): Go column width and Cue panel height (Ducking collapsed, a track cued).
BEFORE = {"console": {"desktop": 156, "phone": 224.7, "touch": 224.7}, "studio": {"desktop": 171.2, "phone": 248, "touch": 248},
          "stage": {"desktop": 249.6, "phone": 302, "touch": 302}}
GOCOL_W = 51.2


def check(name, ok, info=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"   {info}"))
    if not ok:
        FAILS.append(name)


JS = """v=>{const q=s=>document.querySelector(s),r=e=>e.getBoundingClientRect(),inp=q('#foc_xf'),s=q('#xfc span');
  if(v!=null)inp.value=v;
  const cs=getComputedStyle(inp),c=document.createElement('canvas').getContext('2d');c.font=cs.font;const tw=c.measureText(inp.value).width;
  const ib=r(inp),sb=r(s),pl=parseFloat(cs.paddingLeft),pr=parseFloat(cs.paddingRight),cx=ib.left+pl+(ib.width-pl-pr)/2;
  return {inside:sb.left>=ib.left-0.5&&sb.right<=ib.right+0.5&&sb.top>=ib.top-0.5&&sb.bottom<=ib.bottom+0.5,right:sb.left>=cx+tw/2-0.5,text:tw,avail:ib.width-pl-pr,
    scroll:inp.scrollWidth,client:inp.clientWidth,gocol:r(q('#gocol')).width,fs:r(q('#fs')).height,xfc:r(q('#xfc')).width,iw:ib.width}}"""


def main():
    from playwright.sync_api import sync_playwright
    with Instance(wav_only=True, project_dir=os.environ.get("XF_PROJECT") or PROJECT) as inst, sync_playwright() as p:
        api = client.Api(inst.base_url, osc_port=inst.osc_port)
        api.post("/api/playlists", {"name": "T"}); api.post("/api/playlists/0/add", {"files": ["long_120s.wav"]}); api.get("/api/0/0/focus")
        br = p.chromium.launch()
        for skin in ("console", "studio", "stage"):
            for theme in ("dark", "light"):
                for tag, kw in (("desktop", dict(viewport={"width": 1400, "height": 1000})), ("phone", dict(viewport={"width": 420, "height": 900})),
                                ("touch", dict(viewport={"width": 430, "height": 932}, has_touch=True, is_mobile=True))):
                    label = f"{skin}/{theme}/{tag}"
                    c = br.new_context(**kw)
                    c.add_init_script(f"localStorage.setItem('cp_tour','1');localStorage.setItem('cp_skin','{skin}');localStorage.setItem('cp_theme','{theme}')")
                    pg = c.new_page(); errs = []
                    pg.on("pageerror", lambda e: errs.append(str(e)))
                    pg.goto(inst.base_url); pg.wait_for_selector("#foc_xf"); pg.wait_for_function("!foc_xf.disabled", timeout=5000)
                    d0 = pg.evaluate(JS, None)
                    check(f"{label}: the s is inside the field's box", d0["inside"], d0)
                    check(f"{label}: Go column keeps its width ({GOCOL_W}) and the field fills it", abs(d0["gocol"] - GOCOL_W) < 0.6 and abs(d0["iw"] - GOCOL_W) < 0.6, d0)
                    check(f"{label}: Cue panel not taller than before ({BEFORE[skin][tag]})", d0["fs"] <= BEFORE[skin][tag] + 0.5, d0["fs"])
                    for v in ("0.5", "3", "10", "2.5", "30"):
                        d = pg.evaluate(JS, v)
                        check(f"{label}: '{v}' shown whole, left of the s", d["inside"] and d["right"] and d["text"] <= d["avail"] + 0.5, d)
                    # typing and saving: same request as before (xftime), same stored value
                    pg.click("#foc_xf", click_count=3); pg.keyboard.type("2.5"); pg.keyboard.press("Tab")
                    pg.wait_for_timeout(400)
                    xf = api.get("/api/playlists").json
                    xf = (xf["playlists"] if isinstance(xf, dict) and "playlists" in xf else xf)[0]["tracks"][0].get("xfade")
                    check(f"{label}: typing 2.5 saves 2500 ms", xf == 2500, xf)
                    # clicking the s focuses the field
                    pg.evaluate("foc_xf.blur()")
                    box = pg.locator("#xfc span").bounding_box()
                    pg.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
                    check(f"{label}: clicking the s focuses the field", pg.evaluate("document.activeElement===foc_xf"))
                    # dim on Cut, full on focus
                    pg.evaluate("goSet('cut')"); pg.evaluate("foc_xf.blur()"); pg.mouse.move(2, 2); pg.wait_for_timeout(400)
                    op = pg.evaluate("+getComputedStyle(xfc).opacity")
                    check(f"{label}: dimmed while Go is on Cut", op < 0.6, op)
                    pg.evaluate("goSet('crossfade')")
                    pg.evaluate("foc_xf.value='';focXfSave()")
                    pg.wait_for_timeout(300)
                    check(f"{label}: no page errors", not errs, errs)
                    c.close()
        br.close()
    print(f"\n{len(FAILS)} failure(s)")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
