#!/usr/bin/env python3
"""Close buttons are circles or squares, never ovals (2.8.0 follow-up2, Task 4; desktop and tablet widths, the phone layout is out of scope).
Real player (own disposable instance) + Playwright (Chromium). For every close button in the app (Settings, the Health panel, the download and playlist
toasts, the file-information popover) it measures the bounding box and asserts abs(width - height) <= 0.5 and a computed border-radius that is 0 or at
least half the width (a pill radius on a box that is not square is the oval of the Stage skin: the generic button rule gives min-height:var(--btn) = 46 px
there). Also: Stage in light and dark at three widths, one check each in Console and Studio, a Health title that wraps, the ✕ against its background
(>= 3:1), the focus ring (>= 3:1, round, not clipped by the panel).
    python tests/test_close_buttons_ui.py [SHOT_DIR]      (SHOT_DIR: before/after screenshots of the Stage skin)"""
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from harness import client                       # noqa: E402
from harness.instance import Instance, PROJECT   # noqa: E402

FAILS = []
SHOTS = sys.argv[1] if len(sys.argv) > 1 else None

LUM = r"""
const num=s=>(s.match(/-?[\d.]+(?:e-?\d+)?/g)||[]).map(Number);
const parse=s=>{if(!s||s==='transparent')return null;const n=num(s);if(s.startsWith('color(')){return n.length<3?null:[n[0]*255,n[1]*255,n[2]*255,n.length>3?n[3]:1]}if(s.startsWith('rgb')){return [n[0],n[1],n[2],n.length>3?n[3]:1]}return null};
const over=(t,b)=>{const a=t[3];return [t[0]*a+b[0]*(1-a),t[1]*a+b[1]*(1-a),t[2]*a+b[2]*(1-a),1]};
const bgOf=el=>{const ch=[];for(let e=el;e;e=e.parentElement){const c=parse(getComputedStyle(e).backgroundColor);if(c&&c[3]>0)ch.push(c)}let b=[255,255,255,1];for(let i=ch.length-1;i>=0;i--)b=over(ch[i],b);return b};
const lum=c=>{const f=v=>{v/=255;return v<=0.03928?v/12.92:Math.pow((v+0.055)/1.055,2.4)};return 0.2126*f(c[0])+0.7152*f(c[1])+0.0722*f(c[2])};
const ratio=(a,b)=>{const l1=lum(a),l2=lum(b);return (Math.max(l1,l2)+0.05)/(Math.min(l1,l2)+0.05)};
"""
MEASURE = "sel=>{" + LUM + """
  const b=document.querySelector(sel);if(!b)return null;const r=b.getBoundingClientRect();const cs=getComputedStyle(b);
  const rad=cs.borderTopLeftRadius;const rp=rad.endsWith('%')?parseFloat(rad)/100*r.width:parseFloat(rad);
  let fg=parse(cs.color);const back=bgOf(b);if(fg[3]<1)fg=over(fg,back);
  return {w:r.width,h:r.height,radius:rp,rad,ratio:Math.round(ratio(fg,back)*100)/100,shown:r.width>0&&r.height>0}}"""
FOCUS = "sel=>{" + LUM + """
  const b=document.querySelector(sel);b.focus();const cs=getComputedStyle(b);const r=b.getBoundingClientRect();
  const ow=parseFloat(cs.outlineWidth)||0,off=parseFloat(cs.outlineOffset)||0,ext=ow+Math.max(off,0);
  let clipped=false;for(let e=b.parentElement;e&&e!==document.documentElement;e=e.parentElement){const o=getComputedStyle(e);
   if(/(auto|hidden|scroll|clip)/.test(o.overflowX+o.overflowY)){const c=e.getBoundingClientRect();if(r.left-ext<c.left-0.5||r.right+ext>c.right+0.5||r.top-ext<c.top-0.5||r.bottom+ext>c.bottom+0.5){clipped=true}}}
  const vis=b.matches(':focus-visible');const col=parse(cs.outlineColor);const back=bgOf(b.parentElement);
  return {style:cs.outlineStyle,ow,off,vis,clipped,ratio:col&&ow>0?Math.round(ratio(col[3]<1?over(col,back):col,back)*100)/100:0}}"""

