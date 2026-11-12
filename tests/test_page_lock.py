#!/usr/bin/env python3
"""Page lock (2.7.5 rc3): while a modal dialog or the tour dims the page, the page behind it does not move (wheel, keys, touch) and its scroll position
comes back on close; one counter, so two overlays at once do not unlock early; no sideways shift; scrolling inside the dialog does not chain into the page.
python tests/test_page_lock.py   (needs playwright; own disposable player)"""
import os
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from harness import client                       # noqa: E402
from harness.instance import Instance, PROJECT   # noqa: E402

FAILS = []


def check(name, ok, info=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"   {info}"))
    if not ok:
        FAILS.append(name)


# where the page is: the document is fixed at -y while locked, so the offset is read from the body then, else from scrollY
POS = "()=>{const b=document.body;return b.classList.contains('plock')?-parseFloat(b.style.top||0):window.scrollY}"
GEOM = "()=>{const r=document.querySelector('#now').getBoundingClientRect();return [Math.round(r.left*10)/10,Math.round(r.width*10)/10]}"


def run(pg, label, touch):
    pg.goto(BASE); pg.wait_for_selector("#setbtn"); time.sleep(0.8)
    pg.evaluate("document.body.style.minHeight='3000px'")             # a page that really scrolls, whatever the library holds
    pg.evaluate("window.scrollTo(0, 420)"); time.sleep(0.2)
    y0 = pg.evaluate("window.scrollY")
    check(f"{label}: the page is scrolled", y0 > 300, y0)
    geo0 = pg.evaluate(GEOM)
    pg.evaluate("openSettings()"); pg.wait_for_selector("#settings[open]"); time.sleep(0.4)
    check(f"{label}: locked at the same place", pg.evaluate(POS) == y0 and pg.evaluate("document.body.classList.contains('plock')"), pg.evaluate(POS))
    check(f"{label}: no sideways shift when locking", pg.evaluate(GEOM) == geo0, (geo0, pg.evaluate(GEOM)))
    if touch:
        cdp = pg.context.new_cdp_session(pg)
        for dy in (-300, 300, -600):
            cdp.send("Input.synthesizeScrollGesture", {"x": 20, "y": 400, "yDistance": dy, "gestureSourceType": "touch", "speed": 800})
            time.sleep(0.3)
        check(f"{label}: touch swipes on the backdrop do not move the page", pg.evaluate(POS) == y0, pg.evaluate(POS))
    else:
        pg.mouse.move(40, 300)
        for dy in (400, -900, 2500):
            pg.mouse.wheel(0, dy); time.sleep(0.15)
        check(f"{label}: wheel over the backdrop does not move the page", pg.evaluate(POS) == y0, pg.evaluate(POS))
        for k in ("PageDown", "End", "ArrowDown", "Home", "PageUp"):      # not Space: the focused close button would take it
            pg.keyboard.press(k)
        check(f"{label}: keys do not move the page", pg.evaluate(POS) == y0, pg.evaluate(POS))
    # scrolling inside the dialog works and does not chain into the page at its end
    pg.evaluate("document.getElementById('settings').scrollTop=0")
    pg.evaluate("(()=>{const d=document.getElementById('settings');d.style.maxHeight='260px';d.style.minHeight='0'})()")
    can = pg.evaluate("(()=>{const d=document.getElementById('settings');return d.scrollHeight>d.clientHeight+20})()")
    check(f"{label}: the dialog itself can scroll", can)
    if not touch:
        box = pg.evaluate("(()=>{const r=document.getElementById('settings').getBoundingClientRect();return [r.left+r.width/2,r.top+r.height/2]})()")
        pg.mouse.move(*box)
        for _ in range(6):
            pg.mouse.wheel(0, 700); time.sleep(0.1)
        st = pg.evaluate("(()=>{const d=document.getElementById('settings');return d.scrollTop+d.clientHeight>=d.scrollHeight-2})()")
        check(f"{label}: the dialog scrolled to its end", st)
        pg.mouse.wheel(0, 900); time.sleep(0.2)
        check(f"{label}: at the end of the dialog the page does not take the scroll", pg.evaluate(POS) == y0, pg.evaluate(POS))
    pg.evaluate("document.getElementById('settings').style.cssText=''")
    # two overlays at once: the first close must not unlock
    pg.evaluate("document.getElementById('lxdlg').showModal()"); time.sleep(0.2)
    pg.evaluate("document.getElementById('lxdlg').close()"); time.sleep(0.3)
    check(f"{label}: closing the second dialog keeps the lock", pg.evaluate("document.body.classList.contains('plock')") and pg.evaluate(POS) == y0)
    pg.evaluate("settings.close()"); time.sleep(0.4)
    check(f"{label}: unlocked and the exact scroll position is back", not pg.evaluate("document.body.classList.contains('plock')") and pg.evaluate("window.scrollY") == y0, pg.evaluate("window.scrollY"))
    check(f"{label}: no sideways shift after closing", pg.evaluate(GEOM) == geo0, (geo0, pg.evaluate(GEOM)))
    # the other modal dialogs go through the same helper
    for d in ("fdlg", "lidlg", "dldlg", "trdlg"):
        pg.evaluate(f"document.getElementById('{d}').showModal()"); time.sleep(0.15)
        locked = pg.evaluate("document.body.classList.contains('plock')") and pg.evaluate(POS) == y0
        pg.evaluate(f"document.getElementById('{d}').close()"); time.sleep(0.2)
        check(f"{label}: #{d} locks and restores", locked and pg.evaluate("window.scrollY") == y0 and not pg.evaluate("document.body.classList.contains('plock')"), pg.evaluate("window.scrollY"))
    # the tour
    pg.evaluate("startTour()"); time.sleep(0.4)
    check(f"{label}: the tour locks the page", pg.evaluate("document.body.classList.contains('plock')") and pg.evaluate(POS) == y0, pg.evaluate(POS))
    pg.evaluate("tourClose()"); time.sleep(0.3)
    check(f"{label}: closing the tour restores the position", pg.evaluate("window.scrollY") == y0 and not pg.evaluate("document.body.classList.contains('plock')"), pg.evaluate("window.scrollY"))
    pg.evaluate("openSettings()"); pg.wait_for_selector("#settings[open]"); pg.keyboard.press("Escape"); time.sleep(0.4)
    check(f"{label}: Esc closes Settings and restores the position", pg.evaluate("window.scrollY") == y0, pg.evaluate("window.scrollY"))


def main():
    global BASE
    from playwright.sync_api import sync_playwright
    with Instance(wav_only=True, project_dir=os.environ.get("PP_PROJECT") or PROJECT) as inst, sync_playwright() as p:
        BASE = inst.base_url
        br = p.chromium.launch()
        for label, vp, touch in (("desktop", {"width": 1280, "height": 600}, False), ("phone touch", {"width": 390, "height": 700}, True)):
            c = br.new_context(viewport=vp, has_touch=touch, is_mobile=touch)
            c.add_init_script("localStorage.setItem('cp_tour','1')")
            pg = c.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
            run(pg, label, touch)
            check(f"{label}: no page errors", not errs, errs)
            c.close()
        br.close()
    print(f"\n{len(FAILS)} failed" if FAILS else "\nall passed")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
