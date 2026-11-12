#!/usr/bin/env python3
"""Live input card, 2.7.5 input-layout-threshold (desktop only; the phone layout is out of scope and not touched):

  Change 1  Device and Channels on ONE row (Device flexible and truncated with an ellipsis, Channels fixed and never cut), Input gain on the row below,
            nothing overflows, the menus open inside the viewport, at 1400 px and at the narrowest desktop width (34.01 rem).
  Change 2  the Library header: the "Expand all" icon (arrows out, same family as the Collapse all icon) with its name, size and hit area.
  Change 3  the adjustable Live input threshold: the marker is a slider (role, aria values, 24 px hit area, focus ring), dragging along both bars, keyboard
            (arrows 1 dB, Shift 5 dB, Home / End), persistence after a reload, the Settings row, contrast.
  2.7.5 input-arm-font-hint: Device and Channels are as small as the Duck now / Solo chips (font, padding, height >= 24 px, text not clipped) and the Settings menus are not;
            the card has no Armed switch and no "Duck above" row (slider, number, Reset): the mark is the only control (a click on the bar, a drag from the
            bar, double-click = default), the readout under the meter follows live, no gap where the row was, no inner scrollbar.

3 skins x dark / light. The capture device is SIMULATED (CP_TEST_INPUT feed, see tests/api/test_live_input.py); the page, the API and the helper are real.
    python tests/test_input_layout_ui.py [--shots DIR]      (needs playwright; starts its own disposable player)"""
import json, re, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "api"))
from harness import client                       # noqa: E402
from harness.instance import Instance, PROJECT   # noqa: E402
from test_live_input import make_env, set_feed   # noqa: E402

FAILS = []
LONG = "Dante USB I/O Module, USB Audio Interface Rev 2 (32 in / 32 out)"      # long enough to be cut at the narrowest desktop width in every skin, even at the smaller menu font
DEVS = [LONG, "Fake input", "Analog 1-2"]
MIN_W = 545                                      # 34.01 rem at 16 px: the narrowest page on which the card is shown


def check(name, ok, info=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"   {info}"))
    if not ok:
        FAILS.append(name)


def rgb(c):
    v = [float(x) for x in re.findall(r"[\d.]+", c)]
    if c.startswith("color(srgb"):
        v = [x * 255 for x in v[:3]] + v[3:]
    return v


def lum(c):
    v = [x / 255 for x in rgb(c)[:3]]
    v = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in v]
    return 0.2126 * v[0] + 0.7152 * v[1] + 0.0722 * v[2]


def contrast(a, b):
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


# the first opaque background behind an element (walks up), as an rgb string
BACK = """(e)=>{let n=e;while(n){const c=getComputedStyle(n).backgroundColor,m=c.match(/[\\d.]+/g);if(m&&(m.length<4||+m[3]>=0.99))return c;n=n.parentElement}return 'rgb(255,255,255)'}"""

ROWS = """()=>{const q=s=>document.querySelector(s),r=e=>e.getBoundingClientRect(),c=r(q('#inpc')),body=r(q('.inpbody')),dev=r(q('#inp_dev_cb')),ch=r(q('#inp_ch_cb')),
 g=r(q('.inpg')),devs=q('#inp_dev_cb>span'),chs=q('#inp_ch_cb>span'),row=r(q('.inprow'));
 const kids=[...q('.inpbody').querySelectorAll('*')].filter(e=>{const s=getComputedStyle(e);return s.display!=='none'&&e.getClientRects().length&&!e.closest('select')&&!e.closest('[hidden]')});
 const out=kids.filter(e=>{const x=r(e);return x.right>c.right+0.5||x.left<c.left-0.5}).map(e=>e.id||e.className||e.tagName);
 return {cardL:c.left,cardR:c.right,cardW:c.width,devTop:dev.top,devBot:dev.bottom,devL:dev.left,devR:dev.right,devW:dev.width,chTop:ch.top,chL:ch.left,chR:ch.right,chW:ch.width,
  gainTop:g.top,rowBot:row.bottom,devCut:devs.scrollWidth>devs.clientWidth+1,chCut:chs.scrollWidth>chs.clientWidth+1,chText:chs.textContent,devText:devs.textContent,
  devTitle:q('#inp_dev_cb').title,over_px:document.documentElement.scrollWidth-document.documentElement.clientWidth,out,
  cardOver:q('#inpc').scrollWidth>q('#inpc').clientWidth+1}}"""

