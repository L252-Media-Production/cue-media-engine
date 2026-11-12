#!/usr/bin/env python3
"""The shared dB scale (2.7.5 preview-rc2): centred between the Live pair and the PRV pair (equal gaps within 1 px), its labels centred on the column's centre line (also the one-character 0
and the infinity label, true minus sign U+2212), vertical positions unchanged (every label sits on its dB level of the meters; the -20 dBFS tone reaches the -20 line), nothing else moves
when the PRV pair appears or disappears (card size, meter size, label heights), and no scale in the one-line bar.   3 skins x light / dark x zoom 100 / 125 / 150 %, Chromium; Firefox and
WebKit at 100 and 150 %.     python tests/test_scale_centred.py [SHOT_DIR]      (needs playwright with the three browsers; own disposable player)"""
import io
import os
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from harness import client                       # noqa: E402
from harness.instance import Instance, PROJECT   # noqa: E402

FAILS = []
SHOTS = sys.argv[1] if len(sys.argv) > 1 else None
WANT = ["0", "−5", "−10", "−20", "−30", "−40", "−50", "−60", "−∞"]
BOTTOM = ["100%", "88%", "76%", "60%", "46%", "33%", "21%", "10%", "0%"]        # the label heights of rc1: unchanged
M = r"""(pvon)=>{
 const R=e=>{const r=e.getBoundingClientRect();return {l:r.left,t:r.top,r:r.right,b:r.bottom,w:r.width,h:r.height,cx:(r.left+r.right)/2,cy:(r.top+r.bottom)/2}};
 if(pvon!==null){lvl.classList.toggle('pvon',pvon);pvlvl.hidden=!pvon;pcap.hidden=!pvon;pvbtns.hidden=!pvon}
 const sc=document.querySelector('#lvl .dbs'),S=R(sc),lb=R(document.querySelector('#lbars')),card=R(document.getElementById('cl'));
 const pb=pvon?R(document.querySelector('#pvlvl .vm')):null,pbs=pvon?R(document.querySelector('#pvlvl .bars')):null;
 const labels=[...sc.querySelectorAll('b')].map(b=>{const g=document.createRange();g.selectNodeContents(b.firstChild);const t=g.getBoundingClientRect(),g2=document.createRange();g2.selectNodeContents(b);const w=g2.getBoundingClientRect();return {txt:b.textContent,bottom:b.style.bottom,cx:(w.left+w.right)/2,cy:(t.top+t.bottom)/2,w:w.width}});   // vertical: the line of the digits or the minus sign; horizontal: the whole label
 const grp=R(document.querySelector('#lvl .msb')),pgrp=pvon?R(document.querySelector('#lvl .msb.pvb')):null;
 const ms=document.getElementById('ms');
 return {S,lb,card,pbs,labels,lvlW:R(lvl).w,gapL:S.l-lb.r,gapR:pb?pb.l-S.r:null,
  grpFits:(grp.w<=parseFloat(getComputedStyle(lvl).getPropertyValue('--lgw'))+0.5)&&[...document.querySelectorAll('#lvl .msb:not([hidden])')].every(m=>{const q=m.getBoundingClientRect(),k=[...m.children].map(c=>c.getBoundingClientRect());return k[0].left>=q.left-0.5&&k[k.length-1].right<=q.right+0.5}),grpCentre:Math.abs(grp.cx-lb.cx)<=1.5,
  pgrpCentre:pgrp?Math.abs(pgrp.cx-pbs.cx)<=1.5:true,msScale:ms?ms.querySelectorAll('.scl,.dbs').length:0,
  yAt:db=>0}}"""


def check(name, ok, info=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"   {info}"))
    if not ok:
        FAILS.append(name)


