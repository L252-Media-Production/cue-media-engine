#!/usr/bin/env python3
"""The hint on the Cue container's "Input Gain" (2.7.5 input-arm-font-hint, change 2), desktop only (3 skins x dark / light at 1400 px, plus the narrowest desktop width, a
short window and a touch device):

  * a real button (`#hint_ig`, aria-label "About Input Gain", aria-expanded) next to the unchanged label "Input Gain", keyboard focusable, a hit area of at least 24 px,
  * click, Enter and Space (and a tap on a touch device) open the popover with exactly the agreed text; Escape closes it and gives the focus back; so do a click outside
    and a second click on the button,
  * the popover stays inside the visible viewport (1400 px, 545 px, a 380 px high window), the focus ring is not clipped,
  * contrast: the hint text >= 4.5:1, the icon >= 3:1,
  * the Input Gain slider still works (saved by the player),
  * at phone width the icon is hidden (the layout is unchanged) and the Live input card's Armed switch is still in the DOM.

    python tests/test_input_hint_ui.py [--shots DIR]      (needs playwright; starts its own disposable player)"""
import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "api"))
from harness import client                       # noqa: E402
from harness.instance import Instance            # noqa: E402
from test_input_stereo_ui import CONTRAST        # noqa: E402

FAILS = []
SHOTS = sys.argv[sys.argv.index("--shots") + 1] if "--shots" in sys.argv else None
TEXT = "Level of the track played on top (Play on Top). This is not the Live input gain, which is on the Live input card."
MIN_W = 545                                      # 34.01 rem at 16 px


def check(name, ok, info=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"   {info}"))
    if not ok:
        FAILS.append(name)


POP = """()=>{const p=document.getElementById('hintpop'),b=document.getElementById('hint_ig'),r=p.getBoundingClientRect(),vv=window.visualViewport;
  return {hidden:p.hidden,text:p.textContent,l:r.left,t:r.top,r:r.right,b:r.bottom,w:vv?vv.width:innerWidth,h:vv?vv.height:innerHeight,exp:b.getAttribute('aria-expanded'),
   active:document.activeElement&&document.activeElement.id,disp:getComputedStyle(p).display}}"""
BTN = """()=>{const b=document.getElementById('hint_ig'),r=b.getBoundingClientRect(),cs=getComputedStyle(b),lab=b.closest('label'),cx=r.left+r.width/2,cy=r.top+r.height/2,
  at=(dx,dy)=>document.elementFromPoint(cx+dx,cy+dy)===b;
  return {tag:b.tagName,type:b.type,label:b.getAttribute('aria-label'),exp:b.getAttribute('aria-expanded'),tab:b.tabIndex,w:r.width,h:r.height,vis:r.width>0&&cs.display!=='none',
   hit:at(12,0)&&at(-12,0)&&at(0,12)&&at(0,-12),labelText:lab.firstChild.textContent.trim(),slider:document.getElementById('top_trk').getAttribute('aria-label'),
   pad:cs.padding,ctrl:b.getAttribute('aria-controls')}}"""
RING = """()=>{const e=document.activeElement,cs=getComputedStyle(e),r=e.getBoundingClientRect(),o=(parseFloat(cs.outlineWidth)||0)+(parseFloat(cs.outlineOffset)||0);
  let clip=false;for(let n=e.parentElement;n;n=n.parentElement){const s=getComputedStyle(n);if(s.overflow!=='visible'||s.overflowX!=='visible'||s.overflowY!=='visible'){const q=n.getBoundingClientRect();
   if(r.left-o<q.left-0.5||r.right+o>q.right+0.5||r.top-o<q.top-0.5||r.bottom+o>q.bottom+0.5)clip=true}}
  return {id:e.id,style:cs.outlineStyle,w:parseFloat(cs.outlineWidth)||0,clip}}"""
RINGC = """()=>{const e=document.activeElement,cs=getComputedStyle(e);return {ring:cs.outlineColor,back:getComputedStyle(e.closest('.strip')||document.body).backgroundColor}}"""


def ratio(a, b):
    import re
    def lum(c):
        v = [float(x) for x in re.findall(r"[\d.]+", c)[:3]]
        if c.startswith("color("):
            v = [x * 255 for x in v]
        v = [x / 255 for x in v]
        v = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in v]
        return 0.2126 * v[0] + 0.7152 * v[1] + 0.0722 * v[2]
    x, y = sorted((lum(a), lum(b)), reverse=True)
    return (x + 0.05) / (y + 0.05)


def inside(m):
    return m["l"] >= -0.5 and m["t"] >= -0.5 and m["r"] <= m["w"] + 0.5 and m["b"] <= m["h"] + 0.5


def open_duck(pg):
    pg.evaluate("()=>duckTog(true)"); time.sleep(0.2)