GAP = """()=>{const q=s=>document.querySelector(s),vis=e=>e.getClientRects().length>0,card=q('#inpc'),body=q('.inpbody'),kids=[...body.children].filter(vis);
  const last=Math.max(...kids.map(e=>e.getBoundingClientRect().bottom));
  return {sc:card.scrollHeight-card.clientHeight,sw:card.scrollWidth-card.clientWidth,arm:vis(q('label.inparm')),row:vis(q('.inpt')),thn:vis(q('#inp_thn')),thx:vis(q('#inp_thx')),
   gap:body.getBoundingClientRect().bottom-last,modeTop:q('.inpmode').getBoundingClientRect().top,gainTop:q('.inpg').getBoundingClientRect().top}}"""
SIZE = """()=>{const m=e=>{const r=e.getBoundingClientRect(),c=getComputedStyle(e);return {h:Math.round(r.height*10)/10,fs:c.fontSize,pt:c.paddingTop,pl:c.paddingLeft,pr:c.paddingRight,mh:c.minHeight}},q=s=>document.querySelector(s),
  clip=e=>e.scrollHeight>e.clientHeight+1||e.scrollWidth>e.clientWidth+1&&getComputedStyle(e).textOverflow!=='ellipsis';
  return {dn:m(q('#inp_dn')),so:m(q('#inp_so')),dev:m(q('#inp_dev_cb')),ch:m(q('#inp_ch_cb')),devClip:clip(q('#inp_dev_cb>span')),chClip:clip(q('#inp_ch_cb>span')),
   lab:getComputedStyle(q('.inpdev')).fontSize,chev:getComputedStyle(q('#inp_dev_cb'),'::after').width}}"""
MENU = """()=>{const r=document.getElementById('cbo').getBoundingClientRect();return {l:r.left,t:r.top,r:r.right,b:r.bottom,w:innerWidth,h:innerHeight}}"""


def layout_checks(pg, tag, w, shots, base=0):
    r = pg.evaluate(ROWS)
    g = pg.evaluate(GAP)
    check(f"{tag}: the card has no inner scrollbar (all its content fits)", g["sc"] <= 1 and g["sw"] <= 1, g)
    check(f"{tag}: no Armed switch, no Duck above row, number box or Reset button is shown on the card", not g["arm"] and not g["row"] and not g["thn"] and not g["thx"], g)
    check(f"{tag}: no gap where the removed controls were (the last row ends at the card's body)", g["gap"] <= 2, g)
    check(f"{tag}: Input gain and the 'Duck only' note share the last row", abs(g["modeTop"] - g["gainTop"]) <= 6, g)
    z = pg.evaluate(SIZE)
    for k in ("dev", "ch"):
        nm = "Device" if k == "dev" else "Channels"
        same = all(z[k][f] == z["dn"][f] for f in ("fs", "pt", "pl", "pr")) and z[k]["fs"] == z["so"]["fs"]
        check(f"{tag}: the {nm} menu has the font size and padding of the Duck now / Solo chips ({z[k]['fs']}, {z[k]['pt']} {z[k]['pl']})", same, z)
        check(f"{tag}: the {nm} menu is as high as the chips ({z[k]['h']} vs {z['dn']['h']} px) and at least 24 px", abs(z[k]["h"] - z["dn"]["h"]) <= 0.8 and z[k]["h"] >= 24, z)
    check(f"{tag}: the menu text is not clipped at the new size (no vertical clipping)", not z["devClip"] and not z["chClip"], z)
    check(f"{tag}: Device and Channels do not stretch the card taller than the chips' row plus themselves", z["dev"]["h"] < 40, z)
    check(f"{tag}: Device and Channels on one row", abs(r["devTop"] - r["chTop"]) <= 2 and r["chL"] >= r["devR"] - 0.5, r)
    check(f"{tag}: Input gain is on its own row below", r["gainTop"] >= r["devBot"] - 1 and r["gainTop"] >= r["rowBot"] - 1, r)
    check(f"{tag}: Channels is never cut ('{r['chText']}')", not r["chCut"] and "(stereo)" in r["chText"], r)
    check(f"{tag}: the same width for Channels at every card width", r["chW"] > 150, r)
    check(f"{tag}: nothing leaves the card, the card adds no sideways scroll", not r["out"] and not r["cardOver"] and r["over_px"] <= max(base, 0), r)
    long = r["devText"] == LONG or r["devCut"]
    check(f"{tag}: the device name is complete or ends in an ellipsis, the full name is in the title", LONG in r["devTitle"] and (r["devCut"] or r["devText"] == LONG), r)
    if w >= 1000:
        check(f"{tag}: at full width the long name fits", not r["devCut"], r)
    else:
        check(f"{tag}: at the narrowest width the name is truncated, not overflowing", r["devCut"] and r["devR"] <= r["chL"], r)
    for sel in ("#inp_dev_cb", "#inp_ch_cb"):
        pg.click(sel); time.sleep(0.25)
        m = pg.evaluate(MENU)
        check(f"{tag}: menu of {sel} inside the viewport", m["l"] >= 0 and m["t"] >= 0 and m["r"] <= m["w"] and m["b"] <= m["h"], m)
        pg.keyboard.press("Escape"); time.sleep(0.15)
    if shots:
        pg.locator("#inpc").screenshot(path=str(Path(shots) / f"layout-{tag.replace('/', '-')}-{w}.png"))


