#!/usr/bin/env python3
"""Live input, stereo pairs and the armed state in the Cue container (2.7.5 input-stereo), desktop only, 3 skins x 2 themes at 1400 px.
Checks: the Channels menu (groups, tick, inside the viewport, the same value in the card and in Settings), one bar for a single channel and two for a pair with
one threshold marker, the Cue container states A (armed, no cue), B (off, no cue), C (a cue is loaded: the pill), D (armed, no input) and the unchanged container
with no device, the switch (Cue container, card, Settings: all update without a reload), keyboard and focus ring, contrast (text 4.5:1, switch and ring 3:1),
and that switching states moves the container by no more than the status line and never moves Go. The capture device is SIMULATED (CP_TEST_INPUT).
    python tests/test_input_stereo_ui.py [--shots DIR]      (needs playwright; starts its own disposable player)"""
import os, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "api"))
from harness import client                       # noqa: E402
from harness.instance import Instance            # noqa: E402
from test_live_input import make_env, set_feed   # noqa: E402

FAILS = []
SHOTS = sys.argv[sys.argv.index("--shots") + 1] if "--shots" in sys.argv else None
GONE = dict(state="gone", db=-90.0, channels=2, reason="the input device \"Fake input\" was not found (unplugged, or not running)")


def check(name, ok, info=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"   {info}"))
    if not ok:
        FAILS.append(name)


# contrast of the text colour of each matched element against the composited background; a non-text part (a switch border, a focus ring) is measured with kind="border"/"outline"
CONTRAST = r"""args=>{const [sels,kind]=args;
  const num=s=>(s.match(/-?[\d.]+(?:e-?\d+)?/g)||[]).map(Number);
  const parse=s=>{if(!s||s==='transparent')return null;const n=num(s);if(s.startsWith('color(')){return n.length<3?null:[n[0]*255,n[1]*255,n[2]*255,n.length>3?n[3]:1]}
    if(s.startsWith('rgb')){return [n[0],n[1],n[2],n.length>3?n[3]:1]}return null};
  const over=(top,bot)=>{const a=top[3];return [top[0]*a+bot[0]*(1-a),top[1]*a+bot[1]*(1-a),top[2]*a+bot[2]*(1-a),1]};
  const bg=el=>{const chain=[];for(let e=el;e;e=e.parentElement){const c=parse(getComputedStyle(e).backgroundColor);if(c&&c[3]>0)chain.push(c)}
    let base=[255,255,255,1];for(let i=chain.length-1;i>=0;i--)base=over(chain[i],base);return base};
  const lum=c=>{const f=v=>{v/=255;return v<=0.03928?v/12.92:Math.pow((v+0.055)/1.055,2.4)};return 0.2126*f(c[0])+0.7152*f(c[1])+0.0722*f(c[2])};
  const out=[];
  for(const sel of sels)document.querySelectorAll(sel).forEach(e=>{const b=e.getBoundingClientRect();if(!b.width||!b.height||e.closest('[hidden]'))return;
    const cs=getComputedStyle(e);if(cs.display==='none'||cs.visibility==='hidden')return;
    const surround=e.parentElement?bg(e.parentElement):[255,255,255,1];
    const own=kind==='text'?parse(cs.color):kind==='border'?parse(cs.borderTopColor):parse(cs.outlineColor);
    if(!own)return;const back=kind==='text'?bg(e):surround;const f=own[3]<1?over(own,back):own,l1=lum(f),l2=lum(back),r=(Math.max(l1,l2)+0.05)/(Math.min(l1,l2)+0.05);
    out.push({sel,text:(e.textContent||'').trim().slice(0,28),ratio:Math.round(r*100)/100})});
  return out}"""
RING = """()=>{const e=document.activeElement;if(!e)return null;const cs=getComputedStyle(e),r=e.getBoundingClientRect(),fs=document.getElementById('fs').getBoundingClientRect(),o=parseFloat(cs.outlineOffset)+parseFloat(cs.outlineWidth);
  return {id:e.id,style:cs.outlineStyle,w:parseFloat(cs.outlineWidth)||0,inside:r.left-o>=fs.left&&r.right+o<=fs.right&&r.top-o>=fs.top&&r.bottom+o<=fs.bottom,name:e.getAttribute('aria-label')||''}}"""
