#!/usr/bin/env python3
"""ElevenLabs (2.9.0) in the web page: Settings › System › ElevenLabs, the Library header button and the Generate dialog.
3 skins x dark/light x desktop (1400 px) / tablet (820 px). Phone width is out of scope (the button is hidden there).

    python tests/test_elevenlabs_ui.py        (needs playwright; its own disposable player with the fake ElevenLabs of CP_TEST_ELEVENLABS: no network)

Checks: a generated row and a normal row have their buttons at the same x; "Edit text and regenerate…" in the Rename or move dialog
for generated tracks only (opens Generate pre-filled, rename edits not saved, focus returns); Save to folder is a select with Create new
folder… first, the Rename dialog's folders, the default rules and name validation; the group sits between Library and Health and alerts; No key / Key set chip; the key field is a password field, the key saves
only on Save key and never appears in the page; Test key's green box; the header button matches Expand all (size, top, icon size, title);
the dialog without a key says "Connect your ElevenLabs account" and opens the Settings group; voices, quota line, character count;
the amber quota warning disables Generate; generate, waveform and time; Save puts a track with the ElevenLabs chip and the
"Edit text and regenerate" button in the Generated folder, which opens the dialog pre-filled; keyboard focus ring; Esc closes and returns
focus; closing with unsaved audio (Esc, X, backdrop) asks "Discard the generated audio?" with Keep editing (focused) and Discard,
no question when nothing was generated or it is saved; the dialog stays inside the viewport; text contrast >= 4.5:1 and control contrast >= 3:1 (the result boxes' coloured borders
are the shared Settings pattern and not a control: their title and text carry the meaning, so only their text is measured). The key used is made up."""
import json, os, shutil, subprocess, sys, tempfile, time
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
    for name, hz in (("speech.mp3", 330), ("speech2.mp3", 550), ("speech3.mp3", 770)):      # three different sounds (a repeat is a duplicate)
        if not ff or subprocess.run([ff, "-v", "error", "-y", "-f", "lavfi", "-i", f"sine=frequency={hz}:duration=2", "-ac", "1", "-b:a", "64k", str(d / name)]).returncode:
            print("SKIP: needs ffmpeg to make a decodable mp3 for the fake ElevenLabs")
            sys.exit(0)
    spec(d, 100)
    return d


def spec(d, used, audio="speech.mp3"):
    (d / "fake.json").write_text(json.dumps({
        "key": KEY,
        "voices": {"status": 200, "body": {"voices": [{"voice_id": "v1", "name": "Narrator", "category": "premade", "preview_url": None},
                                                      {"voice_id": "v2", "name": "My clone", "category": "cloned", "preview_url": None}], "has_more": False}},
        "usage": {"status": 200, "body": {"character_count": used, "character_limit": 10000, "next_character_count_reset_unix": 1900000000}},
        "models": {"status": 401, "body": {"detail": {"status": "missing_permissions", "message": "missing the permission models_read"}}},
        "speech": {"status": 200, "file": audio, "delay": 0.3}}))


def wav_bytes(seconds=2, rate=22050):
    import io, wave
    b = io.BytesIO()
    with wave.open(b, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate); w.writeframes(bytes(int(seconds * rate) * 2))
    return b.getvalue()


def setup_library(api, d):
    """A generated track and a plain track side by side in Generated (same depth), and a folder Other."""
    api.post("/api/elevenlabs/key", {"key": KEY})
    spec(d, 100, "speech2.mp3")
    api.post("/api/elevenlabs/generate", {"name": "Preset", "text": "Preset announcement.", "voice_id": "v1", "voice_name": "Narrator"})
    for _ in range(100):
        if api.get("/api/elevenlabs/job").json["state"] != "running":
            break
        time.sleep(0.05)
    r = api.post("/api/elevenlabs/save", {"name": "Preset", "new_folder": "Generated"})
    assert r.status == 200 and r.json["id"] == GEN, r.text
    assert api.upload("plain.wav", wav_bytes(), folder="Generated").status == 200
    api.post("/api/library/folder", {"path": "Other"})
    assert api.post("/api/elevenlabs/save", {"name": "x", "folder": "../../etc"}).status in (400, 409), "the server refuses a folder outside the library"
    spec(d, 100)


GEN, PLAIN = "Generated/Preset.mp3", "Generated/plain.wav"
ROWPOS = """(ids)=>ids.map(id=>{const r=[...document.querySelectorAll('#lib .lt')].find(x=>x.dataset.id===id);if(!r)return null;
 const out=[...r.querySelectorAll(':scope > .ib, :scope > .sz')].map(e=>{const b=e.getBoundingClientRect();return [e.dataset.act||e.dataset.info&&'info'||e.className,Math.round(b.left*10)/10,Math.round(b.right*10)/10]});
 return {pos:out,chip:(r.querySelector('.elchip')||{}).textContent||'',edit:!!r.querySelector('[data-act=elgen]')}})"""


