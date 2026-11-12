#!/usr/bin/env python3
"""Keyboard focus and hover on the highlighted playlist rows (2.7.5 preview-rc2): on the playing, cued / focused, REF and flashed rows (and a plain row) the keyboard focus ring of the row's
controls is at least 3:1 against the row's real background, and hovering a control gives a clearly visible state: its own icon / text >= 3:1 against its hovered background, and the hover itself
shows (a background step of 1.25:1 against the row, or a border / outline >= 3:1).  3 skins x light / dark x desktop / phone.     python tests/test_row_states.py   (needs playwright; own player)"""
import os
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from harness import client                       # noqa: E402
from harness.instance import Instance, PROJECT   # noqa: E402

FAILS = []
JS = r"""sel=>{
  const el=document.querySelector(sel);if(!el)return {err:'none '+sel};
  const num=s=>(s.match(/-?[\d.]+(?:e-?\d+)?/g)||[]).map(Number);
  const parse=s=>{if(!s||s==='transparent')return null;const n=num(s);if(s.startsWith('color(')){return n.length<3?null:[n[0]*255,n[1]*255,n[2]*255,n.length>3?n[3]:1]}if(s.startsWith('rgb')){return [n[0],n[1],n[2],n.length>3?n[3]:1]}return null};
  const over=(t,b)=>{const a=t[3];return [t[0]*a+b[0]*(1-a),t[1]*a+b[1]*(1-a),t[2]*a+b[2]*(1-a),1]};
  const bgOf=(e,self)=>{const ch=[];for(let x=self?e:e.parentElement;x;x=x.parentElement){const c=parse(getComputedStyle(x).backgroundColor);if(c&&c[3]>0)ch.push(c)}let b=[255,255,255,1];for(let i=ch.length-1;i>=0;i--)b=over(ch[i],b);return b};
  const lum=c=>{const f=v=>{v/=255;return v<=0.03928?v/12.92:Math.pow((v+0.055)/1.055,2.4)};return 0.2126*f(c[0])+0.7152*f(c[1])+0.0722*f(c[2])};
  const ratio=(a,b)=>{const l1=lum(a),l2=lum(b);return (Math.max(l1,l2)+0.05)/(Math.min(l1,l2)+0.05)};
  const cs=getComputedStyle(el),row=el.closest('li.t,.lt')||el.parentElement,rowBg=bgOf(row,true),selfBg=bgOf(el,true);
  const fgc=parse(cs.color)||[0,0,0,1],fg=fgc[3]<1?over(fgc,selfBg):fgc;
  const oc=parse(cs.outlineColor),ow=parseFloat(cs.outlineWidth)||0,os=cs.outlineStyle;
  const bc=parse(cs.borderTopColor),bw=parseFloat(cs.borderTopWidth)||0;
  return {fgRatio:ratio(fg,selfBg),outline:(os!=='none'&&ow>0&&oc)?{w:ow,ratio:ratio(oc[3]<1?over(oc,rowBg):oc,rowBg)}:null,
          border:(bw>0&&bc&&bc[3]>0)?ratio(bc[3]<1?over(bc,rowBg):bc,rowBg):null,bgStep:ratio(selfBg,rowBg),shadow:cs.boxShadow!=='none'}}"""


def check(name, ok, info=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"   {info}"))
    if not ok:
        FAILS.append(name)


