#!/usr/bin/env python3
"""ElevenLabs (2.9.0) in the web page: Settings › System › ElevenLabs, the Library header button and the Generate dialog.
3 skins x dark/light x desktop (1400 px) / tablet (820 px). Phone width is out of scope (the button is hidden there).

    python tests/test_elevenlabs_ui.py        (needs playwright; its own disposable player with the fake ElevenLabs of CP_TEST_ELEVENLABS: no network)

Checks: the group sits between Library and Health and alerts; No key / Key set chip; the key field is a password field, the key saves
only on Save key and never appears in the page; Test key's green box; the header button matches Expand all (size, top, icon size, title);
the dialog without a key says "Connect your ElevenLabs account" and opens the Settings group; voices, quota line, character count;
the amber quota warning disables Generate; generate, waveform and time; Save puts a track with the ElevenLabs chip and the
"Edit text and regenerate" button in the Generated folder, which opens the dialog pre-filled; keyboard focus ring; Esc closes and returns
focus; closing with unsaved audio (Esc, X, backdrop) asks "Discard the generated audio?" with Keep editing (focused) and Discard,
no question when nothing was generated or it is saved; the dialog stays inside the viewport; text contrast >= 4.5:1 and control contrast >= 3:1 (the result boxes' coloured borders
are the shared Settings pattern and not a control: their title and text carry the meaning, so only their text is measured). The key used is made up."""
import json, os, shutil, subprocess, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from harness import client                       # noqa: E402
from harness.instance import Instance, PROJECT   # noqa: E402

KEY = "test-not-a-real-key-4444-qrst"
FAILS = []


def check(name, ok, info=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"   {info}"))
    if not ok:
        FAILS.append(name)


CONTRAST = """(sels)=>{
 const cv=document.createElement('canvas');cv.width=cv.height=1;const g=cv.getContext('2d',{willReadFrequently:true});
 const paint=(c,under)=>{g.clearRect(0,0,1,1);g.fillStyle=under;g.fillRect(0,0,1,1);g.fillStyle=c;g.fillRect(0,0,1,1);const d=g.getImageData(0,0,1,1).data;return `rgb(${d[0]},${d[1]},${d[2]})`};
 const alpha=c=>{g.clearRect(0,0,1,1);g.fillStyle=c;g.fillRect(0,0,1,1);return g.getImageData(0,0,1,1).data[3]/255};
 const bg=el=>{const st=[];for(let e=el;e;e=e.parentElement){const b=getComputedStyle(e).backgroundColor;st.push(b);if(alpha(b)>=1)break}
  let cur='rgb(255,255,255)';for(const b of st.reverse())cur=paint(b,cur);return cur};
 const lum=c=>{const v=c.match(/\\d+/g).slice(0,3).map(x=>{x=x/255;return x<=0.03928?x/12.92:((x+0.055)/1.055)**2.4});return .2126*v[0]+.7152*v[1]+.0722*v[2]};
 const ratio=(a,b)=>{const [x,y]=[lum(a),lum(b)].sort((p,q)=>q-p);return (x+.05)/(y+.05)};
 const out=[];
 for(const [sel,kind] of sels){for(const el of document.querySelectorAll(sel)){const r=el.getBoundingClientRect();if(!r.width||!r.height||getComputedStyle(el).visibility==='hidden')continue;
  const b=bg(el.parentElement||el),cs=getComputedStyle(el);let fg;
  if(kind==='text'){fg=paint(cs.color,bg(el))}
  else if(kind==='border'){fg=paint(cs.borderTopColor,b)}
  else{fg=paint(cs.backgroundColor,b)}
  out.push({sel,kind,id:el.id||el.className,ratio:Math.round(ratio(fg,kind==='text'?bg(el):b)*100)/100})}}
 return out}"""


