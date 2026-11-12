#!/usr/bin/env python3
"""Live input card (Duck only), desktop only: chip states (No input / No signal / Signal present), the level meter and the threshold marker, Armed, Duck now, Solo,
the device and channel menus, the Settings > Audio rows, keyboard access, accessible names and visible focus rings. 3 skins x 2 themes at 1400 px.
The capture device is SIMULATED (CP_TEST_INPUT feed, see tests/api/test_live_input.py); the page, the API and the helper are real.
    python tests/test_input_card_ui.py      (needs playwright; starts its own disposable player)"""
import json, os, sys, tempfile, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "api"))
from harness import client                       # noqa: E402
from harness.instance import Instance, PROJECT   # noqa: E402
from test_live_input import make_env, set_feed   # noqa: E402

FAILS = []


def check(name, ok, info=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"   {info}"))
    if not ok:
        FAILS.append(name)


# outline of the element that has keyboard focus (a checkbox is drawn by its sibling <i>)
RING = """()=>{let e=document.activeElement;if(!e)return null;const t=e.matches('input[type=checkbox]')?e.nextElementSibling:e;const cs=getComputedStyle(t);
  const bx=getComputedStyle(e);return {id:e.id,tag:e.tagName,outline:cs.outlineStyle,w:parseFloat(cs.outlineWidth)||0,shadow:cs.boxShadow,btnOutline:bx.outlineStyle,
  name:(e.getAttribute('aria-label')||e.getAttribute('title')||e.textContent||'').trim().slice(0,40)}}"""


def focus_chain(pg, ids, limit=40):
    """Press Tab until each id has had focus; return {id: ring info}."""
    got = {}
    pg.focus("#inp_t")
    got["inp_t"] = pg.evaluate(RING)
    for _ in range(limit):
        pg.keyboard.press("Tab")
        r = pg.evaluate(RING)
        if r and r["id"] in ids and r["id"] not in got:
            got[r["id"]] = r
        if len(got) == len(ids):
            break
    return got


