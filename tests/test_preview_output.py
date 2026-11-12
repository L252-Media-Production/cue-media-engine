#!/usr/bin/env python3
"""Preview panel output (2.7.5 rc1): the Output dropdown is on the transport row to the RIGHT of the volume slider (headphone icon and the device name, no "Output" label, no separate Output
row), the waveform runs the full width below, the full name is in the title, nothing is clipped. 3 skins x desktop / 420 / 320 / touch.
    python tests/test_preview_output.py      (needs playwright; starts its own disposable player)"""
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from harness.instance import Instance, PROJECT   # noqa: E402

FAILS = []
NAME = "HDA Intel PCH: ALC892 Analog (hw:0,0) with a rather long device name"
JS = """name=>{PVDEV=name;fillPvTarget();pvsel.value='pi';cbSync(pvsel);
  const q=s=>document.querySelector(s),r=e=>e.getBoundingClientRect(),cb=q('#pvsel_cb'),lab=cb.closest('label'),main=q('#pv .pvmain'),vol=q('#pvvol'),sp=cb.firstChild;
  const row=q('#pv .pvseekrow'),wf=q('#wfp');
  return {cls:lab.className,w:r(lab).width,mw:r(main).width,icon:!!lab.querySelector('svg.pvic'),hasSmall:!!lab.querySelector('small'),inRow:row.contains(lab),
          right:r(cb).left>=r(vol).right-1,sameLine:r(cb).top<r(vol).bottom&&r(cb).bottom>r(vol).top,ctlRow:!!q('#pv .pvctl'),
          title:cb.title,txt:sp.textContent,ell:sp.scrollWidth>sp.clientWidth,over:q('#pv').scrollWidth>q('#pv').clientWidth+1,
          rightIn:r(cb).right<=r(main).right+1&&r(q('#pvtime')).right<=r(main).right+1,
          wfFull:Math.abs(r(wf).width-r(main).width)<2,hasMeters:!!q('#pv #pvlvl')||!!q('#pv .vmeter')}}"""


def check(name, ok, info=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"   {info}"))
    if not ok:
        FAILS.append(name)


def main():
    from playwright.sync_api import sync_playwright
    with Instance(wav_only=True, project_dir=os.environ.get("PO_PROJECT") or PROJECT) as inst, sync_playwright() as p:
        br = p.chromium.launch()
        for skin in ("console", "studio", "stage"):
            for tag, kw in (("1400", dict(viewport={"width": 1400, "height": 1000})), ("420", dict(viewport={"width": 420, "height": 900})),
                            ("320", dict(viewport={"width": 320, "height": 800})), ("touch", dict(viewport={"width": 430, "height": 932}, has_touch=True, is_mobile=True))):
                label = f"{skin}/{tag}"
                c = br.new_context(**kw)
                c.add_init_script(f"localStorage.setItem('cp_tour','1');localStorage.setItem('cp_wave','1');localStorage.setItem('cp_skin','{skin}')")
                pg = c.new_page(); errs = []
                pg.on("pageerror", lambda e: errs.append(str(e)))
                pg.goto(inst.base_url); pg.wait_for_selector("#pvsel_cb")
                d = pg.evaluate(JS, NAME)
                check(f"{label}: an outsel label with the headphone icon and no 'Output' text", "outsel" in d["cls"].split() and d["icon"] and not d["hasSmall"], d)
                check(f"{label}: it is on the transport row, to the right of the volume slider (on a phone the row is too narrow for it, so it wraps to the line below the slider)", d["inRow"] and (d["right"] or not label.endswith("/1400")) and not d["ctlRow"], d)
                if label.endswith(("1400",)):
                    check(f"{label}: ... on the same line as the slider", d["sameLine"], d)
                check(f"{label}: the waveform runs the full width of the panel and the meters are gone", d["wfFull"] and not d["hasMeters"], d)
                check(f"{label}: full name in the title", NAME in d["title"], d["title"])
                check(f"{label}: nothing overflows the card", d["rightIn"] and not d["over"], d)
                if d["ell"]:
                    check(f"{label}: (ellipsis only because the name overflows)", d["txt"] == "Player output (" + NAME + ")")
                check(f"{label}: no page errors", not errs, errs)
                c.close()
        br.close()
    print(f"\n{len(FAILS)} failure(s)")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