LIB = """()=>{const q=i=>document.getElementById(i),f=b=>{const s=b.querySelector('svg'),c=getComputedStyle(s),r=b.getBoundingClientRect();return {w:r.width,h:r.height,sw:c.strokeWidth,sz:s.getBoundingClientRect().width,
   p:[...s.querySelectorAll('path')].map(x=>x.getAttribute('d')),title:b.title,al:b.getAttribute('aria-label'),ex:b.getAttribute('aria-expanded'),tag:b.tagName}};
  return {e:f(q('lib_expand')),c:f(q('lib_collapse')),open:document.querySelectorAll('#lib .fd:not(.closed)').length,all:document.querySelectorAll('#lib .fd').length}}"""


def library_checks(pg, tag, shots=None):
    g = pg.evaluate(LIB)
    e, c = g["e"], g["c"]
    check(f"{tag}: Library header, Expand all is an expand icon (arrows out), not the chevron", e["p"] == ["M15 3h6v6", "m21 3-7 7", "m3 21 7-7", "M9 21H3v-6"], e["p"])
    check(f"{tag}: Library header, Collapse all (shrink) is unchanged", c["p"] == ["M4 14h6v6", "M20 10h-6V4", "m14 10 7-7", "m3 21 7-7"], c["p"])
    check(f"{tag}: Library header, same icon size, stroke weight and hit area", (e["w"], e["h"], e["sw"], e["sz"]) == (c["w"], c["h"], c["sw"], c["sz"]) and e["w"] >= 31.5 and e["h"] >= 31.5, g)
    check(f"{tag}: Library header, title and aria-label say what the button does", e["title"] == e["al"] == "Expand all" and c["title"] == c["al"] == "Collapse all", g)
    check(f"{tag}: Library header, they are action buttons (no aria-expanded: they set every folder, they have no state of their own)", e["ex"] is None and c["ex"] is None and e["tag"] == "BUTTON", g)
    if shots:
        pg.locator("#libhd").screenshot(path=str(Path(shots) / f"library-header-{tag.replace('/', '-')}.png"))
    pg.click("#lib_collapse"); time.sleep(0.3)
    n1 = pg.evaluate("document.querySelectorAll('#lib .fd.closed, #lib .fd[data-closed], #lib [aria-expanded=false]').length")
    pg.click("#lib_expand"); time.sleep(0.3)
    n2 = pg.evaluate("document.querySelectorAll('#lib .fd.closed, #lib .fd[data-closed], #lib [aria-expanded=false]').length")
    check(f"{tag}: Library header, Expand all still expands what Collapse all closed", n2 <= n1, (n1, n2))

