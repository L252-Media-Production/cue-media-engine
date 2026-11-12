#!/usr/bin/env python3
"""Output aliases in the page (2.8.0 output-alias), with the device list of the NUC (CP_TEST_DEVICES): the Live, Preview and Mirror menus and Settings > Audio show the
label ("Dante over IP" under the heading "Network audio"), keep the raw name in the hover text, never list the hidden far end of the loopback card unless it is the
current choice or "Show hidden outputs" is on (dimmed, marked hidden), offer a live-only output in the Live menu only, and show the server's refusal text.
3 skins x light / dark x desktop / tablet. Checks keyboard operation, the focus ring, menus inside the viewport and text contrast (>= 4.5:1, controls >= 3:1).
python tests/test_output_alias_ui.py [SHOT_DIR]    (needs playwright; own disposable player, desktop and tablet only: the phone layout is out of scope)"""
import json, sys, tempfile, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from harness import client
from harness.instance import Instance, PROJECT
from playwright.sync_api import sync_playwright

SH = sys.argv[1] if len(sys.argv) > 1 else None
NUC = ["Dante USB I/O Module, USB Audio", "HDA Intel PCH, ALC233 Analog", "HDA Intel PCH, ALC233 Digital", "HDA Intel PCH, HDMI 0", "HDA Intel PCH, HDMI 1",
       "HDA Intel PCH, HDMI 2", "Loopback, Loopback PCM", "Loopback, Loopback PCM (2)"]
LB1, LB2, USB = NUC[6], NUC[7], NUC[0]
REFUSAL = "Only one program can use Dante over IP. Use it for Live."
fails = []


def chk(n, ok, info=""):
    print(("PASS " if ok else "FAIL ") + n + ("" if ok else "   " + str(info)))
    if not ok:
        fails.append(n)


MENU = """()=>{const l=document.getElementById('cbo_l'),c=document.getElementById('cbo'),R=e=>e.getBoundingClientRect(),cr=R(c);
 return {rows:[...l.querySelectorAll('.cbo-i')].map(e=>({t:e.querySelector('span').textContent,title:e.title,hid:e.classList.contains('hid')})),
  heads:[...l.querySelectorAll('.cbo-g')].map(e=>e.textContent),
  inside:cr.left>=-0.5&&cr.right<=innerWidth+0.5&&cr.top>=-0.5&&cr.bottom<=innerHeight+0.5}}"""
RGB = """(sel)=>{const e=document.querySelector(sel);if(!e)return null;
 const P=s=>{const m=s.match(/rgba?\\(([^)]+)\\)/);if(!m)return null;const a=m[1].split(/[ ,\\/]+/).map(Number);return {r:a[0],g:a[1],b:a[2],a:a.length>3?a[3]:1}};
 let bg={r:255,g:255,b:255},stack=[];for(let n=e;n;n=n.parentElement){const c=P(getComputedStyle(n).backgroundColor);if(c&&c.a>0)stack.push(c);if(c&&c.a>=1)break}
 for(const c of stack.reverse())bg={r:bg.r*(1-c.a)+c.r*c.a,g:bg.g*(1-c.a)+c.g*c.a,b:bg.b*(1-c.a)+c.b*c.a};
 const t=P(getComputedStyle(e).color);return {fg:[t.r,t.g,t.b],bg:[bg.r,bg.g,bg.b],op:+getComputedStyle(e).opacity}}"""


TRACK = """()=>{const P=s=>{const a=s.match(/[\\d.]+/g).map(Number);return {r:a[0],g:a[1],b:a[2],a:a.length>3?a[3]:1}};
 const t=document.getElementById('set_hidout').nextElementSibling;let bg=null;for(let n=t.parentElement;n;n=n.parentElement){const c=P(getComputedStyle(n).backgroundColor);if(c.a>=1){bg=c;break}}
 const cs=getComputedStyle(t),sh=cs.boxShadow.match(/rgba?\\([^)]*\\)/),f=P(sh?sh[0]:cs.backgroundColor);return {fg:[f.r,f.g,f.b],bg:bg?[bg.r,bg.g,bg.b]:[255,255,255]}}"""


def lum(c):
    f = lambda v: (v / 255 / 12.92) if v / 255 <= 0.03928 else (((v / 255) + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2])


def ratio(fg, bg, op=1.0):
    fg = [fg[i] * op + bg[i] * (1 - op) for i in range(3)]
    a, b = sorted((lum(fg), lum(bg)), reverse=True)
    return (a + 0.05) / (b + 0.05)


