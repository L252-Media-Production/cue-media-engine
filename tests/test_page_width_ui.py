#!/usr/bin/env python3
"""Page width (2.8.1, Settings > Look > Appearance): the maximum width of the page on desktop and tablet.
Default Standard (1320 px, as before), presets Wide (1800 px) and Full width (no limit), Custom 800-3840 px clamped
(2.9.1: a range slider in steps of 20 px with the value as text; live while dragging, saved on release or a keyboard step);
saved per browser (cp_pagew, cp_pagew_px), applied by the head script before the first paint, a bad stored value
falls back to Standard, and phone widths are not affected.
    python tests/test_page_width_ui.py      (needs playwright; starts its own disposable player)"""
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from harness import client                       # noqa: E402
from harness.instance import Instance, PROJECT   # noqa: E402

FAILS = []
DESK = dict(viewport={"width": 2560, "height": 1200})


def check(name, ok, info=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"   {info}"))
    if not ok:
        FAILS.append(name)


# what the page shows: the mode, the property, the body's real width, saved values, the Settings row state
STATE = """()=>{const d=document.documentElement,b=document.body.getBoundingClientRect(),g=k=>{try{return localStorage.getItem(k)}catch(e){return 'ERR'}};
 const on=[...document.querySelectorAll('#set_pagew button.on')].map(x=>x.dataset.v);
 return {mode:d.dataset.pagew,prop:d.style.getPropertyValue('--pagew'),maxw:getComputedStyle(document.body).maxWidth,bodyw:Math.round(b.width),
   saved:g('cp_pagew'),px:g('cp_pagew_px'),on,custom:!pw_cw.hidden,reset:!pw_reset.hidden,input:set_pagewpx.value,
   hscroll:d.scrollWidth>innerWidth,row:getComputedStyle(document.querySelector('.pwrow')).display,
   ms:Math.round(document.querySelector('#ms').getBoundingClientRect().width)}}"""
# captured at DOMContentLoaded, before the first paint of the body content
EARLY = "document.addEventListener('DOMContentLoaded',()=>{window.__pw0=document.documentElement.style.getPropertyValue('--pagew')});"


def page(br, inst, store=None, kw=DESK, extra=""):
    c = br.new_context(**kw)
    init = "localStorage.setItem('cp_tour','1');"
    for k, v in (store or {}).items():
        init += f"localStorage.setItem('{k}','{v}');"
    c.add_init_script(init + extra + EARLY)
    pg = c.new_page(); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(inst.base_url); pg.wait_for_selector("#lists li.t")
    return c, pg, errs