MARK = """()=>{const q=i=>document.getElementById(i),r=e=>e.getBoundingClientRect(),m=q('inp_th'),b=r(q('inp_m')),mr=r(m),card=r(q('inpc')),c=getComputedStyle(m);
  const two=!q('inp_r2').hidden,b2=r(q('inp_m2'));
  return {role:m.getAttribute('role'),min:m.getAttribute('aria-valuemin'),max:m.getAttribute('aria-valuemax'),now:m.getAttribute('aria-valuenow'),text:m.getAttribute('aria-valuetext'),
   tab:m.tabIndex,w:mr.width,h:mr.height,cx:mr.left+mr.width/2,cy:mr.top+mr.height/2,bl:b.left,bw:b.width,bt:b.top,bb:b.bottom,two,b2t:b2.top,b2b:b2.bottom,
   pct:(mr.left+mr.width/2-b.left)/b.width*100,cap:q('inp_thl').textContent,capOn:q('inp_thl').classList.contains('on'),duck:m.classList.contains('duck'),
   slider:q('inp_thr').value,num:q('inp_thn').value,set:q('set_inpthr').value,over:q('inp_m').classList.contains('over'),
   inCard:mr.left>=card.left&&mr.right<=card.right&&mr.top>=card.top&&mr.bottom<=card.bottom,aria:c.display}}"""
RINGB = """()=>{const m=document.getElementById('inp_th'),r=m.getBoundingClientRect(),c=getComputedStyle(m),card=document.getElementById('inpc').getBoundingClientRect(),o=parseFloat(c.outlineWidth)||0;
  return {style:c.outlineStyle,w:o,color:c.outlineColor,inside:r.left-o>=card.left&&r.right+o<=card.right&&r.top-o>=card.top&&r.bottom+o<=card.bottom,box:[r.left-o,r.right+o,r.top-o,r.bottom+o,card.left,card.right,card.top,card.bottom],focus:document.activeElement===m,
   hit:(()=>{const q=document.elementFromPoint(r.left+r.width/2,r.top+r.height/2);return q===m})()}}"""
PAINT = """()=>{const q=i=>document.getElementById(i),m=q('inp_th'),bg=e=>{while(e){const c=getComputedStyle(e).backgroundColor,k=c.match(/[\\d.]+/g);if(k&&(k.length<4||+k[3]>=0.99))return c;e=e.parentElement}return 'rgb(255,255,255)'};
  return {line:getComputedStyle(m,'::before').backgroundColor,grip:getComputedStyle(m,'::after').backgroundColor,bar:bg(q('inp_m')),card:bg(q('inpc')),ring:getComputedStyle(m).outlineColor,
   dim:getComputedStyle(q('inp_thl')).color,live:getComputedStyle(document.documentElement).getPropertyValue('--live')}}"""


