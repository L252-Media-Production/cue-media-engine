#!/usr/bin/env python3
"""Live meter: the Mute (M) and Solo (S) buttons have a 6 px radius in every skin, the M / S / speaker group is centred under the two meter bars and their scale and sits below the LIVE caption. 3 skins x 2 themes x desktop / phone / touch.
    python tests/test_mute_solo.py      (needs playwright; starts its own disposable player; MS_PROJECT=<other checkout> tests an older copy)"""
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from harness import client                       # noqa: E402
from harness.instance import Instance, PROJECT   # noqa: E402

FAILS = []
JS = """()=>{const r=e=>{const b=document.querySelector(e).getBoundingClientRect();return {l:b.left,r:b.right,t:b.top,b:b.bottom,h:b.height}};
  const q=s=>document.querySelector(s),rad=s=>getComputedStyle(q(s)).borderTopLeftRadius+'|'+getComputedStyle(q(s)).borderBottomRightRadius;
  const m=r('#mutebtn'),s=r('#pvsolo'),o=r('#dev_out'),bars=r('#lbars'),sc=r('#lvl .dbs'),cap=r('#lvl small'),lv=r('#lvl');
  return {radM:rad('#mutebtn'),radS:rad('#pvsolo'),pair:(Math.min(m.l,s.l,o.l)+Math.max(m.r,s.r,o.r))/2,bars:(bars.l+sc.r)/2,ms:[m.l,s.l,o.l,m.r,s.r,o.r],pairTop:Math.min(m.t,s.t),capBottom:cap.b,
          wm:m.r-m.l,hm:m.b-m.t,lvlH:lv.h,sclL:r('#lvl .scl').l}}"""


def check(name, ok, info=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"   {info}"))
    if not ok:
        FAILS.append(name)


def main():
    from playwright.sync_api import sync_playwright
    with Instance(wav_only=True, project_dir=os.environ.get("MS_PROJECT") or PROJECT) as inst, sync_playwright() as p:
        client.Api(inst.base_url, osc_port=inst.osc_port)
        br = p.chromium.launch()
        for skin in ("console", "studio", "stage"):
            for theme in ("dark", "light"):
                for tag, kw in (("1400", dict(viewport={"width": 1400, "height": 1000})), ("420", dict(viewport={"width": 420, "height": 900})),
                                ("touch", dict(viewport={"width": 430, "height": 932}, has_touch=True, is_mobile=True))):
                    label = f"{skin}/{theme}/{tag}"
                    c = br.new_context(**kw)
                    c.add_init_script(f"localStorage.setItem('cp_tour','1');localStorage.setItem('cp_theme','{theme}');localStorage.setItem('cp_skin','{skin}')")
                    pg = c.new_page(); errs = []
                    pg.on("pageerror", lambda e: errs.append(str(e)))
                    pg.goto(inst.base_url); pg.wait_for_selector("#mutebtn")
                    d = pg.evaluate(JS)
                    check(f"{label}: both buttons have a 6 px radius", d["radM"] == "6px|6px" and d["radS"] == "6px|6px", (d["radM"], d["radS"]))
                    check(f"{label}: 26 px square", abs(d["wm"] - 26) < .5 and abs(d["hm"] - 26) < .5, d)
                    check(f"{label}: M, S and the speaker button (2.7.5 rc1) are centred under the Live bars and scale (within 1 px)", abs(d["pair"] - d["bars"]) <= 1, d)
                    check(f"{label}: pair below the caption", d["pairTop"] >= d["capBottom"], d)
                    print(f"     {label}: live meter height {d['lvlH']:.1f}")
                    check(f"{label}: no page errors", not errs, errs)
                    c.close()
        br.close()
    print(f"\n{len(FAILS)} failure(s)")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