def main():
    from playwright.sync_api import sync_playwright
    with Instance(wav_only=True, project_dir=os.environ.get("PP_PROJECT") or PROJECT) as inst, sync_playwright() as p:
        api = client.Api(inst.base_url, osc_port=inst.osc_port)
        api.post("/api/playlists", {"name": "Pads"})
        api.post("/api/playlists/0/add", {"files": ["tone_a.wav", "tone_b.wav", "tone_c.wav", "long_120s.wav"]})
        api.post("/api/playlists/0/norm", {"mode": "track", "ref": 1})
        time.sleep(3.0)
        br = p.chromium.launch()
        for skin in ("console", "studio", "stage"):
            for theme in ("light", "dark"):
                for wn, vp, touch in (("desktop", {"width": 1280, "height": 900}, False), ("phone", {"width": 390, "height": 844}, True)):
                    tag = f"{skin}/{theme}/{wn}"
                    c = br.new_context(viewport=vp, has_touch=touch, is_mobile=touch)
                    c.add_init_script(f"localStorage.setItem('cp_tour','1');localStorage.setItem('cp_wave','1');localStorage.setItem('cp_skin','{skin}');localStorage.setItem('cp_theme','{theme}')")
                    pg = c.new_page(); errs = []
                    pg.on("pageerror", lambda e: errs.append(str(e)))
                    api.cmd("0/3"); api.wait_playing("0/3"); api.cmd("0/1/focus")
                    pg.goto(inst.base_url); pg.wait_for_selector("li.t"); time.sleep(1.2)
                    rows = {"plain": 1, "cued+REF": 2, "playing": 4}
                    for name, k in rows.items():
                        r = f"li.t:nth-child({k})"
                        for ctl, csel in (("PVW", ".ib.pv"), ("Go", "button.go, .go"), ("delete", ".ib.del"), ("info", ".ib[data-info]")):
                            if not pg.evaluate("s=>!!document.querySelector(s)", f"{r} {csel}"):
                                continue
                            # keyboard focus ring
                            pg.evaluate("s=>document.querySelector(s).focus({focusVisible:true})", f"{r} {csel}")
                            pg.keyboard.press("Shift+Tab"); pg.keyboard.press("Tab")           # make the browser treat it as keyboard focus
                            f = pg.evaluate(JS, f"{r} {csel}:focus-visible")
                            ok = not f.get("err") and f["outline"] and f["outline"]["ratio"] >= 3 and f["outline"]["w"] >= 2
                            check(f"{tag}: {name} row, {ctl}: the keyboard focus ring is >= 2 px and >= 3:1 against the row", ok, f)
                            # hover
                            pg.hover(f"{r} {csel}"); time.sleep(0.25)
                            h = pg.evaluate(JS, f"{r} {csel}")
                            shows = (h["bgStep"] >= 1.25) or (h["border"] and h["border"] >= 3) or (h["outline"] and h["outline"]["ratio"] >= 3)
                            check(f"{tag}: {name} row, {ctl}: hover is clearly visible and its icon / text is >= 3:1", shows and h["fgRatio"] >= 3, h)
                    # the flashed rows
                    pg.evaluate("PFL={fid:PL[0].tracks[0].id,i:0,until:Date.now()+600000};lastHtml='';render(true)"); time.sleep(0.8)
                    f2 = pg.evaluate(JS, "li.t.flash .ib.pv")
                    pg.evaluate("document.querySelector('li.t.flash .ib.pv').focus({focusVisible:true})"); pg.keyboard.press("Shift+Tab"); pg.keyboard.press("Tab")
                    f = pg.evaluate(JS, "li.t.flash .ib.pv:focus-visible")
                    check(f"{tag}: flashed row: the keyboard focus ring is >= 2 px and >= 3:1 against the row", not f.get("err") and f["outline"] and f["outline"]["ratio"] >= 3 and f["outline"]["w"] >= 2, f)
                    pg.hover("li.t.flash .ib.pv"); time.sleep(0.25)
                    h = pg.evaluate(JS, "li.t.flash .ib.pv")
                    check(f"{tag}: flashed row: hover is clearly visible", ((h["bgStep"] >= 1.25) or (h["border"] and h["border"] >= 3)) and h["fgRatio"] >= 3, h)
                    check(f"{tag}: no page errors", not errs, errs)
                    c.close()
        br.close()
    print(f"\n{len(FAILS)} failure(s)")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
