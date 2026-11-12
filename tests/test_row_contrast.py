#!/usr/bin/env python3
"""Playlist row highlights (2.7.5 preview-rc2): no solid bright fill any more. For every state of a row (normal, playing, cued/focus, previewing, the "show me" flash, playing+flash,
the REF chip row, a flashed library row) every text, icon and control on the row is measured against the REAL rendered background (ancestors composited, colour-mix included):
text >= 4.5:1 (3:1 for large text), icons >= 3:1. 3 skins x light / dark x desktop / phone, with before/after screenshots (SHOT_DIR).
    python tests/test_row_contrast.py [SHOT_DIR]      (needs playwright; own disposable player)"""
import os
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from harness import client                       # noqa: E402
from harness.instance import Instance, PROJECT   # noqa: E402

FAILS = []
SHOTS = sys.argv[1] if len(sys.argv) > 1 else None
CONTRAST = r"""sel=>{
  const row=document.querySelector(sel);if(!row)return {err:'no row '+sel};
  const num=s=>(s.match(/-?[\d.]+(?:e-?\d+)?/g)||[]).map(Number);
  const parse=s=>{if(!s||s==='transparent')return null;const n=num(s);if(s.startsWith('color(')){return n.length<3?null:[n[0]*255,n[1]*255,n[2]*255,n.length>3?n[3]:1]}if(s.startsWith('rgb')){return [n[0],n[1],n[2],n.length>3?n[3]:1]}return null};
  const over=(t,b)=>{const a=t[3];return [t[0]*a+b[0]*(1-a),t[1]*a+b[1]*(1-a),t[2]*a+b[2]*(1-a),1]};
  const bg=el=>{const ch=[];for(let e=el;e;e=e.parentElement){const c=parse(getComputedStyle(e).backgroundColor);if(c&&c[3]>0)ch.push(c)}let b=[255,255,255,1];for(let i=ch.length-1;i>=0;i--)b=over(ch[i],b);return b};
  const lum=c=>{const f=v=>{v/=255;return v<=0.03928?v/12.92:Math.pow((v+0.055)/1.055,2.4)};return 0.2126*f(c[0])+0.7152*f(c[1])+0.0722*f(c[2])};
  const out=[];
  const els=[row,...row.querySelectorAll('*')];
  for(const e of els){const r=e.getBoundingClientRect();if(!r.width||!r.height)continue;const cs=getComputedStyle(e);if(cs.display==='none'||cs.visibility==='hidden'||+cs.opacity===0)continue;
   if(e.closest('canvas')||e.tagName==='CANVAS')continue;
   const isSvg=e.tagName.toLowerCase()==='svg';
   const own=[...e.childNodes].some(n=>n.nodeType===3&&n.textContent.trim().length);
   if(!isSvg&&!own)continue;
   let back=bg(e);const fg0=parse(cs.color);if(!fg0)continue;const fg=fg0[3]<1?over(fg0,back):fg0;
   const l1=lum(fg),l2=lum(back),ratio=(Math.max(l1,l2)+0.05)/(Math.min(l1,l2)+0.05);
   const px=parseFloat(cs.fontSize),bold=+cs.fontWeight>=700,large=px>=24||(px>=18.66&&bold);
   const need=isSvg?3:(large?3:4.5);
   out.push({e:(e.id||e.className||e.tagName).toString().slice(0,28),txt:(e.textContent||'').trim().slice(0,18),ratio:Math.round(ratio*10)/10,need,bad:ratio<need})}
  return {n:out.length,bad:out.filter(x=>x.bad)}}"""


def check(name, ok, info=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"   {info}"))
    if not ok:
        FAILS.append(name)


