#!/usr/bin/env python3
"""2.9.1 web page: the pinned header, the Preview meters without their outline, waveforms on by default, and nothing of it at phone width.

    python tests/test_pin_header_ui.py [--shots DIR]     (needs playwright; starts its own disposable player)

  1. Pin header (Settings > Look > Appearance, per browser, cp_pinhdr on|off, default on, html[data-pinhdr] set by the head script before the first
     paint): the top bar sticks to the top, the one-line Live strip (#ms) sits directly under it (no gap, no overlap) at 1366x768 and 1024x768 in
     every skin; off = the header scrolls away and the strip is back at the very top; default, on, off, a bad stored value and storage that throws.
  2. The header covers nothing that should be on top of it: Settings and the Generate audio dialog (top layer, page lock keeps the header and the
     scroll position), the health panel, the output menu, the file-information popover; a row scrolled into view is not hidden under the bars;
     Page width still applies to the header content; the header content does not move at the top of the page.
  3. The Preview pair in the Live panel (#lvl .pcol) and the strip's PRV chip (#ms .mg.pvc) have no outline, border or shadow in 3 skins x 2 themes,
     idle / live playing / Solo; the Live bars keep their green.
  4. Waveforms: on for a fresh browser, a stored off ('0') stays off and is not rewritten, '1' on, a bad value and failing storage = on.
  5. Phone width (420x900 and a touch phone): the header is not sticky, the strip stays at the top, the Pin header row is hidden, the Preview pair keeps
     its outline, waveforms stay off by default, and the page geometry is the same whatever cp_pinhdr says.
"""
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from harness import client                       # noqa: E402
from harness.instance import Instance, PROJECT   # noqa: E402

FAILS = []
SHOTS = sys.argv[sys.argv.index("--shots") + 1] if "--shots" in sys.argv else None


def check(name, ok, info=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"   {info}"))
    if not ok:
        FAILS.append(name)


EARLY = "document.addEventListener('DOMContentLoaded',()=>{window.__ph0=document.documentElement.dataset.pinhdr});"
GEO = """()=>{const t=document.querySelector('body>.top'),r=t.getBoundingClientRect(),m=document.getElementById('ms'),q=m.getBoundingClientRect(),g=k=>{try{return localStorage.getItem(k)}catch(e){return 'ERR'}};
 return {y:scrollY,pos:getComputedStyle(t).position,hdr:[r.top,r.bottom,r.height],ms:[q.top,q.bottom,q.height],mshidden:m.hidden,attr:document.documentElement.dataset.pinhdr,
  stored:g('cp_pinhdr'),box:set_pinhdr.checked,row:getComputedStyle(document.querySelector('#settings .phrow')).display}}"""


def page(br, inst, store=None, kw=None, extra=""):
    c = br.new_context(**(kw or dict(viewport={"width": 1366, "height": 768})))
    init = "localStorage.setItem('cp_tour','1');"
    for k, v in (store or {}).items():
        init += f"localStorage.setItem('{k}','{v}');"
    c.add_init_script(init + extra + EARLY)
    pg = c.new_page(); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(inst.base_url); pg.wait_for_selector("#lists li.t"); pg.wait_for_timeout(300)
    return c, pg, errs


def scroll(pg, y):
    pg.evaluate(f"scrollTo(0,{y})"); pg.wait_for_timeout(350)


