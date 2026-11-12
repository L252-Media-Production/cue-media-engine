#!/usr/bin/env python3
"""RAM indicator UI (2.7.3 Phase 2): header pill left of Cache (loading ring + N/M + bar / ready check + N/M / full alert circle + Full; order pill, Cache, RAM; 2 s hysteresis), the marker before each track name (filled green = in RAM, spinning blue ring =
loading, grey hollow ring = not loaded; shapes differ, each has a title and aria-label), "N of M in RAM" in the playlist header, and the Go button's
"Loading… N s" state with its hint (display only). 3 skins x dark/light x desktop / phone / touch.
    python tests/test_ram_ui.py [SHOT_DIR]      (needs playwright; starts its own disposable player)"""
import os
import re
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from harness import client                       # noqa: E402
from harness.instance import Instance, PROJECT   # noqa: E402

FULLTIP = "Cache full. The oldest tracks are dropped to make room. Tracks not in RAM start after a short wait."
RC1_H = {"console": (28, 97.3), "studio": (32, 102.4), "stage": (46, 118)}      # header height of v2.7.3-rc1 (desktop, phone width)
FAILS = []
SHOTS = sys.argv[1] if len(sys.argv) > 1 else None


def check(name, ok, info=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"   {info}"))
    if not ok:
        FAILS.append(name)


MEM = dict(ram_total=33285996544, ram_used=7600000000, proc=200000000, cache=4400000000, cache_budget=12884901888, cache_tracks=35)
SHOW = """r=>{window.__ramShow(r);const c=document.getElementById('ramchip'),q=s=>c.querySelector(s),vis=e=>getComputedStyle(e).display!=='none',cr=c.getBoundingClientRect(),top=document.querySelector('.top'),
  mc=document.getElementById('mem_cachew'),mr=document.querySelector('.mr');
  return {st:c.dataset.st,hidden:c.hidden,txt:q('.rct').innerText,ring:vis(q('.rcr')),check:vis(q('.rck')),alert:vis(q('.rca')),bar:vis(q('.rcb')),w:q('.rcb b').style.width,
    spin:getComputedStyle(q('.rcr')).animationName,shim:getComputedStyle(q('.rcb b')).animationName,title:c.title,aria:c.getAttribute('aria-label'),h:cr.height,
    inView:cr.left>=-0.5&&cr.right<=innerWidth+0.5,topOver:top.scrollWidth>top.clientWidth+1,cacheCol:getComputedStyle(mc.querySelector('b:not([style*=none])')).color,
    cacheAmber:mc.classList.contains('full')}}"""
ORDER = """()=>{const k=[...document.getElementById('memro').children].map(e=>e.id),c=document.getElementById('ramchip').getBoundingClientRect(),m=document.getElementById('mem_cachew').getBoundingClientRect(),
  r=document.querySelector('.mr').getBoundingClientRect(),n=e=>e.innerText.replace(/\u00a0/g,' ').trim();
  return {ids:k,pillBeforeCache:c.right<=m.left+0.5||c.bottom<=m.top,cacheBeforeRam:m.right<=r.left+0.5||m.bottom<=r.top,sameRow:Math.abs(c.top+c.height/2-(m.top+m.height/2))<12,
    cache:n(document.getElementById('mem_cachew')),ram:n(document.querySelector('.mr')),gap:m.left-c.right,
    cl:[...document.querySelectorAll('#memro *')].filter(e=>e.getBoundingClientRect().width&&(e.scrollWidth>e.clientWidth+1&&getComputedStyle(e).overflow!=='visible')).length,
    ro:document.getElementById('memro').getBoundingClientRect().right<=innerWidth+0.5&&document.getElementById('memro').getBoundingClientRect().left>=-0.5}}"""
HYST = """()=>{let now=1000000;Date.now=()=>now;const f=r=>{window.__ramShow(r);return document.getElementById('ramchip').dataset.st},c=document.getElementById('ramchip'),
  L=dict=>Object.assign({used_mb:100,budget_mb:12288,tracks_total:10,tracks_in_ram:4,loading:true,full:false,rev:1},dict),R={tracks_in_ram:10,loading:false};
  c._k='';RAMV.st=null;RAMV.rdy=0;const out=[];out.push(f(L({})));                 // loading, at once
  out.push(f(L(R)));now+=1000;out.push(f(L(R)));now+=900;out.push(f(L(R)));        // ready held 0 / 1.0 / 1.9 s: still loading
  now+=200;out.push(f(L(R)));                                                      // 2.1 s: ready
  out.push(f(L({})));                                                              // back to loading: at once
  out.push(f(L(R)));now+=500;out.push(f(L({})));now+=5000;out.push(f(L(R)));       // ready for 0 s after a flap: still loading (timer restarted)
  now+=2100;out.push(f(L(R)));clearTimeout(RAMV.tm);return out}"""
