#!/usr/bin/env python3
"""Playlist header and track rows (2.7.4 Phase 1b): "Track N of M" with a capital T in every mode; the mode pill only while the playlist is collapsed (and no jump when
it expands); no played check and no "in RAM" dot on rows (decoding ring and hollow ring stay); the playing row keeps all seven icons on ONE line in the same place as the
other rows (loudness and elapsed / length under the name); the quick-flag stripe is visible on the playing row and the progress line sits under it, inside the corners.
3 skins x dark/light at desktop width, plus a mid width and a touch tablet.    python tests/test_playlist_header_ui.py [SHOT_DIR]      (needs playwright; own disposable player)
Phone widths are out of scope for the row layout (tackled later)."""
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from harness import client                       # noqa: E402
from harness.instance import Instance, PROJECT   # noqa: E402

FAILS = []
SHOTS = sys.argv[1] if len(sys.argv) > 1 else None


def check(name, ok, info=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"   {info}"))
    if not ok:
        FAILS.append(name)


# 4 tracks, the 2nd is live (with a loudness pill, a trim badge and an own crossfade), the 3rd is cued; RAM states in / loading / out / in
SET = """cfg=>{render=async()=>{};PL[0].tracks.forEach((t,k)=>{t.dur_eff=[60,120,180,240][k];t.end='default'});PL[0].mode=cfg.mode;PL[0].shuffle_left=null;PL[0].norm={mode:'lufs',lufs:-16};
  PL[0].tracks.forEach(t=>{t.measured=true;t.lufs=-14;t.gain_db=-2});if(cfg.plain){delete PL[0].tracks[1].trim;PL[0].tracks[1].xfade=null;delete PL[0].tracks[1].triggers}else{PL[0].tracks[1].trim={in:5,out:50};PL[0].tracks[1].xfade=2000;PL[0].tracks[1].triggers=[{id:'g1',at:10,name:'Sting',enabled:true,file:'x'}]}
  PL[1].mode='stop';PL[1].tracks.forEach(t=>t.dur_eff=100);
  LASTS.live_id='0/1';LASTS.focus_id='0/2';LASTS.live_pass=1;LASTS.live_passes=1;LIVE={fid:'x',pos:30,dur:120,lo:0,hi:120,playing:false,t0:performance.now()};
  ['in','in','loading','out'].forEach((r,k)=>PL[0].tracks[k].ram=r);PL[0].ram_in=2;PL[0].ram_total=4;
  PL[0].tracks.forEach((t,k)=>{t.name=cfg.long&&k===1?'Foundations - a quite long track name for the playing row':t.name});
  if(cfg.coll)COLL.add(PL[0].name);else COLL.delete(PL[0].name);
  lastHtml='';PGD={};renderLists(LASTS);plProgTick(true);fitSub();
  const f=document.querySelectorAll('#lists .pl')[0].querySelectorAll('li.t .flag');f.forEach((e,i)=>e.style.setProperty('--fc',['#3b82f6','#f97316','#22c55e','#a855f7'][i]))}"""
HEAD = """()=>{const pl=document.querySelectorAll('#lists .pl')[0],ppl=pl.querySelector('.ppl'),ppm=pl.querySelector('.ppm'),r=e=>e.getBoundingClientRect();
  return {txt:pl.querySelector('.ppt').textContent,chipTxt:ppm.textContent,chipShown:getComputedStyle(ppm).display!=='none'&&r(ppm).width>0,pplH:r(ppl).height,pplTop:r(ppl).top-r(pl).top,
   barTop:r(pl.querySelector('.pbar')).top-r(pl).top,plh:r(pl.querySelector('.plh')).height,coll:pl.classList.contains('coll')}}"""