def measure(pg, tag, api, snap):
    idle = pg.evaluate(M, False)
    shown = pg.evaluate(M, True)
    check(f"{tag}: the scale labels are {WANT} (true minus sign)", [l["txt"] for l in idle["labels"]] == WANT, [l["txt"] for l in idle["labels"]])
    check(f"{tag}: the label heights are the same as in rc1", [l["bottom"] for l in idle["labels"]] == BOTTOM, [l["bottom"] for l in idle["labels"]])
    check(f"{tag}: equal gaps Live pair | scale | PRV pair (within 1 px)", abs(shown["gapL"] - shown["gapR"]) <= 1, (shown["gapL"], shown["gapR"]))
    check(f"{tag}: with the PRV pair hidden the scale is beside the Live pair as before (a gap of 20 to 32 px, rc1: 29 / 23 px) and the block is not wider than the button group", 20 <= idle["gapL"] <= 32 and idle["lvlW"] <= 104, (idle["gapL"], idle["lvlW"]))
    off = max(abs(l["cx"] - shown["S"]["cx"]) for l in shown["labels"])
    check(f"{tag}: every label (also 0, -5 and the infinity one) is centred on the column's centre line (within 1 px)", off <= 1, [(l["txt"], round(l["cx"] - shown["S"]["cx"], 2)) for l in shown["labels"]])
    off = max(abs(l["cx"] - idle["S"]["cx"]) for l in idle["labels"])
    check(f"{tag}: ... and with the PRV pair hidden", off <= 1, off)
    # vertical: each label on its dB level (the meter's own height)
    bars = shown["lb"]
    want = [0, -5, -10, -20, -30, -40, -50, -60, -90]
    pct = pg.evaluate("db=>meterPct(db)", None) if False else None
    ys = [pg.evaluate("db=>meterPct(db)", d) for d in want]
    err = max(abs((bars["b"] - y / 100 * bars["h"]) - l["cy"]) for y, l in zip(ys, shown["labels"]))
    check(f"{tag}: every label stays on its dB level of the meters (within 1.5 px)", err <= 1.5, err)
    check(f"{tag}: showing / hiding the PRV pair moves nothing vertically and changes no size (card, meters, labels, scale)",
          abs(idle["card"]["h"] - shown["card"]["h"]) < 0.6 and abs(idle["card"]["w"] - shown["card"]["w"]) < 0.6 and abs(idle["lb"]["h"] - shown["lb"]["h"]) < 0.6 and abs(idle["lb"]["t"] - shown["lb"]["t"]) < 0.6
          and abs(idle["lb"]["w"] - shown["lb"]["w"]) < 0.6 and all(abs(a["cy"] - b["cy"]) < 0.6 for a, b in zip(idle["labels"], shown["labels"])) and abs(idle["S"]["w"] - shown["S"]["w"]) < 0.6,
          (idle["card"], shown["card"]))
    check(f"{tag}: the button groups are centred under their own bars and fit the column", shown["grpFits"] and shown["grpCentre"] and shown["pgrpCentre"], {k: shown[k] for k in ("grpFits", "grpCentre", "pgrpCentre")})
    check(f"{tag}: the one-line bar has no scale", shown["msScale"] == 0)
    if snap:
        pg.locator("#lvl").screenshot(path=snap)
    pg.evaluate(M, False)


def ink_ratio(png, dpr):
    from PIL import Image
    import numpy as np
    im = np.asarray(Image.open(io.BytesIO(png)).convert("L")).astype(int)
    bg = np.median(im)
    mask = np.abs(im - bg) > 60
    if not mask.any():
        return None
    ys, xs = np.nonzero(mask)
    return (ys.max() - ys.min() + 1) / dpr