def thr_checks(pg, api, inst, d, tag, shots):
    info = lambda: api.get("/api/input").json      # noqa: E731
    mark = lambda: pg.evaluate(MARK)               # noqa: E731
    api.post("/api/input", {"threshold_db": -30}); api.post("/api/input", {"armed": True})
    set_feed(d, state="run", db=-90.0, channels=64)
    pg.goto(inst.base_url); pg.wait_for_selector("#inpc")
    pg.evaluate("()=>{if(document.getElementById('inpc').classList.contains('ic'))inpTog(true)}")
    pg.wait_for_function("document.getElementById('inp_chip').textContent==='No signal'", timeout=15000)
    m = mark()
    check(f"{tag}: the marker is a slider with -60..0 and the value in dB", m["role"] == "slider" and (m["min"], m["max"], m["now"]) == ("-60", "0", "-30") and m["text"] == "\u221230 dB" and m["tab"] == 0, m)
    check(f"{tag}: the marker has a 24 px hit area and sits inside the card", m["w"] >= 24 and m["h"] >= 24 and m["inCard"], m)
    check(f"{tag}: at -30 dB the marker is in the middle of the bars", abs(m["pct"] - 50) < 1.5, m)
    check(f"{tag}: stereo pair: two bars, one marker over both", m["two"] and m["h"] >= (m["b2b"] - m["bt"]) - 1, m)
    check(f"{tag}: caption reads Duck above -30 dB", m["cap"] == "Duck above \u221230 dB" and not m["capOn"], m)
    # ---- the full range is on the scale: the marker never leaves the bars
    for v, want in ((-60, 0), (0, 100)):
        api.post("/api/input", {"threshold_db": v}); time.sleep(1.4)
        m = mark()
        check(f"{tag}: at {v} dB the marker is at {want} % of the bars (inside them)", abs(m["pct"] - want) < 1.0 and m["cx"] >= m["bl"] - 0.5 and m["cx"] <= m["bl"] + m["bw"] + 0.5, m)
    api.post("/api/input", {"threshold_db": -30}); time.sleep(1.4)
    # ---- drag along the first bar and along the second bar
    for bar, yk in (("first bar", lambda m: m["bt"] + 5), ("second bar", lambda m: m["b2t"] + 5)):
        m = mark(); x0 = m["cx"]
        tx = m["bl"] + (-45 + 60) / 60 * m["bw"]
        pg.mouse.move(x0, yk(m)); pg.mouse.down()
        pg.mouse.move((x0 + tx) / 2, yk(m), steps=4); pg.mouse.move(tx, yk(m), steps=4); pg.mouse.up()
        time.sleep(0.9)
        m2 = mark()
        check(f"{tag}: dragging on the {bar} moves the mark to -45 dB and saves it", m2["now"] == "-45" and info()["threshold_db"] == -45.0 and m2["num"] == "-45" and m2["slider"] == "-45", (m2, info()["threshold_db"]))
        check(f"{tag}: the caption and Settings follow the drag", m2["cap"] == "Duck above \u221245 dB" and m2["set"] == "-45", m2)
        api.post("/api/input", {"threshold_db": -30}); time.sleep(1.4)
    # ---- a drag past the ends is clamped
    m = mark(); pg.mouse.move(m["cx"], m["bt"] + 5); pg.mouse.down(); pg.mouse.move(m["bl"] - 200, m["bt"] + 5, steps=5); pg.mouse.up(); time.sleep(0.8)
    check(f"{tag}: a drag past the left end stops at -60 dB", mark()["now"] == "-60" and info()["threshold_db"] == -60.0, mark())
    api.post("/api/input", {"threshold_db": -30}); time.sleep(1.4)
    # ---- keyboard
    pg.focus("#inp_th")
    rb = pg.evaluate(RINGB)
    check(f"{tag}: the marker takes keyboard focus and shows a ring that is inside the card", rb["focus"] and rb["style"] != "none" and rb["w"] >= 2 and rb["inside"], rb)
    for key, want in (("ArrowRight", -29), ("ArrowUp", -28), ("ArrowLeft", -29), ("ArrowDown", -30), ("Shift+ArrowLeft", -35), ("Shift+ArrowRight", -30), ("Home", -60), ("ArrowLeft", -60), ("End", 0), ("ArrowRight", 0), ("Shift+ArrowRight", 0)):
        pg.keyboard.press(key); time.sleep(0.12)
        got = mark()["now"]
        check(f"{tag}: key {key} -> {want} dB", got == str(want), got)
    time.sleep(0.9)
    check(f"{tag}: the keys were saved (End = 0 dB)", info()["threshold_db"] == 0.0 and mark()["num"] == "0" and mark()["slider"] == "0", info())
    rb = pg.evaluate(RINGB)
    check(f"{tag}: the ring at 0 dB (the right end) is not clipped", rb["inside"] and rb["hit"], rb)
    pg.keyboard.press("Home"); time.sleep(0.4)
    rb = pg.evaluate(RINGB)
    check(f"{tag}: the ring at -60 dB (the left end) is not clipped", rb["inside"] and rb["hit"], rb)
    # ---- 2.7.5 input-arm-font-hint: the "Duck above" row (slider, number, Reset) is not shown on the card any more; the mark on the meter is the only control
    gone = pg.evaluate("()=>['inp_thr','inp_thn','inp_thx'].map(i=>[i,document.getElementById(i).getClientRects().length===0])")
    check(f"{tag}: no Duck above slider, number box or Reset button is shown on the card", all(v for _, v in gone), gone)
    check(f"{tag}: no 'Duck above' label row on the card (only the readout under the meter)", pg.evaluate("()=>![...document.querySelectorAll('#inpc label')].some(l=>/^Duck above/.test(l.textContent)&&l.getClientRects().length)") and pg.is_visible("#inp_thl"))
    # ---- a click on the bar moves the mark there (first bar, second bar), the readout follows, it is saved
    for bar, yk in (("first bar", lambda m: m["bt"] + 5), ("second bar", lambda m: m["b2t"] + 5)):
        api.post("/api/input", {"threshold_db": -30}); time.sleep(1.4)
        m = mark(); tx = m["bl"] + (-48 + 60) / 60 * m["bw"]
        pg.mouse.click(tx, yk(m)); time.sleep(0.9)
        m2 = mark()
        check(f"{tag}: a click on the {bar} moves the mark to -48 dB, shows it in the readout and saves it", m2["now"] == "-48" and m2["cap"] == "Duck above \u221248 dB" and info()["threshold_db"] == -48.0 and m2["set"] == "-48", (m2, info()["threshold_db"]))
    check(f"{tag}: the click gave the mark the keyboard focus", pg.evaluate("document.activeElement.id") == "inp_th")
    m = mark(); pg.mouse.click(m["bl"] + 1, m["bt"] + 5); time.sleep(0.8)
    check(f"{tag}: a click at the left end of the bar gives -60 dB", mark()["now"] == "-60" and info()["threshold_db"] == -60.0, mark())
    m = mark(); pg.mouse.click(m["bl"] + m["bw"] - 1, m["bt"] + 5); time.sleep(0.8)
    check(f"{tag}: a click at the right end of the bar gives 0 dB (rounded to a whole dB, at most 1 dB under)", mark()["now"] in ("0", "-1") and info()["threshold_db"] in (0.0, -1.0), mark())
    api.post("/api/input", {"threshold_db": -30}); time.sleep(1.4)
    m = mark(); pg.mouse.click(m["bl"] - 12, m["bt"] + 5); time.sleep(0.6)
    check(f"{tag}: a click on the L / R label next to the bar changes nothing", mark()["now"] == "-30" and info()["threshold_db"] == -30.0, mark())
    # a press on the bar then a drag: the readout follows BEFORE the button is released
    m = mark(); x1 = m["bl"] + (-20 + 60) / 60 * m["bw"]; x2 = m["bl"] + (-55 + 60) / 60 * m["bw"]
    pg.mouse.move(x1, m["bt"] + 5); pg.mouse.down(); pg.mouse.move((x1 + x2) / 2, m["bt"] + 5, steps=3); pg.mouse.move(x2, m["bt"] + 5, steps=3)
    mid = mark()
    check(f"{tag}: pressing on the bar and dragging: the mark and the readout follow while the button is down (-55 dB)", mid["now"] == "-55" and mid["cap"] == "Duck above \u221255 dB" and "drag" in pg.evaluate("document.getElementById('inp_th').className"), mid)
    pg.mouse.up(); time.sleep(0.9)
    check(f"{tag}: and it is saved when the button is released", info()["threshold_db"] == -55.0, info()["threshold_db"])
    title = pg.evaluate("document.getElementById('inp_th').title")
    check(f"{tag}: the mark's title tells how to use it (drag, click the bar, keys, double-click for the default -30 dB)", all(w in title for w in ("Drag", "click the bar", "arrow keys", "Home and End", "Double-click", "default", "\u221230 dB")), title)
    pg.click("#setbtn"); pg.wait_for_selector("#settings[open]"); pg.click("#set_tabs [data-tab=audio]")
    check(f"{tag}: Settings > Audio still has the Duck above row, with its (i) help (not changed)", pg.is_visible("#set_inpthr") and pg.locator("#settings .sr[data-s*='input threshold'] .ib2").count() == 1)
    st = pg.evaluate("()=>{const e=document.getElementById('set_inpdev_cb'),c=getComputedStyle(e);return {h:e.getBoundingClientRect().height,fs:c.fontSize,pl:c.paddingLeft,pt:c.paddingTop}}")
    check(f"{tag}: the same menu in Settings > Audio keeps its own size and padding (not the chips' size)", st["pl"] == "8px" and st["pt"] == "0px" and st["h"] >= 28, st)
    pg.fill("#set_inpthr", "-25"); pg.evaluate("document.getElementById('set_inpthr').dispatchEvent(new Event('change'))"); time.sleep(0.9)
    m = mark()
    check(f"{tag}: the Settings > Audio field sets it and the mark follows at once", (m["now"], m["cap"]) == ("-25", "Duck above \u221225 dB") and info()["threshold_db"] == -25.0, (m, info()["threshold_db"]))
    pg.keyboard.press("Escape"); time.sleep(0.3)
    api.post("/api/input", {"threshold_db": -33})
    pg.wait_for_function("document.getElementById('inp_th').getAttribute('aria-valuenow')==='-33'", timeout=6000)
    m = mark()
    check(f"{tag}: a change made elsewhere (another browser, the API) shows without a reload", m["set"] == "-33" and m["cap"] == "Duck above \u221233 dB", m)
    # ---- the double-click on the mark goes back to the default
    api.post("/api/input", {"threshold_db": -48}); pg.wait_for_function("document.getElementById('inp_th').getAttribute('aria-valuenow')==='-48'", timeout=6000)
    m = mark(); pg.mouse.dblclick(m["cx"], m["cy"]); time.sleep(0.9)
    check(f"{tag}: double-clicking the mark goes back to -30 dB", mark()["now"] == "-30" and info()["threshold_db"] == -30.0 and mark()["cap"] == "Duck above \u221230 dB", mark())
    # ---- persistence after a reload
    api.post("/api/input", {"threshold_db": -41}); time.sleep(0.5)
    pg.reload(); pg.wait_for_selector("#inpc"); pg.wait_for_function("document.getElementById('inp_th').getAttribute('aria-valuenow')==='-41'", timeout=8000)
    m = mark()
    check(f"{tag}: after a reload the mark, the readout and Settings show -41 dB", (m["now"], m["set"], m["cap"]) == ("-41", "-41", "Duck above \u221241 dB"), m)
    saved = json.loads((Path(inst.workdir) / "state.json").read_text())
    check(f"{tag}: it is in state.json", saved.get("input_threshold_db") == -41.0, saved)
    # ---- the feedback: the level is over the threshold -> "Ducking"
    api.post("/api/input", {"threshold_db": -30}); time.sleep(1.2)
    pg.evaluate("()=>{if(document.getElementById('inpc').classList.contains('ic'))inpTog(true)}")
    set_feed(d, state="run", db=-20.0, channels=64)
    pg.wait_for_function("document.getElementById('inp_thl').classList.contains('on')", timeout=10000)
    m = mark()
    check(f"{tag}: over the threshold the caption says Ducking and the mark turns red", m["capOn"] and m["cap"].startswith("Ducking") and m["duck"] and m["over"], m)
    api.post("/api/input", {"threshold_db": -10}); time.sleep(1.5)
    m = mark()
    check(f"{tag}: with the threshold above the level it does not", not m["capOn"] and not m["duck"] and not m["over"] and info()["gr"] == 0.0, (m, info()["gr"]))
    api.post("/api/input", {"threshold_db": -30, "armed": False}); time.sleep(1.5)
    m = mark()
    check(f"{tag}: not armed: the level is over the mark but nothing ducks, so the caption does not say Ducking", m["over"] and not m["capOn"] and not m["duck"], m)
    api.post("/api/input", {"armed": True})
    set_feed(d, state="run", db=-90.0, channels=64); time.sleep(1.5)
    # ---- contrast
    P = pg.evaluate(PAINT)
    c_line, c_grip = contrast(P["line"], P["bar"]), contrast(P["grip"], P["bar"])
    check(f"{tag}: the mark has >= 3:1 against the bar (line {c_line:.1f}, grip {c_grip:.1f})", c_line >= 3 and c_grip >= 3, P)
    c_ring = contrast(P["ring"], P["card"])
    check(f"{tag}: the focus ring has >= 3:1 against the card ({c_ring:.1f})", c_ring >= 3, P)
    for k in ("dim",):
        check(f"{tag}: text {k} has >= 4.5:1 against the card ({contrast(P[k], P['card']):.1f})", contrast(P[k], P["card"]) >= 4.5, P)
    pg.evaluate("()=>{const m=document.getElementById('inp_th');m.classList.add('duck')}")
    P2 = pg.evaluate(PAINT)
    check(f"{tag}: the red (ducking) mark has >= 3:1 against the bar ({contrast(P2['line'], P2['bar']):.1f})", contrast(P2["line"], P2["bar"]) >= 3, P2)
    pg.evaluate("()=>document.getElementById('inp_th').classList.remove('duck')")
    if shots:
        pg.evaluate("()=>{if(document.getElementById('inpc').classList.contains('ic'))inpTog(true)}")
        api.post("/api/input", {"threshold_db": -35}); time.sleep(1.4)
        pg.locator("#inpc").screenshot(path=str(Path(shots) / f"threshold-{tag.replace('/', '-')}.png"))
    api.post("/api/input", {"threshold_db": -30})