def main():
    from playwright.sync_api import sync_playwright
    d, env = make_env()
    set_feed(d, state="gone", db=-90.0, channels=2, reason="the input device \"Fake input\" was not found (unplugged, or not running)")
    cfg = {"input_device": "Fake input", "input_armed": True, "preview_device": "Mock out 1", "duck_threshold_db": -30, "duck_hold": False, "duck_release_ms": 200}
    with Instance(wav_only=True, extra_config=cfg, extra_env=env) as inst, sync_playwright() as p:
        api = client.Api(inst.base_url, osc_port=inst.osc_port)
        api.cmd("rescan")
        api.post("/api/playlists", {"name": "T"})
        api.post("/api/playlists/0/add", {"files": ["long_120s.wav"]})
        time.sleep(1.5)
        br = p.chromium.launch()
        info = lambda: api.get("/api/input").json      # noqa: E731
        for skin in ("console", "studio", "stage"):
            for theme in ("dark", "light"):
                tag = f"{skin}/{theme}"
                c = br.new_context(viewport={"width": 1400, "height": 1000})
                c.add_init_script(f"localStorage.setItem('cp_tour','1');localStorage.setItem('cp_theme','{theme}');localStorage.setItem('cp_skin','{skin}');localStorage.removeItem('cp_inp')")
                pg = c.new_page(); errs = []
                pg.on("pageerror", lambda e: errs.append(str(e)))
                api.cmd("stopall"); api.cmd("input/armed/on"); api.cmd("input/ducknow/off"); api.post("/api/input/solo", {"on": False})
                set_feed(d, state="gone", db=-90.0, channels=2, reason="the input device \"Fake input\" was not found (unplugged, or not running)")
                time.sleep(2.6)
                pg.goto(inst.base_url); pg.wait_for_selector("#inpc")
                pg.wait_for_function("document.getElementById('inp_chip').textContent==='No input'", timeout=8000)
                # --- collapsed by default: the header shows the controls, the setup is hidden
                check(f"{tag}: collapsed by default, header controls visible (the Armed switch is not on the card any more; arming is in the Cue container)", pg.is_visible("#inp_chip") and pg.is_hidden("label.inparm") and pg.is_visible("#inp_dn") and pg.is_visible("#inp_so") and not pg.is_visible("#inp_dev_cb"))
                # --- No input, plain reason, Duck now not available
                pg.click("#inp_t")
                check(f"{tag}: opens", pg.is_visible("#inp_dev_cb") and pg.is_visible("#inp_ch_cb") and pg.is_visible("#inp_gain") and pg.get_attribute("#inp_t", "aria-expanded") == "true")
                check(f"{tag}: chip says No input with the reason", pg.inner_text("#inp_chip") == "No input" and "not found" in pg.inner_text("#inp_why"), pg.inner_text("#inp_why"))
                check(f"{tag}: Duck now stays available without input", not pg.is_disabled("#inp_dn"))
                pg.click("#inp_dn"); time.sleep(0.8)
                check(f"{tag}: Duck now works with no input, header says so", info()["duck_now"] is True and "DUCK NOW" in pg.inner_text("#inp_sum") and pg.get_attribute("#inp_dn", "aria-pressed") == "true", pg.inner_text("#inp_sum"))
                pg.click("#inp_dn"); time.sleep(0.5)
                check(f"{tag}: the card is its own block right after the Cue/Preview row, not inside the Cue block", pg.evaluate("()=>!document.querySelector('#fs #inpc')&&document.getElementById('cuerow').nextElementSibling.id==='inpc'"))
                check(f"{tag}: 'Duck only' is plain text, no selector", pg.inner_text(".inpmode") == "Duck only" and pg.locator(".inpmode select, .inpmode button, .inpmode input").count() == 0)
                # --- the device comes: No signal, then Signal present with the meter and the threshold marker
                set_feed(d, state="run", db=-90.0, channels=2)
                pg.wait_for_function("document.getElementById('inp_chip').textContent==='No signal'", timeout=15000)
                set_feed(d, state="run", db=-40.0, channels=2)
                pg.wait_for_function("document.getElementById('inp_chip').textContent==='Signal present'", timeout=8000)
                time.sleep(0.5)
                m = pg.evaluate("()=>{const m=document.getElementById('inp_m').getBoundingClientRect(),l=document.getElementById('inp_lv').getBoundingClientRect(),t=document.getElementById('inp_th').getBoundingClientRect();"
                                "return {w:m.width,fill:l.width/m.width*100,mark:(t.left+t.width/2-m.left)/m.width*100,now:+document.getElementById('inp_m').getAttribute('aria-valuenow'),cls:document.getElementById('inp_m').className}}")
                check(f"{tag}: meter fill = (-40+60)/60 = 33 %", abs(m["fill"] - 100 / 3) < 3, m)
                check(f"{tag}: threshold marker at the ducking threshold (-30 dB = 50 %)", abs(m["mark"] - 50) < 1.5, m)
                check(f"{tag}: meter value for assistive tech", abs(m["now"] + 40) <= 1 and "over" not in m["cls"], m)
                # --- over the threshold: the meter turns, the reduction meter shows the input's reduction
                api.cmd("0/0")
                set_feed(d, state="run", db=-15.0, channels=2)
                pg.wait_for_function("document.getElementById('inp_m').classList.contains('over')", timeout=8000)
                pg.wait_for_function("parseFloat(document.getElementById('dk_grv').textContent.replace('−','-'))<-5", timeout=8000)
                check(f"{tag}: the Reduction meter shows the input's reduction", pg.evaluate("()=>document.getElementById('dk_grm').classList.contains('duck')"))
                check(f"{tag}: header says ducking", "ducking" in pg.inner_text("#inp_sum"), pg.inner_text("#inp_sum"))
                # --- Armed: click, then keyboard
                cue_sw = pg.locator("#cia_sw, #cue_pill_sw").locator("visible=true").first       # the one place to arm: the Cue container (status line or header pill)
                cue_sw.click()
                time.sleep(0.5)
                check(f"{tag}: Armed off (Cue container click); the card's hidden switch and read-only text follow", info()["armed"] is False and not pg.is_checked("#inp_arm") and pg.inner_text("#inp_sum") == "not armed", pg.inner_text("#inp_sum"))
                pg.wait_for_function("!document.getElementById('inp_sum').textContent.startsWith('ducking')", timeout=8000)
                cue_sw.focus(); pg.keyboard.press("Space"); time.sleep(0.5)
                check(f"{tag}: Armed on (Cue container, keyboard Space)", info()["armed"] is True and pg.is_checked("#inp_arm"))
                # --- Duck now
                set_feed(d, state="run", db=-90.0, channels=2)
                time.sleep(1.2)
                pg.focus("#inp_dn"); pg.keyboard.press("Enter"); time.sleep(0.5)
                check(f"{tag}: Duck now on (keyboard Enter), pressed state", info()["duck_now"] is True and pg.get_attribute("#inp_dn", "aria-pressed") == "true")
                pg.wait_for_function("document.getElementById('inp_sum').textContent.startsWith('DUCK NOW')", timeout=6000)
                pg.click("#inp_dn"); time.sleep(0.5)
                check(f"{tag}: Duck now off (click)", info()["duck_now"] is False and pg.get_attribute("#inp_dn", "aria-pressed") == "false")
                # --- Solo
                pg.click("#inp_so"); time.sleep(0.8)
                check(f"{tag}: Solo on", info()["solo"] is True and pg.get_attribute("#inp_so", "aria-pressed") == "true")
                pg.focus("#inp_so"); pg.keyboard.press("Space"); time.sleep(0.5)
                check(f"{tag}: Solo off (keyboard)", info()["solo"] is False and pg.get_attribute("#inp_so", "aria-pressed") == "false")
                # --- gain slider and channel
                pg.focus("#inp_gain"); pg.keyboard.press("End"); time.sleep(0.6)
                check(f"{tag}: gain slider saves (End = +24 dB)", info()["gain_db"] == 24.0 and "+24" in pg.inner_text("#inp_gain_v"), info())
                pg.focus("#inp_gain"); pg.keyboard.press("Home"); time.sleep(0.6)
                check(f"{tag}: gain slider Home = -12 dB", info()["gain_db"] == -12.0, info())
                pg.fill("#inp_gain", "0") if False else pg.evaluate("()=>{const e=document.getElementById('inp_gain');e.value=0;e.dispatchEvent(new Event('input'));e.dispatchEvent(new Event('change'))}")
                time.sleep(0.5)
                pg.click("#inp_ch_cb"); pg.click("#cbo_l [role=option]:has-text('Channel 2 (mono)')"); time.sleep(1.0)
                check(f"{tag}: channel select saves", info()["channel_list"] == [2], info())
                pg.click("#inp_ch_cb"); pg.click("#cbo_l [role=option]:has-text('Channel 1 (mono)')"); time.sleep(0.8)
                # --- the device menu: searchable, tick on the current device, inside the viewport
                pg.click("#inp_dev_cb")
                pg.wait_for_selector("#cbo:popover-open, #cbo[open], #cbo_l [role=option]")
                opts = pg.locator("#cbo_l [role=option]")
                names = opts.all_inner_texts()
                cur = pg.evaluate("()=>[...document.querySelectorAll('#cbo_l [role=option]')].filter(o=>o.getAttribute('aria-selected')==='true').map(o=>o.textContent.trim())")
                box = pg.evaluate("()=>{const r=document.getElementById('cbo').getBoundingClientRect();return {l:r.left,t:r.top,r:r.right,b:r.bottom,w:innerWidth,h:innerHeight}}")
                check(f"{tag}: device menu lists the input devices, current one selected", any("Fake input" in n for n in names) and any("Fake input" in c for c in cur) and any("Dante" in n for n in names), (names, cur))
                check(f"{tag}: device menu inside the viewport", box["l"] >= 0 and box["t"] >= 0 and box["r"] <= box["w"] and box["b"] <= box["h"], box)
                pg.fill("#cbo_q", "dante"); time.sleep(0.2)
                t = pg.locator("#cbo_l [role=option]").all_inner_texts()
                check(f"{tag}: device menu search (the pinned 'No input' stays)", t == ["No input", "Dante Virtual Soundcard"], t)
                pg.keyboard.press("Escape")
                # --- keyboard: every control reachable, named, with a visible focus ring
                ids = ["inp_t", "inp_dn", "inp_so", "inp_dev_cb", "inp_ch_cb", "inp_gain"]
                pg.wait_for_function("document.getElementById('inp_chip').textContent!=='No input'", timeout=15000)       # a channel change restarts the capture helper
                chain = focus_chain(pg, ids)
                check(f"{tag}: Tab reaches every control", set(chain) == set(ids), sorted(set(ids) - set(chain)))
                bad = [k for k, v in chain.items() if v["outline"] in ("none", "") or v["w"] < 1.5]
                check(f"{tag}: visible focus ring on every control", not bad, {k: chain[k] for k in bad})
                bad = [k for k, v in chain.items() if not v["name"]]
                check(f"{tag}: every control has an accessible name", not bad, bad)
                check(f"{tag}: chip is a live status, meter has a role", pg.get_attribute("#inp_chip", "role") == "status" and pg.get_attribute("#inp_m", "role") == "meter")
                # --- Settings > Audio: the same state, saved as it is made
                pg.click("#setbtn"); pg.wait_for_selector("#settings[open]")
                pg.click("#set_tabs [data-tab=audio]")
                check(f"{tag}: Settings > Audio has the Live input rows", all(pg.is_visible(x) for x in ("#set_inparm", "#set_inpdev_cb", "#set_inpch_cb", "#set_inpgain")) if pg.is_visible("#set_inpch_cb") else False)
                check(f"{tag}: (i) help on the Live input rows", pg.locator("#settings .sr[data-s*='live input'] .ib2, #settings .sr[data-s*='input gain'] .ib2").count() >= 2)
                pg.evaluate("()=>{const e=document.getElementById('set_inpgain');e.value=6;e.dispatchEvent(new Event('change'))}"); time.sleep(0.6)
                check(f"{tag}: Settings gain saves and the card follows", info()["gain_db"] == 6.0 and abs(float(pg.input_value("#inp_gain")) - 6.0) < 0.01, info())
                pg.evaluate("()=>{const e=document.getElementById('set_inpgain');e.value=0;e.dispatchEvent(new Event('change'))}"); time.sleep(0.5)
                pg.evaluate("()=>{const e=document.getElementById('set_inpgain');e.value=99;e.dispatchEvent(new Event('change'))}"); time.sleep(0.6)
                check(f"{tag}: Settings refuses a gain out of range and goes back", info()["gain_db"] == 0.0 and pg.input_value("#set_inpgain") == "0", (info()["gain_db"], pg.input_value("#set_inpgain")))
                pg.keyboard.press("Escape")
                check(f"{tag}: no page errors", not errs, errs)
                c.close()
        br.close()
    print("\n%d check(s) failed" % len(FAILS) if FAILS else "\nall passed")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