def main():
    from playwright.sync_api import sync_playwright
    with Instance(wav_only=True) as inst, sync_playwright() as p:
        api = client.Api(inst.base_url, osc_port=inst.osc_port)
        api.cmd("rescan")
        api.post("/api/playlists", {"name": "T"})
        api.post("/api/playlists/0/add", {"files": ["tone_a.wav"]})
        br = p.chromium.launch()
        for skin in ("console", "studio", "stage"):
            for theme in ("dark", "light"):
                tag = f"{skin}/{theme}"
                c = br.new_context(viewport={"width": 1400, "height": 1000})
                c.add_init_script(f"localStorage.setItem('cp_tour','1');localStorage.setItem('cp_theme','{theme}');localStorage.setItem('cp_skin','{skin}');localStorage.removeItem('cp_duck')")
                pg = c.new_page(); errs = []
                pg.on("pageerror", lambda e: errs.append(str(e)))
                pg.goto(inst.base_url); pg.wait_for_selector("#hint_ig", state="attached")
                check(f"{tag}: collapsed Ducking section: the hint button is not shown", not pg.is_visible("#hint_ig"))
                open_duck(pg)
                b = pg.evaluate(BTN)
                check(f"{tag}: a real button named 'About Input Gain', shown next to the unchanged label", b["tag"] == "BUTTON" and b["type"] == "button" and b["label"] == "About Input Gain" and b["vis"] and b["labelText"] == "Input Gain" and b["tab"] == 0, b)
                check(f"{tag}: the slider keeps its own name", b["slider"] == "Input gain: level of the track played on top, in percent", b)
                check(f"{tag}: closed: aria-expanded=false, controls the popover, popover hidden", b["exp"] == "false" and b["ctrl"] == "hintpop" and pg.evaluate(POP)["hidden"], b)
                check(f"{tag}: a hit area of at least 24 px (the 18 px circle plus 4 px around it)", b["hit"], b)
                # --- click opens, the exact text, inside the viewport
                pg.click("#hint_ig"); time.sleep(0.15)
                m = pg.evaluate(POP)
                check(f"{tag}: click opens the hint with exactly the agreed text", not m["hidden"] and m["text"] == TEXT and m["exp"] == "true" and m["disp"] != "none", m)
                check(f"{tag}: the hint is inside the viewport", inside(m), m)
                cs = pg.evaluate(CONTRAST, [["#hintpop"], "text"])
                check(f"{tag}: hint text >= 4.5:1 ({cs[0]['ratio'] if cs else '?'})", cs and cs[0]["ratio"] >= 4.5, cs)
                ci = pg.evaluate(CONTRAST, [["#hint_ig"], "border"]); ct = pg.evaluate(CONTRAST, [["#hint_ig"], "text"])
                check(f"{tag}: the icon (circle {ci[0]['ratio'] if ci else '?'}, glyph {ct[0]['ratio'] if ct else '?'}) >= 3:1", ci and ct and ci[0]["ratio"] >= 3 and ct[0]["ratio"] >= 3, (ci, ct))
                if SHOTS:
                    pg.screenshot(path=f"{SHOTS}/hint-{skin}-{theme}.png", clip={"x": 0, "y": max(0, pg.evaluate("document.getElementById('hint_ig').getBoundingClientRect().top") - 150), "width": 1400, "height": 260})
                # --- second click closes; Escape closes and returns the focus; click outside closes
                pg.click("#hint_ig"); time.sleep(0.1)
                check(f"{tag}: a second click closes it", pg.evaluate(POP)["hidden"] and pg.evaluate(BTN)["exp"] == "false")
                pg.click("#hint_ig"); time.sleep(0.1); pg.keyboard.press("Escape"); time.sleep(0.1)
                m = pg.evaluate(POP)
                check(f"{tag}: Escape closes it and the focus is on the button", m["hidden"] and m["active"] == "hint_ig" and m["exp"] == "false", m)
                check(f"{tag}: Escape with the hint closed does not break the page (no dialog opened)", not pg.evaluate("document.querySelector('dialog[open]')"))
                pg.click("#hint_ig"); time.sleep(0.1); pg.mouse.click(700, 8); time.sleep(0.1)
                check(f"{tag}: a click outside closes it", pg.evaluate(POP)["hidden"])
                pg.click("#hint_ig"); time.sleep(0.1); pg.click("#dk_rel"); time.sleep(0.1)
                check(f"{tag}: using another control closes it", pg.evaluate(POP)["hidden"])
                # --- keyboard: Tab reaches the button from the slider before it, with a visible ring that is not clipped; Enter and Space open it
                pg.focus("#dk_rel"); pg.keyboard.press("Tab"); time.sleep(0.1)
                rg = pg.evaluate(RING)
                check(f"{tag}: Tab reaches the hint button, with a visible 2 px ring that is not clipped", rg["id"] == "hint_ig" and rg["style"] != "none" and rg["w"] >= 2 and not rg["clip"], rg)
                rc = pg.evaluate(RINGC)
                check(f"{tag}: the focus ring has >= 3:1 ({ratio(rc['ring'], rc['back']):.1f})", ratio(rc["ring"], rc["back"]) >= 3, rc)
                pg.keyboard.press("Enter"); time.sleep(0.1)
                check(f"{tag}: Enter opens it", not pg.evaluate(POP)["hidden"] and pg.evaluate(POP)["text"] == TEXT)
                pg.keyboard.press("Escape"); time.sleep(0.1); pg.keyboard.press("Space"); time.sleep(0.1)
                check(f"{tag}: Space opens it (after Escape the focus was on the button)", not pg.evaluate(POP)["hidden"])
                pg.keyboard.press("Space"); time.sleep(0.1)
                check(f"{tag}: Space again closes it", pg.evaluate(POP)["hidden"])
                # --- scrolling the page moves the hint with the button; collapsing Ducking closes it
                pg.click("#hint_ig"); time.sleep(0.1)
                pg.evaluate("()=>duckTog(false)"); time.sleep(0.2)
                check(f"{tag}: collapsing the Ducking section closes the hint", pg.evaluate(POP)["hidden"] and pg.evaluate(BTN)["exp"] == "false")
                open_duck(pg)
                # --- the slider still works and the player holds the value
                pg.evaluate("()=>{const e=document.getElementById('top_trk');e.value=55;e.dispatchEvent(new Event('input',{bubbles:true}));e.dispatchEvent(new Event('change',{bubbles:true}))}"); time.sleep(0.8)
                top = api.get("/api/settings/top").json
                check(f"{tag}: the Input Gain slider still saves its value", int(top.get("track_pct", top.get("top_track_pct", -1))) == 55 or 55 in [int(v) for v in top.values() if isinstance(v, (int, float))], top)
                pg.evaluate("()=>{const e=document.getElementById('top_trk');e.value=100;e.dispatchEvent(new Event('input',{bubbles:true}));e.dispatchEvent(new Event('change',{bubbles:true}))}"); time.sleep(0.5)
                # --- narrowest desktop width and a short window: still inside
                pg.set_viewport_size({"width": MIN_W, "height": 1000}); pg.goto(inst.base_url); pg.wait_for_selector("#hint_ig", state="attached"); open_duck(pg)
                pg.click("#hint_ig"); time.sleep(0.15)
                m = pg.evaluate(POP)
                check(f"{tag}: at {MIN_W} px the hint is inside the viewport", not m["hidden"] and inside(m) and m["r"] - m["l"] <= MIN_W - 15, m)
                pg.keyboard.press("Escape")
                pg.set_viewport_size({"width": 1400, "height": 380}); pg.goto(inst.base_url); pg.wait_for_selector("#hint_ig", state="attached"); open_duck(pg)
                pg.locator("#hint_ig").scroll_into_view_if_needed(); pg.click("#hint_ig"); time.sleep(0.15)
                m = pg.evaluate(POP)
                check(f"{tag}: in a 380 px high window the hint is inside the viewport", not m["hidden"] and inside(m), m)
                pg.keyboard.press("Escape")
                # --- phone width: the icon is hidden, the card's switch is still in the DOM
                pg.set_viewport_size({"width": 500, "height": 900}); pg.goto(inst.base_url); pg.wait_for_selector("#hint_ig", state="attached"); open_duck(pg)
                check(f"{tag}: at phone width the hint icon is hidden (layout unchanged)", not pg.is_visible("#hint_ig"))
                check(f"{tag}: at phone width the Live input card still has its Armed switch in the DOM (shown there as before)", pg.locator("label.inparm #inp_arm").count() == 1
                      and pg.evaluate("getComputedStyle(document.querySelector('label.inparm')).display") != "none")
                check(f"{tag}: no script errors", not errs, errs)
                c.close()
        # --- a touch device: a tap opens it, a tap outside closes it
        c = br.new_context(viewport={"width": 1000, "height": 800}, has_touch=True, is_mobile=False)
        c.add_init_script("localStorage.setItem('cp_tour','1');localStorage.removeItem('cp_duck')")
        pg = c.new_page(); pg.goto(inst.base_url); pg.wait_for_selector("#hint_ig", state="attached"); open_duck(pg)
        pg.tap("#hint_ig"); time.sleep(0.2)
        m = pg.evaluate(POP)
        check("touch: a tap opens the hint without hover", not m["hidden"] and m["text"] == TEXT and inside(m), m)
        pg.touchscreen.tap(700, 8); time.sleep(0.2)
        check("touch: a tap outside closes it", pg.evaluate(POP)["hidden"])
        c.close()
        br.close()
    print(f"\n{len(FAILS)} failed" if FAILS else "\nall passed")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