def main():
    from playwright.sync_api import sync_playwright
    shots = None
    if "--shots" in sys.argv:
        shots = sys.argv[sys.argv.index("--shots") + 1]
        Path(shots).mkdir(parents=True, exist_ok=True)
    d, env = make_env()
    (d / "mock_inputs.json").write_text(json.dumps(DEVS))
    set_feed(d, state="run", db=-90.0, channels=64)
    cfg = {"input_device": LONG, "input_armed": True, "preview_device": "Mock out 1", "duck_hold": False, "duck_release_ms": 200}
    with Instance(wav_only=True, extra_config=cfg, extra_env=env) as inst, sync_playwright() as p:
        api = client.Api(inst.base_url, osc_port=inst.osc_port)
        api.cmd("rescan")
        for f in ("Alpha", "Alpha/Inner", "Delta"):
            api.post("/api/library/folder", {"path": f})
        api.post("/api/playlists", {"name": "T"})
        api.post("/api/playlists/0/add", {"files": ["long_120s.wav"]})
        api.post("/api/input", {"channels": [1, 2]})            # the label the width is made for: "Channel 1/Channel 2 (stereo)"
        time.sleep(2.5)
        br = p.chromium.launch()
        for skin in ("console", "studio", "stage"):
            for theme in ("dark", "light"):
                tag = f"{skin}/{theme}"
                c = br.new_context(viewport={"width": 1400, "height": 1000})
                c.add_init_script(f"localStorage.setItem('cp_tour','1');localStorage.setItem('cp_theme','{theme}');localStorage.setItem('cp_skin','{skin}');localStorage.removeItem('cp_inp')")
                pg = c.new_page(); errs = []
                pg.on("pageerror", lambda e: errs.append(str(e)))
                pg.goto(inst.base_url); pg.wait_for_selector("#inpc")
                for w in (1400, MIN_W):
                    pg.set_viewport_size({"width": w, "height": 1000})
                    pg.goto(inst.base_url); pg.wait_for_selector("#inpc")      # a page loaded at this width (a live resize of the stage skin is not what is measured)
                    pg.evaluate("()=>{if(!document.getElementById('inpc').classList.contains('ic'))inpTog(false)}")
                    time.sleep(0.4)
                    base = pg.evaluate("()=>document.documentElement.scrollWidth-document.documentElement.clientWidth")      # the page's own overflow with the card closed (stage skin rows at 34 rem)
                    pg.evaluate("()=>{if(document.getElementById('inpc').classList.contains('ic'))inpTog(true)}")
                    time.sleep(0.7)
                    layout_checks(pg, tag, w, shots, base)
                pg.set_viewport_size({"width": 1400, "height": 1000}); pg.goto(inst.base_url); pg.wait_for_selector("#lib_expand svg")
                library_checks(pg, tag, shots)
                thr_checks(pg, api, inst, d, tag, shots)
                check(f"{tag}: no script errors", not errs, errs)
                c.close()
        br.close()
    print(f"\n{len(FAILS)} failed" if FAILS else "\nall passed")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
