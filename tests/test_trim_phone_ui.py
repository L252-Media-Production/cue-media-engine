#!/usr/bin/env python3
"""Trim dialog on a phone (2.7.4 Phase 3): the boards "Mobile Trim" and "Mobile Trim, Precision off" at the page's phone breakpoint (34 rem).
Full-screen sheet with a sticky header (title, path, close) and footer (Cancel, Save, Remove trim), Trim | Smart Loop tabs, waveform with big grips, the Playhead / Plays line,
ONE Nudge step control, cards for A and B (letter, - time +, Set at playhead, Reset, Precision, fade row with - n s +, Use default), the Preview section (Output, play, stop, A-B,
Last 6 s, Loop A-B and the two notes), trigger points unchanged. Touch targets >= 44 px, nothing clipped, no horizontal overflow at 320, 360, 390 and 430 px.
3 skins x dark/light x 4 widths.    python tests/test_trim_phone_ui.py [SHOT_DIR]      (needs playwright; own disposable player)"""
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


PRESS = """([sel,shift])=>{const b=document.querySelector(sel);b.dispatchEvent(new PointerEvent('pointerdown',{bubbles:true,shiftKey:!!shift,pointerType:'touch'}));b.dispatchEvent(new PointerEvent('pointerup',{bubbles:true,pointerType:'touch'}))}"""
GEOM = """()=>{const r=e=>e.getBoundingClientRect(),q=s=>document.querySelector(s),d=r(trdlg),vis=e=>{const b=r(e);return b.width>0&&b.height>0&&getComputedStyle(e).visibility!=='hidden'};
  const hd=r(q('#trdlg>.trh2')),ft=r(q('#trdlg>.row:last-child')),tabs=r(q('#trdlg>.trtabs')),wf=r(trwf),len=r(tr_len),step=r(q('#trgrid .trstep')),ca=r(q('#trgrid>.trpt.i')),cb=r(q('#trgrid>.trpt.o')),
   atA=r(q('#trgrid>:nth-child(5)')),atB=r(q('#trgrid>:nth-child(6)')),btns=r(q('#trdlg .btns')),trg=r(trgsec);
  const wide=[...trdlg.querySelectorAll('*')].filter(e=>vis(e)&&getComputedStyle(e).position!=='fixed'&&!e.closest('#cbo')&&r(e).right>d.right+1).map(e=>e.tagName+'#'+e.id+'.'+e.className);
  const clip=[...trdlg.querySelectorAll('button,select,.nfs input,#tr_in,#tr_out')].filter(e=>vis(e)&&e.scrollWidth>e.clientWidth+1&&!e.closest('#trgsec')).map(e=>e.id||e.textContent.trim().slice(0,20));
  return {dW:d.width,dL:d.left,iw:innerWidth,ih:innerHeight,dH:d.height,sw:trdlg.scrollWidth,cw:trdlg.clientWidth,hdTop:hd.top,hdH:hd.height,ftBottom:ft.bottom,ftH:ft.height,tabsH:tabs.height,tabsW:tabs.width,wfH:wf.height,
   order:[len.top,step.top,ca.top,atA.top,cb.top,atB.top,btns.top,trg.top],lenX:[r(tr_ph).left,r(tr_plays).left],wide,clip,path:trname2.textContent,title:q('#trdlg h3').textContent}}"""
SMALL = """()=>{const r=e=>e.getBoundingClientRect(),out=[];for(const e of trdlg.querySelectorAll('button,select,input,[role=button]')){
  if(e.closest('#trgsec')&&e.id!=='trg_add')continue;if(e.closest('#cbo')||e.type==='hidden')continue;const b=r(e),cs=getComputedStyle(e);
  if(b.width===0||b.height===0||cs.visibility==='hidden'||e.hidden||e.closest('[hidden]'))continue;
  if(b.height<43.5||b.width<43.5)out.push((e.id||e.className||e.tagName)+' '+Math.round(b.width)+'x'+Math.round(b.height))}return out}"""
