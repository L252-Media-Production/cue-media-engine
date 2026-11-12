#!/usr/bin/env python3
"""Ducking row (2.7.2-rc3): the Reduction meter sits on the Input Gain row (right-hand column) as a slim 8 px red meter, label and value styled like Ratio's;
"Stay ducked until it ends" is in the Ducking heading line; nothing clips or overflows; the Cue panel is not taller than in rc2.
(3 skins x dark/light x desktop 1400 / phone 420 / touch).    python tests/test_reduction_meter.py      (needs playwright; starts its own disposable player)"""
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from harness import client                       # noqa: E402
from harness.instance import Instance, PROJECT   # noqa: E402

FAILS = []
# Height of #fs (Cue panel, Ducking open) measured at v2.7.2-rc2 (1911cf1): the bound. Same for dark and light.
RC2 = {"console": {"desktop": 269.14, "phone": 417.09, "touch": 417.09},
       "studio": {"desktop": 326.17, "phone": 443.73, "touch": 443.73},
       "stage": {"desktop": 379.34, "phone": 510.91, "touch": 510.91}}
RED = "rgb(%s)"   # filled per theme from --live


def check(name, ok, info=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"   {info}"))
    if not ok:
        FAILS.append(name)


JS = """()=>{const q=s=>document.querySelector(s),r=e=>e.getBoundingClientRect(),cs=e=>getComputedStyle(e),
  g=q('#dk_grm'),bar=q('#dk_grm .grbar'),pot=q('#potrow'),rv=q('#dk_grv'),gl=q('#dk_grm .grl'),ig=q('#top_trk').closest('label'),rat=q('#dk_rat').closest('label'),
  rv0=q('#dk_rat_v'),rl=q('#dk_rel').closest('label'),head=q('.dkhead'),hold=q('#dk_hold').closest('label'),pr=r(pot);
  const inside=[g,bar,rv,gl,hold].every(e=>{const b=r(e);return b.left>=pr.left-1&&b.right<=pr.right+1});
  const txt=e=>e.firstChild&&e.firstChild.nodeType===3?e.firstChild.parentNode:e;
  return {h:r(bar).height,w:r(bar).width,
    sameRow:Math.abs(r(g).top-r(ig).top)<=1,rightCol:Math.abs(r(g).left-r(rat).left)<=1||Math.abs(r(g).left-r(rl).left)<=1,
    colAfter:r(g).left>r(ig).left,
    gl:[cs(gl).fontSize,cs(gl).fontFamily],ratl:[cs(rat).fontSize,cs(rat).fontFamily],
    v:[cs(rv).fontSize,cs(rv).fontFamily,cs(rv).fontWeight],ratv:[cs(rv0).fontSize,cs(rv0).fontFamily,cs(rv0).fontWeight],
    inside,scrollOver:pot.scrollWidth>pot.clientWidth+1,txt:rv.textContent,col0:cs(rv).color,dim:cs(gl).color,
    holdInHead:head.contains(hold),holdAbove:r(hold).bottom<=r(q('#dk_thr').closest('label')).top+1,
    summaryInHead:head.contains(q('#duck_sum')),fsH:r(q('#fs')).height,
    docOver:document.documentElement.scrollWidth>innerWidth+1,live:cs(document.documentElement).getPropertyValue('--live').trim()||cs(q('#fs')).getPropertyValue('--live').trim(),
    holdH:r(hold).height,ticks:getComputedStyle(q('#dk_grm .grbar'),'::after').backgroundSize,below:r(g).top>=r(ig).bottom-1,fsOver:q('#fs').scrollWidth>q('#fs').clientWidth+1}}"""


def main():
    from playwright.sync_api import sync_playwright
    with Instance(wav_only=True, project_dir=os.environ.get("RM_PROJECT") or PROJECT) as inst, sync_playwright() as p:
        api = client.Api(inst.base_url, osc_port=inst.osc_port)
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
                    pg.goto(inst.base_url); pg.wait_for_selector("#duckt"); pg.click("#duckt")
                    d = pg.evaluate(JS)
                    check(f"{label}: meter is 8 px high", abs(d["h"] - 8) < 1.1, d["h"])
                    if tag == "desktop":
                        check(f"{label}: Reduction is in the Input Gain row (tops within 1 px)", d["sameRow"], d)
                    if tag == "desktop":
                        check(f"{label}: Reduction is in the right-hand column, lined up with Ratio/Release", d["colAfter"] and d["rightCol"], d)
                    else:
                        check(f"{label}: one column: Reduction follows Input Gain", d["below"] or d["sameRow"], d)
                    check(f"{label}: label has Ratio's font size and family", d["gl"] == d["ratl"], (d["gl"], d["ratl"]))
                    check(f"{label}: value has the other values' size, family and weight (bold)", d["v"] == d["ratv"] and int(d["v"][2]) >= 600, (d["v"], d["ratv"]))
                    check(f"{label}: idle value is -0.0 dB, dim", d["txt"] == "-0.0 dB" and d["col0"] == d["dim"], (d["txt"], d["col0"], d["dim"]))
                    check(f"{label}: checkbox is in the Ducking heading, above the settings, and so is the summary", d["holdInHead"] and d["holdAbove"] and d["summaryInHead"], d)
                    check(f"{label}: nothing clips or overflows (Cue panel; the page-wide overflow at phone width is older and unchanged)", d["inside"] and not d["scrollOver"] and not d["fsOver"], d)
                    check(f"{label}: Cue panel not taller than rc2 ({RC2[skin][tag]} px)", d["fsH"] <= RC2[skin][tag] + 0.5, d["fsH"])
                    check(f"{label}: tick every 10 dB on the 30 dB scale", "33.33" in d["ticks"] or "33.3" in d["ticks"], d["ticks"])
                    # forced ducked value (the page's own meter feed would overwrite it between two holds, so the feed is switched off for this check: it raced about once in ten runs)
                    pg.evaluate("window.meterFrame=()=>{};window.__lk=()=>{dk_gr.style.setProperty('--gr','20%');dk_grv.textContent='-6.1 dB';dk_grm.classList.add('duck')};__lk();setInterval(__lk,5)")
                    pg.wait_for_timeout(80)
                    e = pg.evaluate("()=>({fill:getComputedStyle(dk_gr).backgroundColor,txt:getComputedStyle(dk_grv).color,w:dk_gr.getBoundingClientRect().width/dk_gr.parentNode.clientWidth,live:(()=>{const t=document.createElement('i');t.style.color='var(--live)';document.body.appendChild(t);const c=getComputedStyle(t).color;t.remove();return c})()})")
                    check(f"{label}: fill and value are the page's red (--live) while ducking", e["fill"] == e["live"] and e["txt"] == e["live"], e)
                    check(f"{label}: -6 dB fills 20 % of the track (0 dB left, 30 dB right)", abs(e["w"] - 0.2) < 0.03, e)
                    # checkbox: clicking its label toggles it and the API state follows
                    before = bool(api.get("/api/settings/top").json["hold"])
                    pg.click("label.dkhold")
                    pg.wait_for_timeout(300)
                    after = bool(api.get("/api/settings/top").json["hold"])
                    check(f"{label}: clicking the checkbox label toggles the setting (API {before} -> {after})", before != after and pg.evaluate("dk_hold.checked") == after)
                    api.post("/api/settings/top", {"hold": False})
                    check(f"{label}: no page errors", not errs, errs)
                    c.close()
        br.close()
    print(f"\n{len(FAILS)} failure(s)")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
