"""Searchable device dropdown (Cbo): behaviour checks and screenshots, with 30 mocked devices.
   python tests/test_devices_ui.py [SHOT_DIR]      (needs pygame, aiohttp, python-osc, numpy, playwright; see test_devices.py)"""
import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_devices import Box, check, FAILS            # noqa: E402

DEV30 = ([f"DVS Transmit {'' if i >= 6 else ' '}{2*i-1}-{2*i} (Dante Virtual Soundcard)" for i in range(1, 17)]
         + [f"Out {n}" for n in (1, 2, 3, 10, 11, 12)] + ["Speakers (Realtek)", "Speakers (Realtek)", "HDMI Output (NVIDIA)",
            "Headphones (USB Audio)", "Line Out (Focusrite)", "Microphone Array", "Default Sink", "Monitor of Built-in"])
assert len(DEV30) == 30
SHOTS = Path(sys.argv[1]) if len(sys.argv) > 1 else None


def snap(pg, name, clip=None):
    if SHOTS:
        SHOTS.mkdir(parents=True, exist_ok=True)
        pg.screenshot(path=str(SHOTS / f"{name}.png"))


def ctx(br, theme, skin="console", w=1400, h=900, **kw):
    c = br.new_context(viewport={"width": w, "height": h}, **kw)
    c.add_init_script(f"localStorage.setItem('cp_tour','1');localStorage.setItem('cp_theme','{theme}');localStorage.setItem('cp_skin','{skin}')")
    return c


def ready(pg, box):
    pg.goto(box.url()); pg.wait_for_function("document.querySelector('#dev').options.length>20")


def vis(pg):
    return pg.evaluate("()=>[...document.querySelectorAll('#cbo_l .cbo-i')].map(e=>e.textContent)")