ROWS = """()=>{const pl=document.querySelectorAll('#lists .pl')[0],r=e=>e.getBoundingClientRect(),lis=[...pl.querySelectorAll('li.t')];
  return lis.map(li=>{const lr=r(li),acts=[...li.querySelectorAll('.acts > *')],ar=acts.map(r),fl=li.querySelector('.flag'),fr=r(fl),
    mid=e=>{const b=r(e);return document.elementFromPoint(b.left+Math.min(3,b.width/2),b.top+b.height/2)},low=document.elementFromPoint(fr.left+3,fr.bottom-2),
    pr=li.querySelector('.rpl')?r(li.querySelector('.rpl')):null,tn=li.querySelector('.tn'),sub=li.querySelector('.tsub'),gd=li.querySelector('.gdb'),gr=gd?r(gd):null;
   return {cls:li.className,n:acts.length,oneLine:ar.every(b=>Math.abs((b.top+b.height/2)-(ar[0].top+ar[0].height/2))<1.5),
    centred:Math.abs((ar[0].top+ar[0].height/2)-(lr.top+lr.height/2))<3,inside:ar.every(b=>b.left>=lr.left-.5&&b.right<=lr.right+.5&&b.top>=lr.top-.5&&b.bottom<=lr.bottom+.5),
    firstX:Math.round(ar[0].left),lastX:Math.round(ar[ar.length-1].right),h:lr.height,
    stripe:fl.classList.contains('flag')&&fr.width>=6&&mid(fl)===fl&&low===fl,stripeBg:getComputedStyle(fl).backgroundColor,
    prog:pr?{underStripe:pr.top>=fr.bottom-4&&true,w:pr.width,inside:pr.left>=lr.left&&pr.right<=lr.right&&pr.bottom<=lr.bottom,z:getComputedStyle(fl).zIndex}:null,
    chk:!!li.querySelector('.rck'),dot:li.querySelector('.rd')?li.querySelector('.rd').className:null,
    sub:sub?{t:sub.textContent.trim(),below:r(sub).top>=r(tn).bottom-1,gain:!!sub.querySelector('.gdb'),rpe:!!sub.querySelector('.rpe')}:null,
    pill:gr?{cx:gr.left+gr.width/2,cy:gr.top+gr.height/2,inName:!!(li.querySelector('.tnw')&&li.querySelector('.tnw').contains(gd)),sibOfActs:gd.parentElement===li,actsCy:ar[0].top+ar[0].height/2,right:gr.right}:null,
    tnW:r(tn).width,tnTitle:tn.getAttribute('title')===null?'':'title',hid:[...li.querySelectorAll('.bw[hidden]')].map(e=>e.className),bdgInSub:li.querySelectorAll('.tsub .bw').length,bdgOutside:[...li.children].filter(c=>c.classList&&c.classList.contains('trb')||c.classList.contains('trgbg')).length,flagR:fr.right,flagBottomEl:document.elementFromPoint(fr.right-1.5,fr.bottom-1.5)===fl,progL:pr?pr.left:null,
    badges:[...li.children].some(c=>c.classList&&c.classList.contains('rpe')),over:li.scrollWidth>li.clientWidth+1,tnOver:tn.scrollWidth>tn.clientWidth+1}})}"""