def main():
    from playwright.sync_api import sync_playwright
    d = fake_dir()
    with Instance(wav_only=True, project_dir=PROJECT, extra_env={"CP_TEST_ELEVENLABS": str(d)}) as inst, sync_playwright() as p:
        api = client.Api(inst.base_url, osc_port=inst.osc_port)
        setup_library(api, d)
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

                    # ---- a generated row and a normal row: every row button (and the length) at exactly the same x
                    pg.wait_for_selector(f'#lib .lt[data-id="{GEN}"]')
                    gr, nr = pg.evaluate(ROWPOS, [GEN, PLAIN])
                    check(f"{label}: generated and normal rows: identical button x positions", gr and nr and gr["pos"] == nr["pos"] and len(gr["pos"]) >= 5, (gr, nr))
                    check(f"{label}: ElevenLabs chip on the generated row only, no row button", gr["chip"] == "ElevenLabs" and nr["chip"] == "" and not gr["edit"]
                          and not pg.evaluate("()=>!!document.querySelector('#lib [data-act=elgen]')"), (gr, nr))

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

                    # ---- Rename or move: "Edit text and regenerate…" only for a generated track
                    pg.click(f'#lib .lt[data-id="{PLAIN}"] [data-act=ren]')
                    pg.wait_for_function("()=>fdlg.open")
                    check(f"{label}: rename of a normal track: no regenerate button", pg.evaluate("()=>fd_gen.hidden"), "")
                    pg.keyboard.press("Escape")
                    pg.wait_for_function("()=>!fdlg.open")
                    pg.click(f'#lib .lt[data-id="{GEN}"] [data-act=ren]')
                    pg.wait_for_function("()=>fdlg.open")
                    o = pg.evaluate("""()=>{const g=fd_gen.getBoundingClientRect(),c=[...fdlg.querySelectorAll('.row button')].map(b=>b.textContent),cx=[...fdlg.querySelectorAll('.row button')].map(b=>b.getBoundingClientRect().left);
                        return {vis:!fd_gen.hidden&&!!fd_gen.offsetParent,txt:fd_gen.textContent,order:c,left:cx[0]<cx[1]&&cx[1]<cx[2],gap:cx[1]-g.right,pri:fd_gen.classList.contains('pri'),ti:fd_gen.tabIndex}}""")
                    check(f"{label}: rename of a generated track: secondary button on the left of the footer",
                          o["vis"] and o["txt"] == "Edit text and regenerate…" and o["order"] == ["Edit text and regenerate…", "Cancel", "Save"] and o["left"] and o["gap"] > 20 and not o["pri"] and o["ti"] == 0, o)
                    pg.focus("#fd_folder")
                    pg.keyboard.press("Tab")
                    check(f"{label}: the button is in the dialog's tab order", pg.evaluate("()=>document.activeElement.id") == "fd_gen", pg.evaluate("()=>document.activeElement.id"))
                    pg.fill("#fd_name", "Must not be saved")
                    pg.focus("#fd_gen")
                    pg.keyboard.press("Enter")
                    pg.wait_for_function("()=>eldlg.open&&!fdlg.open")
                    pg.wait_for_function("()=>el_text.value.length>0")
                    o = pg.evaluate("()=>({n:el_name.value,t:el_text.value,note:!el_editnote.hidden,form:!el_form.hidden})")
                    check(f"{label}: it opens Generate pre-filled with the stored text, in edit mode", o == {"n": "Preset", "t": "Preset announcement.", "note": True, "form": True}, o)
                    ids = [x["id"] for x in api.get("/api/library").json["files"]]
                    check(f"{label}: the rename edits were not saved", GEN in ids and not any("Must not be saved" in i for i in ids), "")
                    pg.keyboard.press("Escape")
                    pg.wait_for_function("()=>!eldlg.open")
                    pg.wait_for_timeout(150)
                    foc = pg.evaluate("()=>{const e=document.activeElement;return [e.dataset.act||e.id,(e.closest('.lt')||{dataset:{}}).dataset.id]}")
                    check(f"{label}: Esc returns focus to that row's rename button", foc == ["ren", GEN], foc)

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

                    # ---- Save to folder: a select like Parent Folder, Create new folder… first, validated
                    o = pg.evaluate("()=>({tag:el_folder.tagName,opts:[...el_folder.options].map(o=>o.textContent),fd:[...fd_folder.options].map(o=>o.textContent),val:el_folder.value,nh:el_newrow.hidden,dis:el_savebtn.disabled})")
                    check(f"{label}: folder select: Create new folder… first, then the Rename dialog's folders", o["tag"] == "SELECT" and o["opts"][0] == "Create new folder…"
                          and o["opts"][1:] == o["fd"] and "Generated" in o["opts"] and "Other" in o["opts"] and not any(x.startswith("_") for x in o["opts"]), o)
                    check(f"{label}: default: Generated (it exists), no name field", o["val"] == "Generated" and o["nh"] and not o["dis"], o)
                    pg.select_option("#el_folder", label="Create new folder…")
                    o = pg.evaluate("()=>({nh:el_newrow.hidden,name:el_newname.value,msg:el_fmsg.textContent,cls:el_fmsg.className,dis:el_savebtn.disabled,pick:!!document.getElementById('el_fpick')})")
                    check(f"{label}: Create new folder… reveals Name prefilled Generated; it exists: say so, offer to select it",
                          not o["nh"] and o["name"] == "Generated" and "already exists" in o["msg"] and o["cls"] == "elfmsg warn" and o["dis"] and o["pick"], o)
                    cr = pg.evaluate(CONTRAST, [["#el_fmsg", "text"], ["#el_fpick", "text"]])
                    bad = [x for x in cr if x["ratio"] < 4.5]
                    check(f"{label}: folder message contrast", not bad, bad)
                    pg.click("#el_fpick")
                    o = pg.evaluate("()=>({v:el_folder.value,nh:el_newrow.hidden,focus:document.activeElement.id,dis:el_savebtn.disabled})")
                    check(f"{label}: Select it instead picks the existing folder", o == {"v": "Generated", "nh": True, "focus": "el_folder", "dis": False}, o)
                    pg.select_option("#el_folder", label="Create new folder…")
                    for bad_name, why in (("", "Type a name"), ("a/b", "cannot contain"), ("_x", "cannot start"), ("bad*", "letters, digits"), ("other", "already exists")):
                        pg.fill("#el_newname", bad_name)
                        o = pg.evaluate("()=>({msg:el_fmsg.textContent,dis:el_savebtn.disabled,hid:el_fmsg.hidden})")
                        check(f"{label}: new folder name {bad_name!r} refused ({why})", why in o["msg"] and o["dis"] and not o["hid"], o)
                    pg.fill("#el_newname", "Never created here")
                    o = pg.evaluate("()=>({hid:el_fmsg.hidden,dis:el_savebtn.disabled})")
                    check(f"{label}: a valid new name: no message, Save enabled", o == {"hid": True, "dis": False}, o)
                    pg.select_option("#el_folder", label="Generated")
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
                        o = pg.evaluate("""()=>{const r={};const t=v=>{try{v===null?localStorage.removeItem('cp_el_folder'):localStorage.setItem('cp_el_folder',v)}catch(e){}elFolderFill();return [el_folder.value===ELNEW?'NEW':el_folder.value,el_newname.value,el_newrow.hidden]};
                            r.last=t('Other');r.top=t('');r.gone=t('Gone');const keep=LIBD;LIBD=LIBD.filter(d=>d!=='Generated');r.none=t(null);LIBD=keep;t(null);return r}""")
                        check(f"{label}: default = the last folder used in this browser if it exists (also the top level)", o["last"][0] == "Other" and o["top"][0] == "", o)
                        check(f"{label}: default = Generated when the last one is gone", o["gone"][0] == "Generated", o)
                        check(f"{label}: no Generated folder: Create new folder… with Generated prefilled", o["none"] == ["NEW", "Generated", False], o)
                        pg.select_option("#el_folder", label="Generated")
                        pg.click("#el_savebtn")
                        pg.wait_for_function("()=>!eldlg.open")
                        pg.wait_for_selector('#lib .lt[data-id="Generated/Doors open.mp3"]')
                        row = '#lib .lt[data-id="Generated/Doors open.mp3"]'
                        check(f"{label}: saved: the folder is remembered in this browser", pg.evaluate("()=>localStorage.getItem('cp_el_folder')") == "Generated", "")
                        check(f"{label}: saved track has the ElevenLabs chip", pg.inner_text(f"{row} .elchip") == "ElevenLabs", "")
                        pg.click(f"{row} [data-act=ren]")
                        pg.wait_for_function("()=>fdlg.open&&!fd_gen.hidden")
                        pg.click("#fd_gen")
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
                        check(f"{label}: Esc from an edit asks; Discard returns focus to the row's rename button", foc == "ren", foc)
                        check(f"{label}: Discard deletes the audio", api.get("/api/elevenlabs/job").json["has_temp"] is False, "")
                        # save into a new folder, created only on Save
                        spec(d, 100, "speech3.mp3")
                        pg.click("#lib_gen")
                        pg.wait_for_selector("#eldlg[open] #el_form:not([hidden])")
                        pg.wait_for_selector("#el_voices input[type=radio]")
                        pg.fill("#el_name", "Fresh one")
                        pg.fill("#el_text", "A fresh line.")
                        pg.wait_for_function("()=>!el_go.disabled")
                        pg.click("#el_go")
                        pg.wait_for_selector("#el_done:not([hidden])", timeout=15000)
                        check(f"{label}: the folder used last is the default", pg.evaluate("()=>el_folder.value") == "Generated", pg.evaluate("()=>el_folder.value"))
                        pg.select_option("#el_folder", label="Create new folder…")
                        pg.fill("#el_newname", "Fresh folder")
                        check(f"{label}: the new folder does not exist before Save", not (inst.workdir / "media" / "library" / "Fresh folder").exists(), "")
                        pg.click("#el_savebtn")
                        pg.wait_for_function("()=>!eldlg.open")
                        pg.wait_for_selector('#lib .lt[data-id="Fresh folder/Fresh one.mp3"]')
                        check(f"{label}: saved into the new folder, remembered", pg.evaluate("()=>localStorage.getItem('cp_el_folder')") == "Fresh folder", "")
                        spec(d, 100)
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