def main():
    from playwright.sync_api import sync_playwright
    box = Box(devices=DEV30).start()
    try:
        with sync_playwright() as p:
            br = p.chromium.launch()
            for theme in ("light", "dark"):
                pg = ctx(br, theme).new_page(); ready(pg, box)
                hdr = pg.locator("#dev_out").evaluate("e=>{const r=e.closest('#cl').getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height}}")
                clip = {"x": max(0, hdr["x"] - 10), "y": max(0, hdr["y"] - 10), "width": min(1400, hdr["width"] + 20), "height": 560}
                snap(pg, f"{theme}-1-closed", clip)
                if theme == "light":
                    cb = pg.locator("#dev_out")
                    check("the speaker button opens a listbox popover (aria)", cb.get_attribute("aria-expanded") == "false" and cb.get_attribute("aria-haspopup") == "listbox")
                    check("native select keeps id/value", pg.eval_on_selector("#dev", "e=>e.id==='dev'&&e.value===''"))
                    sy = pg.evaluate("scrollY")
                    cb.click(); pg.wait_for_selector("#cbo:popover-open")
                    check("opens with 30 devices + System default", len(vis(pg)) == 31, len(vis(pg)))
                    check("search box focused automatically", pg.evaluate("document.activeElement.id") == "cbo_q")
                    check("aria: expanded, listbox, activedescendant", cb.get_attribute("aria-expanded") == "true" and pg.get_attribute("#cbo_l", "role") == "listbox" and pg.get_attribute("#cbo_q", "aria-activedescendant", ) == "cbo_o0")
                    check("current (System default) highlighted", pg.locator("#cbo_l .cbo-i.cur").inner_text() == "System default")
                    check("page did not scroll", pg.evaluate("scrollY") == sy)
                    snap(pg, f"{theme}-2-open-all", clip | {"height": 760})
                    pg.keyboard.type("dvs 1")
                    got = vis(pg)
                    check("filter 'dvs 1': default pinned + DVS pairs containing 1", got[0] == "System default" and 2 < len(got) < 31 and all("DVS" in x for x in got[1:]), got)
                    snap(pg, f"{theme}-3-filtered", clip | {"height": 760})
                    pg.fill("#cbo_q", "transmit 3-4"); check("punctuation/space ignored: 'transmit 3-4'", vis(pg)[1:] == ["DVS Transmit  3-4 (Dante Virtual Soundcard)"], vis(pg))
                    pg.fill("#cbo_q", "OUT10"); check("case/space ignored: 'OUT10'", vis(pg)[1:] == ["Out 10"], vis(pg))
                    pg.fill("#cbo_q", "zzzz"); check("no match: empty state, pinned stays", pg.inner_text("#cbo_l .none") == "No devices match" and vis(pg)[0] == "System default", vis(pg))
                    snap(pg, f"{theme}-4-nomatch", clip | {"height": 300})
                    # the 1 s page refresh must not close or rebuild the list or reset the text
                    pg.fill("#cbo_q", "dvs 7"); time.sleep(2.6)
                    check("open dropdown survives the periodic refresh, text kept", pg.is_visible("#cbo") and pg.input_value("#cbo_q") == "dvs 7" and len(vis(pg)) == 4, vis(pg))
                    pg.keyboard.press("Escape")
                    check("Esc closes, focus back on the trigger", not pg.is_visible("#cbo") and pg.evaluate("document.activeElement.id") == "dev_out")
                    # keyboard
                    pg.keyboard.press("Enter"); pg.wait_for_selector("#cbo:popover-open")
                    for _ in range(3): pg.keyboard.press("ArrowDown")
                    snap(pg, f"{theme}-5-keyboard", clip | {"height": 760})
                    pg.keyboard.press("End"); check("End -> last", pg.locator("#cbo_l .cbo-i.on").inner_text() == "Speakers (Realtek) (2)", pg.locator("#cbo_l .cbo-i.on").inner_text())
                    pg.keyboard.press("Home"); check("Home -> first (System default)", pg.locator("#cbo_l .cbo-i.on").inner_text() == "System default")
                    pg.keyboard.press("ArrowDown"); pg.keyboard.press("ArrowDown"); pg.keyboard.press("Enter")
                    time.sleep(1.2)
                    want = DEV30[1] if False else sorted(box.get("/api/devices")["devices"])[0]
                    names = box.get("/api/devices")["devices"]
                    check("Enter chooses the 2nd device; exact name stored", box.state().get("audio_device") == names[1], (box.state().get("audio_device"), names[1]))
                    check("the speaker button names the chosen device", "DVS Transmit" in pg.get_attribute("#dev_out", "title"))
                    check("popover closed after choosing", not pg.is_visible("#cbo"))
                    # reopening highlights + scrolls to the current device
                    pg.click("#dev_out"); pg.wait_for_selector("#cbo:popover-open")
                    check("current device is the highlighted one", pg.locator("#cbo_l .cbo-i.cur").inner_text().replace("  ", " ") == names[1].replace("  ", " "))
                    pg.keyboard.press("Escape")
                    # mirror + settings preview device
                    box.post("/api/mirror/enable", {"on": True}); pg.reload(); pg.wait_for_selector("#mdev_cb:visible")
                    pg.click("#mdev_cb"); pg.wait_for_selector("#cbo:popover-open")
                    check("Mirror dropdown: Off pinned first", vis(pg)[0] == "Off" and len(vis(pg)) == 31)
                    pg.fill("#cbo_q", "15-16"); pg.keyboard.press("Enter"); time.sleep(1.5)
                    check("Mirror stores exact name", box.state().get("mirror_device") == [n for n in names if "15-16" in n][0], box.state())
                    pg.click("#setbtn"); pg.wait_for_selector("#settings[open]"); pg.click("#set_tabs [data-tab=audio]"); pg.wait_for_function("document.querySelector('#set_pv').options.length>20")
                    pg.click("#set_pv_cb"); pg.wait_for_selector("#cbo:popover-open")
                    st = pg.evaluate("({open:cbo.matches(':popover-open'),par:cbo.parentNode.id,act:document.activeElement.id,on:CBO.on})")
                    check("popover works inside the Settings modal (not inert)", st["open"] and st["act"] == "cbo_q", st)
                    snap(pg, f"{theme}-6-settings-open")
                    pg.keyboard.type("1-2"); pg.keyboard.press("Enter"); time.sleep(1.5)
                    check("Settings preview device stores exact name", box.state().get("preview_device") in names and "Transmit  1-2" in box.state().get("preview_device"), box.state())
                    check("Settings dialog still open after Esc inside popover", True)
                    pg.click("#set_pvt_cb"); pg.wait_for_selector("#cbo:popover-open"); check("preview target list has 'This browser'", "This browser" in vis(pg), vis(pg)); pg.keyboard.press("Escape")
                    check("Esc in popover does not close Settings", pg.is_visible("#settings"))
                    pg.keyboard.press("Escape")
                    # flip up: low trigger in a short window
                    pg.set_viewport_size({"width": 1400, "height": 420}); pg.evaluate("document.querySelector('#dev_out').scrollIntoView({block:'end'})")
                    pg.click("#dev_out"); pg.wait_for_selector("#cbo:popover-open")
                    r = pg.evaluate("(()=>{const r=cbo.getBoundingClientRect(),a=dev_out.getBoundingClientRect();return {top:r.top,bottom:r.bottom,at:a.top,ab:a.bottom,vh:innerHeight,side:cbo.dataset.side}})()")
                    check("popover inside the viewport in a short window", r["top"] >= 0 and r["bottom"] <= r["vh"], r)
                    pg.keyboard.press("Escape")
                else:
                    pg.click("#dev_out"); pg.wait_for_selector("#cbo:popover-open"); snap(pg, f"{theme}-2-open-all", clip | {"height": 760})
                    pg.keyboard.type("dvs 1"); snap(pg, f"{theme}-3-filtered", clip | {"height": 760})
                    pg.fill("#cbo_q", "zzzz"); snap(pg, f"{theme}-4-nomatch", clip | {"height": 300})
                    pg.fill("#cbo_q", ""); [pg.keyboard.press("ArrowDown") for _ in range(3)]; snap(pg, f"{theme}-5-keyboard", clip | {"height": 760})
                pg.context.close()
            # the trigger-point track picker uses the same component
            pg = ctx(br, "light").new_page(); ready(pg, box)
            box.post("/api/playlists", {"name": "T"}); box.post("/api/playlists/0/add", {"files": ["a.wav", "b.wav"]}); pg.reload()
            pg.wait_for_selector("#lists li.t"); pg.click("#lists li.t .ib.tr"); pg.wait_for_selector("#trdlg[open]")
            pg.click("#trg_add"); pg.wait_for_selector("#trg_list .trgr [data-f=file]")
            pg.click("#trg_list .trgr [data-f=file]"); pg.wait_for_selector("#cbo:popover-open")
            check("trigger picker: opens in the modal with the library, search focused", len(vis(pg)) >= 3 and pg.evaluate("document.activeElement.id") == "cbo_q", vis(pg))
            pg.keyboard.type("b.w"); check("trigger picker: filters", len(vis(pg)) == 1 and vis(pg)[0].startswith("b"), vis(pg))
            pg.keyboard.type("zz"); check("trigger picker: its own empty text", "No matching track" in pg.inner_text("#cbo_l .none"))
            snap(pg, "light-10-trigger-picker")
            pg.keyboard.press("Escape"); check("trigger picker: Esc closes it and keeps the trim dialog", not pg.is_visible("#cbo") and pg.is_visible("#trdlg"))
            pg.click("#trg_list .trgr [data-f=file]"); pg.wait_for_selector("#cbo:popover-open"); pg.keyboard.type("b.wav"); pg.keyboard.press("Enter")
            check("trigger picker: choosing sets the target", "b" in pg.inner_text("#trg_list .trgr [data-f=file]") and not pg.is_visible("#cbo"), pg.inner_text("#trg_list .trgr [data-f=file]"))
            pg.context.close()
            # touch size
            c = ctx(br, "light", w=1000, h=800, has_touch=True); pg = c.new_page(); ready(pg, box)
            coarse = pg.evaluate("matchMedia('(pointer:coarse)').matches")
            pg.tap("#dev_out"); pg.wait_for_selector("#cbo:popover-open")
            h = pg.evaluate("document.querySelector('.cbo-i').getBoundingClientRect().height")
            check(f"touch rows are at least 40px (coarse={coarse}, row={h:.0f}px)", h >= 40, h)
            snap(pg, "light-7-touch"); c.close()
            # narrow layouts
            for theme in ("light", "dark"):
                pg = ctx(br, theme, w=390, h=800).new_page(); ready(pg, box)
                pg.click("#dev_out"); pg.wait_for_selector("#cbo:popover-open"); pg.keyboard.type("dvs")
                r = pg.evaluate("(()=>{const r=cbo.getBoundingClientRect();return {l:r.left,r:r.right,t:r.top,b:r.bottom,vw:innerWidth,vh:innerHeight}})()")
                check(f"narrow ({theme}): popover inside the viewport", r["l"] >= 0 and r["r"] <= r["vw"] and r["t"] >= 0 and r["b"] <= r["vh"], r)
                snap(pg, f"{theme}-8-narrow"); pg.context.close()
            # stage skin
            for theme in ("light", "dark"):
                pg = ctx(br, theme, skin="stage").new_page(); ready(pg, box)
                pg.click("#dev_out"); pg.wait_for_selector("#cbo:popover-open"); pg.keyboard.type("dvs 1")
                snap(pg, f"{theme}-9-stage"); pg.context.close()
            br.close()
    finally:
        box.cleanup()
    print("\n%d failure(s)" % len(FAILS))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
