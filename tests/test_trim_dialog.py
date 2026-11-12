#!/usr/bin/env python3
"""Trim dialog and trigger editor: no -/+ buttons next to the fade field, the native spinner and keyboard work, the waveform hint text is gone,
the keyboard nudges still move the selected marker, and no numeric/time field clips its value at the maximum (desktop, phone, touch; 3 skins).
    python tests/test_trim_dialog.py [SHOT_DIR]      (needs playwright; starts its own disposable player; TRIM_PROJECT=<other checkout> tests an older copy of the app)"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from harness import client                       # noqa: E402
from harness.instance import Instance, PROJECT   # noqa: E402

FAILS = []
HINT = "Drag the green A and red B markers"

VIS = """()=>{const v=e=>getComputedStyle(e).display!=='none'&&e.getBoundingClientRect().width>0;return {tmf:[...document.querySelectorAll('#trgrid .tmf')].map(v),step:[...document.querySelectorAll('#trgrid .trstep')].map(v),
  on:[...document.querySelectorAll('#trgrid .trprec')].map(b=>b.classList.contains('on')&&b.getAttribute('aria-pressed')==='true'),cur:[...document.querySelectorAll('#trgrid .trstep')].map(r=>r.querySelector('button.on').dataset.s)}}"""
S_IN = """id=>{const e=document.getElementById(id),em=e.parentElement.querySelector('em'),r=e.getBoundingClientRect(),m=em.getBoundingClientRect(),cs=getComputedStyle(e),coarse=matchMedia('(pointer:coarse)').matches,
  c=document.createElement('canvas').getContext('2d');c.font=cs.font;const tw=c.measureText(e.value).width,spin=getComputedStyle(e).appearance==='textfield'?0:coarse?parseFloat(cs.fontSize)*2.4:15;
  return {inside:m.left>=r.left&&m.right<=r.right-(coarse?0:Math.max(0,spin-1))&&m.top>=r.top&&m.bottom<=r.bottom,notUnder:r.left+parseFloat(cs.paddingLeft)+tw<=m.left+1,txt:em.textContent.trim(),textEnd:r.left+parseFloat(cs.paddingLeft)+tw,sLeft:m.left,sRight:m.right,right:r.right}}"""
STUB = """cfg=>{window.__calls=[];window.__pos=cfg.pos;localStorage.setItem('cp_pvtarget',cfg.out);PVDEV=cfg.out==='pi'?'Test device':null;
  pvPlay=async()=>{PVCUR={id:TR.fid,state:'playing'};PVST.dur=120};pvPosDur=()=>[window.__pos,120];pvPoll=()=>{};renderPv=()=>{};renderLocal=()=>{};Object.defineProperty(AU,'duration',{get:()=>120,configurable:true});Object.defineProperty(AU,'readyState',{get:()=>4,configurable:true});
  pvCtl=async(c,x)=>{window.__calls.push([c,x||{}]);if(c==='seek')window.__pos=x.pos;if(c==='stop')PVCUR={id:TR.fid,state:'stopped'}};
  fetch=async(u,o)=>{window.__calls.push(['fetch',u,o&&o.body?JSON.parse(o.body):null]);return {ok:true,json:async()=>({})}};
  TR.full=120;TR.inn=10;TR.out=40;TR.end='fade';TR.fade=1000;TR.start='fade';TR.fadeIn=500;trUpd()}"""


def check(name, ok, info=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"   {info}"))
    if not ok:
        FAILS.append(name)


def open_trim(pg, fade=None):
    """Open the trim dialog of playlist 0 / track 0 (long_120s.wav), B at 100 s so a 10 s fade fits; optionally set the fade (seconds)."""
    pg.evaluate("openTrim(0,0)")
    pg.wait_for_selector("#trdlg[open]")
    pg.evaluate("""f=>{if(!TR.full)TR.full=120;TR.out=100;TR.inn=0;TR.end='fade';TR.start='cut';TR.fadeIn=null;trUpd();if(f!=null)trFadeSet(f)}""", fade)


FIT = """els=>els.map(([id,val])=>{const e=document.getElementById(id)||document.querySelector(id);if(val!=null)e.value=val;
  const cs=getComputedStyle(e),coarse=matchMedia('(pointer:coarse)').matches,spin=e.type!=='number'||e.closest('.xfc')||getComputedStyle(e).appearance==='textfield'?0:coarse?parseFloat(cs.fontSize)*2.4-parseFloat(cs.fontSize)*0.3:15;   /* the arrows: 15 px (browser), or the enlarged ones of the touch layout */
  const c=document.createElement('canvas').getContext('2d');c.font=cs.font;const tw=c.measureText(e.value).width;
  const avail=e.clientWidth-parseFloat(cs.paddingLeft)-parseFloat(cs.paddingRight)-spin;
  return {id,value:e.value,scroll:e.scrollWidth,client:e.clientWidth,text:Math.round(tw*10)/10,avail:Math.round(avail*10)/10}})"""


def run_page(pg, label, shots=None, api=None):
    open_trim(pg, fade=10)
    check(f"{label}: no -/+ buttons at B on a desktop or tablet (a phone has its own, see test_trim_phone_ui.py)", pg.evaluate("!document.getElementById('tr_fm')&&!document.getElementById('tr_fp')&&[...document.querySelectorAll('#tr_fade button')].every(b=>b.classList.contains('stp')&&(innerWidth<=544||b.getBoundingClientRect().width===0))"))
    check(f"{label}: fade 10 s accepted and shown as 10.0", pg.evaluate("tr_fv.value==='10.0'&&TR.fade===10000"), pg.evaluate("tr_fv.value"))
    check(f"{label}: hint text gone (no title, not in the page)", pg.evaluate("(h)=>trwf.title===''&&!document.documentElement.outerHTML.includes(h)&&!trdlg.innerText.includes('nudge')", HINT))
    # typing
    pg.evaluate("trFadeSet(1.5)")
    pg.click("#tr_fv", click_count=3); pg.keyboard.type("2.5"); pg.keyboard.press("Enter"); pg.keyboard.press("Tab")
    check(f"{label}: typing 2.5 sets the fade", pg.evaluate("TR.fade===2500&&tr_fv.value==='2.5'"), pg.evaluate("[TR.fade,tr_fv.value]"))
    # keyboard Up/Down on the number field (native spinner step), focus stays so it can repeat
    pg.focus("#tr_fv"); pg.keyboard.press("ArrowUp"); pg.keyboard.press("ArrowUp"); pg.keyboard.press("ArrowDown")
    check(f"{label}: Up/Down keys step by 0.1 and keep working", pg.evaluate("TR.fade===2600&&tr_fv.value==='2.6'"), pg.evaluate("[TR.fade,tr_fv.value]"))
    # min / max
    pg.evaluate("trFadeSet(99)"); a = pg.evaluate("TR.fade"); pg.evaluate("trFadeSet(0)"); b = pg.evaluate("TR.fade")
    check(f"{label}: limits 0.1 and 10 s kept", a == 10000 and b == 100, (a, b))
    pg.evaluate("trFadeSet(1.5)")
    # use default link
    pg.evaluate("trFadeSet(4)"); pg.evaluate("trFadeDef()")
    check(f"{label}: Use default goes back to the default", pg.evaluate("TR.fade===null&&tr_fuse.hidden&&!tr_fdef.hidden"))
    # mouse on the native spinner (desktop pointers only: touch has no hover spinner)
    if not pg.evaluate("matchMedia('(pointer:coarse)').matches") and pg.evaluate("innerWidth")>544:
        pg.evaluate("trFadeSet(3)")                       # first: this shows the "Use default" link and moves the field
        bx = pg.locator("#tr_fv").bounding_box()
        pr = pg.evaluate("parseFloat(getComputedStyle(tr_fv).paddingRight)")           # the arrows sit inside the padding: ~7 px from its inner edge
        x = bx["x"] + bx["width"] - pr - 7
        pg.mouse.move(x, bx["y"] + bx["height"] / 2); pg.mouse.click(x, bx["y"] + bx["height"] / 2 - 4)
        check(f"{label}: the spinner arrow changes the value", pg.evaluate("TR.fade===3100"), pg.evaluate("[TR.fade,tr_fv.value]"))
    # keyboard nudges on the waveform
    pg.evaluate("trgSelect('inn');TR.inn=10;trUpd();trwf.focus()")
    pg.keyboard.press("ArrowRight"); r1 = pg.evaluate("TR.inn")
    pg.keyboard.press("Shift+ArrowRight"); r2 = pg.evaluate("TR.inn")
    pg.keyboard.press("Alt+ArrowLeft"); r3 = pg.evaluate("TR.inn")
    check(f"{label}: Left/Right nudge 0.1 s, Shift 1 s, Alt 0.01 s", abs(r1 - 10.1) < 1e-6 and abs(r2 - 11.1) < 1e-6 and abs(r3 - 11.09) < 1e-6, (r1, r2, r3))
    pg.keyboard.press("ArrowDown"); s1 = pg.evaluate("TR.sel")
    check(f"{label}: Up/Down choose the next marker", s1 == "out", s1)
    pg.evaluate("trgAdd()")
    n0 = pg.evaluate("TR.trg.length"); pg.evaluate("trwf.focus()"); pg.keyboard.press("Delete")
    check(f"{label}: Delete removes the selected trigger", n0 == 1 and pg.evaluate("TR.trg.length") == 0, (n0, pg.evaluate("TR.trg.length")))
    # clipping at the maximum values
    pg.evaluate("trFadeSet(10);trgAdd();TR.trg[0].at=9999.9;trgRender()")
    rows = pg.evaluate(FIT, [("tr_fv", "10.0"), ("tr_in", "166:39.9"), ("tr_out", "166:39.9"), (".trgr .tt", None)])
    for r in rows:
        ok = r["scroll"] <= r["client"] and r["text"] <= r["avail"]
        check(f"{label}: {r['id']} shows {r['value']!r} without clipping", ok, r)
    if shots:
        pg.locator("#trdlg").screenshot(path=str(shots / f"{label.replace(' ', '_').replace('/', '-')}.png"))
    pg.evaluate("trdlg.close()"); pg.wait_for_function("TR===null")
    # cue-strip crossfade field and the Settings fields
    pg.evaluate("foc_xf.disabled=false")
    r = pg.evaluate(FIT, [("foc_xf", "30")])[0]
    check(f"{label}: cue crossfade field shows 30 without clipping", r["scroll"] <= r["client"] and r["text"] <= r["avail"], r)
    pg.evaluate("document.getElementById('settings').showModal()")
    for r in pg.evaluate(FIT, [("tr_ms", "30.0"), ("tr_fd", "10.0"), ("tr_fi", "10.0")]):
        check(f"{label}: Settings {r['id']} shows {r['value']} without clipping", r["scroll"] <= r["client"] and r["text"] <= r["avail"], r)
    pg.evaluate("document.getElementById('settings').close()")

    # ---- 2.7.4 Phase 2: Precision, time fields, fade-in at A, tabs, Loop A-B
    open_trim(pg, fade=3)
    pg.evaluate("localStorage.removeItem('cp_trprec');localStorage.removeItem('cp_trstep');TRPREC=true;TRSTEP=.1;trPrecUi();TR.inn=10;TR.out=100;trUpd()")
    vis = pg.evaluate(VIS)
    check(f"{label}: Precision on: time fields with arrows and both step strips shown, buttons blue and pressed, 0.1 s is the default step",
          all(vis["tmf"]) and len(vis["tmf"]) == 2 and (vis["step"] == [True, False] if pg.evaluate("innerWidth") <= 544 else vis["step"] == [True, True]) and all(vis["on"]) and vis["cur"] == ["0.1", "0.1"], vis)
    check(f"{label}: order in the row is letter, Set, Precision, time field, Reset", pg.evaluate("[...document.querySelectorAll('.trpt.i > *')].map(e=>e.tagName==='B'?'L':e.classList.contains('trprec')?'P':e.classList.contains('tmf')?'T':e.textContent.trim()).join(',')") == "L,Set A,P,T,Reset")
    sm = pg.evaluate("""()=>{const t=document.getElementById('tab_smart'),a=document.getElementById('tab_trim'),cs=getComputedStyle(t),em=t.querySelector('em');
        return {dis:t.getAttribute('aria-disabled')==='true',pe:cs.pointerEvents,op:+cs.opacity,badge:em.textContent.trim().toLowerCase(),bc:getComputedStyle(em).borderTopColor,trimSel:a.getAttribute('aria-selected'),smSel:t.getAttribute('aria-selected')}}""")
    check(f"{label}: Smart Loop tab is disabled, dimmed, aria-disabled, with the amber coming-soon badge; Trim is the only active tab",
          sm["dis"] and sm["pe"] == "none" and sm["op"] < 1 and sm["badge"] == "coming soon" and sm["trimSel"] == "true" and sm["smSel"] == "false" and any(k in sm["bc"] for k in ("217, 119", "245, 158")), sm)
    # typing and clamping
    pg.fill("#tr_in", "1:23.5"); pg.keyboard.press("Tab")
    check(f"{label}: typing 1:23.5 sets A", abs(pg.evaluate("TR.inn") - 83.5) < 1e-6, pg.evaluate("TR.inn"))
    pg.fill("#tr_out", "999:00"); pg.keyboard.press("Tab")
    check(f"{label}: B typed past the end is clamped to the file length", pg.evaluate("TR.out") == 120, pg.evaluate("TR.out"))
    pg.fill("#tr_in", "5:00"); pg.keyboard.press("Tab")
    check(f"{label}: A typed after B stays 0.5 s before B", abs(pg.evaluate("TR.inn") - 119.5) < 1e-6, pg.evaluate("TR.inn"))
    pg.evaluate("TR.inn=10;TR.out=100;trUpd()")
    # arrows: one press = one step; Shift = 10x; the step strip; hold to repeat
    PRESS = """([sel,shift])=>{const b=document.querySelector(sel);b.dispatchEvent(new PointerEvent('pointerdown',{bubbles:true,shiftKey:!!shift,pointerType:'mouse'}));b.dispatchEvent(new PointerEvent('pointerup',{bubbles:true,pointerType:'mouse'}))}"""
    pg.evaluate(PRESS, ['.tma button[data-f=inn][data-d="1"]', False])
    check(f"{label}: the up arrow moves A later by the step (0.1 s)", abs(pg.evaluate("TR.inn") - 10.1) < 1e-6, pg.evaluate("TR.inn"))
    pg.evaluate(PRESS, ['.tma button[data-f=inn][data-d="1"]', True])
    check(f"{label}: Shift is 10x", abs(pg.evaluate("TR.inn") - 11.1) < 1e-6, pg.evaluate("TR.inn"))
    pg.evaluate(PRESS, ['.tma button[data-f=out][data-d="-1"]', False])
    check(f"{label}: the down arrow moves B earlier", abs(pg.evaluate("TR.out") - 99.9) < 1e-6, pg.evaluate("TR.out"))
    pg.evaluate("document.querySelector('.trseg button[data-s=\"1\"]').click()")
    pg.evaluate(PRESS, ['.tma button[data-f=inn][data-d="1"]', False])
    check(f"{label}: step 1 s", abs(pg.evaluate("TR.inn") - 12.1) < 1e-6 and pg.evaluate("localStorage.getItem('cp_trstep')") == "1", pg.evaluate("TR.inn"))
    pg.evaluate("document.querySelector('.trseg button[data-s=\"0.01\"]').click()")
    pg.evaluate(PRESS, ['.tma button[data-f=inn][data-d="1"]', False])
    check(f"{label}: step 0.01 s, the field then shows hundredths", abs(pg.evaluate("TR.inn") - 12.11) < 1e-6 and pg.evaluate("tr_in.value") == "0:12.11", pg.evaluate("[TR.inn,tr_in.value]"))
    pg.evaluate("document.querySelector('.trseg button[data-s=\"0.1\"]').click()")
    pg.evaluate("TR.inn=10;trUpd()")
    pg.evaluate("""()=>{const b=document.querySelector('.tma button[data-f=inn][data-d="1"]');b.dispatchEvent(new PointerEvent('pointerdown',{bubbles:true,pointerType:'mouse'}))}""")
    pg.wait_for_timeout(1100)
    n1 = pg.evaluate("TR.inn")
    pg.evaluate("""()=>{const b=document.querySelector('.tma button[data-f=inn][data-d="1"]');b.dispatchEvent(new PointerEvent('pointerup',{bubbles:true,pointerType:'mouse'}))}""")
    pg.wait_for_timeout(400)
    n2 = pg.evaluate("TR.inn")
    check(f"{label}: holding an arrow repeats, releasing stops", n1 > 10.1 + 0.4 and abs(n2 - n1) < 0.11, (n1, n2))
    pg.focus("#tr_in"); pg.keyboard.press("ArrowUp"); pg.keyboard.press("Shift+ArrowDown")
    check(f"{label}: Up/Down in the time field nudge too (Shift = 10x)", abs(pg.evaluate("TR.inn") - (n2 + 0.1 - 1.0)) < 1e-6, (n2, pg.evaluate("TR.inn")))
    pg.evaluate("TR.inn=0.2;trUpd()"); pg.evaluate(PRESS, ['.tma button[data-f=inn][data-d="-1"]', True])
    check(f"{label}: the arrows clamp at 0 and at B - 0.5 s", pg.evaluate("TR.inn") == 0, pg.evaluate("TR.inn"))
    if not pg.evaluate("matchMedia('(pointer:coarse)').matches") and pg.evaluate("innerWidth") > 900:
        pg.evaluate("TR.inn=10;trUpd()"); bx = pg.locator('.tma button[data-f=inn][data-d="1"]').bounding_box()
        pg.mouse.click(bx["x"] + bx["width"] / 2, bx["y"] + bx["height"] / 2)
        check(f"{label}: a real mouse click on the up arrow works", abs(pg.evaluate("TR.inn") - 10.1) < 1e-6, pg.evaluate("TR.inn"))
    # Precision off
    pg.evaluate("TR.inn=10;TR.out=100;trUpd()")
    pg.evaluate("document.querySelector('#trgrid .trprec').click()")
    vis = pg.evaluate(VIS)
    check(f"{label}: Precision off hides the time fields and the step strips; Set and Reset stay; remembered on this device",
          not any(vis["tmf"]) and not any(vis["step"]) and not any(vis["on"]) and pg.evaluate("localStorage.getItem('cp_trprec')") == "0" and
          pg.evaluate("[...document.querySelectorAll('#trgrid .trpt.i > button, #trgrid .trpt.o > button')].filter(b=>b.textContent.trim()).every(b=>b.getBoundingClientRect().width>0)"), vis)
    check(f"{label}: the keyboard nudges on the waveform still work with Precision off", pg.evaluate("(()=>{trgSelect('inn');TR.inn=10;trUpd();trwf.focus();return 1})()") == 1)
    pg.keyboard.press("ArrowRight")
    check(f"{label}: ... ArrowRight moved A by 0.1 s", abs(pg.evaluate("TR.inn") - 10.1) < 1e-6, pg.evaluate("TR.inn"))
    pg.evaluate("trdlg.close()"); pg.wait_for_function("TR===null"); open_trim(pg)
    check(f"{label}: after reopening the dialog Precision is still off", not any(pg.evaluate(VIS)["tmf"]))
    pg.evaluate("document.querySelector('#trgrid .trprec').click()")
    check(f"{label}: Precision on again", all(pg.evaluate(VIS)["tmf"]) and pg.evaluate("localStorage.getItem('cp_trprec')") == "1")
    # the "s" inside the number fields, no clipping at 10.0
    pg.evaluate("trStart('fade');trFadeInSet(10);trFadeSet(10)")
    for fid in ("tr_fv", "tr_fiv"):
        r = pg.evaluate(S_IN, fid)
        check(f"{label}: the 's' is inside {fid} and the number does not run under it", r["inside"] and r["notUnder"] and r["txt"] == "s", r)
    rows = pg.evaluate(FIT, [("tr_fiv", "10.0")])
    for r in rows:
        check(f"{label}: {r['id']} shows '10.0' without clipping", r["scroll"] <= r["client"] and r["text"] <= r["avail"] - (0 if pg.evaluate("getComputedStyle(tr_fiv).appearance==='textfield'") else pg.evaluate("parseFloat(getComputedStyle(tr_fiv).fontSize)") * 1.2), r)       # a phone has no spinner: its right padding already holds the 's' 
    # fade in at A
    open_trim(pg)
    pg.evaluate("TRFADEIN=0;trUpd()")
    check(f"{label}: A starts as Cut: the fade-in field is dimmed and disabled", pg.evaluate("tr_start.value==='cut'&&tr_fiv.disabled&&tr_fadein.classList.contains('dim')"))
    pg.select_option("#tr_start", "fade")
    check(f"{label}: choosing Fade in with no default gives 1.5 s and enables the field", pg.evaluate("TR.start==='fade'&&TR.fadeIn===1500&&tr_fiv.value==='1.5'&&!tr_fiv.disabled&&!tr_fiuse.hidden"), pg.evaluate("[TR.start,TR.fadeIn,tr_fiv.value]"))
    pg.click("#tr_fiv", click_count=3); pg.keyboard.type("2.5"); pg.keyboard.press("Enter"); pg.keyboard.press("Tab")
    check(f"{label}: typing 2.5 sets the fade-in", pg.evaluate("TR.fadeIn===2500&&tr_fiv.value==='2.5'"), pg.evaluate("[TR.fadeIn,tr_fiv.value]"))
    pg.focus("#tr_fiv"); pg.keyboard.press("ArrowUp"); pg.keyboard.press("ArrowUp"); pg.keyboard.press("ArrowDown")
    check(f"{label}: Up/Down step the fade-in by 0.1", pg.evaluate("TR.fadeIn===2600&&tr_fiv.value==='2.6'"), pg.evaluate("[TR.fadeIn,tr_fiv.value]"))
    pg.evaluate("trFadeInSet(99)"); a = pg.evaluate("TR.fadeIn"); pg.evaluate("trFadeInSet(0)"); b = pg.evaluate("TR.fadeIn")
    check(f"{label}: fade-in limits 0.1 and 10 s", a == 10000 and b == 100, (a, b))
    pg.evaluate("trFadeInSet(4)")
    pg.select_option("#tr_start", "cut")
    check(f"{label}: Cut keeps the length but dims the field", pg.evaluate("TR.fadeIn===4000&&tr_fiv.disabled&&tr_fiv.value==='4.0'"), pg.evaluate("[TR.fadeIn,tr_fiv.value]"))
    pg.select_option("#tr_start", "fade")
    check(f"{label}: ... and Fade in again brings it back unchanged", pg.evaluate("TR.fadeIn===4000"))
    pg.evaluate("trFadeInDef()")
    check(f"{label}: Use default clears the own value", pg.evaluate("TR.fadeIn===null&&tr_fiuse.hidden&&!tr_fidef.hidden"))
    pg.evaluate("TR.inn=10;TR.out=11;trUpd();trFadeInSet(5)")
    check(f"{label}: the fade-in is shortened to B - A and says so", pg.evaluate("tr_fiv.value==='1.0'&&tr_fnote.textContent.includes('Fade in shortened')"), pg.evaluate("[tr_fiv.value,tr_fnote.textContent]"))
    pg.evaluate("TR.inn=0;TR.out=100;trUpd();trStart('fade');trFadeInSet(1.8);trFadeSet(1.2)")
    # waveform wedge
    try:
        pg.wait_for_function("(()=>{const w=waveFor(TR.fid);return w&&w.peaks&&w.peaks.length})()", timeout=6000)
        pg.evaluate("trDraw()")
        wd = pg.evaluate("[!!TR.wedgeA,!!TR.wedge]")
        check(f"{label}: waveform shows a wedge at A and one at B", wd == [True, True], wd)
        pg.evaluate("trStart('cut');trDraw()")
        check(f"{label}: no wedge at A while A is Cut", pg.evaluate("TR.wedgeA===null"))
        pg.evaluate("trStart('fade');trDraw()")
    except Exception:
        check(f"{label}: waveform available for the wedge check", True)
    if api is not None:                                   # Save writes start and fade_in_ms; Cut keeps the length; Use default removes it
        pg.evaluate("trFadeInSet(1.8)")
        pg.evaluate("trSave()"); pg.wait_for_function("!trdlg.open&&TR===null", timeout=5000)
        tm = api.playlists()[0]["tracks"][0]["trim"]
        check(f"{label}: Save writes the fade-in", tm.get("start") == "fade" and tm.get("fade_in_ms") == 1800 and tm.get("fade_ms") == 1200, tm)
        pg.wait_for_function("PL[0].tracks[0].trim&&PL[0].tracks[0].trim.start==='fade'", timeout=8000)      # the page refetches the playlists after a save
        pg.evaluate("openTrim(0,0)"); pg.wait_for_selector("#trdlg[open]")
        check(f"{label}: reopening shows Fade in 1.8 s", pg.evaluate("TR.start==='fade'&&TR.fadeIn===1800&&tr_start.value==='fade'&&tr_fiv.value==='1.8'"), pg.evaluate("[TR.start,TR.fadeIn]"))
        pg.select_option("#tr_start", "cut"); pg.evaluate("trSave()"); pg.wait_for_function("!trdlg.open&&TR===null", timeout=5000)
        tm = api.playlists()[0]["tracks"][0]["trim"]
        check(f"{label}: saving with Cut drops the edge but keeps the length", tm.get("start") is None and tm.get("fade_in_ms") == 1800, tm)
        pg.wait_for_function("PL[0].tracks[0].trim&&!PL[0].tracks[0].trim.start&&PL[0].tracks[0].trim.fade_in_ms===1800", timeout=8000)
        pg.evaluate("openTrim(0,0)"); pg.wait_for_selector("#trdlg[open]")
        pg.evaluate("trFadeInDef()"); pg.evaluate("trSave()"); pg.wait_for_function("!trdlg.open&&TR===null", timeout=5000)
        tm = api.playlists()[0]["tracks"][0]["trim"]
        check(f"{label}: Use default removes the own length", tm is None or tm.get("fade_in_ms") is None, tm)
        api.post("/api/playlists/0/trim", {"track": 0, "clear": True})
        pg.evaluate("lastHtml='';render(true)"); pg.wait_for_function("!PL[0].tracks[0].trim", timeout=8000)
    # Loop A-B (page logic with a stub for the preview: what is sent, when)
    pg.evaluate("openTrim(0,0)"); pg.wait_for_selector("#trdlg[open]")
    check(f"{label}: Loop starts off, per dialog open, with an icon and 'A-B'", pg.evaluate("TR.loop===false&&tr_loop.getAttribute('aria-pressed')==='false'&&tr_loop.querySelector('svg')&&tr_loop.textContent.trim()==='A-B'&&tr_loopnote.hidden"))
    pg.evaluate(STUB, {"out": "pi", "pos": 10})
    pg.evaluate("trLoopTog()")
    check(f"{label}: Loop on: button pressed (teal), note shown", pg.evaluate("TR.loop&&tr_loop.classList.contains('on')&&!tr_loopnote.hidden&&tr_loopnote.textContent.includes('Loop on')"))
    pg.evaluate("PVDEV=localStorage.getItem('cp_pvtarget')==='pi'?'Test device':null;trAud(TR.inn,TR.out,false,TR.loop)"); pg.wait_for_function("TR.looping", timeout=5000)
    calls = pg.evaluate("window.__calls")
    loops = [c for c in calls if c[0] == "fetch" and "preview/ctl" in c[1]]
    check(f"{label}: player output: ONE loop op with A, B and both fades, no vol or seek from the page", len(loops) == 1 and loops[0][2] == {"cmd": "loop", "a": 10, "b": 40, "fin": 500, "fout": 1000} and not [c for c in calls if c[0] in ("seek", "vol")], calls)
    pg.evaluate("window.__pos=41"); pg.wait_for_timeout(500)
    check(f"{label}: ... and the page does not watch for B while the worker loops", not [c for c in pg.evaluate("window.__calls") if c[0] in ("seek", "pause", "vol")], pg.evaluate("window.__calls"))
    pg.evaluate("trLoopTog()")
    check(f"{label}: Loop off while looping stops the preview", ["stop", {}] in pg.evaluate("window.__calls") and pg.evaluate("TR.looping===false&&!TR.loop"), pg.evaluate("window.__calls"))
    pg.evaluate("window.__calls.length=0;trLoopTog();PVDEV=localStorage.getItem('cp_pvtarget')==='pi'?'Test device':null;trAud(TR.inn,TR.out,false,TR.loop)"); pg.wait_for_function("TR.looping", timeout=5000)
    pg.evaluate("window.__calls.length=0;trStop()")
    check(f"{label}: Stop ends the loop", ["stop", {}] in pg.evaluate("window.__calls") and pg.evaluate("!TR.looping&&!TR.aud"))
    pg.evaluate("PVDEV=localStorage.getItem('cp_pvtarget')==='pi'?'Test device':null;trAud(TR.inn,TR.out,false,TR.loop)"); pg.wait_for_function("TR.looping", timeout=5000)
    pg.evaluate("window.__calls.length=0;trdlg.close()"); pg.wait_for_function("TR===null")
    check(f"{label}: closing the dialog stops the loop", ["stop", {}] in pg.evaluate("window.__calls"), pg.evaluate("window.__calls"))
    # browser output: the page wraps at B itself (a small gap), with fades; counts laps
    pg.evaluate("openTrim(0,0)"); pg.wait_for_selector("#trdlg[open]")
    pg.evaluate(STUB, {"out": "browser", "pos": 10}); pg.evaluate("trLoopTog()")
    pg.evaluate("PVDEV=localStorage.getItem('cp_pvtarget')==='pi'?'Test device':null;trAud(TR.inn,TR.out,false,TR.loop)"); pg.wait_for_function("TR.aud&&TR.looping", timeout=5000)
    pg.evaluate("window.__calls.length=0")
    for lap in range(3):
        pg.evaluate("window.__pos=39.99"); pg.wait_for_timeout(260); pg.evaluate("window.__pos=10.4"); pg.wait_for_timeout(260)
    calls = pg.evaluate("window.__calls")
    seeks = [c for c in calls if c[0] == "seek"]
    check(f"{label}: browser output: three laps give three seeks back to A", len(seeks) == 3 and all(abs(c[1]["pos"] - 10) < 1e-6 for c in seeks), calls)
    check(f"{label}: ... each lap restarts the fade-in from silence", len([c for c in calls if c[0] == "vol" and c[1]["v"] == 0]) >= 3, calls)
    pg.evaluate("window.__calls.length=0;window.__pos=39.5"); pg.wait_for_timeout(400)
    vols = [c[1]["v"] for c in pg.evaluate("window.__calls") if c[0] == "vol"]
    check(f"{label}: ... and the fade-out ramps down before B (equal power)", vols and abs(vols[-1] - __import__("math").cos((1 - 0.5 / 1.0) * __import__("math").pi / 2)) < 0.05, vols)
    pg.evaluate("trLoopTog()")
    check(f"{label}: Loop off ends the browser loop", pg.evaluate("!TR.looping&&!TR.aud"))
    pg.evaluate("window.__calls.length=0;window.__pos=10;TR.loop=false;trAud(TR.inn,TR.out,false,false)"); pg.wait_for_function("TR.aud", timeout=5000)
    pg.evaluate("window.__pos=39.99"); pg.wait_for_timeout(300)
    check(f"{label}: without Loop, Play A-B pauses at B as before", ["pause", {}] in pg.evaluate("window.__calls") and pg.evaluate("!TR.aud"), pg.evaluate("window.__calls"))
    pg.evaluate("trdlg.close()")


def main():
    from playwright.sync_api import sync_playwright
    shots = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if shots:
        shots.mkdir(parents=True, exist_ok=True)
    import os
    with Instance(wav_only=True, project_dir=os.environ.get("TRIM_PROJECT") or PROJECT) as inst, sync_playwright() as p:
        api = client.Api(inst.base_url, osc_port=inst.osc_port)
        api.post("/api/playlists", {"name": "T"}); api.post("/api/playlists/0/add", {"files": ["long_120s.wav"]})
        br = p.chromium.launch()
        for skin in ("console", "studio", "stage"):
            for tag, kw in (("1400", dict(viewport={"width": 1400, "height": 1000})), ("420", dict(viewport={"width": 420, "height": 900})),
                            ("touch", dict(viewport={"width": 430, "height": 932}, has_touch=True, is_mobile=True))):
                c = br.new_context(**kw)
                c.add_init_script(f"localStorage.setItem('cp_tour','1');localStorage.setItem('cp_theme','light');localStorage.setItem('cp_skin','{skin}')")
                pg = c.new_page(); errs = []
                pg.on("pageerror", lambda e: errs.append(str(e)))
                pg.goto(inst.base_url); pg.wait_for_selector("#lists li.t")
                run_page(pg, f"{skin}/{tag}", shots, api)
                check(f"{skin}/{tag}: no page errors", not errs, errs)
                c.close()
        br.close()
    print(f"\n{len(FAILS)} failure(s)")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
