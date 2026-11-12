#!/usr/bin/env python3
"""2.7.5 rc1, Preview meters beside Live and the pinned Live panel (Playwright, own disposable player):
 idle = only the Live meters; previewing = the Preview pair (thinner, own Mute, speaker) to the right of the shared scale, gone again when it stops; the Mute buttons share one row;
 the speaker buttons open the output menu (search, Wired group, tick); the Preview Mute never touches Live; the pin (on by default, filled upright / outlined tilted, saved per browser, the
 Settings switches); the one-line strip once the full panel has scrolled out of view (PRV chip only while previewing); the phone strip and order (Live, Cue, Playlists).
    python tests/test_preview_meters_ui.py [SHOT_DIR]"""
import os
import sys
import time
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


R = "e=>{const r=e.getBoundingClientRect();return [r.left,r.top,r.right,r.bottom,r.width,r.height]}"


def ctx(br, w=1280, h=800, touch=False, skin=None, theme=None, extra=""):
    c = br.new_context(viewport={"width": w, "height": h}, has_touch=touch, is_mobile=touch)
    c.add_init_script("localStorage.setItem('cp_tour','1');" + (f"localStorage.setItem('cp_skin','{skin}');" if skin else "") + (f"localStorage.setItem('cp_theme','{theme}');" if theme else "") + extra)
    return c


def preview_row(pg):
    pg.locator(".lt", has_text="long_120s").first.locator(".ib.pv").click()
    pg.wait_for_function("PVCUR.state==='playing'", timeout=8000)
    time.sleep(0.4)