def main():
    from playwright.sync_api import sync_playwright
    with Instance(wav_only=True, project_dir=os.environ.get("TI_PROJECT") or PROJECT) as inst, sync_playwright() as p:
        api = client.Api(inst.base_url, osc_port=inst.osc_port)
        for i in range(3):
            api.post("/api/playlists", {"name": f"P{i}"}); api.post(f"/api/playlists/{i}/add", {"files": ["long_120s.wav", "tone_a.wav"] * 6})
        api.get("/api/0/0")
        br = p.chromium.launch()

        # 1. pinned header and the strip under it
        sizes = {}
        for skin in ("console", "studio", "stage"):
            for w, h in ((1366, 768), (1024, 768)):
                c, pg, errs = page(br, inst, {"cp_skin": skin}, kw=dict(viewport={"width": w, "height": h}))
                d0 = pg.evaluate(GEO)
                scroll(pg, 1200)
                d = pg.evaluate(GEO)
                tag = f"{skin} {w}x{h}"
                check(f"{tag}: default on, header sticky and at the very top", d["attr"] == "on" and d["pos"] == "sticky" and abs(d["hdr"][0]) < 0.5, d)
                check(f"{tag}: strip shown directly under the header (no gap, no overlap)", not d["mshidden"] and abs(d["ms"][0] - d["hdr"][1]) < 0.75, d)
                check(f"{tag}: header the same height at the top and pinned", abs(d0["hdr"][2] - d["hdr"][2]) < 0.5, (d0, d))
                sizes[tag] = (round(d["hdr"][2], 1), round(d["ms"][2], 1), round(d["ms"][1], 1))
                if SHOTS and skin == "console":
                    pg.screenshot(path=os.path.join(SHOTS, f"pinhdr-{w}x{h}.png"))
                check(f"{tag}: no page errors", not errs, errs)
                c.close()
        for tag, (hh, mh, tot) in sizes.items():
            vh = int(tag.split("x")[1])
            print(f"     {tag}: header {hh} px, strip {mh} px, together {tot} px = {tot / vh * 100:.1f} % of {vh}")
            check(f"{tag}: header + strip under a fifth of the height", tot <= vh / 5, tot)

        # 1b. the option: default, on, off, kept, bad value, storage failure
        c, pg, errs = page(br, inst)
        pg.evaluate("openSettings();setTab('look')"); pg.wait_for_function("settings.open")
        d = pg.evaluate(GEO)
        check("option: default on, checkbox ticked, nothing stored, set before the first paint",
              d["attr"] == "on" and d["box"] and d["stored"] is None and pg.evaluate("window.__ph0") == "on", d)
        check("option: the row sits right below Page width", pg.evaluate("document.querySelector('#settings .pwrow').nextElementSibling.classList.contains('phrow')"))
        check("option: has a visible label and an accessible name", pg.evaluate("set_pinhdr.labels[0].textContent==='Pin header'&&set_pinhdr.getAttribute('aria-label')==='Pin header'"))
        pg.evaluate("set_pinhdr.click()")
        d = pg.evaluate(GEO)
        check("option off: stored 'off', header no longer sticky", d["attr"] == "off" and d["stored"] == "off" and d["pos"] != "sticky" and not d["box"], d)
        pg.evaluate("settings.close()"); pg.wait_for_timeout(200); scroll(pg, 1200)
        d = pg.evaluate(GEO)
        check("option off: the header scrolled away and the strip is at the very top", d["hdr"][1] <= 0 and not d["mshidden"] and abs(d["ms"][0]) < 0.5, d)
        pg.reload(); pg.wait_for_selector("#lists li.t")
        check("option off: kept after a reload, before the first paint", pg.evaluate("window.__ph0") == "off")
        pg.evaluate("openSettings();setTab('look')"); pg.wait_for_function("settings.open"); pg.evaluate("set_pinhdr.click()"); pg.evaluate("settings.close()")
        pg.wait_for_timeout(200); scroll(pg, 1500)
        d = pg.evaluate(GEO)
        check("option on again: stored 'on', strip under the header", d["stored"] == "on" and d["pos"] == "sticky" and abs(d["ms"][0] - d["hdr"][1]) < 0.75, d)
        check("option: no page errors", not errs, errs)
        c.close()
        for label, store, extra, want in (("bad value", {"cp_pinhdr": "banana"}, "", "on"), ("stored on", {"cp_pinhdr": "on"}, "", "on"),
                                          ("storage throws", {"cp_pinhdr": "off"}, "Storage.prototype.getItem=function(){throw new Error('blocked')};", "on")):
            c, pg, errs = page(br, inst, store, extra=extra)
            d = pg.evaluate(GEO)
            check(f"option {label}: {want}", d["attr"] == want and pg.evaluate("window.__ph0") == want and d["pos"] == ("sticky" if want == "on" else "static"), d)
            if label == "storage throws":
                pg.evaluate("Storage.prototype.setItem=function(){throw new Error('blocked')};openSettings();setTab('look');set_pinhdr.click()")
                check("option, storage throws: switching still works for this page", pg.evaluate("document.documentElement.dataset.pinhdr") == "off")
            check(f"option {label}: no page errors", not errs, errs)
            c.close()

        # 2. nothing hidden under the header
        c, pg, errs = page(br, inst)
        scroll(pg, 1200)
        hb = pg.evaluate(GEO)["hdr"][1]
        top_hit = "(x,y)=>{const e=document.elementFromPoint(x,y);return e?!!e.closest('body>.top'):null}"
        pg.evaluate("openSettings()"); pg.wait_for_function("settings.open"); pg.wait_for_timeout(200)
        g = pg.evaluate(GEO)
        check("Settings open: page locked at its place, header still at the top", g["hdr"][0] == 0 or abs(g["hdr"][0]) < 0.5, g)
        check("Settings open: the header is under the modal (top layer)", pg.evaluate(f"({top_hit})(20,20)") is False)
        pg.evaluate("settings.close()"); pg.wait_for_timeout(150)
        check("Settings closed: exact scroll position back", pg.evaluate("scrollY") == 1200, pg.evaluate("scrollY"))
        pg.evaluate("elOpen(null,lib_gen)"); pg.wait_for_timeout(300)
        check("Generate audio dialog: open, header under it", pg.evaluate("eldlg.open") and pg.evaluate(f"({top_hit})(20,20)") is False)
        pg.evaluate("eldlg.close()"); pg.wait_for_timeout(150)
        check("Generate audio closed: scroll position back", pg.evaluate("scrollY") == 1200)
        pg.evaluate("hpOpen()"); pg.wait_for_timeout(150)
        r = pg.evaluate("(()=>{const r=hpop.getBoundingClientRect(),e=document.elementFromPoint(r.left+r.width/2,r.top+10);return {top:r.top,mine:!!(e&&e.closest('#hpop'))}})()")
        check("health panel: below the health dot, on top of everything there", r["mine"] and r["top"] >= 0, r)
        pg.evaluate("hpClose(true)")
        pg.evaluate("outOpen(dev,dev_out)"); pg.wait_for_timeout(200)
        r = pg.evaluate("(()=>{const r=cbo.getBoundingClientRect(),e=document.elementFromPoint(r.left+r.width/2,r.top+r.height/2);return {h:r.height,mine:!!(e&&e.closest('#cbo'))}})()")
        check("output menu: on top", r["h"] > 0 and r["mine"], r)
        pg.keyboard.press("Escape"); pg.wait_for_timeout(100)
        fid = pg.evaluate("document.querySelector('#lists li.t [data-info]')?.dataset.info||null")
        if fid:
            pg.evaluate("(()=>{const b=[...document.querySelectorAll('#lists li.t [data-info]')].find(b=>{const r=b.getBoundingClientRect();return r.top>200&&r.bottom<innerHeight});b&&b.click()})()")
            pg.wait_for_timeout(300)
            r = pg.evaluate("(()=>{const r=infopop.getBoundingClientRect(),e=document.elementFromPoint(r.left+r.width/2,r.top+8);return {vis:!infopop.hidden,top:r.top,mine:!!(e&&e.closest('#infopop'))}})()")
            check("file-information popover: on top of the header and strip", r["vis"] and r["mine"], r)
            pg.evaluate("infoClose&&infoClose()")
        # anchors: a row scrolled to the top of the view stays clear of the header and the strip
        r = pg.evaluate("""(()=>{const li=[...document.querySelectorAll('#lists li.t')].at(-3);li.scrollIntoView({block:'start'});return new Promise(ok=>setTimeout(()=>{
            const a=li.getBoundingClientRect(),m=document.getElementById('ms'),mb=m.hidden?0:m.getBoundingClientRect().bottom,hb=document.querySelector('body>.top').getBoundingClientRect().bottom;
            ok({row:a.top,bars:Math.max(mb,hb)})},400))})()""")
        check("anchor: a row scrolled into view is below the header and the strip", r["row"] >= r["bars"] - 0.5, r)
        check("z-order checks: no page errors", not errs, errs)
        c.close()

        # the header content does not move at the top of the page, and Page width applies to it
        rects = {}
        for v in ("on", "off"):
            c, pg, errs = page(br, inst, {"cp_pinhdr": v, "cp_pagew": "wide"}, kw=dict(viewport={"width": 2560, "height": 1200}))
            rects[v] = pg.evaluate("[...document.querySelectorAll('body>.top>*')].map(e=>{const r=e.getBoundingClientRect();return [Math.round(r.left),Math.round(r.top),Math.round(r.width)]})"
                                   ".concat([[Math.round(document.getElementById('now').getBoundingClientRect().top)]])")
            if v == "on":
                w = pg.evaluate("(()=>{const t=document.querySelector('body>.top'),s=getComputedStyle(t),b=document.body.getBoundingClientRect(),bs=getComputedStyle(document.body);"
                                "return {content:t.clientWidth-parseFloat(s.paddingLeft)-parseFloat(s.paddingRight),body:b.width-parseFloat(bs.paddingLeft)-parseFloat(bs.paddingRight),bw:b.width,hw:t.getBoundingClientRect().width}})()")
                check("Page width Wide: the header spans the page (1800 px) and its content the body's content width", abs(w["hw"] - 1800) < 1 and abs(w["content"] - w["body"]) < 1, w)
            c.close()
        check("at the top of the page the header content and the page below it sit exactly where they do unpinned", rects["on"] == rects["off"], rects)

        # 3. no outline around the Preview meters
        OUT = """()=>{const a=getComputedStyle(document.querySelector('#lvl .pcol')),b=getComputedStyle(document.querySelector('#ms .mg.pvc'));
         const none=s=>(s.outlineStyle==='none'||parseFloat(s.outlineWidth)===0)&&s.boxShadow==='none'&&(s.borderStyle==='none'||parseFloat(s.borderTopWidth)===0||s.borderTopColor==='rgba(0, 0, 0, 0)');
         return {pcol:none(a),strip:none(b),vis:!pvlvl.hidden&&pvlvl.getBoundingClientRect().width>0,o:[a.outlineStyle,a.outlineWidth,a.outlineColor,a.boxShadow],s:[b.borderTopColor,b.boxShadow],
          live:getComputedStyle(document.querySelector('#lbars .vm')).backgroundImage}}"""
        for skin in ("console", "studio", "stage"):
            for theme in ("dark", "light"):
                c, pg, errs = page(br, inst, {"cp_skin": skin, "cp_theme": theme})
                for state, js in (("previewing", "PVCUR.state='playing';pvmSync()"), ("paused preview", "PVCUR.state='paused';pvmSync()"),
                                  ("Solo", "PVCUR.state='stopped';pv.classList.add('solo');pvmSync()")):
                    pg.evaluate(js); pg.evaluate("ms.hidden=false")
                    d = pg.evaluate(OUT)
                    check(f"{skin}/{theme} {state}: Preview pair and strip chip have no outline", d["vis"] and d["pcol"] and d["strip"], d)
                check(f"{skin}/{theme}: the Live bars keep their green", "60, 179, 113" in d["live"] or "3cb371" in d["live"].lower(), d["live"])
                if SHOTS and skin == "console" and theme == "dark":
                    pg.locator("#lvl").screenshot(path=os.path.join(SHOTS, "lvl-preview.png"))
                c.close()

        # 4. waveforms default
        WV = "()=>{let s;try{s=localStorage.getItem('cp_wave')}catch(e){s='ERR'}return {wave:WAVE,cls:document.body.classList.contains('wave'),wfl:getComputedStyle(wfl).display,stored:s}}"
        for label, store, extra, want, stored in (("fresh browser", {}, "", True, None), ("stored off", {"cp_wave": "0"}, "", False, "0"),
                                                  ("stored on", {"cp_wave": "1"}, "", True, "1"), ("bad value", {"cp_wave": "yes"}, "", True, "yes"),
                                                  ("storage throws", {"cp_wave": "0"}, "Storage.prototype.getItem=function(){throw new Error('blocked')};", True, "ERR")):
            c, pg, errs = page(br, inst, store, extra=extra)
            pg.wait_for_timeout(400)
            d = pg.evaluate(WV)
            check(f"waveforms, {label}: {'on' if want else 'off'}, storage not rewritten", d["wave"] == want and d["cls"] == want and (d["wfl"] != "none") == want and d["stored"] == stored, d)
            if label == "fresh browser":
                pg.evaluate("openSettings();setTab('look')")
                check("waveforms, fresh browser: the switch is on", pg.evaluate("set_wave.checked"))
                check("waveforms, fresh browser: a layout export says waveforms on", pg.evaluate("layExportObj('t',true).obj.appearance.waveforms") is True)
            check(f"waveforms, {label}: no page errors", not errs, errs)
            c.close()

        # 5. phone width: nothing changes, whatever cp_pinhdr says
        PH = """()=>{const t=document.querySelector('body>.top'),R=s=>{const e=document.querySelector(s);if(!e)return null;const r=e.getBoundingClientRect();return [r.left,r.top,r.width,r.height].map(Math.round)};
         const a=getComputedStyle(document.querySelector('#lvl .pcol'));
         return {pos:getComputedStyle(t).position,hdrh:getComputedStyle(document.documentElement).getPropertyValue('--hdrh').trim(),msTop:getComputedStyle(ms).top,
          row:getComputedStyle(document.querySelector('#settings .phrow')).display,wave:WAVE,outline:a.outlineStyle+' '+a.outlineWidth,
          geo:[R('body>.top'),R('#cl'),R('#lvl'),R('#fs'),R('#plcol'),R('#libcol'),document.documentElement.scrollHeight]}}"""
        for tag, kw in (("phone", dict(viewport={"width": 420, "height": 900})),
                        ("touch", dict(viewport={"width": 430, "height": 932}, has_touch=True, is_mobile=True))):
            seen = {}
            for store in ({}, {"cp_pinhdr": "on"}, {"cp_pinhdr": "off"}):
                c, pg, errs = page(br, inst, store, kw=kw)
                pg.evaluate("PVCUR.state='playing';pvmSync()")
                d = pg.evaluate(PH)
                name = store.get("cp_pinhdr", "unset")
                check(f"{tag} {name}: header not sticky, strip top 0, Pin header row hidden", d["pos"] == "static" and d["hdrh"] in ("0px", "") and d["msTop"] == "0px" and d["row"] == "none", d)
                check(f"{tag} {name}: Preview pair keeps its outline, waveforms off by default", d["outline"] == "solid 1px" and d["wave"] is False, d)
                scroll(pg, 1500)
                g = pg.evaluate(GEO)
                check(f"{tag} {name}: scrolled, the header is gone and the strip at the very top", g["hdr"][1] <= 0 and (g["mshidden"] or abs(g["ms"][0]) < 0.5), g)
                seen[name] = str(d["geo"])
                check(f"{tag} {name}: no page errors", not errs, errs)
                c.close()
            check(f"{tag}: the page geometry is the same for every Pin header value", len(set(seen.values())) == 1, seen)
        br.close()
    print(f"\n{'FAILED: ' + str(len(FAILS)) if FAILS else 'ALL PASSED'}")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
