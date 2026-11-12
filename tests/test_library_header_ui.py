#!/usr/bin/env python3
"""Library header (2.7.4-rc2): one row at every width, Hidden button = icon + count, three plain icon buttons, on-state tint, no overflow.
3 skins x dark/light x desktop / 390 px phone.    python tests/test_library_header_ui.py      (needs playwright; own disposable player)"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from harness import client                       # noqa: E402
from harness.instance import Instance, PROJECT   # noqa: E402

FAILS = []


def check(name, ok, info=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"   {info}"))
    if not ok:
        FAILS.append(name)


GEOM = """()=>{const q=s=>document.querySelector(s),r=e=>e.getBoundingClientRect(),h3=r(q('#libh3')),col=r(q('#libcol')),hd=q('#libhd');
 const bs=['lib_hidden','lib_expand','lib_collapse'].map(i=>q('#'+i)).filter(b=>!b.hidden);
 const info=bs.map(b=>{const c=getComputedStyle(b),br=r(b),sv=b.querySelector('svg');return {id:b.id,top:br.top,right:br.right,w:br.width,h:br.height,
   bg:c.backgroundColor,bw:c.borderTopWidth,col:c.color,txt:b.textContent.trim(),title:b.title,al:b.getAttribute('aria-label'),sv:!!sv,path:sv?sv.innerHTML:''}});
 const sum=q('#libsum'),sr=r(sum);
 return {info,h3bot:h3.bottom,h3top:h3.top,sumTop:sr.top,sumBot:sr.bottom,colRight:col.right,colLeft:col.left,
  over:document.documentElement.scrollWidth>document.documentElement.clientWidth+1,hdOver:hd.scrollWidth>hd.clientWidth+1,
  sumClip:sum.scrollWidth>sum.clientWidth+1,sumText:sum.textContent}}"""
PATH = {"lib_expand": "M15 3h6v6", "lib_collapse": "M4 14h6v6", "lib_hidden": "m3 3 18 18"}


def lum(c):
    import re
    v = [float(x) for x in re.findall(r"[\d.]+", c)[:3]]
    if c.startswith("color(srgb"):
        v = [x * 255 for x in v]
    v = [x / 255 for x in v]
    v = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in v]
    return 0.2126 * v[0] + 0.7152 * v[1] + 0.0722 * v[2]


def contrast(a, b):
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def main():
    from playwright.sync_api import sync_playwright
    with Instance(wav_only=True, project_dir=PROJECT) as inst, sync_playwright() as p:
        api = client.Api(inst.base_url, osc_port=inst.osc_port)
        for d in ("Alpha", "Delta"):
            api.post("/api/library/folder", {"path": d})
        br = p.chromium.launch()
        for skin in ("console", "studio", "stage"):
            for theme in ("dark", "light"):
                for tag, vp in (("desktop", {"width": 1400, "height": 1000}), ("phone", {"width": 390, "height": 900})):
                    label = f"{skin}/{theme}/{tag}"
                    api.post("/api/library/folder/flags", {"path": "Delta", "hidden": False})
                    c = br.new_context(viewport=vp)
                    c.add_init_script(f"localStorage.setItem('cp_tour','1');localStorage.setItem('cp_skin','{skin}');localStorage.setItem('cp_theme','{theme}')")
                    pg = c.new_page(); errs = []
                    pg.on("pageerror", lambda e: errs.append(str(e)))
                    pg.goto(inst.base_url); pg.wait_for_selector("#lib .fd")
                    g = pg.evaluate(GEOM)
                    check(f"{label}: no hidden folder: Hidden button absent, two buttons", [b["id"] for b in g["info"]] == ["lib_expand", "lib_collapse"], g["info"])
                    api.post("/api/library/folder/flags", {"path": "Delta", "hidden": True})
                    pg.reload(); pg.wait_for_selector("#lib_hidden:not([hidden])")
                    for state in ("hidden folder, toggle off", "hidden folder, toggle on", "none again"):
                        if state == "hidden folder, toggle on":
                            pg.evaluate("libHidden()")
                        if state == "none again":
                            pg.evaluate("libHidden()")
                            api.post("/api/library/folder/flags", {"path": "Delta", "hidden": False})
                            pg.reload(); pg.wait_for_selector("#lib .fd")
                        g = pg.evaluate(GEOM); bs = g["info"]; tl = f"{label} [{state}]"
                        want = ["lib_expand", "lib_collapse"] if state == "none again" else ["lib_hidden", "lib_expand", "lib_collapse"]
                        check(f"{tl}: buttons in order {want}", [b["id"] for b in bs] == want, bs)
                        check(f"{tl}: one row (no button below the title's bottom, storage text on the title row)",
                              all(b["top"] < g["h3bot"] for b in bs) and g["sumTop"] < g["h3bot"], g)
                        check(f"{tl}: last button inside the card; no page or header overflow", bs[-1]["right"] <= g["colRight"] + 0.5 and not g["over"] and not g["hdOver"], g)
                        check(f"{tl}: storage text not clipped", not g["sumClip"], g["sumText"])
                        check(f"{tl}: plain (transparent, no border), >= 32 px tap targets, matching icons", all(b["bg"] in ("rgba(0, 0, 0, 0)", "transparent") and b["bw"] == "0px" and b["w"] >= 31.5 and b["h"] >= 31.5 and b["sv"] and PATH[b["id"]] in b["path"] for b in bs), bs)
                        check(f"{tl}: titles and aria-labels", all(b["title"] and b["al"] == b["title"] for b in bs), bs)
                        if "lib_hidden" in [b["id"] for b in bs]:
                            hb = bs[0]
                            check(f"{tl}: Hidden is icon and number only, labelled 'Hidden folders: 1'", hb["txt"] == "1" and hb["al"] == "Hidden folders: 1" and hb["title"] == "Hidden folders: 1", hb)
                            bg = pg.evaluate("getComputedStyle(document.querySelector('#libcol')).backgroundColor")
                            if state.endswith("on"):
                                check(f"{tl}: on-state colour differs from off (tinted icon and count)", hb["col"] != BASE.get(label), hb["col"])
                            else:
                                BASE[label] = hb["col"]
                    # keyboard focus ring on each button
                    api.post("/api/library/folder/flags", {"path": "Delta", "hidden": True})
                    pg.reload(); pg.wait_for_selector("#lib_hidden:not([hidden])")
                    for i in ("lib_hidden", "lib_expand", "lib_collapse"):
                        pg.focus(f"#{i}"); pg.keyboard.press("Shift")
                        o = pg.evaluate(f"(()=>{{const s=getComputedStyle(document.getElementById('{i}'));return [s.outlineStyle,s.outlineWidth]}})()")
                        check(f"{label}: focus ring on #{i}", o[0] != "none" and o[1] != "0px", o)
                    # N follows hide / unhide
                    api.post("/api/library/folder/flags", {"path": "Alpha", "hidden": True}); pg.reload(); pg.wait_for_selector("#lib_hidden:not([hidden])")
                    t = pg.evaluate("(()=>{const b=document.getElementById('lib_hidden');return [b.textContent.trim(),b.title]})()")
                    check(f"{label}: N updates to 2 with two hidden folders", t == ["2", "Hidden folders: 2"], t)
                    api.post("/api/library/folder/flags", {"path": "Alpha", "hidden": False})
                    # on-state contrast against the card
                    pg.reload(); pg.wait_for_selector("#lib_hidden:not([hidden])"); pg.evaluate("libHidden()")
                    cc = pg.evaluate("(()=>{const b=document.getElementById('lib_hidden');let e=b;while(e&&getComputedStyle(e).backgroundColor.match(/0\\)$|transparent/))e=e.parentElement;return [getComputedStyle(b).color,getComputedStyle(e).backgroundColor]})()")
                    ratio = contrast(*cc)
                    check(f"{label}: Hidden on-state contrast >= 3:1 (icon) - got {ratio:.2f}", ratio >= 3.0, cc)
                    check(f"{label}: no page errors", not errs, errs)
                    c.close()
        api.post("/api/library/folder/flags", {"path": "Delta", "hidden": False})
    print("\nFAILED:" if FAILS else "\nall passed", *FAILS, sep="\n  ")
    sys.exit(1 if FAILS else 0)


BASE = {}
if __name__ == "__main__":
    main()