def main():
    from playwright.sync_api import sync_playwright
    if SHOTS:
        os.makedirs(SHOTS, exist_ok=True)
    with Instance(wav_only=True, project_dir=os.environ.get("PP_PROJECT") or PROJECT) as inst, sync_playwright() as p:
        api = client.Api(inst.base_url, osc_port=inst.osc_port)
        br = p.chromium.launch()
        c = ctx(br); pg = c.new_page(); errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto(inst.base_url); pg.wait_for_selector("#setbtn"); time.sleep(1.0)
        pg.evaluate("document.body.style.minHeight='3200px'")

        # ---- idle
        check("idle: only the Live meters (no Preview pair, label or buttons)", pg.evaluate("pvlvl.hidden&&pcap.hidden&&pvbtns.hidden&&ms_pv.hidden&&!lvl.classList.contains('pvon')"))
        check("the Preview panel no longer holds meters", pg.evaluate("!document.querySelector('#pv .vmeter')&&!document.querySelector('#pv #pvlvl')"))
        check("Live output is a speaker button after Mute and Solo", pg.evaluate("[...document.querySelector('#lvl .msb').children].map(e=>e.id).join()") == "mutebtn,pvsolo,dev_out" and not pg.evaluate("!!document.querySelector('.ctrl .outsel #dev, .tbar #dev, .volrow #dev_cb')"))
        check("the Live Output selector is off the transport row", not pg.is_visible("#dev_cb") and pg.evaluate("!document.querySelector('.volrow label.outsel[title^=\"Where the live audio goes\"]')"))

        # ---- previewing
        preview_row(pg)
        check("previewing: the Preview pair, label, Mute and speaker are there", pg.evaluate("!pvlvl.hidden&&!pcap.hidden&&!pvbtns.hidden&&lvl.classList.contains('pvon')"))
        sc, lb, pb = pg.eval_on_selector("#lvl .dbs", R), pg.eval_on_selector("#lbars", R), pg.eval_on_selector("#pvlvl .vm", R)
        lw = pg.eval_on_selector("#lbars .vm", R)[4]
        check("the Preview pair is to the right of the scale, which stays beside the Live pair", pb[0] >= sc[2] - 1 and sc[0] >= lb[2] - 1, (sc, lb, pb))
        check("the Preview pair is thinner than the Live pair", pb[4] < lw, (pb[4], lw))
        mt = [pg.eval_on_selector(s, R)[1] for s in ("#mutebtn", "#pvsolo", "#dev_out", "#pvmute", "#pv_out")]
        check("the Mute buttons, Solo and the speakers share one row", max(mt) - min(mt) < 3, mt)
        check("Preview has Mute and a speaker, no Solo", pg.evaluate("[...pvbtns.children].map(e=>e.id).join()") == "pvmute,pv_out")
        if SHOTS: pg.screenshot(path=f"{SHOTS}/desktop-previewing.png")
        # speaker buttons open the output menus
        pg.click("#dev_out"); pg.wait_for_selector("#cbo:popover-open")
        info = pg.evaluate("({q:!!document.querySelector('#cbo_q'),g:[...document.querySelectorAll('#cbo_l .cbo-g')].map(e=>e.textContent),cur:document.querySelectorAll('#cbo_l .cbo-i.cur').length,exp:dev_out.getAttribute('aria-expanded'),n:document.querySelectorAll('#cbo_l .cbo-i').length})")
        check("Live speaker: menu with a search box, a Wired group, a tick on the current device", info["q"] and info["g"] == ["Wired"] and info["cur"] == 1 and info["exp"] == "true", info)
        check("Live menu has no Bluetooth group (the setting does not exist yet)", "Bluetooth" not in info["g"])
        if SHOTS: pg.screenshot(path=f"{SHOTS}/desktop-live-menu.png")
        pg.keyboard.press("Escape"); time.sleep(0.2)
        check("Esc closes it and puts focus back on the speaker", not pg.is_visible("#cbo") and pg.evaluate("document.activeElement.id") == "dev_out")
        pg.click("#pv_out"); pg.wait_for_selector("#cbo:popover-open")
        info = pg.evaluate("({q:!!document.querySelector('#cbo_q'),cur:document.querySelectorAll('#cbo_l .cbo-i.cur').length,t:[...document.querySelectorAll('#cbo_l .cbo-i')].map(e=>e.textContent)})")
        check("Preview speaker: the same menu, with a tick (This browser is the choice here)", info["q"] and info["cur"] == 1 and "This browser" in info["t"], info)
        pg.keyboard.press("Escape")
        # Preview Mute isolation (browser preview: the page's audio element)
        before = {k: api.state()[k] for k in ("live_volume", "state", "on_top")}
        pg.click("#pvmute"); time.sleep(0.5)
        check("Preview Mute mutes the preview audio only", pg.evaluate("AU.muted===true&&pvmute.classList.contains('muted')&&pvmute.getAttribute('aria-pressed')==='true'&&!mutebtn.classList.contains('muted')&&pvsolo.getAttribute('aria-pressed')==='false'"))
        check("  Live level, state and the Live Mute button are untouched", {k: api.state()[k] for k in before} == before and not pg.evaluate("mutebtn.classList.contains('muted')"))
        check("  the muted preview meter reads empty", pg.evaluate("parseFloat(m_preview_l.style.height)>=99.5"))
        pg.click("#pvmute"); time.sleep(0.3)
        check("Preview Mute toggles back", pg.evaluate("AU.muted===false&&!pvmute.classList.contains('muted')"))
        pg.click("#mutebtn"); time.sleep(0.6)
        check("Live Mute still works on its own and does not mute the preview", api.state()["live_volume"] == "0" and pg.evaluate("AU.muted===false&&!pvmute.classList.contains('muted')"))
        pg.click("#mutebtn"); time.sleep(0.4)
        # ---- the pin and the one-line strip (previewing)
        check("the pin is on by default: a filled, upright pin", pg.evaluate("pinbtn.classList.contains('on')&&pinbtn.getAttribute('aria-pressed')==='true'&&getComputedStyle(pinbtn.querySelector('svg')).fill!=='none'&&getComputedStyle(pinbtn.querySelector('svg')).transform==='none'"))
        check("the strip is hidden while the full panel is in view", pg.evaluate("ms.hidden"))
        pg.evaluate("window.scrollTo(0,1300)"); time.sleep(0.6)
        st = pg.evaluate("({hidden:ms.hidden,top:ms.getBoundingClientRect().top,pos:getComputedStyle(ms).position,text:ms.innerText.replace(/\\s+/g,' ')})")
        check("scrolled: the Live panel shrinks to one line at the top", not st["hidden"] and abs(st["top"]) < 1.5 and st["pos"] == "fixed", st)
        check("the one line has the pin, LIVE pill, title, pause, time and both meter pairs (PRV while previewing)", pg.evaluate("!!ms_pin&&ms_pill.textContent==='LIVE'&&!!ms_name&&!!ms_pp.innerHTML&&!!ms_rem&&!ms_pv.hidden&&ms.querySelectorAll('.hm').length===2&&ms.querySelector('.ml.pvl').textContent==='PRV'"), st)
        check("the pinned panel is not a modal: the page is not locked", pg.evaluate("!document.body.classList.contains('plock')&&PGLOCK.n===0"))
        check("the one line is a single row on a desktop", pg.eval_on_selector("#ms", R)[5] < 60, pg.eval_on_selector("#ms", R))
        if SHOTS: pg.screenshot(path=f"{SHOTS}/desktop-one-line.png")
        pg.click("#ms_pin"); time.sleep(0.3)
        check("unpinning from the strip: outlined tilted pin, the strip goes", pg.evaluate("ms.hidden&&!pinbtn.classList.contains('on')&&pinbtn.classList.contains('off')&&getComputedStyle(pinbtn.querySelector('svg')).transform!=='none'&&getComputedStyle(pinbtn.querySelector('svg')).fill==='none'"))
        pg.evaluate("window.scrollTo(0,0)"); time.sleep(0.3)
        check("the choice is saved in this browser", pg.evaluate("localStorage.getItem('cp_pin')")=="0")
        pg.reload(); pg.wait_for_selector("#setbtn"); time.sleep(0.8)
        check("  and remembered after a reload (still unpinned)", pg.evaluate("!pinbtn.classList.contains('on')"))
        pg.evaluate("document.body.style.minHeight='3200px';window.scrollTo(0,1500)"); time.sleep(0.5)
        check("  unpinned: no strip when scrolled", pg.evaluate("ms.hidden"))
        pg.evaluate("window.scrollTo(0,0)")
        # stop preview: the pair goes
        pg.evaluate("pvCtl('stop')"); time.sleep(0.8)
        check("stopped: the Preview pair goes away", pg.evaluate("pvlvl.hidden&&pvbtns.hidden&&pcap.hidden&&ms_pv.hidden&&!lvl.classList.contains('pvon')"))

        # ---- Settings switches
        pg.evaluate("openSettings()"); pg.wait_for_selector("#settings[open]"); pg.click("#set_tabs [data-tab=look]")
        check("Settings > Look has the three switches with the board's labels", all(pg.inner_text("#settings").find(t) >= 0 for t in ("Pin the Live panel", "Shrink to one line when scrolled", "Remember the pin in this browser")))
        check("the pin switch shows the state (off) and turns it on", not pg.is_checked("#set_pin"))
        pg.evaluate("document.getElementById('set_pin').click()"); time.sleep(0.3)
        check("  switching it on pins the panel, saved", pg.evaluate("PIN===true&&pinbtn.classList.contains('on')&&localStorage.getItem('cp_pin')==='1'"))
        pg.evaluate("document.getElementById('set_pinmini').click()"); time.sleep(0.3)
        check("Shrink off: the whole panel stays at the top (sticky), no strip", pg.evaluate("document.body.classList.contains('pinfull')&&localStorage.getItem('cp_pinmini')==='0'"))
        pg.evaluate("document.getElementById('set_pinmini').click()")
        pg.evaluate("document.getElementById('set_pinkeep').click()"); time.sleep(0.2)
        check("Remember off: the pin is not stored", pg.evaluate("localStorage.getItem('cp_pin')===null&&localStorage.getItem('cp_pinkeep')==='0'"))
        pg.evaluate("document.getElementById('set_pinkeep').click()")
        pg.evaluate("settings.close()")
        check("no page errors (desktop)", not errs, errs)
        c.close()

        # ---- phone
        c = ctx(br, 390, 844, touch=True); pg = c.new_page(); errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto(inst.base_url); pg.wait_for_selector("#setbtn"); time.sleep(1.0)
        pg.evaluate("document.body.style.minHeight='3200px'")
        check("phone: pinned by default", pg.evaluate("PIN===true"))
        tops = pg.evaluate("[cl,fs,plcol,libcol].map(e=>e.getBoundingClientRect().top+scrollY)")
        check("phone order: Live, Cue, Playlists (then the Library)", tops == sorted(tops), tops)
        check("phone: Ducking is collapsed and the Reduction meter is still visible", pg.evaluate("potrow.classList.contains('dkc')&&dk_grm.getBoundingClientRect().height>0"))
        pg.locator(".lt", has_text="long_120s").first.locator(".ib.pv").tap(); pg.wait_for_function("PVCUR.state==='playing'", timeout=8000)
        pg.evaluate("window.scrollTo(0,1400)"); time.sleep(0.7)
        st = pg.evaluate("({hidden:ms.hidden,h:ms.getBoundingClientRect().height,top:ms.getBoundingClientRect().top,stop:getComputedStyle(document.querySelector('#ms .msstop')).display,prog:getComputedStyle(document.querySelector('#ms .msw')).position,pv:!ms_pv.hidden})")
        check("phone: the one-line strip shows after scrolling past the Live panel, with the PRV pair while previewing", not st["hidden"] and abs(st["top"]) < 1.5 and st["pv"], st)
        check("phone: two short rows (pin, LIVE, title, pause / time, meters) with a progress line", st["h"] < 95 and st["stop"] == "none" and st["prog"] == "absolute", st)
        if SHOTS: pg.screenshot(path=f"{SHOTS}/phone-one-line.png")
        pg.evaluate("window.scrollTo(0,0)"); time.sleep(0.5)
        check("phone: back at the top the strip is hidden", pg.evaluate("ms.hidden"))
        sc = pg.eval_on_selector("#cl", "e=>e.scrollWidth<=e.clientWidth+1") and pg.evaluate("document.documentElement.scrollWidth<=innerWidth+1")
        check("phone: the Live card and the page do not overflow sideways with the Preview pair", sc)
        check("no page errors (phone)", not errs, errs)
        c.close()
        br.close()
    print(f"\n{len(FAILS)} failure(s)")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
