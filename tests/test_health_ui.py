#!/usr/bin/env python3
"""2.8.0 health dot and panel (desktop and tablet widths; the phone layout is out of scope).
Real player (own disposable instance, a local webhook receiver) + Playwright (Chromium):
  * the dot in all four states x 3 skins x light / dark: its colour against the real header background >= 3:1, and a different SHAPE per state
    (so the state does not rest on colour alone), title and accessible name
  * the panel for every check state: rows, sentence only when the row is not ok, icons, order, text >= 4.5:1, icons >= 3:1
  * keyboard: Enter opens, focus moves into the panel, Tab reaches Copy report and Open Variables, Esc closes and focus returns to the dot; the page stays usable
  * Copy report: plain text with version, state, checks, driver, devices, uptime, date and NO address / webhook / path
  * Settings > System > Health and alerts: switches save, a bad address is refused, the Send test chip shows green or red
    python tests/test_health_ui.py [SHOT_DIR]"""
import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from harness import client                       # noqa: E402
from harness.instance import Instance, PROJECT   # noqa: E402

FAILS = []
SHOTS = sys.argv[1] if len(sys.argv) > 1 else None
SECRET = "SECRETKEY123"

LUM = r"""
const num=s=>(s.match(/-?[\d.]+(?:e-?\d+)?/g)||[]).map(Number);
const parse=s=>{if(!s||s==='transparent')return null;const n=num(s);if(s.startsWith('color(')){return n.length<3?null:[n[0]*255,n[1]*255,n[2]*255,n.length>3?n[3]:1]}if(s.startsWith('rgb')){return [n[0],n[1],n[2],n.length>3?n[3]:1]}return null};
const over=(t,b)=>{const a=t[3];return [t[0]*a+b[0]*(1-a),t[1]*a+b[1]*(1-a),t[2]*a+b[2]*(1-a),1]};
const bgOf=el=>{const ch=[];for(let e=el;e;e=e.parentElement){const c=parse(getComputedStyle(e).backgroundColor);if(c&&c[3]>0)ch.push(c)}let b=[255,255,255,1];for(let i=ch.length-1;i>=0;i--)b=over(ch[i],b);return b};
const lum=c=>{const f=v=>{v/=255;return v<=0.03928?v/12.92:Math.pow((v+0.055)/1.055,2.4)};return 0.2126*f(c[0])+0.7152*f(c[1])+0.0722*f(c[2])};
const ratio=(a,b)=>{const l1=lum(a),l2=lum(b);return (Math.max(l1,l2)+0.05)/(Math.min(l1,l2)+0.05)};
"""
DOT = "()=>{" + LUM + """
  const d=document.getElementById('hdot');const ps=getComputedStyle(d,'::before');
  const ring=parseFloat(ps.borderTopWidth)>0;const fg=parse(ring?ps.borderTopColor:ps.backgroundColor);const bg=bgOf(d);
  return {ratio:Math.round(ratio(fg,bg)*100)/100,shape:ps.clipPath+'|'+ps.borderRadius+'|'+ps.borderTopWidth,title:d.title,label:d.getAttribute('aria-label')}}"""
PANEL = "()=>{" + LUM + """
  const root=document.getElementById('hpop');const out=[];
  for(const e of [root,...root.querySelectorAll('*')]){const r=e.getBoundingClientRect();if(!r.width||!r.height)continue;const cs=getComputedStyle(e);if(cs.display==='none'||cs.visibility==='hidden')continue;
   const isSvg=e.tagName.toLowerCase()==='svg';const own=[...e.childNodes].some(n=>n.nodeType===3&&n.textContent.trim().length);if(!isSvg&&!own)continue;
   if(e.classList.contains('vh'))continue;
   const back=bgOf(e);const fg0=parse(cs.color);const fg=fg0[3]<1?over(fg0,back):fg0;const rt=ratio(fg,back);const need=isSvg?3:4.5;
   out.push({e:(e.id||e.className&&e.className.baseVal||e.className||e.tagName).toString().slice(0,24),txt:(e.textContent||'').trim().slice(0,22),ratio:Math.round(rt*10)/10,need,bad:rt<need})}
  return {n:out.length,bad:out.filter(x=>x.bad)}}"""