BOX = """()=>{const q=s=>document.querySelector(s).getBoundingClientRect(),fs=q('#fs'),go=q('.cuego'),ia=document.getElementById('cue_ia');
  return {h:fs.height,goFromBottom:fs.bottom-go.bottom,iah:ia.hidden?0:q('#cue_ia').height,top:fs.top}}"""


def main():
    from playwright.sync_api import sync_playwright
    d, env = make_env()
    set_feed(d, state="run", db=-90.0, channels=2)
    cfg = {"input_device": "Fake input", "input_armed": True, "preview_device": "Mock out 1", "duck_hold": False}
    with Instance(wav_only=True, extra_config=cfg, extra_env=env) as inst, Instance(wav_only=True, extra_env=env) as bare, sync_playwright() as p:
        api = client.Api(inst.base_url, osc_port=inst.osc_port)
        api.cmd("rescan")
        api.post("/api/playlists", {"name": "T"})
        api.post("/api/playlists/0/add", {"files": ["tone_a.wav"]})
        info = lambda: api.get("/api/input").json      # noqa: E731
        br = p.chromium.launch()
        for skin in ("console", "studio", "stage"):
            for theme in ("dark", "light"):
                tag = f"{skin}/{theme}"
                c = br.new_context(viewport={"width": 1400, "height": 1000})
                c.add_init_script(f"localStorage.setItem('cp_tour','1');localStorage.setItem('cp_theme','{theme}');localStorage.setItem('cp_skin','{skin}');localStorage.setItem('cp_inp','1')")
                pg = c.new_page(); errs = []
                pg.on("pageerror", lambda e: errs.append(str(e)))
                api.cmd("clear"); api.post("/api/input", {"armed": True, "channels": [1, 2]}); api.cmd("input/ducknow/off")
                set_feed(d, state="run", db=-90.0, channels=2, ch_db={"1": -20.0, "2": -45.0})
                pg.goto(inst.base_url); pg.wait_for_selector("#inpc")
                pg.wait_for_function("document.getElementById('inp_chip').textContent==='Signal present'", timeout=25000)
                time.sleep(0.6)

                # ---------------- the Channels menu
                pg.click("#inp_ch_cb")
                pg.wait_for_selector("#cbo_l [role=option]")
                items = pg.evaluate("()=>[...document.querySelectorAll('#cbo_l [role=option], #cbo_l .cbo-g')].map(e=>({g:e.classList.contains('cbo-g'),t:e.textContent.trim(),sel:e.getAttribute('aria-selected')==='true'}))")
                texts = [i["t"] for i in items]
                check(f"{tag}: menu = groups and exactly the three choices of a 2-channel device",
                      texts == ["Stereo pair", "Channel 1/Channel 2 (stereo)", "Single channel", "Channel 1 (mono)", "Channel 2 (mono)"], texts)
                check(f"{tag}: tick (selected) on the current choice only", [i["t"] for i in items if i["sel"]] == ["Channel 1/Channel 2 (stereo)"], items)
                box = pg.evaluate("()=>{const r=document.getElementById('cbo').getBoundingClientRect();return {l:r.left,t:r.top,r:r.right,b:r.bottom,w:document.documentElement.clientWidth,h:document.documentElement.clientHeight}}")
                check(f"{tag}: menu inside the viewport", box["l"] >= 0 and box["t"] >= 0 and box["r"] <= box["w"] and box["b"] <= box["h"], box)
                pg.keyboard.press("Escape")
                same = pg.evaluate("()=>[document.getElementById('inp_ch_cb').textContent.trim(),document.getElementById('set_inpch_cb').textContent.trim()]")
                check(f"{tag}: the card and Settings show the same value", same[0] == same[1] == "Channel 1/Channel 2 (stereo)", same)

                # ---------------- meters: two bars for a pair, one for a single channel
                bars = lambda: pg.evaluate("()=>[...document.querySelectorAll('#inpc .inpm')].filter(e=>e.getClientRects().length).map(e=>({w:e.getBoundingClientRect().width,fill:e.firstElementChild.getBoundingClientRect().width/e.getBoundingClientRect().width*100,mark:(()=>{const t=document.getElementById('inp_th').getBoundingClientRect();return (t.left+t.width/2-e.getBoundingClientRect().left)/e.getBoundingClientRect().width*100})()}))")   # noqa: E731
                b = bars()
                check(f"{tag}: a pair shows two bars (L and R) with one threshold marker position", len(b) == 2 and abs(b[0]["mark"] - b[1]["mark"]) < 0.6 and abs(b[0]["mark"] - 50) < 1.6, b)
                check(f"{tag}: the bars show their own channel (-20 dB = 67 %, -45 dB = 25 %)", len(b) == 2 and abs(b[0]["fill"] - 66.7) < 4 and abs(b[1]["fill"] - 25) < 4, b)
                check(f"{tag}: bar labels L and R", pg.evaluate("()=>[...document.querySelectorAll('#inpc .inpmr:not([hidden]) .inpl')].map(e=>e.textContent)") == ["L", "R"])
                api.post("/api/input", {"channels": [2]})
                pg.wait_for_function("document.getElementById('inp_r2').hidden===true && document.getElementById('inp_chip').textContent==='Signal present' && Math.abs(+document.getElementById('inp_m').getAttribute('aria-valuenow')+45)<4", timeout=25000)
                time.sleep(0.4)
                b = bars()
                check(f"{tag}: a single channel shows one bar (channel 2: -45 dB)", len(b) == 1 and abs(b[0]["fill"] - 25) < 4, b)
                check(f"{tag}: the menu followed the API change", pg.evaluate("()=>document.getElementById('inp_ch_cb').textContent.trim()") == "Channel 2 (mono)")
                pg.click("#inp_ch_cb"); pg.click("#cbo_l [role=option]:has-text('Channel 1/Channel 2 (stereo)')")
                pg.wait_for_function("document.getElementById('inp_r2').hidden===false && document.getElementById('inp_chip').textContent==='Signal present' && Math.abs(+document.getElementById('inp_m').getAttribute('aria-valuenow')+20)<4", timeout=25000)
                check(f"{tag}: choosing the pair in the menu saves it", info()["channel_list"] == [1, 2])

                # ---------------- the Cue container: states
                pg.wait_for_function("document.getElementById('cue_ia').hidden===false", timeout=5000)
                a = pg.evaluate(BOX)
                check(f"{tag}: A: headline, text, chip and switch", pg.inner_text("#cia_h") == "Input armed" and pg.inner_text("#cia_s") == "Ducking when Channel 1/Channel 2 hears speech"
                      and pg.inner_text("#cia_chip") == "Signal present" and pg.get_attribute("#cia_sw", "aria-pressed") == "true" and pg.is_hidden("#focnm") and pg.is_hidden("#cue_pill"), (pg.inner_text("#cia_h"), pg.inner_text("#cia_s")))
                check(f"{tag}: A: the buttons row and the Go tile are still there", pg.is_visible("text=Play on Top") and pg.is_visible(".cuego"))
                check(f"{tag}: A: switch has a button role and the accessible name", pg.evaluate("()=>{const e=document.getElementById('cia_sw');return e.tagName==='BUTTON'&&e.getAttribute('aria-label')}") == "Input armed. Switch off to disarm")
                if SHOTS: pg.locator("#fs").screenshot(path=f"{SHOTS}/{skin}-{theme}-A-armed-no-cue.png")
                ctext = pg.evaluate(CONTRAST, [["#cia_h", "#cia_s", "#cia_chip"], "text"])
                check(f"{tag}: A: text contrast >= 4.5:1", ctext and all(x["ratio"] >= 4.5 for x in ctext), ctext)
                csw = pg.evaluate(CONTRAST, [["#cia_sw"], "border"])
                check(f"{tag}: A: the switch against its surroundings >= 3:1", csw and csw[0]["ratio"] >= 3, csw)

                # switch from the Cue container: card and Settings follow, no reload
                pg.click("#cia_sw"); time.sleep(0.8)
                st = api.state()
                check(f"{tag}: Cue switch disarms: API, variable, card switch and Settings follow", info()["armed"] is False and st["input_armed"] == "0" and not pg.is_checked("#inp_arm") and not pg.is_checked("#set_inparm"))
                bx = pg.evaluate(BOX)
                check(f"{tag}: B: 'No cue' stays with 'Input off' under it", pg.is_visible("#focnm") and pg.inner_text("#focnm") == "No cue" and pg.inner_text("#cia_h") == "Input off"
                      and pg.inner_text("#cia_s") == "Voice ducking from Channel 1/Channel 2 is not active" and pg.get_attribute("#cia_sw", "aria-pressed") == "false" and pg.is_hidden("#cia_chip"))
                check(f"{tag}: B: the container grew by less than 'No cue' plus a few px; Go did not move from the bottom", 0 <= bx["h"] - a["h"] <= 48 and abs(bx["goFromBottom"] - a["goFromBottom"]) < 1.5, (a, bx))
                if SHOTS: pg.locator("#fs").screenshot(path=f"{SHOTS}/{skin}-{theme}-B-off-no-cue.png")
                ctext = pg.evaluate(CONTRAST, [["#cia_h", "#cia_s", "#focnm"], "text"])
                check(f"{tag}: B: text contrast >= 4.5:1", ctext and all(x["ratio"] >= 4.5 for x in ctext), ctext)
                check(f"{tag}: the Live input card has no Armed switch (arming is only in the Cue container)", pg.is_hidden("label.inparm") and pg.is_hidden("#inp_arm"))
                pg.click("#cia_sw"); time.sleep(0.8)                # the Cue switch arms: the card's read-only text and Settings follow
                check(f"{tag}: the Cue switch arms: the card's text and Settings follow", info()["armed"] is True and pg.get_attribute("#cia_sw", "aria-pressed") == "true" and pg.is_checked("#set_inparm") and pg.is_checked("#inp_arm"))
                pg.click("#setbtn"); pg.wait_for_selector("#settings[open]"); pg.click("#set_tabs [data-tab=audio]")
                pg.click("#set_inparm", force=True); time.sleep(0.8)
                check(f"{tag}: Settings disarms: the Cue switch and the card follow", info()["armed"] is False and pg.get_attribute("#cia_sw", "aria-pressed") == "false" and not pg.is_checked("#inp_arm"))
                pg.keyboard.press("Escape")
                pg.click("#cia_sw"); time.sleep(0.8)

                # C: a cue is loaded
                api.cmd("0/0/focus"); pg.wait_for_function("document.getElementById('cue_pill').hidden===false", timeout=6000)
                c_ = pg.evaluate(BOX)
                check(f"{tag}: C: the pill in the header, the status line gone", pg.inner_text("#cue_pill_t") == "Input armed" and pg.is_hidden("#cue_ia") and pg.is_visible("#focnm") and pg.inner_text("#focnm") == "tone_a", (pg.inner_text("#cue_pill_t"), pg.inner_text("#focnm")))
                pr = pg.evaluate("()=>{const p=document.getElementById('cue_pill').getBoundingClientRect(),f=document.getElementById('fs').getBoundingClientRect(),h=document.querySelector('#fs > b').getBoundingClientRect();return {right:f.right-p.right,sameRow:Math.abs((p.top+p.bottom)/2-(h.top+h.bottom)/2)<14}}")
                check(f"{tag}: C: the pill is right-aligned on the header row", pr["sameRow"] and pr["right"] < 30, pr)
                check(f"{tag}: C: Go stays at the bottom of the container, the container is no taller than in A", abs(c_["goFromBottom"] - a["goFromBottom"]) < 1.5 and c_["h"] <= a["h"] + 2, (a, c_))
                if SHOTS: pg.locator("#fs").screenshot(path=f"{SHOTS}/{skin}-{theme}-C-cue-loaded-pill.png")
                ctext = pg.evaluate(CONTRAST, [["#cue_pill_t"], "text"]); csw = pg.evaluate(CONTRAST, [["#cue_pill_sw"], "border"])
                check(f"{tag}: C: pill text >= 4.5:1, its switch >= 3:1", ctext and ctext[0]["ratio"] >= 4.5 and csw and csw[0]["ratio"] >= 3, (ctext, csw))
                pg.click("#cue_pill_sw"); time.sleep(0.8)
                check(f"{tag}: C: the pill's switch disarms ('Input off', grey)", info()["armed"] is False and pg.inner_text("#cue_pill_t") == "Input off" and pg.get_attribute("#cue_pill", "data-st") == "off")
                ctext = pg.evaluate(CONTRAST, [["#cue_pill_t"], "text"])
                check(f"{tag}: C: 'Input off' text >= 4.5:1", ctext and ctext[0]["ratio"] >= 4.5, ctext)
                if SHOTS: pg.locator("#fs").screenshot(path=f"{SHOTS}/{skin}-{theme}-C-cue-loaded-pill-off.png")
                pg.click("#cue_pill_sw"); time.sleep(0.8)

                # keyboard on the pill: Tab, Space, ring not clipped
                pg.focus("#cue_pill_sw"); pg.keyboard.press("Shift+Tab"); pg.keyboard.press("Tab"); r = pg.evaluate(RING)       # reached by the keyboard, so the focus-visible ring shows
                check(f"{tag}: pill switch: visible focus ring, not clipped, named", r["style"] != "none" and r["w"] >= 2 and r["inside"] and r["name"].startswith("Input armed."), r)
                rc = pg.evaluate(CONTRAST, [["#cue_pill_sw"], "outline"])
                check(f"{tag}: focus ring against its surroundings >= 3:1", rc and rc[0]["ratio"] >= 3, rc)
                pg.keyboard.press("Space"); time.sleep(0.8)
                check(f"{tag}: Space on the pill switch disarms", info()["armed"] is False)
                pg.keyboard.press("Enter"); time.sleep(0.8)
                check(f"{tag}: Enter arms again", info()["armed"] is True)

                # D: armed, no input (with a cue: the amber pill; without: the amber line)
                set_feed(d, **GONE)
                pg.wait_for_function("document.getElementById('cue_pill').dataset.st==='warn'", timeout=15000)
                check(f"{tag}: D with a cue: amber pill 'Input armed, no input', switch still on", pg.inner_text("#cue_pill_t") == "Input armed, no input" and pg.get_attribute("#cue_pill_sw", "aria-pressed") == "true")
                api.cmd("clear")
                pg.wait_for_function("document.getElementById('cue_ia').hidden===false", timeout=6000)
                dd = pg.evaluate(BOX)
                check(f"{tag}: D: amber line with the reason and a 'No input' chip", pg.inner_text("#cia_h") == "Input armed, no input" and pg.inner_text("#cia_s") == "Fake input not found. Ducking is off until it returns."
                      and pg.inner_text("#cia_chip") in ("No input", "Switching…") and pg.get_attribute("#cue_ia", "data-st") == "warn" and pg.get_attribute("#cia_sw", "aria-pressed") == "true", (pg.inner_text("#cia_h"), pg.inner_text("#cia_s"), pg.inner_text("#cia_chip")))
                check(f"{tag}: D: Armed is kept in the API, ducking is off", info()["armed"] is True and info()["gr"] == 0)
                check(f"{tag}: D: the container is as tall as A and Go did not move", abs(dd["h"] - a["h"]) <= dd["iah"] and abs(dd["goFromBottom"] - a["goFromBottom"]) < 1.5, (a, dd))
                ctext = pg.evaluate(CONTRAST, [["#cia_h", "#cia_s", "#cia_chip"], "text"])
                check(f"{tag}: D: text contrast >= 4.5:1", ctext and all(x["ratio"] >= 4.5 for x in ctext), ctext)
                if SHOTS: pg.locator("#fs").screenshot(path=f"{SHOTS}/{skin}-{theme}-D-armed-no-input.png")
                set_feed(d, state="run", db=-90.0, channels=2, ch_db={"1": -20.0, "2": -45.0})
                pg.wait_for_function("document.getElementById('cue_ia').dataset.st==='on'", timeout=20000)
                check(f"{tag}: D: it recovers by itself", pg.inner_text("#cia_h") == "Input armed")
                if SHOTS and theme == "dark" or SHOTS and skin == "console":
                    pg.screenshot(path=f"{SHOTS}/{skin}-{theme}-page-top.png", clip={"x": 0, "y": 0, "width": 1400, "height": 760})
                check(f"{tag}: no page errors", not errs, errs)
                c.close()

        # ---------------- no device chosen: the Cue container is exactly as it was
        c = br.new_context(viewport={"width": 1400, "height": 1000})
        c.add_init_script("localStorage.setItem('cp_tour','1')")
        pg = c.new_page(); pg.goto(bare.base_url); pg.wait_for_selector("#fs"); time.sleep(1.5)
        check("no device: no status line, no pill, 'No cue' as before", pg.is_hidden("#cue_ia") and pg.is_hidden("#cue_pill") and pg.is_visible("#focnm") and pg.inner_text("#focnm") == "No cue")
        bapi = client.Api(bare.base_url, osc_port=bare.osc_port); bapi.post("/api/playlists", {"name": "T"}); bapi.post("/api/playlists/0/add", {"files": ["tone_a.wav"]}); bapi.cmd("0/0/focus"); time.sleep(1.5)
        check("no device, a cue loaded: no pill", pg.is_hidden("#cue_pill") and pg.is_hidden("#cue_ia"))
        c.close(); br.close()
    print("\n%d check(s) failed" % len(FAILS) if FAILS else "\nall passed")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