def main():
    from playwright.sync_api import sync_playwright
    if SHOTS:
        os.makedirs(SHOTS, exist_ok=True)
    with Instance(wav_only=True, project_dir=os.environ.get("PP_PROJECT") or PROJECT) as inst, sync_playwright() as p:
        api = client.Api(inst.base_url, osc_port=inst.osc_port)
        for bname in ("chromium", "firefox", "webkit"):
            br = getattr(p, bname).launch()
            zooms = (1, 1.25, 1.5) if bname == "chromium" else (1, 1.5)
            for zoom in zooms:
                for skin in ("console", "studio", "stage"):
                    for theme in ("light", "dark"):
                        tag = f"{bname}/zoom{int(zoom * 100)}/{skin}/{theme}"
                        c = br.new_context(viewport={"width": int(1400 / zoom), "height": int(900 / zoom)}, device_scale_factor=zoom)
                        c.add_init_script(f"localStorage.setItem('cp_tour','1');localStorage.setItem('cp_skin','{skin}');localStorage.setItem('cp_theme','{theme}')")
                        pg = c.new_page(); errs = []
                        pg.on("pageerror", lambda e: errs.append(str(e)))
                        pg.goto(inst.base_url); pg.wait_for_selector("#lvl .dbs b", state="attached"); time.sleep(0.6)
                        snap = f"{SHOTS}/{bname}-{skin}-{theme}-zoom{int(zoom * 100)}.png" if SHOTS and zoom == 1 else None
                        measure(pg, tag, api, snap)
                        if zoom == 1 and theme == "light":
                            # the infinity sign has the size and weight of the numbers: the ink heights of "0" and of the infinity sign as the page draws them (canvas metrics with the
                            # label's own computed font and the infinity span's own size)
                            r = pg.evaluate("""()=>{const b=document.querySelector('#lvl .dbs b'),inf=document.querySelector('#lvl .dbs .inf'),cs=getComputedStyle(b),ci=getComputedStyle(inf);
                              const c=document.createElement('canvas').getContext('2d'),h=(ch,cs)=>{c.font=cs.fontWeight+' '+cs.fontSize+' '+cs.fontFamily;const m=c.measureText(ch);return m.actualBoundingBoxAscent+m.actualBoundingBoxDescent};
                              const ctr=(ch,s)=>{c.font=s.fontWeight+' '+s.fontSize+' '+s.fontFamily;const m=c.measureText(ch);return (m.actualBoundingBoxAscent-m.actualBoundingBoxDescent)/2};
                              return {digit:h('0',cs),inf:h('\u221e',ci),w:ci.fontWeight===cs.fontWeight,fs:[cs.fontSize,ci.fontSize],dy:ctr('\u221e',ci)-ctr('0',cs)-parseFloat(inf.style.top||0)}}""")
                            check(f"{tag}: the infinity sign has the weight of the numbers and an ink height within 0.8 to 1.25 of theirs (digit {r['digit']:.1f} px, infinity {r['inf']:.1f} px)", r["w"] and 0.8 <= r["inf"] / r["digit"] <= 1.25 and abs(r["dy"]) <= 1, r)
                        check(f"{tag}: no page errors", not errs, errs)
                        c.close()
            br.close()
        # the -20 dBFS tone reaches the -20 line (long_120s is a 300 Hz tone at -20 dBFS peak)
        br = p.chromium.launch(); c = br.new_context(viewport={"width": 1400, "height": 900}); c.add_init_script("localStorage.setItem('cp_tour','1')")
        pg = c.new_page(); pg.goto(inst.base_url); pg.wait_for_selector("#lvl .dbs b", state="attached")
        api.post("/api/playlists", {"name": "T"}); api.post("/api/playlists/0/add", {"files": ["long_120s.wav"]})
        api.cmd("0/0"); api.wait_playing("0/0"); time.sleep(1.5)
        y = pg.evaluate("""()=>{const b=document.querySelector('#lbars').getBoundingClientRect(),i=document.getElementById('m_live_l'),cov=parseFloat(i.style.height)/100,fill=b.top+cov*b.height;
           const lab=[...document.querySelectorAll('#lvl .dbs b')][3],g=document.createRange();g.selectNodeContents(lab);const t=g.getBoundingClientRect();return {fill,label:(t.top+t.bottom)/2,cov}}""")
        check("the -20 dBFS tone reaches the -20 line of the scale (within 4 px)", abs(y["fill"] - y["label"]) <= 4, y)
        api.cmd("stop"); c.close(); br.close()
    print(f"\n{len(FAILS)} failure(s)")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