BTN = "()=>{" + LUM + """
  const out=[];for(const b of document.querySelectorAll('#hpop button')){const cs=getComputedStyle(b);const bc=parse(cs.borderTopColor);const back=bgOf(b.parentElement);
   out.push({id:b.id,border:bc?Math.round(ratio(bc,back)*10)/10:0})}return out}"""


def check(name, ok, info=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"   {info}"))
    if not ok:
        FAILS.append(name)


class Hook:
    def __init__(self):
        self.got = []
        outer = self

        class H(BaseHTTPRequestHandler):
            def do_POST(self):
                body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
                if self.path.startswith("/missing"):
                    self.send_response(404); self.end_headers(); return
                outer.got.append(json.loads(body.decode("utf-8")))
                self.send_response(200); self.end_headers()

            def log_message(self, *a):
                pass
        self.srv = HTTPServer(("127.0.0.1", 0), H)
        self.port = self.srv.server_address[1]
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()


CHECKS = lambda **o: [  # noqa: E731
    {"id": "live_output", "status": o.get("live", "ok"), "title": "Live output", "text": o.get("live_t", "")},
    {"id": "preview_output", "status": o.get("pv", "ok"), "title": "Preview output", "text": o.get("pv_t", "")},
    {"id": "audio_engine", "status": o.get("eng", "ok"), "title": "Audio engine", "text": o.get("eng_t", ""), "note": "Restarted 0 times since start"},
    {"id": "companion", "status": o.get("comp", "ok"), "title": "Companion", "text": o.get("comp_t", "")},
    {"id": "disk", "status": o.get("disk", "ok"), "title": "Media drive space", "text": o.get("disk_t", "")},
    {"id": "cache", "status": o.get("cache", "ok"), "title": "Track cache", "text": o.get("cache_t", "")},
    {"id": "uptime", "status": "ok", "title": "Player uptime", "text": "Up 3 d 4 h"}]
CASES = {
    "starting": dict(status="starting", state="starting", summary="", checks=CHECKS()),
    "ready": dict(status="ready", state="ready", summary="", checks=CHECKS()),
    "degraded": dict(status="ready", state="degraded", summary="Disk space low", checks=CHECKS(disk="warn", disk_t="The media drive is running low: 3.0 GB free (1 %). Delete files you no longer need.", comp="unknown", comp_t="Companion has not asked for anything since the player started.")),
    "problem": dict(status="error", state="problem", summary="Live output problem", checks=CHECKS(live="bad", live_t="The live output (Dante USB) is not available. Start or plug in the device, then press Refresh devices and choose it again.", eng="bad", eng_t="The audio output has stopped moving. The watchdog is restarting the audio engine.", pv="warn", pv_t="The preview output (Phones) is not available. Plug it in.")),
}