BUTTONS = [          # (name, selector, how to show it)
    ("settings", "#settings .setx", "settings.showModal()"),
    ("health", "#hp_x", "hpOpen()"),
    ("download toast", "#dlchipx", "dlchip.hidden=false"),
    ("playlist toast", "#plchip button", "plchip.hidden=false"),
    ("file info popover", "#infopop .ifx", "openInfo('tone_a.wav',document.body)"),
]
HIDE = "try{settings.close()}catch(e){};try{hpClose(false)}catch(e){};dlchip.hidden=true;plchip.hidden=true;try{infoClose(false)}catch(e){}"


def check(name, ok, info=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"   {info}"))
    if not ok:
        FAILS.append(name)


def run(pg, skin, theme, width, tag, shots=None):
    pg.set_viewport_size({"width": width, "height": 900})
    pg.evaluate(f"setLook('skin','{skin}');setLook('theme','{theme}')")
    for name, sel, show in BUTTONS:
        if name == "file info popover" and skin != "stage":
            continue                      # a small rounded rectangle by design in Console / Studio (not an oval); the Stage skin makes it a circle
        pg.evaluate(HIDE)
        pg.evaluate(show)
        pg.wait_for_timeout(250)
        m = pg.evaluate(MEASURE, sel)
        t = f"{name} {skin}/{theme}/{width}"
        if m is None or not m["shown"]:
            check(f"{t}: the button is on screen", False, m)
            continue
        check(f"{t}: square ({m['w']:.1f} x {m['h']:.1f})", abs(m["w"] - m["h"]) <= 0.5, m)
        check(f"{t}: radius is 0 or at least half the width ({m['rad']})", m["radius"] == 0 or m["radius"] >= m["w"] / 2 - 0.01, m)
        check(f"{t}: the x is >= 3:1 against its background ({m['ratio']})", m["ratio"] >= 3.0, m)
        if skin == "stage":
            check(f"{t}: at least 28 px", m["w"] >= 28 and m["h"] >= 28, m)
            pg.keyboard.press("Shift")                                       # keyboard modality, so :focus-visible applies
            f = pg.evaluate(FOCUS, sel)
            check(f"{t}: visible focus ring, not clipped, >= 3:1 ({f})", f["style"] != "none" and f["ow"] > 0 and not f["clipped"] and f["ratio"] >= 3.0, f)
        if shots and skin == "stage" and width == 1280 and name in ("settings", "health"):
            box = pg.evaluate("sel=>{const r=document.querySelector(sel).getBoundingClientRect();return {x:r.x,y:r.y,w:r.width,h:r.height}}", sel)
            pg.screenshot(path=os.path.join(shots, f"{tag}-{name}-{theme}.png"), clip={"x": max(box["x"] - 260, 0), "y": max(box["y"] - 24, 0), "width": 330, "height": 150})
    # a title that wraps next to the Health button: the button must stay round
    pg.evaluate(HIDE)
    pg.evaluate("hpOpen()")
    pg.evaluate("document.querySelector('.hph b').textContent='A rather long health title that has to wrap onto several lines '.repeat(3);hpop.style.width='15rem'")
    m = pg.evaluate(MEASURE, "#hp_x")
    check(f"health {skin}/{theme}/{width}: still square next to a wrapping title ({m['w']:.1f} x {m['h']:.1f})", abs(m["w"] - m["h"]) <= 0.5, m)
    pg.evaluate(HIDE)
    pg.evaluate("document.querySelector('.hph b').textContent='Health';hpop.style.width=''")


def main():
    from playwright.sync_api import sync_playwright
    if SHOTS:
        os.makedirs(SHOTS, exist_ok=True)
    tag = os.environ.get("SHOT_TAG", "shot")
    with Instance(wav_only=True, project_dir=os.environ.get("PP_PROJECT") or PROJECT) as inst, sync_playwright() as p:
        api = client.Api(inst.base_url, osc_port=inst.osc_port)
        br = p.chromium.launch()
        ctx = br.new_context(viewport={"width": 1280, "height": 900})
        ctx.add_init_script("try{localStorage.setItem('cp_tour','1')}catch(e){}")
        pg = ctx.new_page()
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.goto(inst.base_url + "/")
        pg.wait_for_selector("#hdot")
        pg.wait_for_timeout(1500)
        pg.evaluate("window.render=async()=>{}")
        for theme in ("light", "dark"):
            for width in (1280, 900, 768):                                  # desktop, narrowest desktop layout, tablet
                run(pg, "stage", theme, width, tag, SHOTS)
        for skin in ("console", "studio"):
            run(pg, skin, "dark", 1280, tag)
        check("no page errors", not errors, errors[:3])
        br.close()
    print("\n%d failure(s)" % len(FAILS))
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