def contrast(pg, sel):
    r = pg.evaluate(RGB, sel)
    return None if not r else ratio(r["fg"], r["bg"], r["op"])


def menu(pg, btn):
    pg.click(btn)
    pg.wait_for_selector("#cbo:popover-open")
    time.sleep(0.15)
    return pg.evaluate(MENU)


d = Path(tempfile.mkdtemp(prefix="cpalias-ui-"))
(d / "mock_devices.json").write_text(json.dumps(NUC))
with Instance(wav_only=True, project_dir=PROJECT, extra_env={"CP_TEST_DEVICES": str(d)}) as inst, sync_playwright() as p:
    api = client.Api(inst.base_url, osc_port=inst.osc_port)
    api.post("/api/mirror/enable", {"on": True})
    br = p.chromium.launch()
    for skin in ("console", "studio", "stage"):
        for theme in ("light", "dark"):
            for wname, vp, touch in (("desktop", {"width": 1280, "height": 800}, False), ("tablet", {"width": 820, "height": 1100}, True)):
                tag = f"{skin}/{theme}/{wname}"
                api.post("/api/device", {"name": USB}); api.post("/api/preview/device", {"name": None}); api.post("/api/mirror/device", {"name": None})
                c = br.new_context(viewport=vp, has_touch=touch)
                c.add_init_script(f"localStorage.setItem('cp_tour','1');localStorage.setItem('cp_skin','{skin}');localStorage.setItem('cp_theme','{theme}')")
                pg = c.new_page()
                pg.goto(inst.base_url); pg.wait_for_selector("#setbtn"); time.sleep(0.8)
                # --- Live menu
                m = menu(pg, "#dev_out")
                texts = [r["t"] for r in m["rows"]]
                chk(f"{tag} live: Dante over IP is listed", "Dante over IP" in texts, texts)
                chk(f"{tag} live: the hidden far end is not", not any("(2)" in t or LB2 in t for t in texts) and not any("hidden" in t for t in texts), texts)
                chk(f"{tag} live: headings are Wired, Network audio", m["heads"] == ["Wired", "Network audio"], m["heads"])
                row = [r for r in m["rows"] if r["t"] == "Dante over IP"]
                chk(f"{tag} live: hover text keeps the raw name", bool(row) and LB1 in row[0]["title"], row)
                chk(f"{tag} live: the raw loopback name is not shown as its own entry", LB1 not in texts, texts)
                chk(f"{tag} live: menu inside the viewport", m["inside"], m)
                if SH and skin == "console" and theme == "dark" and wname == "desktop":
                    Path(SH).mkdir(parents=True, exist_ok=True)
                    pg.screenshot(path=f"{SH}/live-menu-dante-over-ip.png")
                cg = contrast(pg, "#cbo_l .cbo-g")
                chk(f"{tag} live: group heading contrast >= 4.5", cg is None or cg >= 4.5, cg)
                # keyboard: arrow to Dante over IP and Enter
                for _ in range(len(m["rows"])):
                    if pg.evaluate("document.querySelector('#cbo_l .cbo-i.on span')?.textContent") == "Dante over IP":
                        break
                    pg.keyboard.press("ArrowDown")
                pg.keyboard.press("Enter"); time.sleep(0.8)
                chk(f"{tag} live: the keyboard selects it and the raw name is saved", api.get("/api/devices").json["current"] == LB1, api.get("/api/devices").json["current"])
                st = json.loads((inst.workdir / "state.json").read_text())
                chk(f"{tag} live: state.json holds the raw SDL name", st["audio_device"] == LB1, st.get("audio_device"))
                btn_title = pg.evaluate("document.getElementById('dev_out').title")
                chk(f"{tag} live: the speaker button names label and raw name", "Dante over IP" in btn_title and LB1 in btn_title, btn_title)
                # --- Mirror (Live panel) menu: no live-only entry
                if pg.is_visible("#mdev_cb"):
                    m = menu(pg, "#mdev_cb")
                    chk(f"{tag} mirror: no Dante over IP, no hidden", not any("Dante over IP" in r["t"] or "hidden" in r["t"] or "Loopback" in r["t"] for r in m["rows"]), [r["t"] for r in m["rows"]])
                    chk(f"{tag} mirror: inside the viewport", m["inside"], m)
                    pg.keyboard.press("Escape")
                # --- Settings > Audio
                pg.click("#setbtn"); pg.wait_for_selector("#settings[open]")
                if pg.is_visible("#set_tabs [data-tab=audio]"):
                    pg.click("#set_tabs [data-tab=audio]")
                else:
                    pg.click("[data-sec=audio] .sh")
                m = menu(pg, "#set_pv_cb")
                texts = [r["t"] for r in m["rows"]]
                chk(f"{tag} preview: no Dante over IP, no hidden entry", not any(("Dante" in t and "IP" in t) or "Loopback" in t for t in texts), texts)
                chk(f"{tag} preview: inside the viewport", m["inside"], m)
                pg.keyboard.press("Escape")
                # the refusal text replaces the raw error (forced: the menu never offers it)
                pg.evaluate(f"()=>{{const o=document.createElement('option');o.value={json.dumps(LB1)};o.textContent='x';set_pv.appendChild(o);set_pv.value={json.dumps(LB1)};savePreviewDev()}}")
                time.sleep(0.8)
                msg = pg.evaluate("document.getElementById('setmsg').textContent")
                chk(f"{tag} preview: the refusal text is shown", msg == REFUSAL, msg)
                chk(f"{tag} preview: nothing was saved", api.get("/api/devices").json["preview"] is None)
                # --- Show hidden outputs
                cb = pg.locator("#set_hidout")
                chk(f"{tag} checkbox exists and is off", cb.count() == 1 and not cb.is_checked())
                pg.focus("#set_hidout")
                pg.keyboard.press("Shift+Tab"); pg.keyboard.press("Tab")                      # arrive by keyboard so :focus-visible applies
                ring = pg.evaluate("()=>{const i=document.getElementById('set_hidout');return document.activeElement===i&&getComputedStyle(i.nextElementSibling).outlineStyle!=='none'}")
                chk(f"{tag} checkbox: keyboard focus ring is drawn", ring)
                off = pg.evaluate(TRACK)
                chk(f"{tag} checkbox: off track vs the row >= 3:1", ratio(off["fg"], off["bg"]) >= 3.0, (off, ratio(off["fg"], off["bg"])))
                pg.keyboard.press("Space"); time.sleep(0.8)
                chk(f"{tag} hidden: Space switches it on", cb.is_checked())
                m = menu(pg, "#set_pv_cb")
                hrows = [r for r in m["rows"] if "hidden" in r["t"]]
                chk(f"{tag} hidden: listed dimmed with the word hidden", len(hrows) == 1 and hrows[0]["hid"] and "Loopback, Loopback PCM (2)" in hrows[0]["t"], m["rows"])
                ch = pg.evaluate(RGB, "#cbo_l .cbo-i.hid span")
                chk(f"{tag} hidden: dimmed row text contrast >= 4.5", ch and ratio(ch["fg"], ch["bg"], ch["op"]) >= 4.5, ch)
                chk(f"{tag} hidden: Dante over IP still absent for Preview", not any("Dante over IP" in r["t"] for r in m["rows"]), [r["t"] for r in m["rows"]])
                pg.keyboard.press("Escape")
                if SH and skin == "console" and theme == "dark" and wname == "desktop":
                    menu(pg, "#set_pv_cb")
                    pg.evaluate("document.getElementById('setmsg').textContent=''")
                    pg.screenshot(path=f"{SH}/settings-audio-hidden-shown.png")
                    pg.keyboard.press("Escape")
                # switch back off: gone again
                cb.click(); time.sleep(0.6)
                m = menu(pg, "#set_pv_cb")
                chk(f"{tag} hidden: off again, not listed", not any("hidden" in r["t"] for r in m["rows"]), [r["t"] for r in m["rows"]])
                pg.keyboard.press("Escape")
                # --- the selected hidden output stays visible
                api.post("/api/device", {"name": LB2}); time.sleep(0.3)
                pg.evaluate("loadDevs()"); time.sleep(0.5)
                pg.evaluate("document.getElementById('settings').close()")
                m = menu(pg, "#dev_out")
                cur = [r for r in m["rows"] if "hidden" in r["t"]]
                chk(f"{tag} selected hidden output stays visible, marked hidden", len(cur) == 1 and LB2 in cur[0]["t"], m["rows"])
                lbl = pg.evaluate("document.getElementById('dev_cb')?.textContent||document.getElementById('dev').selectedOptions[0].textContent")
                chk(f"{tag} the Live select shows it, not an empty choice", "Loopback" in lbl, lbl)
                pg.keyboard.press("Escape")
                c.close()
    br.close()
print("\n%d failed" % len(fails) if fails else "\nall passed")
sys.exit(1 if fails else 0)