def main():
    from playwright.sync_api import sync_playwright
    if SHOTS:
        os.makedirs(SHOTS, exist_ok=True)
    hook = Hook()
    with Instance(wav_only=True, project_dir=os.environ.get("PP_PROJECT") or PROJECT) as inst, sync_playwright() as p:
        api = client.Api(inst.base_url, osc_port=inst.osc_port)
        br = p.chromium.launch()
        ctx = br.new_context(viewport={"width": 1280, "height": 900}, permissions=["clipboard-read", "clipboard-write"])
        ctx.add_init_script("try{localStorage.setItem('cp_tour','1')}catch(e){}")      # the first-visit tour stays away
        pg = ctx.new_page()
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.goto(inst.base_url + "/")
        pg.wait_for_selector("#hdot")
        pg.wait_for_timeout(1500)
        check("the dot is a button with an accessible name", pg.evaluate("document.getElementById('hdot').tagName") == "BUTTON" and "Health:" in pg.evaluate("hdot.getAttribute('aria-label')"))
        real = pg.evaluate("HLAST&&HLAST.st")
        check("the real player reports a state", real in ("starting", "ready", "degraded", "problem"), real)

        # freeze the page's own poll so the injected states stay on screen
        pg.evaluate("window.render=async()=>{}")
        pg.wait_for_timeout(1200)
        shapes = {}
        for skin in ("console", "studio", "stage"):
            for theme in ("light", "dark"):
                pg.evaluate(f"setLook('skin','{skin}');setLook('theme','{theme}')")
                for name, h in CASES.items():
                    pg.evaluate("h=>healthSync(h)", h)
                    r = pg.evaluate(DOT)
                    check(f"dot {name} {skin}/{theme}: contrast {r['ratio']}:1 >= 3", r["ratio"] >= 3.0)
                    shapes.setdefault(name, set()).add(r["shape"])
                    check(f"dot {name} {skin}/{theme}: title and name say {name}", name.capitalize() in r["title"] and name in r["label"].lower(), r)
        sh = [next(iter(v)) for v in shapes.values()]
        check("the four states have four different shapes (not colour alone)", len(set(sh)) == 4, shapes)
        check("a state keeps one shape in every skin and theme", all(len(v) == 1 for v in shapes.values()), shapes)

        # the panel, each state, 3 skins x light/dark
        for skin in ("console", "studio", "stage"):
            for theme in ("light", "dark"):
                pg.evaluate(f"setLook('skin','{skin}');setLook('theme','{theme}')")
                for name, h in CASES.items():
                    pg.evaluate("h=>healthSync(h)", h)
                    pg.evaluate("hpClose(false);hpOpen()")
                    rows = pg.evaluate("[...document.querySelectorAll('#hp_list li')].map(l=>({id:l.dataset.id,s:l.dataset.s,sentence:!!l.querySelector('.hpx2:not(.hpn)'),n:l.querySelectorAll('svg').length}))")
                    if skin == "console" and theme == "light":
                        check(f"panel {name}: seven rows in order", [r["id"] for r in rows] == ["live_output", "preview_output", "audio_engine", "companion", "disk", "cache", "uptime"], rows)
                        check(f"panel {name}: a sentence only on rows that are not ok", all(r["sentence"] == (r["s"] != "ok" and r["id"] != "uptime" and bool(CASES[name]["checks"][i]["text"])) for i, r in enumerate(rows)), rows)
                        check(f"panel {name}: every row has an icon", all(r["n"] == 1 for r in rows))
                        check(f"panel {name}: state word", pg.evaluate("hp_state.textContent") == name.capitalize())
                    c = pg.evaluate(PANEL)
                    check(f"panel {name} {skin}/{theme}: text 4.5:1, icons 3:1 ({c['n']} items)", not c["bad"], c["bad"])
                    bc = pg.evaluate(BTN)
                    check(f"panel {name} {skin}/{theme}: buttons keep a 3:1 border", all(b["border"] >= 3.0 for b in bc), bc)
                    if SHOTS and skin == "console" and theme == "dark" or SHOTS and skin == "studio" and theme == "light":
                        pg.screenshot(path=f"{SHOTS}/panel-{name}-{skin}-{theme}.png", clip={"x": 0, "y": 0, "width": 700, "height": 520})
                pg.evaluate("hpClose(false)")

        # keyboard
        pg.evaluate("setLook('skin','console');setLook('theme','dark');healthSync(" + json.dumps(CASES["degraded"]) + ")")
        pg.focus("#hdot")
        pg.keyboard.press("Enter")
        check("Enter opens the panel", pg.evaluate("!hpop.hidden && hdot.getAttribute('aria-expanded')==='true'"))
        check("focus moves into the panel", pg.evaluate("hpop.contains(document.activeElement)"))
        seen = []
        for _ in range(4):
            pg.keyboard.press("Tab")
            seen.append(pg.evaluate("document.activeElement.id"))
        check("Tab reaches Close, Copy report and Open Variables", {"hp_x", "hp_copy", "hp_vars"} <= set(seen), seen)
        pg.keyboard.press("Escape")
        check("Esc closes the panel", pg.evaluate("hpop.hidden"))
        check("focus returns to the dot", pg.evaluate("document.activeElement.id") == "hdot")
        check("the page is not blocked while the panel is open", (pg.evaluate("hpClose(false);hpOpen();document.body.style.position||'static'") in ("", "static")) and pg.evaluate("!document.querySelector('dialog[open]')"))
        pg.evaluate("hpOpen()")
        check("the Audio engine row always shows the restart count", pg.evaluate("document.querySelector('#hp_list li[data-id=audio_engine] .hpn').textContent") == "Restarted 0 times since start")
        pg.mouse.click(900, 600)
        check("a click elsewhere closes it", pg.evaluate("hpop.hidden"))

        # tablet width
        pg.set_viewport_size({"width": 820, "height": 1100})
        pg.evaluate("hpOpen()")
        r = pg.evaluate("(()=>{const b=hpop.getBoundingClientRect();return {l:b.left,r:b.right,w:innerWidth}})()")
        check("tablet 820 px: the panel fits the window", r["l"] >= 0 and r["r"] <= r["w"], r)
        if SHOTS:
            pg.screenshot(path=f"{SHOTS}/panel-tablet.png", clip={"x": 0, "y": 0, "width": 820, "height": 560})
        pg.evaluate("hpClose(false)")
        pg.set_viewport_size({"width": 1280, "height": 900})

        # Copy report: the real server builds it
        pg.evaluate("window.render=undefined;delete window.render") if False else None
        text = api.get("/api/health/report").json["text"]
        for want in ("Cue Media Engine health report", "Version:", "State:", "Checks:", "- Live output:", "Audio driver:", "Live output:", "Preview output:", "Up ", "Date:"):
            check(f"report has '{want}'", want in text, text[:200])
        api.post("/api/settings/health", {"push": {"url": f"http://127.0.0.1:{hook.port}/hook/{SECRET}", "enabled": True}})
        api.post("/api/settings", {"companion_host": "192.168.77.5", "companion_osc_port": 12321})
        text = api.get("/api/health/report").json["text"]
        check("the report holds no webhook address, no Companion address, no paths", SECRET not in text and "192.168.77.5" not in text and "127.0.0.1" not in text and "/media/" not in text and "library" not in text.lower().replace("library folder", ""), text)
        pg.evaluate("hpOpen()")
        pg.click("#hp_copy")
        pg.wait_for_function("hp_msg.textContent.length>0")
        clip = pg.evaluate("navigator.clipboard.readText()")
        check("Copy report puts the report on the clipboard", "Cue Media Engine health report" in clip and SECRET not in clip, clip[:120])
        with ctx.expect_page() as newp:
            pg.click("#hp_vars")
        check("Open Variables opens /variables", newp.value.url.endswith("/variables"), newp.value.url)
        newp.value.close()
        pg.evaluate("hpClose(false)")

        # Settings block
        pg.reload()
        pg.wait_for_selector("#hdot")
        pg.evaluate("openSettings()")
        pg.wait_for_selector("#settings[open]")
        pg.evaluate("setTab('system')")
        pg.wait_for_timeout(500)
        check("the Health and alerts block is on the System tab", pg.is_visible("#set_wd"))
        check("watchdog is on by default", pg.is_checked("#set_wd"))
        pg.click("#set_wd + i") if False else pg.evaluate("set_wd.click()")
        pg.wait_for_timeout(300)
        check("the watchdog switch saves", api.get("/api/settings/health").json["watchdog"] is False)
        pg.evaluate("set_wd.click()")
        pg.wait_for_timeout(300)
        check("... and back on", api.get("/api/settings/health").json["watchdog"] is True)
        check("the saved address shows only the host", "127.0.0.1" in pg.evaluate("hs_host.textContent") and SECRET not in pg.content())
        if os.environ.get("HS_DEBUG"):
            pg.screenshot(path=os.environ["HS_DEBUG"])
        pg.fill("#set_pushurl", "ftp://example.com/x")
        pg.evaluate("set_pushurl.dispatchEvent(new Event('change'))")
        pg.wait_for_timeout(300)
        check("a non-http address is refused", "http" in pg.evaluate("setmsg.textContent") and api.get("/api/settings/health").json["push"]["host"].startswith("http://127.0.0.1"))
        pg.evaluate("set_ev_watchdog.click()")
        pg.wait_for_timeout(300)
        check("an event checkbox saves", api.get("/api/settings/health").json["push"]["events"]["watchdog"] is False)
        pg.evaluate("set_ev_watchdog.click()")
        pg.click("#hs_test")
        pg.wait_for_function("hs_chip.className.includes('ok')||hs_chip.className.includes('bad')")
        check("Send a test message: green chip with the time", "ok" in pg.evaluate("hs_chip.className") and "Sent" in pg.evaluate("hs_chip.textContent"), pg.evaluate("hs_chip.textContent"))
        check("... and the receiver got text and content", hook.got and hook.got[-1]["text"] == hook.got[-1]["content"] and hook.got[-1]["event"] == "test", hook.got[-1:])
        api.post("/api/settings/health", {"push": {"url": f"http://127.0.0.1:{hook.port}/missing/{SECRET}"}})
        pg.evaluate("hsLoad()")
        pg.click("#hs_test")
        pg.wait_for_function("hs_chip.className.includes('bad')")
        check("a refused address gives a red chip with the reason", pg.evaluate("hs_chip.textContent") == "Refused (HTTP 404)", pg.evaluate("hs_chip.textContent"))
        check("... and the failure line", "Refused (HTTP 404)" in pg.evaluate("hs_err.textContent"))
        if SHOTS:
            pg.screenshot(path=f"{SHOTS}/settings-health-and-alerts.png")
        # Player name field: 3 skins x 2 themes, keyboard, contrast
        pg.evaluate("setTab('system')")
        for skin in ("console", "studio", "stage"):
            for theme in ("light", "dark"):
                pg.evaluate(f"setLook('skin','{skin}');setLook('theme','{theme}')")
                r = pg.evaluate("()=>{" + LUM + """
                  const out={};const row=document.getElementById('set_pname').closest('.sr');
                  const lab=row.querySelector('label'),inp=document.getElementById('set_pname'),hint=document.getElementById('hs_name');
                  const t=(e)=>{const cs=getComputedStyle(e);const b=bgOf(e);const f=parse(cs.color);return ratio(f[3]<1?over(f,b):f,b)};
                  out.label=t(lab);out.hint=t(hint);out.input=t(inp);
                  const bc=parse(getComputedStyle(inp).borderTopColor);out.border=ratio(bc,bgOf(row));
                  out.vis=inp.getBoundingClientRect().width>40;out.w=inp.getBoundingClientRect().right<=document.getElementById('settings').getBoundingClientRect().right;return out}""")
                check(f"player name {skin}/{theme}: text 4.5:1 (label {r['label']:.1f}, hint {r['hint']:.1f}, input {r['input']:.1f}), border 3:1 ({r['border']:.1f})", min(r["label"], r["hint"], r["input"]) >= 4.5 and r["border"] >= 3.0 and r["vis"] and r["w"], r)
        pg.evaluate("setLook('skin','console');setLook('theme','dark')")
        pg.focus("#set_pname")
        pg.keyboard.press("Control+A")
        pg.keyboard.type("  L252 NUC ")
        pg.keyboard.press("Tab")
        pg.wait_for_timeout(300)
        check("player name: typing and Tab saves it, trimmed", api.get("/api/settings/health").json["player_name"] == "L252 NUC")
        check("... and the line under the field shows the name in use", pg.evaluate("hs_name.textContent") == "Messages are sent as: L252 NUC", pg.evaluate("hs_name.textContent"))
        check("a 40-character limit is on the field", pg.evaluate("set_pname.maxLength") == 40)
        if SHOTS:
            pg.screenshot(path=f"{SHOTS}/settings-player-name.png")
        api.post("/api/settings/health", {"player_name": ""})
        pg.keyboard.press("Escape")
        pg.set_viewport_size({"width": 390, "height": 800})          # phone layout is out of scope: only "no errors"
        pg.evaluate("hpOpen();hpClose(false)")
        pg.evaluate("openSettings()") if False else None
        check("no page errors", not errors, errors[:3])
        api.post("/api/settings/health", {"push": {"url": "", "enabled": False}})
        br.close()
    print("\nFAILED: " + ", ".join(FAILS) if FAILS else "\nALL PASS")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