def main():
    from playwright.sync_api import sync_playwright
    if SHOTS:
        os.makedirs(SHOTS, exist_ok=True)
    with Instance(wav_only=True, project_dir=os.environ.get("PP_PROJECT") or PROJECT) as inst, sync_playwright() as p:
        api = client.Api(inst.base_url, osc_port=inst.osc_port)
        api.post("/api/playlists", {"name": "Pads"}); api.post("/api/playlists", {"name": "Encore"})
        api.post("/api/playlists/0/add", {"files": ["tone_a.wav", "tone_b.wav", "tone_c.wav", "short_1s.wav"]})
        api.post("/api/playlists/1/add", {"files": ["short_1s.wav", "short_2s.wav"]})
        br = p.chromium.launch()
        sizes = (("desktop", dict(viewport={"width": 1400, "height": 1000})), ("mid", dict(viewport={"width": 1100, "height": 900})),
                 ("w1280", dict(viewport={"width": 1280, "height": 900})), ("w1366", dict(viewport={"width": 1366, "height": 900})), ("w1600", dict(viewport={"width": 1600, "height": 1000})),
                 ("tablet", dict(viewport={"width": 820, "height": 1100}, has_touch=True, is_mobile=True)))
        for skin in ("console", "studio", "stage"):
            for theme in ("dark", "light"):
                for tag, kw in sizes:
                    label = f"{skin}/{theme}/{tag}"
                    c = br.new_context(**kw)
                    c.add_init_script(f"localStorage.setItem('cp_tour','1');localStorage.setItem('cp_skin','{skin}');localStorage.setItem('cp_theme','{theme}')")
                    pg = c.new_page(); errs = []
                    pg.on("pageerror", lambda e: errs.append(str(e)))
                    pg.goto(inst.base_url); pg.wait_for_selector("#lists li.t"); pg.wait_for_function("LASTS&&PL.length===2")
                    # ---- header: text and pill, all four modes, collapsed and expanded
                    for mode, chip in (("stop", "Stop at end"), ("loop_playlist", "Loop"), ("shuffle", "Shuffle"), ("next_playlist", "Next playlist")):
                        pg.evaluate(SET, {"mode": mode, "coll": True}); hc = pg.evaluate(HEAD)
                        pg.evaluate(SET, {"mode": mode, "coll": False}); he = pg.evaluate(HEAD)
                        check(f"{label}: {mode}: 'Track 2 of 4' with a capital T, collapsed and expanded", hc["txt"].startswith("Track ") and he["txt"].startswith("Track ") and " of 4 · " in he["txt"], (hc["txt"], he["txt"]))
                        check(f"{label}: {mode}: pill '{chip}' shown only while collapsed", hc["coll"] and hc["chipShown"] and hc["chipTxt"] == chip and not he["coll"] and not he["chipShown"], (hc, he))
                        check(f"{label}: {mode}: expanding does not change the header height or move the text / bar", abs(hc["pplH"] - he["pplH"]) < 0.6 and abs(hc["pplTop"] - he["pplTop"]) < 0.6 and abs(hc["barTop"] - he["barTop"]) < 0.6, (hc, he))
                    # the real toggle button flips it at once
                    pg.evaluate(SET, {"mode": "loop_playlist", "coll": False})
                    pg.locator("#lists .pl .plcol").first.evaluate("e=>e.scrollIntoView({block:'center'})")
                    pg.locator("#lists .pl .plcol").first.click(); h1 = pg.evaluate(HEAD)
                    check(f"{label}: the collapse button shows the pill at once", h1["coll"] and h1["chipShown"], h1)
                    pg.locator("#lists .pl .plcol").first.click(); h2 = pg.evaluate(HEAD)
                    check(f"{label}: ... and hides it again on expand", not h2["coll"] and not h2["chipShown"], h2)
                    # ---- rows
                    for long in (False, True):
                        pg.evaluate(SET, {"mode": "loop_playlist", "coll": False, "long": long}); rows = pg.evaluate(ROWS)
                        tag2 = f"{label}{' long name' if long else ''}"
                        check(f"{tag2}: no played check and no green in-RAM dot on any row", not any(r["chk"] for r in rows) and [r["dot"] for r in rows] == [None, None, "rd loading", "rd out"], [(r["chk"], r["dot"]) for r in rows])
                        check(f"{tag2}: played row (0) is still dimmed", "done" in rows[0]["cls"].split() and "done" not in rows[2]["cls"].split(), [r["cls"] for r in rows])
                        check(f"{tag2}: all seven icons on one line, inside the row, vertically centred, on every row", all(r["n"] == 7 and r["oneLine"] and r["inside"] and r["centred"] for r in rows), rows)
                        check(f"{tag2}: the icons are in the same place on the playing row as on the others", len({r["lastX"] for r in rows}) == 1 and len({r["firstX"] for r in rows}) == 1, [(r["firstX"], r["lastX"]) for r in rows])
                        live = rows[1]
                        check(f"{tag2}: playing row: only elapsed / length is under the name; the loudness pill is not in the name block", live["sub"] and live["sub"]["below"] and not live["sub"]["gain"] and live["sub"]["rpe"] and "▶ 0:30 / 2:00" in live["sub"]["t"] and not live["badges"] and live["pill"] and not live["pill"]["inName"] and live["pill"]["sibOfActs"], live["sub"])
                        check(f"{tag2}: the pill is on the icons' line (same vertical centre as the icons, as on the other rows)", all(abs(r["pill"]["cy"] - r["pill"]["actsCy"]) < 2.5 for r in rows if r["pill"]), [r["pill"] for r in rows])
                        if tag != "tablet":
                            check(f"{tag2}: the pill and the icons are at the same x as on the other rows (pill right edge, icons left / right)", len({round(r["pill"]["right"], 1) for r in rows}) == 1 and len({r["firstX"] for r in rows}) == 1 and len({r["lastX"] for r in rows}) == 1, [(r["pill"]["right"], r["firstX"], r["lastX"]) for r in rows])
                            wpx = {"desktop": 1400, "mid": 1100, "w1280": 1280, "w1366": 1366, "w1600": 1600}[tag]
                            need = 120 if wpx >= 1280 else 80
                            if wpx < 1280 and skin in ("stage", "studio"):
                                print("NOTE", tag2, f"name width {live['tnW']:.0f} px (80 px floor not applied at {wpx} px in {skin}); truncates with an ellipsis, full name in its title")
                                need = 0
                            check(f"{tag2}: the name on the playing row is at least {need} px wide (120 at 1280+, 80 below; 1100 px stage / studio exempt); full name in its title", live["tnW"] >= need and "title" in live["tnTitle"], (live["tnW"], live["tnTitle"]))
                            check(f"{tag2}: trim / trigger / crossfade badges are on the second line only (none on the name line)", live["bdgOutside"] == 0 and live["bdgInSub"] == 3, (live["bdgOutside"], live["bdgInSub"], live["hid"]))
                            if live["hid"]:
                                print("NOTE", tag2, "badges hidden on the playing row:", live["hid"])
                        check(f"{tag2}: other rows do not have the second line", all(r["sub"] is None for k, r in enumerate(rows) if k != 1))
                        check(f"{tag2}: quick-flag stripe is visible on every row, including the playing and cued rows", all(r["stripe"] for r in rows) and all(r["stripeBg"] != "rgba(0, 0, 0, 0)" for r in rows), [(r["stripe"], r["stripeBg"]) for r in rows])
                        check(f"{tag2}: progress line is inside the row's corners and under the stripe", live["prog"] and live["prog"]["inside"] and live["prog"]["w"] > 5 and live["prog"]["z"] == "1", live["prog"])
                        check(f"{tag2}: progress line starts at the stripe's right edge, not under it; the stripe's bottom-left pixel is the stripe", live["progL"] >= live["flagR"] - 0.5 and live["flagBottomEl"], (live["progL"], live["flagR"], live["flagBottomEl"]))
                        check(f"{tag2}: the playing row is a little taller than the others, nothing overflows", live["h"] > rows[0]["h"] and not any(r["over"] for r in rows), [r["h"] for r in rows])
                    pg.evaluate(SET, {"mode": "loop_playlist", "coll": False, "plain": True}); rows = pg.evaluate(ROWS)
                    check(f"{label}: the pill's centre x on the playing row equals the pill's centre x on the other rows (same column)", len({round(r["pill"]["cx"], 1) for r in rows}) == 1 and len({round(r["pill"]["right"], 1) for r in rows}) == 1, [r["pill"] for r in rows])
                    if SHOTS and theme == "dark":
                        pg.evaluate(SET, {"mode": "loop_playlist", "coll": False}); pg.locator("#lists .pl").first.screenshot(path=f"{SHOTS}/{skin}-{tag}-expanded.png")
                        pg.evaluate(SET, {"mode": "loop_playlist", "coll": True}); pg.locator("#lists .pl").first.screenshot(path=f"{SHOTS}/{skin}-{tag}-collapsed.png")
                    check(f"{label}: no page errors", not errs, errs)
                    c.close()
        br.close()
    print(f"\n{len(FAILS)} failure(s)")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