def main():
    from playwright.sync_api import sync_playwright
    with Instance(wav_only=True, project_dir=os.environ.get("TI_PROJECT") or PROJECT) as inst, sync_playwright() as p:
        api = client.Api(inst.base_url, osc_port=inst.osc_port)
        api.post("/api/playlists", {"name": "T"}); api.post("/api/playlists/0/add", {"files": ["long_120s.wav", "tone_a.wav"]})
        br = p.chromium.launch()

        # 1. default
        c, pg, errs = page(br, inst)
        d = pg.evaluate(STATE)
        check("default: mode is Standard", d["mode"] == "standard", d)
        check("default: --pagew is today's 1320px", d["prop"] == "1320px" and d["maxw"] == "1320px" and d["bodyw"] == 1320, d)
        check("default: set before the first paint", pg.evaluate("window.__pw0") == "1320px")
        check("default: Standard button is on, Custom field and Reset hidden", d["on"] == ["standard"] and not d["custom"] and not d["reset"], d)
        check("default: nothing saved until a change", d["saved"] is None, d)

        # 2. each preset sets the property, saves, survives a reload and applies before the first paint
        pg.evaluate("openSettings();setTab('look')")
        for mode, prop, width in (("wide", "1800px", 1800), ("full", "100vw", 2560), ("standard", "1320px", 1320)):
            pg.click(f"#set_pagew button[data-v={mode}]")
            d = pg.evaluate(STATE)
            check(f"{mode}: --pagew is {prop} and the page is {width} px wide at once", d["mode"] == mode and d["prop"] == prop and d["bodyw"] == width, d)
            check(f"{mode}: saved, button on, Reset shown only when not Standard", d["saved"] == mode and d["on"] == [mode] and d["reset"] == (mode != "standard"), d)
            check(f"{mode}: no horizontal scroll", not d["hscroll"], d)
            pg.evaluate("settings.close()"); pg.reload(); pg.wait_for_selector("#lists li.t")
            d = pg.evaluate(STATE)
            check(f"{mode}: kept after a reload, before the first paint", d["mode"] == mode and pg.evaluate("window.__pw0") == prop and d["bodyw"] == width, d)
            pg.evaluate("openSettings();setTab('look')")

        # 3. custom (2.9.1: a range slider 800-3840 px in steps of 20, the value as text beside it): live while dragging, saved on release
        #    or on a keyboard step, clamped; Reset goes back to Standard
        pg.click("#set_pagew button[data-v=custom]")
        d = pg.evaluate(STATE)
        check("custom: shows the slider with the remembered value (1600) and its text", d["custom"] and d["input"] == "1600" and d["prop"] == "1600px"
              and pg.evaluate("pw_val.textContent") == "1,600 px", d)
        a = pg.evaluate("()=>{const s=set_pagewpx;return {type:s.type,min:s.min,max:s.max,step:s.step,lbl:s.labels.length?s.labels[0].textContent:'',"
                        "lblvis:s.labels.length&&s.labels[0].getBoundingClientRect().width>0,vt:s.getAttribute('aria-valuetext')}}")
        check("slider: range 800-3840, step 20", a["type"] == "range" and a["min"] == "800" and a["max"] == "3840" and a["step"] == "20", a)
        check("slider: visible label, accessible name and value text", a["lbl"] == "Custom width" and a["lblvis"] and a["vt"] == "1,600 px", a)
        snap = pg.accessibility.snapshot(root=pg.query_selector("#pw_cw")) if hasattr(pg, "accessibility") else None
        if snap is not None:
            names = []
            def walk(n):
                names.append((n.get("role"), n.get("name")))
                for k in n.get("children", []) or []:
                    walk(k)
            walk(snap)
            check("slider: the accessibility tree has a slider named Custom width", ("slider", "Custom width") in names, names)
        # live while dragging: a real mouse drag, checked before and after the release
        box = pg.locator("#set_pagewpx").bounding_box()
        y = box["y"] + box["height"] / 2
        pg.mouse.move(box["x"] + box["width"] * (1600 - 800) / 3040, y); pg.mouse.down()
        pg.mouse.move(box["x"] + box["width"] * 0.6, y, steps=6)
        d = pg.evaluate(STATE); mid = d["prop"]
        check("drag: the page follows while the thumb is held, nothing saved yet", d["prop"] != "1600px" and d["bodyw"] == min(2560, int(d["prop"][:-2])) and d["px"] == "1600"
              and pg.evaluate("pw_val.textContent") == f"{int(d['prop'][:-2]):,} px", d)
        pg.mouse.up()
        d = pg.evaluate(STATE)
        check("drag: saved on release", d["px"] == mid[:-2] and d["saved"] == "custom" and d["prop"] == mid and int(mid[:-2]) % 20 == 0, (mid, d))
        # keyboard: arrows step by 20 and save, Home / End go to the ends
        pg.evaluate("pagewPx('2000')")
        pg.wait_for_selector("#set_pagewpx", state="visible"); pg.focus("#set_pagewpx")
        for key, want in (("ArrowRight", 2020), ("ArrowRight", 2040), ("ArrowLeft", 2020), ("ArrowUp", 2040), ("ArrowDown", 2020), ("Home", 800), ("End", 3840)):
            pg.keyboard.press(key)
            d = pg.evaluate(STATE)
            check(f"keyboard {key}: {want} px, live and saved", d["prop"] == f"{want}px" and d["px"] == str(want) and d["input"] == str(want)
                  and pg.evaluate("pw_val.textContent") == f"{want:,} px", d)
        # the save function still clamps (a value from a layout or a script)
        for typed, want in (("500", 800), ("5000", 3840), ("1999.6", 2000), ("2400", 2400)):
            pg.evaluate(f"pagewPx('{typed}')")
            d = pg.evaluate(STATE)
            check(f"custom: {typed} is clamped to {want}", d["prop"] == f"{want}px" and d["px"] == str(want) and d["input"] == str(want) and d["saved"] == "custom", d)
        pg.evaluate("pagewPx('')")
        d = pg.evaluate(STATE)
        check("custom: an empty value keeps the last value", d["prop"] == "2400px" and d["px"] == "2400" and d["input"] == "2400", d)
        check("custom: the Appearance summary names it", "2400 px page" in pg.evaluate("sum_appearance.textContent"))
        pg.click("#pw_reset")
        d = pg.evaluate(STATE)
        check("Reset to Standard: back to 1320px and saved", d["mode"] == "standard" and d["prop"] == "1320px" and d["saved"] == "standard" and not d["reset"], d)
        check("no page errors (main page)", not errs, errs)
        c.close()

        # 4. bad stored values fall back to Standard (custom px out of range is clamped)
        for label, store, extra, mode, prop in (
                ("unknown mode", {"cp_pagew": "huge"}, "", "standard", "1320px"),
                ("custom with a non-number", {"cp_pagew": "custom", "cp_pagew_px": "abc"}, "", "standard", "1320px"),
                ("custom far too large", {"cp_pagew": "custom", "cp_pagew_px": "99999"}, "", "custom", "3840px"),
                ("custom too small", {"cp_pagew": "custom", "cp_pagew_px": "10"}, "", "custom", "800px"),
                ("storage throws", {"cp_pagew": "full"}, "Storage.prototype.getItem=function(){throw new Error('blocked')};", "standard", "1320px")):
            c, pg, errs = page(br, inst, store, extra=extra)
            d = pg.evaluate("()=>({mode:document.documentElement.dataset.pagew,prop:document.documentElement.style.getPropertyValue('--pagew')})")
            check(f"stored {label}: {mode} / {prop}", d["mode"] == mode and d["prop"] == prop and pg.evaluate("window.__pw0") == prop, d)
            check(f"stored {label}: no page errors", not errs, errs)
            c.close()

        # 4b. 2.9.1: a stored Custom value off the 20 px steps or out of range is honoured (clamped) and shown at the nearest step; the stored
        #     value is not rewritten until the slider is moved
        for stored, applied, shown in (("1610", 1610, "1620"), ("99999", 3840, "3840"), ("10", 800, "800"), ("2001", 2001, "2000")):
            c, pg, errs = page(br, inst, {"cp_pagew": "custom", "cp_pagew_px": stored})
            pg.evaluate("openSettings();setTab('look')")
            d = pg.evaluate(STATE)
            check(f"stored px {stored}: page {applied} px, slider at {shown}, text {applied:,} px, storage untouched",
                  d["prop"] == f"{applied}px" and d["input"] == shown and pg.evaluate("pw_val.textContent") == f"{applied:,} px" and d["px"] == stored, d)
            pg.evaluate("settings.close()"); pg.evaluate("openSettings();setTab('look');syncLook()")
            check(f"stored px {stored}: still untouched after reopening Settings", pg.evaluate(STATE)["px"] == stored)
            pg.wait_for_selector("#set_pagewpx", state="visible"); pg.wait_for_timeout(150)
            pg.focus("#set_pagewpx"); pg.keyboard.press("ArrowLeft" if shown != "800" else "ArrowRight")
            d = pg.evaluate(STATE)
            want = int(shown) - 20 if shown != "800" else 820
            check(f"stored px {stored}: moving the slider saves the stepped value {want}", d["px"] == str(want) and d["prop"] == f"{want}px", d)
            check(f"stored px {stored}: no page errors", not errs, errs)
            c.close()

        # 5. phone widths: every setting gives the same page; the Settings row is hidden
        for tag, kw in (("phone", dict(viewport={"width": 420, "height": 900})),
                        ("touch", dict(viewport={"width": 430, "height": 932}, has_touch=True, is_mobile=True))):
            seen = {}
            for store in ({}, {"cp_pagew": "wide"}, {"cp_pagew": "full"}, {"cp_pagew": "custom", "cp_pagew_px": "800"}):
                c, pg, errs = page(br, inst, store, kw=kw)
                d = pg.evaluate(STATE)
                seen[store.get("cp_pagew", "standard")] = (d["maxw"], d["bodyw"], d["ms"], d["hscroll"])
                check(f"{tag} {store.get('cp_pagew', 'standard')}: Page width row hidden, no page errors", d["row"] == "none" and not errs, (d, errs))
                c.close()
            check(f"{tag}: the setting has no effect (body max-width, width, strip, scroll identical)", len(set(seen.values())) == 1 and seen["standard"][0] == "1320px", seen)

        # 6. inner limits at Full width (that they do not bind at Standard was measured by hand: see CHANGELOG 2.8.1)
        c, pg, errs = page(br, inst, {"cp_pagew": "full"})
        pg.evaluate("document.querySelector('#inpc button').click()"); pg.wait_for_timeout(300)
        d = pg.evaluate("()=>{const w=s=>document.querySelector(s).getBoundingClientRect().width,rem=parseFloat(getComputedStyle(document.documentElement).fontSize);"
                        "return {dev:w('#inpc .inpdev'),open:w('#inpc .inpbody')>0,gi:w('#inpc .inpg input'),max1:60*rem,max2:72*rem}}")
        check("full: Device menu and gain slider capped", d["open"] and d["dev"] <= d["max1"] + 1 and d["gi"] <= d["max2"] + 1, d)
        c.close()
        br.close()
    print(f"\n{'FAILED: ' + str(len(FAILS)) if FAILS else 'ALL PASSED'}")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