def main():
    from playwright.sync_api import sync_playwright
    if SHOTS:
        os.makedirs(SHOTS, exist_ok=True)
    with Instance(wav_only=True, project_dir=os.environ.get("PP_PROJECT") or PROJECT) as inst, sync_playwright() as p:
        api = client.Api(inst.base_url, osc_port=inst.osc_port)
        api.post("/api/playlists", {"name": "Pads"})
        api.post("/api/playlists/0/add", {"files": ["tone_a.wav", "tone_b.wav", "tone_c.wav", "long_120s.wav"]})
        api.post("/api/playlists/0/norm", {"mode": "track", "ref": 1})            # the REF chip on tone_b
        time.sleep(3.0)                                                          # loudness is measured in the background
        br = p.chromium.launch()
        for skin in ("console", "studio", "stage"):
            for theme in ("light", "dark"):
                for wn, vp, touch in (("desktop", {"width": 1280, "height": 900}, False), ("phone", {"width": 390, "height": 844}, True)):
                    tag = f"{skin}/{theme}/{wn}"
                    c = br.new_context(viewport=vp, has_touch=touch, is_mobile=touch)
                    c.add_init_script(f"localStorage.setItem('cp_tour','1');localStorage.setItem('cp_wave','1');localStorage.setItem('cp_skin','{skin}');localStorage.setItem('cp_theme','{theme}')")
                    pg = c.new_page(); errs = []
                    pg.on("pageerror", lambda e: errs.append(str(e)))
                    api.cmd("0/3"); api.wait_playing("0/3"); api.cmd("0/1/focus")        # long_120s is live, tone_b is cued
                    pg.goto(inst.base_url); pg.wait_for_selector("li.t"); time.sleep(1.2)
                    rows = pg.evaluate("[...document.querySelectorAll('li.t')].map(e=>e.className)")
                    sel = lambda k: f"li.t:nth-child({k})"       # noqa: E731
                    def shot(n):
                        if SHOTS:
                            pg.locator(sel(n[1])).scroll_into_view_if_needed(); time.sleep(0.15)
                            pg.locator("ol").first.screenshot(path=f"{SHOTS}/{skin}-{theme}-{wn}-{n[0]}.png")
                    # states
                    check(f"{tag}: the rows carry the live and focus classes", "live" in rows[3] and "focus" in rows[1], rows)
                    for name, k in (("normal", 1 + 1), ("playing", 4), ("cued", 2)):
                        pass
                    res = {}
                    res["normal"] = pg.evaluate(CONTRAST, sel(1)); res["playing"] = pg.evaluate(CONTRAST, sel(4)); res["cued"] = pg.evaluate(CONTRAST, sel(2))
                    res["ref-row"] = pg.evaluate(CONTRAST, sel(2))        # tone_b is both the cue and the REF item
                    pg.evaluate("window.scrollTo(0,0)")
                    shot(("playing", 4)); shot(("cued", 2)); shot(("ref", 2))
                    # the jump flash (on the playing row and on a normal row) and the previewed row
                    pg.evaluate("PFL={fid:PL[0].tracks[3].id,i:0,until:Date.now()+600000};lastHtml='';render(true)"); time.sleep(0.8)
                    res["playing+flash"] = pg.evaluate(CONTRAST, sel(4)); shot(("playing-flash", 4))
                    pg.evaluate("PFL={fid:PL[0].tracks[0].id,i:0,until:Date.now()+600000};lastHtml='';render(true)"); time.sleep(0.8)
                    res["flash"] = pg.evaluate(CONTRAST, sel(1)); shot(("flash", 1))
                    pg.evaluate("PFL={fid:null,i:-1,until:0};lastHtml='';render(true)"); time.sleep(0.5)
                    pg.evaluate("FLASH={path:null,id:PL[0].tracks[0].id,until:Date.now()+600000};lastHtml='';lastLib='';renderLib()"); time.sleep(0.5)
                    lt = pg.evaluate("!!document.querySelector('.lt.flash')")
                    if lt:
                        res["library flash"] = pg.evaluate(CONTRAST, ".lt.flash")
                    pg.evaluate("FLASH={path:null,id:null,until:0};lastLib='';renderLib()")
                    for name, r in res.items():
                        check(f"{tag}: {name} row: every text and icon passes the contrast limits ({r.get('n')} measured)", not r.get("err") and not r["bad"] and r["n"] > 3, r)
                    check(f"{tag}: no page errors", not errs, errs)
                    c.close()
        br.close()
    print(f"\n{len(FAILS)} failure(s)")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
