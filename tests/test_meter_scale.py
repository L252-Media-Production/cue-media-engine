#!/usr/bin/env python3
"""Meter scale: ONE scale (0, \u22125 ... \u221260, \u2212\u221e) beside the Live pair serves the Preview pair that sits to its right while previewing (2.7.5 rc1): the labels, their heights, none clipped, and the Live and
Preview bars span exactly the scale (same top, same bottom).
3 skins x desktop / 420 / touch.    python tests/test_meter_scale.py      (needs playwright; starts its own disposable player)"""
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from harness.instance import Instance, PROJECT   # noqa: E402

FAILS = []
WANT = ["0", "\u22125", "\u221210", "\u221220", "\u221230", "\u221240", "\u221250", "\u221260", "\u2212\u221e"]      # a true minus sign (U+2212) since preview-rc2
JS = """()=>{const sc=document.querySelector('#lvl .dbs'),bs=[...sc.querySelectorAll('b')],sr=sc.getBoundingClientRect(),R=e=>e.getBoundingClientRect();
  const l=R(document.querySelector('#lbars .vm')),pv=R(document.querySelector('#pvlvl .vm')),pc=R(document.querySelector('#pvlvl'));
  return {t:bs.map(b=>b.textContent),pos:bs.map(b=>b.style.bottom),clip:bs.some(b=>b.getBoundingClientRect().right>sr.right+0.5),
          spanLive:Math.round(sr.height)===Math.round(l.height)&&Math.abs(sr.top-l.top)<1.5,
          samePair:Math.abs(l.top-pv.top)<2&&Math.abs(l.bottom-pv.bottom)<2,pvRight:pc.left>=sr.right-0.5,pvThin:pv.width<l.width,scales:document.querySelectorAll('#lvl .scl').length}}"""


def check(name, ok, info=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"   {info}"))
    if not ok:
        FAILS.append(name)


def main():
    from playwright.sync_api import sync_playwright
    with Instance(wav_only=True, project_dir=os.environ.get("MSC_PROJECT") or PROJECT) as inst, sync_playwright() as p:
        br = p.chromium.launch()
        for skin in ("console", "studio", "stage"):
            for tag, kw in (("1400", dict(viewport={"width": 1400, "height": 1000})), ("420", dict(viewport={"width": 420, "height": 900})),
                            ("touch", dict(viewport={"width": 430, "height": 932}, has_touch=True, is_mobile=True))):
                label = f"{skin}/{tag}"
                c = br.new_context(**kw)
                c.add_init_script(f"localStorage.setItem('cp_tour','1');localStorage.setItem('cp_skin','{skin}')")
                pg = c.new_page(); errs = []
                pg.on("pageerror", lambda e: errs.append(str(e)))
                pg.goto(inst.base_url); pg.wait_for_selector("#lvl .dbs b", state="attached")
                pg.evaluate("lvl.classList.add('pvon');pvlvl.hidden=false")      # the Preview pair as it looks while previewing
                d = pg.evaluate(JS)
                check(f"{label}: the scale labels are {WANT}", d["t"] == WANT, d["t"])
                check(f"{label}: there is one scale, shared", d["scales"] == 1, d["scales"])
                check(f"{label}: every non-zero label starts with a minus", all(t == "0" or t.startswith("\u2212") for t in d["t"]))
                check(f"{label}: the scale spans the Live bars", d["spanLive"], d)
                check(f"{label}: the Preview pair spans the same height as the Live pair", d["samePair"], d)
                check(f"{label}: the Preview pair is to the right of the scale and thinner", d["pvRight"] and d["pvThin"], d)
                check(f"{label}: no label is clipped", not d["clip"], d)
                check(f"{label}: no page errors", not errs, errs)
                c.close()
        br.close()
    print(f"\n{len(FAILS)} failure(s)")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