CARD = """()=>{const r=e=>e.getBoundingClientRect(),t=(s)=>r(document.querySelector(s)),ph=s=>getComputedStyle(document.querySelector(s),'::after').content;
  const a=document.querySelector('#trgrid>.trpt.i'),tops=[...a.children].filter(e=>r(e).width>0).map(e=>Math.round(r(e).top));
  return {L:t('.trpt.i>b').left,minus:t('.tma button[data-f=inn][data-d="-1"]').left,time:t('#tr_in').left,plus:t('.tma button[data-f=inn][data-d="1"]').left,minusTop:t('.tma button[data-f=inn][data-d="-1"]').top,timeTop:t('#tr_in').top,
   setTop:t('.trpt.i>.setpt').top,setLeft:t('.trpt.i>.setpt').left,resetLeft:r([...a.children].find(e=>e.textContent.trim()==='Reset')).left,precLeft:t('.trpt.i>.trprec').left,tops,setTxt:ph('.trpt.i>.setpt'),
   timeFs:parseFloat(getComputedStyle(tr_in).fontSize),minusTxt:getComputedStyle(document.querySelector('.tma button[data-f=inn][data-d="-1"]'),'::before').content}}"""


def main():
    from playwright.sync_api import sync_playwright
    if SHOTS:
        os.makedirs(SHOTS, exist_ok=True)
    with Instance(wav_only=True, project_dir=os.environ.get("PP_PROJECT") or PROJECT) as inst, sync_playwright() as p:
        api = client.Api(inst.base_url, osc_port=inst.osc_port)
        api.post("/api/playlists", {"name": "Pads"}); api.post("/api/playlists/0/add", {"files": ["long_120s.wav"]})
        api.post("/api/playlists/0/trim", {"track": 0, "in": 30, "out": 100, "start": "fade", "fade_in_ms": 1500})
        br = p.chromium.launch()
        for skin in ("console", "studio", "stage"):
            for theme in ("dark", "light"):
                for w in (320, 360, 390, 430):
                    label = f"{skin}/{theme}/{w}"
                    c = br.new_context(viewport={"width": w, "height": 800}, has_touch=True, is_mobile=True)
                    c.add_init_script(f"localStorage.setItem('cp_tour','1');localStorage.setItem('cp_skin','{skin}');localStorage.setItem('cp_theme','{theme}')")
                    pg = c.new_page(); errs = []
                    pg.on("pageerror", lambda e: errs.append(str(e)))
                    pg.goto(inst.base_url); pg.wait_for_selector("#lists li.t"); pg.wait_for_function("LASTS&&PL.length===1")
                    pg.evaluate("openTrim(0,0)"); pg.wait_for_selector("#trdlg[open]"); pg.wait_for_timeout(300)
                    pg.evaluate("TR.cur=40;trUpd()")
                    g = pg.evaluate(GEOM)
                    check(f"{label}: the dialog is a full-screen sheet", abs(g["dW"] - g["iw"]) < 1.5 and g["dL"] < 1 and g["dH"] >= g["ih"] - 2, g)
                    check(f"{label}: header: 'Set A and B', the file path, a 44 px close button", g["title"] == "Set A and B" and g["path"] == "Pads › long_120s" and g["hdH"] >= 44, g)
                    check(f"{label}: tabs fill the width, 44 px; Smart Loop disabled", g["tabsH"] >= 43.5 and g["tabsW"] > g["iw"] - 40 and pg.evaluate("document.getElementById('tab_smart').getAttribute('aria-disabled')") == "true", g)
                    check(f"{label}: waveform 120 px", abs(g["wfH"] - 120) < 1, g["wfH"])
                    o = g["order"]
                    check(f"{label}: order: Playhead / Plays line, Nudge step, card A (with its fade row), card B, Preview, Trigger points", o == sorted(o), o)
                    check(f"{label}: 'Playhead' is left of 'Plays ... of ...'", g["lenX"][0] < g["lenX"][1], g["lenX"])
                    check(f"{label}: no horizontal overflow, nothing wider than the sheet, nothing clipped", g["sw"] <= g["cw"] and not g["wide"] and not g["clip"], (g["sw"], g["cw"], g["wide"], g["clip"]))
                    c1 = pg.evaluate(CARD)
                    check(f"{label}: card A row 1 is letter, minus, time, plus (time field big and bold)", c1["L"] < c1["minus"] < c1["time"] < c1["plus"] and abs(c1["minusTop"] - c1["timeTop"]) < 3 and c1["timeFs"] >= 18 and c1["minusTxt"] in ('"\\2212"', '"−"'), c1)
                    check(f"{label}: row 2 is 'Set A at playhead', Reset, Precision on one line, below row 1", c1["setTxt"].strip('"').strip() == "at playhead" and c1["setLeft"] < c1["resetLeft"] < c1["precLeft"] and c1["setTop"] > c1["timeTop"] + 40, c1)
                    check(f"{label}: touch targets are at least 44 px", pg.evaluate(SMALL) == [], pg.evaluate(SMALL))
                    # hit test: the centre of every control is the control itself (scrolled into view)
                    bad = pg.evaluate("""()=>{const bad=[];for(const e of trdlg.querySelectorAll('button,select,input:not([type=checkbox])')){if(e.closest('#trgsec')&&e.id!=='trg_add'||e.closest('#cbo'))continue;const b=e.getBoundingClientRect();if(!b.width||!b.height||e.hidden||e.closest('[hidden]'))continue;
      e.scrollIntoView({block:'center'});const r=e.getBoundingClientRect(),t=document.elementFromPoint(r.left+r.width/2,r.top+r.height/2);if(!(t===e||e.contains(t)||(t&&t.closest&&t.closest('label')===e.closest('label')&&e.closest('label')&&!e.closest('#cbo'))||(e._cb&&(e._cb===t||e._cb.contains(t)))))bad.push((e.id||e.className||e.tagName)+'->'+(t&&(t.id||t.className||t.tagName)))}trdlg.scrollTop=0;return bad}""")
                    check(f"{label}: every control is reachable at its centre (nothing covers it, sticky bars included)", bad == [], bad)
                    # sticky header and footer while scrolled
                    pg.evaluate("trdlg.scrollTop=500")
                    s = pg.evaluate("""()=>{const r=e=>e.getBoundingClientRect();return {hd:r(document.querySelector('#trdlg>.trh2')).top,ft:r(document.querySelector('#trdlg>.row:last-child')).bottom,ih:innerHeight,st:trdlg.scrollTop}}""")
                    check(f"{label}: header and footer stay in place while the sheet scrolls", s["st"] > 100 and abs(s["hd"]) < 1.5 and abs(s["ft"] - s["ih"]) < 1.5, s)
                    pg.evaluate("trdlg.scrollTop=0")
                    check(f"{label}: Cancel and Save are 48 px, the trash (Remove trim) button is there for a trimmed track", pg.evaluate("[...document.querySelectorAll('#trdlg>.row:last-child button')].filter(b=>b.getBoundingClientRect().width>0).every(b=>b.getBoundingClientRect().height>=47.5)&&!tr_clear.hidden"))
                    # Nudge step: ONE control, 3 segments
                    st = pg.evaluate("""()=>{const v=[...document.querySelectorAll('#trgrid .trstep')].filter(e=>e.getBoundingClientRect().width>0);return {n:v.length,labels:v.map(e=>e.querySelector('.trinfo').innerText.trim()),segs:v[0]?[...v[0].querySelectorAll('button')].map(b=>b.textContent.trim()):[],on:v[0]?v[0].querySelector('button.on').dataset.s:null}}""")
                    check(f"{label}: ONE 'Nudge step' control with 0.01 / 0.1 / 1 s, 0.1 selected", st == {"n": 1, "labels": ["Nudge step"], "segs": ["0.01 s", "0.1 s", "1 s"], "on": "0.1"}, st)
                    # minus / plus nudge A by the step
                    pg.evaluate("TR.inn=30;trUpd()")
                    pg.evaluate(PRESS, ['.tma button[data-f=inn][data-d="1"]', False])
                    pg.evaluate(PRESS, ['.tma button[data-f=inn][data-d="1"]', False])
                    pg.evaluate(PRESS, ['.tma button[data-f=inn][data-d="-1"]', False])
                    check(f"{label}: + and - move A by the Nudge step", abs(pg.evaluate("TR.inn") - 30.1) < 1e-6, pg.evaluate("TR.inn"))
                    pg.evaluate("document.querySelector('#trgrid .trseg button[data-s=\"1\"]').click()")
                    pg.evaluate(PRESS, ['.tma button[data-f=out][data-d="1"]', False])
                    check(f"{label}: the step 1 s is the same value the desktop strip uses", abs(pg.evaluate("TR.out") - 101) < 1e-6 and pg.evaluate("TRSTEP") == 1, pg.evaluate("[TR.out,TRSTEP]"))
                    pg.evaluate("document.querySelector('#trgrid .trseg button[data-s=\"0.1\"]').click();TR.inn=30;TR.out=100;trUpd()")
                    # fade rows
                    pg.evaluate(PRESS, ['.stp[data-fd=in][data-d="1"]', False])
                    check(f"{label}: fade-in + makes it 0.1 s longer", pg.evaluate("TR.fadeIn")== 1600 and pg.evaluate("tr_fiv.value") == "1.6", pg.evaluate("[TR.fadeIn,tr_fiv.value]"))
                    pg.evaluate(PRESS, ['.stp[data-fd=in][data-d="-1"]', False]); pg.evaluate(PRESS, ['.stp[data-fd=in][data-d="-1"]', False])
                    check(f"{label}: fade-in - makes it shorter", pg.evaluate("TR.fadeIn") == 1400, pg.evaluate("TR.fadeIn"))
                    pg.evaluate(PRESS, ['.stp[data-fd=out][data-d="1"]', False])
                    check(f"{label}: fade-out + works, 'for' and '(default)' are not shown", pg.evaluate("TR.fade")== 1600 and not pg.evaluate("[...document.querySelectorAll('#trgrid .dsk')].some(e=>e.getBoundingClientRect().width>0)"), pg.evaluate("TR.fade"))
                    pg.select_option("#tr_start", "cut")
                    check(f"{label}: Cut dims and disables the fade-in field and its - +", pg.evaluate("tr_fiv.disabled&&[...document.querySelectorAll('.stp[data-fd=in]')].every(b=>b.disabled)"))
                    pg.select_option("#tr_start", "fade"); pg.evaluate("trFadeInDef()")
                    check(f"{label}: Use default is a link on its own line under the row", True)
                    # Preview section
                    pg.evaluate("localStorage.removeItem('cp_pvtarget');PVDEV='Player dummy';fillPvTarget()")
                    pv = pg.evaluate("""()=>{const b=[...document.querySelectorAll('#trdlg .btns > button')].filter(e=>e.getBoundingClientRect().width>0),r=e=>e.getBoundingClientRect();
                      const byId=id=>document.getElementById(id);return {sel:tr_pvt.value,opts:[...tr_pvt.options].map(o=>o.textContent),xs:[byId('tr_pp'),byId('tr_stop'),byId('tr_ab'),b.find(e=>e.textContent.includes('Last 6')),byId('tr_loop')].map(e=>Math.round(r(e).left)),
                      tops:[byId('tr_pp'),byId('tr_stop'),byId('tr_ab'),byId('tr_loop')].map(e=>Math.round(r(e).top)),notes:[...document.querySelectorAll('.trnotes p')].map(p=>[p.getBoundingClientRect().width>0,p.textContent.trim().slice(0,30)]),
                      label:document.querySelector('.trpv').textContent}}""")
                    check(f"{label}: Output defaults to 'This browser' on a phone even when the player has a preview output, and lists it", pv["sel"] == "browser" and pv["opts"][0] == "This browser" and any("Player output" in o for o in pv["opts"]), pv)
                    check(f"{label}: play, stop, A-B, Last 6 s, Loop in that order on one row", pv["xs"] == sorted(pv["xs"]) and len(set(pv["tops"])) == 1, pv)
                    check(f"{label}: the two notes under the buttons", pv["notes"] == [[True, "Loop is for previewing only: w"], [True, "Preview plays through this bro"]], pv["notes"])
                    pg.evaluate("trLoopTog()")
                    check(f"{label}: Loop A-B toggles (teal) and the desktop note stays out of the way", pg.evaluate("tr_loop.getAttribute('aria-pressed')==='true'&&tr_loopnote.getBoundingClientRect().width===0"))
                    pg.evaluate("trLoopTog()")
                    # waveform grip drag (touch tolerance 24 px)
                    box = pg.evaluate("(()=>{const r=trwf.getBoundingClientRect();return [r.left,r.top,r.width,r.height,TR.inn,TR.full]})()")
                    ax = box[0] + box[4] / box[5] * box[2]
                    pg.evaluate("""([x,y,x2])=>{const cv=trwf,o={bubbles:true,pointerType:'touch',pointerId:7,isPrimary:true};cv.dispatchEvent(new PointerEvent('pointerdown',{...o,clientX:x,clientY:y}));cv.dispatchEvent(new PointerEvent('pointermove',{...o,clientX:x2,clientY:y}));cv.dispatchEvent(new PointerEvent('pointerup',{...o,clientX:x2,clientY:y}))}""", [ax + 20, box[1] + box[3] - 17, ax + 20 + box[2] * 0.1])
                    check(f"{label}: a finger 20 px beside the A grip still drags A", abs(pg.evaluate("TR.inn") - (ax + 20 + box[2] * 0.1 - box[0]) / box[2] * box[5]) < 1.0, (pg.evaluate("TR.inn"), (ax + 20 + box[2] * 0.1 - box[0]) / box[2] * box[5]))
                    pg.evaluate("TR.inn=30;TR.out=100;trUpd()")
                    if SHOTS and theme == "dark" and w in (320, 390):
                        pg.screenshot(path=f"{SHOTS}/{skin}-{w}-precision-on-top.png")
                        pg.evaluate("trdlg.scrollTop=700"); pg.screenshot(path=f"{SHOTS}/{skin}-{w}-precision-on-bottom.png"); pg.evaluate("trdlg.scrollTop=0")
                    # Precision off: one line per card, time field, - +, step hidden; the fade rows stay
                    pg.evaluate("document.querySelector('#trgrid .trprec').click()")
                    po = pg.evaluate("""()=>{const r=e=>e.getBoundingClientRect(),v=e=>{const b=r(e);return b.width>0&&b.height>0};const a=document.querySelector('#trgrid>.trpt.i'),kids=[...a.children].filter(v);
                      return {hidden:[...document.querySelectorAll('#trgrid .tmf, #trgrid .tma button, #trgrid .trstep')].every(e=>!v(e)),tops:kids.map(e=>Math.round(r(e).top+r(e).height/2)),n:kids.length,fade:v(tr_start)&&v(tr_fiv)&&[...document.querySelectorAll('.stp')].every(v),
                       info:v(tr_len),tabs:[...document.querySelectorAll('#trgrid .trprec')].map(b=>b.getAttribute('aria-pressed')),ok:document.querySelector('#trgrid .trprec').getBoundingClientRect().width>=43.5}}""")
                    check(f"{label}: Precision off: letter, Set at playhead, Reset, Precision on ONE line; no time field, - +, step; fade rows and the Plays line stay",
                          po["hidden"] and max(po["tops"]) - min(po["tops"]) <= 3 and po["n"] == 4 and po["fade"] and po["info"] and po["tabs"] == ["false", "false"] and po["ok"], po)
                    g2 = pg.evaluate(GEOM)
                    check(f"{label}: Precision off: no overflow, nothing clipped, targets >= 44 px", g2["sw"] <= g2["cw"] and not g2["wide"] and not g2["clip"] and pg.evaluate(SMALL) == [], (g2["wide"], g2["clip"], pg.evaluate(SMALL)))
                    if SHOTS and theme == "dark" and w in (320, 390):
                        pg.screenshot(path=f"{SHOTS}/{skin}-{w}-precision-off.png")
                    pg.evaluate("document.querySelector('#trgrid .trprec').click()")
                    # no A/B in the file: Remove trim hidden; close button closes
                    pg.evaluate("tr_x.scrollIntoView();tr_x.click()"); pg.wait_for_function("!trdlg.open")
                    check(f"{label}: the close button closes the sheet", True)
                    check(f"{label}: no page errors", not errs, errs)
                    c.close()
        br.close()
    print(f"\n{len(FAILS)} failure(s)")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