DOTS = """()=>{const set=(i,k,v)=>{PL[i].tracks[k].ram=v};set(0,0,'in');set(0,1,'loading');set(0,2,'out');PL[0].ram_in=1;PL[0].ram_total=3;lastHtml='';renderLists(LASTS);
  const d=[...document.querySelectorAll('#lists li.t')].slice(0,3).map(li=>li.querySelector('.rd')),cs=e=>getComputedStyle(e);
  return d.map((e,n)=>!e?null:({cls:e.className,w:e.getBoundingClientRect().width,h:e.getBoundingClientRect().height,bg:cs(e).backgroundColor,bw:cs(e).borderTopWidth,bt:cs(e).borderTopColor,an:cs(e).animationName,
    title:e.title,label:e.getAttribute('aria-label'),role:e.getAttribute('role'),clip:(()=>{const r=e.getBoundingClientRect(),l=e.closest('li').getBoundingClientRect();return r.left>=l.left&&r.right<=l.right&&r.top>=l.top-1&&r.bottom<=l.bottom+1})(),
    before:e.nextElementSibling&&e.nextElementSibling.classList.contains('tn')}))}"""


def main():
    from playwright.sync_api import sync_playwright
    if SHOTS:
        os.makedirs(SHOTS, exist_ok=True)
    with Instance(wav_only=True, project_dir=os.environ.get("RU_PROJECT") or PROJECT) as inst, sync_playwright() as p:
        api = client.Api(inst.base_url, osc_port=inst.osc_port)
        api.post("/api/playlists", {"name": "Show"}); api.post("/api/playlists/0/add", {"files": ["tone_a.wav", "tone_b.wav", "tone_c.wav"]}); api.get("/api/0/0/focus")
        br = p.chromium.launch()
        for skin in ("console", "studio", "stage"):
            for theme in ("dark", "light"):
                for tag, kw in (("desktop", dict(viewport={"width": 1400, "height": 1000})), ("phone", dict(viewport={"width": 420, "height": 900})),
                                ("touch", dict(viewport={"width": 430, "height": 932}, has_touch=True, is_mobile=True))):
                    label = f"{skin}/{theme}/{tag}"
                    c = br.new_context(**kw)
                    c.add_init_script(f"localStorage.setItem('cp_tour','1');localStorage.setItem('cp_skin','{skin}');localStorage.setItem('cp_theme','{theme}')")
                    pg = c.new_page(); errs = []
                    pg.on("pageerror", lambda e: errs.append(str(e)))
                    pg.goto(inst.base_url); pg.wait_for_selector("#lists li.t")
                    # the real thing: the warm-up finishes, the pill is Ready, no row is marked (2.7.4: a track in RAM has no marker), the header says 3 of 3
                    pg.wait_for_function("document.getElementById('ramchip').dataset.st==='ready'&&document.querySelectorAll('#lists li.t').length===3&&document.querySelector('.plram')&&document.querySelector('.plram').textContent==='3 of 3 in RAM'", timeout=20000)
                    check(f"{label}: real data: pill Ready, rows in RAM carry no marker and no played check", pg.evaluate("document.querySelectorAll('#lists li.t .rd, #lists li.t .rck').length") == 0)
                    check(f"{label}: playlist header says 3 of 3 in RAM", pg.evaluate("document.querySelector('.plram')&&document.querySelector('.plram').textContent")  == "3 of 3 in RAM")
                    pg.evaluate("window.__ramShow=ramShow;ramShow=()=>{}")      # freeze the page's own refresh so forced states stay put
                    pg.evaluate("m=>memShow(m)", MEM)
                    pg.evaluate("r=>{ramchip._k='';RAMV.st=null;window.__ramShow(r)}", dict(used_mb=4300, budget_mb=12288, tracks_total=35, tracks_in_ram=35, loading=False, full=False, rev=9))
                    od = pg.evaluate(ORDER)
                    check(f"{label}: order in the DOM and on screen: pill, Cache, RAM", od["ids"] == ["ramchip", "mem_cachew", ""], od)
                    check(f"{label}: pill directly left of Cache, Cache before RAM, one row, inside the window", od["pillBeforeCache"] and od["cacheBeforeRam"] and od["sameRow"] and od["ro"] and od["cl"] == 0, od)
                    if tag != "desktop":
                        check(f"{label}: phone text 'Cache 4.1 / 12.0 GB' and 'RAM 23%'", od["cache"] == "Cache 4.1 / 12.0 GB" and od["ram"] == "RAM 23%", od)
                    else:
                        check(f"{label}: Cache and RAM text with units on both numbers", re.fullmatch(r"Cache \d+\.\d GB / \d+\.\d GB", od["cache"]) and re.fullmatch(r"RAM \d+% \(\d+\.\d GB / \d+ GB\)", od["ram"]), od)
                        check(f"{label}: a non-breaking space before the slash in the RAM text", "GB\u00a0/ " in pg.evaluate("document.querySelector('.mr').textContent"))
                    hh = pg.evaluate("document.querySelector('.top').getBoundingClientRect().height")
                    check(f"{label}: header no taller than rc1 ({RC1_H[skin][tag != 'desktop']} px)", hh <= RC1_H[skin][tag != "desktop"] + 0.5, hh)
                    shapes = {}
                    for name, r, st, txt, tip in (
                            ("loading", dict(used_mb=4300, budget_mb=12288, tracks_total=48, tracks_in_ram=31, loading=True, full=False, rev=1), "loading", "31/48", "31 of 48 tracks in RAM. Tracks not in RAM start after a short wait."),
                            ("ready", dict(used_mb=4300, budget_mb=12288, tracks_total=35, tracks_in_ram=35, loading=False, full=False, rev=2), "ready", "35/35", "35 of 35 tracks in RAM. Tracks not in RAM start after a short wait."),
                            ("full", dict(used_mb=12288, budget_mb=12288, tracks_total=212, tracks_in_ram=150, loading=False, full=True, rev=3), "full", "Full", FULLTIP)):
                        pg.evaluate("RAMV.st=null;RAMV.rdy=0;document.getElementById('ramchip')._k=''")
                        d = pg.evaluate(SHOW, r); shapes[name] = (d["ring"], d["check"], d["alert"], d["bar"])
                        check(f"{label}: pill {name}: state, text, title and aria-label", d["st"] == st and d["txt"] == txt and d["title"] == tip and d["aria"] == tip, d)
                        check(f"{label}: pill {name}: 24 px high, visible, inside the window, header not overflowing", d["h"] == 24 and not d["hidden"] and d["inView"] and not d["topOver"], d)
                        if name == "loading":
                            check(f"{label}: pill loading: ring, bar at 64.6 %, shimmer and spin", d["ring"] and d["bar"] and not d["check"] and not d["alert"] and d["w"].startswith("64.58") and d["shim"] == "rcsh" and d["spin"] == "rdspin", d)
                        if name == "ready":
                            check(f"{label}: pill ready: check, no bar, Cache not amber", d["check"] and not d["ring"] and not d["alert"] and not d["bar"] and not d["cacheAmber"], d)
                        if name == "full":
                            check(f"{label}: pill full: alert circle, 'Full', Cache numbers amber", d["alert"] and not d["ring"] and not d["check"] and not d["bar"] and d["cacheAmber"] and d["cacheCol"] == "rgb(217, 138, 0)", d)
                        if SHOTS and theme == "dark" and tag != "touch":
                            pg.locator(".top").screenshot(path=f"{SHOTS}/pill-{name}-{skin}-{tag}.png")
                    check(f"{label}: the three shapes differ", len(set(shapes.values())) == 3, shapes)
                    pg.evaluate("RAMV.st=null;RAMV.rdy=0;document.getElementById('ramchip')._k=''")
                    d0 = pg.evaluate(SHOW, dict(used_mb=0, budget_mb=12288, tracks_total=0, tracks_in_ram=0, loading=False, full=False, rev=4))
                    check(f"{label}: no playlist tracks (M = 0): pill hidden", d0["hidden"], d0)
                    hy = pg.evaluate(HYST)
                    check(f"{label}: hysteresis: loading at once, ready after 2 s, back to loading at once, a flap restarts the 2 s",
                          hy == ["loading", "loading", "loading", "loading", "ready", "loading", "loading", "loading", "loading", "ready"], hy)
                    pg.evaluate("Date.now=()=>performance.timeOrigin+performance.now()")
                    # reduced motion: static ring, plain bar
                    pg.emulate_media(reduced_motion="reduce")
                    pg.evaluate("RAMV.st=null;RAMV.rdy=0;document.getElementById('ramchip')._k=''")
                    d = pg.evaluate(SHOW, dict(used_mb=4300, budget_mb=12288, tracks_total=48, tracks_in_ram=31, loading=True, full=False, rev=1))
                    check(f"{label}: reduced motion: no spin, no shimmer, ring and bar still there", d["spin"] == "none" and d["shim"] == "none" and d["ring"] and d["bar"], d)
                    pg.emulate_media(reduced_motion="no-preference")
                    # row markers
                    dots = pg.evaluate(DOTS)
                    check(f"{label}: a track in RAM has no marker; loading and not loaded do (12 px, before the name)", dots[0] is None, dots)
                    dots = dots[1:]
                    cls = [d["cls"].split()[-1] for d in dots]
                    check(f"{label}: markers loading / out, 12 px, before the name", cls == ["loading", "out"] and all(d["w"] == 12 and d["h"] == 12 and d["before"] for d in dots), dots)
                    check(f"{label}: shapes differ (spinning ring / hollow ring), not colour alone",
                          dots[0]["bw"] == "2px" and dots[1]["bw"] == "2px" and dots[0]["an"] == "rdspin" and dots[1]["an"] == "none" and dots[0]["bt"] != dots[1]["bt"], dots)
                    check(f"{label}: markers have role, title and aria-label", [d["label"] for d in dots] == ["Loading", "Not loaded, starts after a short wait"]
                          and [d["title"] for d in dots] == [d["label"] for d in dots] and all(d["role"] == "img" for d in dots), dots)
                    check(f"{label}: markers are not clipped", all(d["clip"] for d in dots), dots)
                    check(f"{label}: header text for 1 of 3", pg.evaluate("document.querySelector('.plram').textContent") == "1 of 3 in RAM")
                    # Go button: loading state, same size, hint, back to Go
                    g0 = pg.evaluate("(()=>{const r=document.querySelector('.cuego').getBoundingClientRect();return [r.width,r.height]})()")
                    pg.evaluate("GOLOAD={t:Date.now()-3000,id:'0/0'};LASTS.loading='tone_a';LASTS.live_id='-';goBusy()")
                    g = pg.evaluate("(()=>{const b=document.querySelector('.cuego'),r=b.getBoundingClientRect(),s=b.querySelector('span').getBoundingClientRect();return {t:b.textContent.trim(),w:r.width,h:r.height,sp:!!b.querySelector('.gsp'),title:b.title,busy:b.getAttribute('aria-busy'),hint:prepmsg.textContent,wait:b.classList.contains('wait'),clip:s.left>=r.left-0.5&&s.right<=r.right+0.5&&s.bottom<=r.bottom+0.5}})()")
                    check(f"{label}: Go shows a spinner and 'Loading… 3 s' (counting)", g["t"].startswith("Loading… 3") and g["sp"] and g["wait"] and g["busy"] == "true", g)
                    check(f"{label}: Go keeps its size and the text is not clipped", abs(g["w"] - g0[0]) < 0.5 and abs(g["h"] - g0[1]) < 0.5 and g["clip"], (g, g0))
                    check(f"{label}: hint says the cued track is not in RAM yet", g["title"] == g["hint"] == "Cued track is not in RAM yet. It starts as soon as it is decoded.", g)
                    if SHOTS and theme == "dark" and tag != "touch":
                        pg.locator("#fs").screenshot(path=f"{SHOTS}/go-loading-{skin}-{tag}.png")
                    pg.evaluate("LASTS.loading='-';LASTS.live_id='0/0';goBusy()")
                    g2 = pg.evaluate("(()=>{const b=document.querySelector('.cuego');return {t:b.textContent.trim(),wait:b.classList.contains('wait'),busy:b.getAttribute('aria-busy')}})()")
                    check(f"{label}: Go is back to normal once the track is live", g2["t"] == "Go" and not g2["wait"] and g2["busy"] == "false", g2)
                    if SHOTS and theme == "dark" and tag != "touch":
                        pg.locator("#lists .pl").first.screenshot(path=f"{SHOTS}/rows-{skin}-{tag}.png")
                    check(f"{label}: no page errors", not errs, errs)
                    c.close()
        br.close()
    print(f"\n{len(FAILS)} failure(s)")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