def fake_dir():
    d = Path(tempfile.mkdtemp(prefix="cpelui-"))
    ff = shutil.which("ffmpeg")
    if not ff or subprocess.run([ff, "-v", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=330:duration=2", "-ac", "1", "-b:a", "64k", str(d / "speech.mp3")]).returncode:
        print("SKIP: needs ffmpeg to make a decodable mp3 for the fake ElevenLabs")
        sys.exit(0)
    spec(d, 100)
    return d


def spec(d, used):
    (d / "fake.json").write_text(json.dumps({
        "key": KEY,
        "voices": {"status": 200, "body": {"voices": [{"voice_id": "v1", "name": "Narrator", "category": "premade", "preview_url": None},
                                                      {"voice_id": "v2", "name": "My clone", "category": "cloned", "preview_url": None}], "has_more": False}},
        "usage": {"status": 200, "body": {"character_count": used, "character_limit": 10000, "next_character_count_reset_unix": 1900000000}},
        "models": {"status": 401, "body": {"detail": {"status": "missing_permissions", "message": "missing the permission models_read"}}},
        "speech": {"status": 200, "file": "speech.mp3", "delay": 0.3}}))


def main():
    from playwright.sync_api import sync_playwright
    d = fake_dir()
    with Instance(wav_only=True, project_dir=PROJECT, extra_env={"CP_TEST_ELEVENLABS": str(d)}) as inst, sync_playwright() as p:
        api = client.Api(inst.base_url, osc_port=inst.osc_port)
        br = p.chromium.launch()
        first = True
        for skin in ("console", "studio", "stage"):
            for theme in ("dark", "light"):
                for tag, vp in (("desktop", {"width": 1400, "height": 1000}), ("tablet", {"width": 820, "height": 1180})):
                    label = f"{skin}/{theme}/{tag}"
                    api.delete("/api/elevenlabs/key")
                    spec(d, 100)
                    c = br.new_context(viewport=vp)
                    c.add_init_script(f"localStorage.setItem('cp_tour','1');localStorage.setItem('cp_skin','{skin}');localStorage.setItem('cp_theme','{theme}');localStorage.setItem('cp_pvtarget','browser')")
                    pg = c.new_page(); errs = []
                    pg.on("pageerror", lambda e: errs.append(str(e)))
                    pg.goto(inst.base_url); pg.wait_for_selector("#lib .lt")

                    # ---- Library header button
                    g = pg.evaluate("""()=>{const r=id=>{const b=document.getElementById(id),x=b.getBoundingClientRect(),s=b.querySelector('svg').getBoundingClientRect();
                        return {w:x.width,h:x.height,top:x.top,sw:s.width,sh:s.height,title:b.title,al:b.getAttribute('aria-label'),vis:getComputedStyle(b).display!=='none'}};
                        return {gen:r('lib_gen'),exp:r('lib_expand')}}""")
                    check(f"{label}: header button visible, same size, row and icon size as Expand all",
                          g["gen"]["vis"] and abs(g["gen"]["w"] - g["exp"]["w"]) < 0.5 and abs(g["gen"]["h"] - g["exp"]["h"]) < 0.5 and abs(g["gen"]["top"] - g["exp"]["top"]) < 0.5
                          and abs(g["gen"]["sw"] - g["exp"]["sw"]) < 0.5, g)
                    check(f"{label}: header button title and label", g["gen"]["title"] == g["gen"]["al"] == "Generate audio with ElevenLabs", g["gen"])

                    # ---- dialog without a key
                    pg.click("#lib_gen")
                    pg.wait_for_selector("#eldlg[open] #el_conn:not([hidden])")
                    check(f"{label}: no key: Connect your ElevenLabs account, no empty picker",
                          "Connect your ElevenLabs account" in pg.inner_text("#el_conn") and pg.is_hidden("#el_form"), "")
                    pg.click("#el_conn .pri")
                    pg.wait_for_selector("#settings[open]")
                    o = pg.evaluate("""()=>({tab:settings.dataset.tab,secs:[...settings.querySelectorAll('.ss[data-tab=system]')].map(s=>s.dataset.sec),focus:document.activeElement.id,
                        vis:!!document.querySelector('[data-sec=eleven]').offsetParent,type:el_key.type,chip:el_chip.textContent})""")
                    check(f"{label}: Settings opened on System with the ElevenLabs group, key field focused", o["tab"] == "system" and o["vis"] and o["focus"] == "el_key", o)
                    check(f"{label}: group between Library and Health and alerts", o["secs"][:3] == ["library", "eleven", "health"], o["secs"])
                    check(f"{label}: password field, chip No key", o["type"] == "password" and o["chip"] == "No key", o)
                    check(f"{label}: two notes shown with no key", pg.is_visible("#el_n1") and pg.is_visible("#el_n2") and "text_to_speech" in pg.inner_text("#el_n1"), "")

                    # ---- save the key (only on Save key) and test it
                    pg.fill("#el_key", KEY)
                    pg.dispatch_event("#el_key", "change")
                    pg.wait_for_timeout(150)
                    check(f"{label}: typing does not save", api.get("/api/elevenlabs").json["key"]["set"] is False, "")
                    pg.click("#el_save")
                    pg.wait_for_selector("#el_has:not([hidden])")
                    o = pg.evaluate("()=>({chip:el_chip.textContent,cls:el_chip.className,val:el_key.value,html:document.documentElement.outerHTML})")
                    check(f"{label}: chip Key set · ends in qrst", o["chip"] == "Key set · ends in qrst" and "ok" in o["cls"], o["chip"])
                    check(f"{label}: the key is nowhere in the page after saving", KEY not in o["html"] and o["val"] == "", "")
                    pg.click("#el_test")
                    pg.wait_for_selector("#el_res.ok")
                    check(f"{label}: Test key: green, Key works, usage shown", "Key works" in pg.inner_text("#el_res") and "characters left" in pg.inner_text("#el_res"), pg.inner_text("#el_res"))
                    cr = pg.evaluate(CONTRAST, [["#el_chip", "text"], ["#el_res", "text"], ["#el_test", "border"], ["#settings [data-sec=eleven] .hint2", "text"], ["#el_test", "text"]])
                    bad = [x for x in cr if x["ratio"] < (4.5 if x["kind"] == "text" else 3)]
                    check(f"{label}: Settings group contrast (text 4.5, controls 3)", not bad, bad)
                    pg.keyboard.press("Escape")
                    pg.wait_for_function("()=>!settings.open")

                    # ---- the dialog with a key
                    pg.click("#lib_gen")
                    pg.wait_for_selector("#eldlg[open] #el_form:not([hidden])")
                    pg.wait_for_selector("#el_voices input[type=radio]")
                    pg.wait_for_selector("#el_quota:not([hidden])")
                    o = pg.evaluate("()=>({n:el_voices.querySelectorAll('input[type=radio]').length,kinds:[...el_voices.querySelectorAll('.elk')].map(x=>x.textContent),q:el_qtxt.textContent,models:[...el_model.options].map(o=>o.text),focus:document.activeElement.id})")
                    check(f"{label}: voices with Library / Cloned chips, quota line, Default model only", o["n"] == 2 and sorted(o["kinds"]) == ["Cloned", "Library"] and "9,900 of 10,000" in o["q"] and o["models"] == ["Default model"], o)
                    check(f"{label}: focus starts in Track name", o["focus"] == "el_name", o["focus"])
                    pg.keyboard.press("Tab")
                    ring = pg.evaluate("()=>{const e=document.activeElement,c=getComputedStyle(e);return {id:e.id,os:c.outlineStyle,ow:c.outlineWidth}}")
                    check(f"{label}: keyboard focus ring", ring["os"] != "none" and ring["ow"] not in ("0px", ""), ring)
                    pg.fill("#el_name", "Doors open")
                    pg.fill("#el_text", "Ladies and gentlemen, doors are now open.")
                    o = pg.evaluate("()=>({cnt:el_count.textContent,go:el_go.disabled})")
                    check(f"{label}: live character count, Generate enabled", o["cnt"].startswith("41 / 10,000") and not o["go"], o)
                    rect = pg.evaluate("()=>{const r=eldlg.getBoundingClientRect();return {l:r.left,t:r.top,r:r.right,b:r.bottom,w:innerWidth,h:innerHeight}}")
                    check(f"{label}: dialog inside the viewport", rect["l"] >= 0 and rect["t"] >= 0 and rect["r"] <= rect["w"] and rect["b"] <= rect["h"], rect)
                    cr = pg.evaluate(CONTRAST, [["#eldlg .elsub", "text"], ["#eldlg label", "text"], ["#el_count", "text"], ["#eldlg .elk", "text"], ["#eldlg .hint2", "text"],
                                                ["#el_qtxt", "text"], ["#el_go", "text"], ["#el_vref", "text"], ["#eldlg summary", "text"], ["#el_go", "bg"], ["#el_cancel", "border"]])
                    bad = [x for x in cr if x["ratio"] < (4.5 if x["kind"] == "text" else 3)]
                    check(f"{label}: dialog contrast (text 4.5, controls 3)", not bad, bad)

                    # ---- quota warning: amber, Generate disabled
                    spec(d, 9990)
                    pg.evaluate("elUsage()")
                    pg.wait_for_function("()=>el_qtxt.textContent.startsWith('10 of')")
                    pg.evaluate("elCheck()")
                    o = pg.evaluate("()=>({cls:el_msg.className,hid:el_msg.hidden,go:el_go.disabled,t:el_msg.textContent})")
                    check(f"{label}: text longer than the quota left: amber box, Generate disabled", o["cls"] == "resbox warn" and not o["hid"] and o["go"] and "only 10 are left" in o["t"], o)
                    cr = pg.evaluate(CONTRAST, [["#el_msg", "text"], ["#el_count", "text"]])
                    bad = [x for x in cr if x["ratio"] < (4.5 if x["kind"] == "text" else 3)]
                    check(f"{label}: amber box and over-count contrast", not bad, bad)
                    spec(d, 100)
                    pg.evaluate("elUsage()")
                    pg.wait_for_function("()=>!el_go.disabled")

                    # ---- generate, preview card
                    pg.click("#el_go")
                    pg.wait_for_selector("#el_done:not([hidden])", timeout=15000)
                    pg.wait_for_function("()=>EL.peaks&&EL.dur>1", timeout=15000)
                    o = pg.evaluate("()=>({t:el_time.textContent,out:el_out.textContent,v:el_rvoice.textContent,ch:el_rchars.textContent,folder:el_folder.value,mode:el_mode.hidden,focus:document.activeElement.id})")
                    check(f"{label}: preview card: time, output name, voice, characters, Generated folder", o["t"] == "00:00 / 00:02" and "This browser" in o["out"] and o["v"] == "My clone"
                          and o["ch"] == "41" and o["folder"] == "Generated" and o["mode"] and o["focus"] == "el_play", o)
                    cr = pg.evaluate(CONTRAST, [["#el_time", "text"], ["#el_out", "text"], ["#eldlg .eldl dt", "text"], ["#el_play", "bg"], ["#el_savebtn", "text"], ["#el_savebtn", "bg"], ["#el_done .row button:not(.pri)", "border"], ["#el_done .row button:not(.pri)", "text"]])
                    bad = [x for x in cr if x["ratio"] < (4.5 if x["kind"] == "text" else 3)]
                    check(f"{label}: preview card contrast", not bad, bad)
                    # ---- closing with unsaved audio asks first (Esc, X, backdrop); Keep editing has the focus
                    st = lambda: pg.evaluate("()=>({dlg:eldlg.open,ask:elask.open,focus:document.activeElement.id})")      # noqa: E731
                    pg.keyboard.press("Escape")
                    pg.wait_for_function("()=>elask.open")
                    o = st()
                    check(f"{label}: Esc with unsaved audio asks, the dialog stays, Keep editing has the focus", o == {"dlg": True, "ask": True, "focus": "elask_keep"}, o)
                    txt = pg.evaluate("()=>elask_t.textContent+' '+elask_d.textContent")
                    btns = pg.evaluate("()=>[...elask.querySelectorAll('button')].map(b=>b.textContent)")
                    check(f"{label}: the question and its two buttons", txt == "Discard the generated audio? Generating it again uses characters." and btns == ["Keep editing", "Discard"], (txt, btns))
                    cr = pg.evaluate(CONTRAST, [["#elask h3", "text"], ["#elask_d", "text"], ["#elask_keep", "text"], ["#elask_go", "text"], ["#elask_keep", "border"], ["#elask_go", "border"]])
                    bad = [x for x in cr if x["ratio"] < (4.5 if x["kind"] == "text" else 3)]
                    check(f"{label}: question contrast", not bad, bad)
                    r = pg.evaluate("()=>{const b=elask.getBoundingClientRect();return b.left>=0&&b.top>=0&&b.right<=innerWidth&&b.bottom<=innerHeight}")
                    check(f"{label}: question inside the viewport", r, "")
                    pg.keyboard.press("Escape")
                    pg.wait_for_function("()=>!elask.open")
                    pg.wait_for_timeout(50)
                    o = st()
                    check(f"{label}: Esc on the question = Keep editing; focus back where it was", o == {"dlg": True, "ask": False, "focus": "el_play"}, o)
                    check(f"{label}: Keep editing keeps the audio", api.get("/api/elevenlabs/job").json["has_temp"] is True, "")
                    pg.click("#eldlg .elhd .setx")
                    pg.wait_for_function("()=>elask.open")
                    pg.keyboard.press("Tab")
                    f1 = pg.evaluate("()=>document.activeElement.id")
                    pg.keyboard.press("Shift+Tab")
                    f2 = pg.evaluate("()=>document.activeElement.id")
                    check(f"{label}: X asks; Tab / Shift+Tab move between Discard and Keep editing", (f1, f2) == ("elask_go", "elask_keep"), (f1, f2))
                    pg.keyboard.press("Enter")
                    pg.wait_for_function("()=>!elask.open")
                    check(f"{label}: Enter on Keep editing keeps the dialog", st()["dlg"] is True and api.get("/api/elevenlabs/job").json["has_temp"] is True, st())
                    pg.click("#el_out")
                    pg.wait_for_timeout(50)
                    check(f"{label}: a click inside the dialog does not ask", st()["ask"] is False, st())
                    pg.mouse.click(4, 4)
                    pg.wait_for_function("()=>elask.open")
                    check(f"{label}: a click on the backdrop asks", st()["dlg"] is True, st())
                    if not first:
                        pg.keyboard.press("Tab")
                        pg.keyboard.press("Enter")
                        pg.wait_for_function("()=>!eldlg.open&&!elask.open")
                        pg.wait_for_timeout(150)
                        check(f"{label}: Discard (keyboard) closes both, deletes the audio, focus back on the header button",
                              api.get("/api/elevenlabs/job").json["has_temp"] is False and pg.evaluate("()=>document.activeElement.id") == "lib_gen", pg.evaluate("()=>document.activeElement.id"))
                        pg.click("#lib_gen")
                        pg.wait_for_selector("#eldlg[open] #el_form:not([hidden])")
                    else:
                        pg.click("#elask_keep")
                        pg.wait_for_function("()=>!elask.open")
                    if first:
                        first = False
                        pg.click("#el_savebtn")
                        pg.wait_for_function("()=>!eldlg.open")
                        pg.wait_for_selector('#lib .lt[data-id="Generated/Doors open.mp3"]')
                        row = '#lib .lt[data-id="Generated/Doors open.mp3"]'
                        o = pg.evaluate(f"""()=>{{const r=document.querySelector('{row}');const b=r.querySelector('[data-act=elgen]'),ren=r.querySelector('[data-act=ren]');
                            const bb=b.getBoundingClientRect(),rr=ren.getBoundingClientRect();return {{chip:(r.querySelector('.elchip')||{{}}).textContent,title:b.title,al:b.getAttribute('aria-label'),
                            next:ren.nextElementSibling===b,h:bb.height,rh:rr.height,top:bb.top,rt:rr.top}}}}""")
                        check(f"{label}: saved track: ElevenLabs chip and Edit text and regenerate beside rename, same size",
                              o["chip"] == "ElevenLabs" and o["title"] == o["al"] == "Edit text and regenerate" and o["next"] and abs(o["h"] - o["rh"]) < 0.5 and abs(o["top"] - o["rt"]) < 1, o)
                        check(f"{label}: plain rows have no ElevenLabs button", pg.evaluate("()=>[...document.querySelectorAll('#lib .lt')].filter(r=>!r.dataset.id.startsWith('Generated/')&&r.querySelector('[data-act=elgen]')).length") == 0, "")
                        pg.click(f"{row} [data-act=elgen]")
                        pg.wait_for_selector("#eldlg[open] #el_form:not([hidden])")
                        pg.wait_for_function("()=>el_text.value.length>0")
                        o = pg.evaluate("()=>({n:el_name.value,t:el_text.value,note:el_editnote.hidden})")
                        check(f"{label}: edit opens pre-filled", o == {"n": "Doors open", "t": "Ladies and gentlemen, doors are now open.", "note": False}, o)
                        pg.wait_for_function("()=>!el_go.disabled")
                        pg.click("#el_go")
                        pg.wait_for_selector("#el_done:not([hidden])", timeout=15000)
                        check(f"{label}: edit mode offers Save as new and Replace", pg.is_visible("#el_mode"), "")
                        pg.keyboard.press("Escape")
                        pg.wait_for_function("()=>elask.open")
                        pg.click("#elask_go")
                        pg.wait_for_function("()=>!eldlg.open&&!elask.open")
                        pg.wait_for_timeout(200)
                        foc = pg.evaluate("()=>{const e=document.activeElement;return e.dataset.act||e.id}")
                        check(f"{label}: Esc from an edit asks; Discard returns focus to the row button", foc == "elgen", foc)
                        check(f"{label}: Discard deletes the audio", api.get("/api/elevenlabs/job").json["has_temp"] is False, "")
                        # already saved (a duplicate leaves the dialog open with its green box): no question
                        pg.click("#lib_gen")
                        pg.wait_for_selector("#eldlg[open] #el_form:not([hidden])")
                        pg.wait_for_selector("#el_voices input[type=radio]")
                        pg.fill("#el_name", "Doors again")
                        pg.fill("#el_text", "Ladies and gentlemen, doors are now open.")
                        pg.wait_for_function("()=>!el_go.disabled")
                        pg.click("#el_go")
                        pg.wait_for_selector("#el_done:not([hidden])", timeout=15000)
                        pg.click("#el_savebtn")
                        pg.wait_for_selector("#el_msg2.ok")
                        check(f"{label}: duplicate save says where it is", "Already in the library" in pg.inner_text("#el_msg2"), pg.inner_text("#el_msg2"))
                        pg.keyboard.press("Escape")
                        pg.wait_for_function("()=>!eldlg.open")
                        check(f"{label}: already saved: closes without asking", not pg.evaluate("()=>elask.open"), "")
                        pg.click("#lib_gen")
                        pg.wait_for_selector("#eldlg[open] #el_form:not([hidden])")
                    pg.keyboard.press("Escape")
                    pg.wait_for_function("()=>!eldlg.open")
                    pg.wait_for_timeout(150)
                    check(f"{label}: nothing generated: Esc closes without asking", not pg.evaluate("()=>elask.open"), "")
                    check(f"{label}: Esc closes the dialog and returns focus to the header button", pg.evaluate("()=>document.activeElement.id") == "lib_gen", pg.evaluate("()=>document.activeElement.id"))
                    check(f"{label}: no page errors", not errs, errs)
                    c.close()
        br.close()
    shutil.rmtree(d, ignore_errors=True)
    print(f"\n{'FAIL' if FAILS else 'PASS'}: {len(FAILS)} failure(s)")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
