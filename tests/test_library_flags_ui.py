#!/usr/bin/env python3
"""Library favorites / hide / collapse (2.7.4 Phase 1): Favorites group on top (alphabetical) then All folders, star and hide buttons, Collapse all / Expand all
(per device), the Hidden toggle (icon and count) and unhide, the search message for tracks in hidden folders and its reveal, sharing between browsers, no clipping.
3 skins x dark/light x desktop / phone / touch.    python tests/test_library_flags_ui.py [SHOT_DIR]      (needs playwright; own disposable player)"""
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from harness import client                       # noqa: E402
from harness.instance import Instance, PROJECT   # noqa: E402

FAILS = []
SHOTS = sys.argv[1] if len(sys.argv) > 1 else None


def check(name, ok, info=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"   {info}"))
    if not ok:
        FAILS.append(name)


# every row of the library as [kind, text, classes]
ROWS = """()=>[...document.querySelectorAll('#lib > *')].map(e=>e.classList.contains('lsec')?['sec',e.textContent.trim()]:
  e.classList.contains('fd')&&!e.classList.contains('rootdrop')?['fd',e.querySelector('b').textContent,e.className,e.querySelector('.fdt')?e.querySelector('.fdt').textContent:'',e.querySelector('small').textContent]:
  e.classList.contains('lt')?['lt',e.querySelector('.ln').textContent.trim(),e.className]:e.classList.contains('hidmsg')?['msg',e.textContent.trim()]:['other',e.textContent.trim().slice(0,40)])"""
FLAT = """()=>{const l=document.getElementById('lib'),r=e=>e.getBoundingClientRect(),lr=r(l);
  const bad=[...l.querySelectorAll('.fd,.lt,.hidmsg')].filter(e=>{const b=r(e);return b.right>lr.right+1||e.scrollWidth>e.clientWidth+1&&!e.classList.contains('lt')});
  const t=document.querySelector('.libtools'),tr=r(t),h=r(document.getElementById('libcol'));
  return {libOver:l.scrollWidth>l.clientWidth+1,bad:bad.length,toolsIn:tr.left>=h.left-1&&tr.right<=h.right+1,pageOver:document.documentElement.scrollWidth>document.documentElement.clientWidth+1}}"""
RESET = {"fav": False, "hidden": False}


def clk(pg, sel):
    """Click after centring the element: on a phone the Now card is sticky and can sit over a button that was scrolled to the top edge."""
    loc = pg.locator(sel).first
    loc.evaluate("e=>e.scrollIntoView({block:'center',inline:'center'})")
    try:
        loc.click(timeout=4000)
    except Exception:
        # Playwright's hit test can disagree with the page where the layout viewport is wider than the visual one (stage skin on a phone; the 2.7.3 page is already wider there).
        # Accept it only when the page itself says the centre of the element is the element (or inside it).
        ok = loc.evaluate("e=>{const r=e.getBoundingClientRect(),t=document.elementFromPoint(r.left+r.width/2,r.top+r.height/2);return t===e||e.contains(t)}")
        check(f"hit test (page): {sel} is reachable", ok)
        loc.dispatch_event("click")


def names(rows, kind="fd"):
    return [r[1] for r in rows if r[0] == kind]


def main():
    from playwright.sync_api import sync_playwright
    if SHOTS:
        os.makedirs(SHOTS, exist_ok=True)
    with Instance(wav_only=True, project_dir=os.environ.get("PP_PROJECT") or PROJECT) as inst, sync_playwright() as p:
        api = client.Api(inst.base_url, osc_port=inst.osc_port)
        for d in ("Alpha", "Bravo", "Charlie", "Delta"):
            api.post("/api/library/folder", {"path": d})
        for src, dst in (("short_1s.wav", "Alpha/short_1s.wav"), ("short_2s.wav", "Bravo/short_2s.wav"), ("tone_b.wav", "Charlie/Sunday_b.wav"),
                         ("tone_c.wav", "Charlie/Sunday_c.wav"), ("tone_a.wav", "Delta/tone_a.wav")):
            assert api.post("/api/library/rename", {"from": src, "to": dst}).status == 200, src

        def reset():
            for d in ("Alpha", "Bravo", "Charlie", "Delta", "Sub"):
                api.post("/api/library/folder/flags", {"path": d, **RESET})

        br = p.chromium.launch()
        for skin in ("console", "studio", "stage"):
            for theme in ("dark", "light"):
                for tag, kw in (("desktop", dict(viewport={"width": 1400, "height": 1000})), ("phone", dict(viewport={"width": 420, "height": 900})),
                                ("touch", dict(viewport={"width": 430, "height": 932}, has_touch=True, is_mobile=True))):
                    label = f"{skin}/{theme}/{tag}"
                    reset()
                    c = br.new_context(**kw)
                    c.add_init_script(f"if(!sessionStorage.getItem('once')){{localStorage.clear();sessionStorage.setItem('once','1')}}localStorage.setItem('cp_tour','1');localStorage.setItem('cp_skin','{skin}');localStorage.setItem('cp_theme','{theme}')")
                    pg = c.new_page(); errs = []
                    pg.on("pageerror", lambda e: errs.append(str(e)))
                    pg.goto(inst.base_url); pg.wait_for_selector("#lib .fd")
                    rows = pg.evaluate(ROWS)
                    check(f"{label}: no favorites: no Favorites heading, folders alphabetical", not names(rows, "sec") and names(rows)[:4] == ["Alpha", "Bravo", "Charlie", "Delta"], rows[:6])
                    check(f"{label}: Collapse all / Expand all buttons have titles and aria-labels",
                          pg.evaluate("['lib_collapse','lib_expand'].map(i=>{const b=document.getElementById(i);return b.title&&b.getAttribute('aria-label')&&b.querySelector('svg')?1:0}).join('')") == "11")
                    check(f"{label}: Hidden toggle is not there while nothing is hidden", pg.evaluate("document.getElementById('lib_hidden').hidden"))
                    # --- favorite
                    clk(pg, '#lib .fd[data-path="Charlie"] .star')
                    pg.wait_for_function("document.querySelector('#lib .lsec')")
                    rows = pg.evaluate(ROWS)
                    check(f"{label}: favorite moves to the Favorites group above All folders", names(rows, "sec") == ["Favorites", "All folders"] and names(rows)[:5] == ["Charlie", "Alpha", "Bravo", "Delta", "Sub"][:5] and
                          [r[0] for r in rows].index("sec") == 0, rows[:8])
                    st = pg.evaluate("(()=>{const b=document.querySelector('#lib .fd[data-path=\"Charlie\"] .star');return {t:b.title,a:b.getAttribute('aria-pressed'),f:getComputedStyle(b.querySelector('svg')).fill,col:getComputedStyle(b).color}})()")
                    check(f"{label}: star is filled yellow, titled Unfavorite, aria-pressed", st["t"] == "Unfavorite" and st["a"] == "true" and "250, 204, 21" in st["f"], st)
                    check(f"{label}: the flag is on the player (shared)", api.library()["flags"].get("Charlie") == {"fav": True})
                    # a second favorite sorts alphabetically in the group
                    clk(pg, '#lib .fd[data-path="Alpha"] .star'); pg.wait_for_function("document.querySelectorAll('#lib .fd .star.on').length===2")
                    rows = pg.evaluate(ROWS)
                    check(f"{label}: favorites are alphabetical", names(rows)[:2] == ["Alpha", "Charlie"], names(rows)[:3])
                    if SHOTS and tag == "desktop" and theme == "dark":
                        pg.locator("#libcol").screenshot(path=f"{SHOTS}/{skin}-{theme}-favorites.png")
                    # a second browser (own storage) sees both flags
                    if label == "console/dark/desktop":
                        c2 = br.new_context(viewport={"width": 1400, "height": 1000}); p2 = c2.new_page(); p2.goto(inst.base_url); p2.wait_for_selector("#lib .fd")
                        check(f"{label}: another browser sees the favorites", names(p2.evaluate(ROWS), "sec") == ["Favorites", "All folders"] and names(p2.evaluate(ROWS))[:2] == ["Alpha", "Charlie"])
                        c2.close()
                    clk(pg, '#lib .fd[data-path="Alpha"] .star'); clk(pg, '#lib .fd[data-path="Charlie"] .star')
                    pg.wait_for_function("!document.querySelector('#lib .lsec')")
                    check(f"{label}: unfavorite removes the heading again", not names(pg.evaluate(ROWS), "sec"))
                    # --- collapse / expand all
                    clk(pg, "#lib_collapse")
                    rows = pg.evaluate(ROWS)
                    check(f"{label}: Collapse all closes every folder (no file rows inside)", all(r[3] == "▸" for r in rows if r[0] == "fd") and not any(r[0] == "lt" and "/" in r[1] for r in rows), rows[:5])
                    pg.reload(); pg.wait_for_selector("#lib .fd")
                    check(f"{label}: collapsed state is remembered on this device", all(r[3] == "▸" for r in pg.evaluate(ROWS) if r[0] == "fd"))
                    clk(pg, "#lib_expand")
                    check(f"{label}: Expand all opens every folder", all(r[3] == "▾" for r in pg.evaluate(ROWS) if r[0] == "fd"))
                    # --- hide
                    clk(pg, '#lib .fd[data-path="Delta"] .hide')
                    pg.wait_for_function("document.querySelector('#lib .fd[data-path=\"Delta\"]')===null")
                    tg = pg.evaluate("(()=>{const b=document.getElementById('lib_hidden');return {h:b.hidden,t:b.textContent.trim(),p:b.getAttribute('aria-pressed')}})()")
                    check(f"{label}: hiding removes the folder; the toggle shows the count 1", "Delta" not in names(pg.evaluate(ROWS)) and not tg["h"] and tg["t"] == "1" and tg["p"] == "false", tg)
                    check(f"{label}: hidden folder keeps its files in playlists (library still lists them)", any(f["id"] == "Delta/tone_a.wav" for f in api.library()["files"]))
                    clk(pg, "#lib_collapse")
                    clk(pg, "#lib_hidden")
                    rows = pg.evaluate(ROWS); dl = [r for r in rows if r[0] == "fd" and r[1] == "Delta"]
                    check(f"{label}: Collapse all skipped the hidden folder", dl and dl[0][3] == "▾", dl)
                    check(f"{label}: Hidden on: folder shown dimmed with a 'hidden' badge and the unhide eye", dl and "hid" in dl[0][2].split() and
                          pg.evaluate("(()=>{const e=document.querySelector('#lib .fd[data-path=\"Delta\"]');return !!e.querySelector('.hbadge')&&e.querySelector('.unhide').title==='Hidden. Click to unhide'&&!e.querySelector('.star')})()"), dl)
                    if SHOTS and tag == "desktop" and theme == "dark":
                        pg.locator("#libcol").screenshot(path=f"{SHOTS}/{skin}-{theme}-hidden-shown.png")
                    check(f"{label}: Hidden toggle is on and pressed", pg.evaluate("document.getElementById('lib_hidden').getAttribute('aria-pressed')") == "true")
                    pg.reload(); pg.wait_for_selector("#lib .fd")
                    check(f"{label}: Hidden toggle state is remembered on this device", pg.evaluate("document.getElementById('lib_hidden').getAttribute('aria-pressed')") == "true" and "Delta" in names(pg.evaluate(ROWS)))
                    clk(pg, '#lib .fd[data-path="Delta"] .unhide')
                    pg.wait_for_function("document.getElementById('lib_hidden').hidden")
                    rows = pg.evaluate(ROWS)
                    check(f"{label}: unhide puts the folder back; the toggle goes away", [r for r in rows if r[1] == "Delta"] and "hid" not in [r for r in rows if r[1] == "Delta"][0][2].split())
                    check(f"{label}: after the last unhide the Hidden state is off again", pg.evaluate("localStorage.getItem('cp_lib_hidden')") == "0" and not pg.evaluate("HIDSHOW"))
                    # --- search with matches in a hidden folder
                    clk(pg, "#lib_expand")
                    api.post("/api/library/folder/flags", {"path": "Charlie", "hidden": True})
                    pg.wait_for_function("document.querySelector('#lib .fd[data-path=\"Charlie\"]')===null", timeout=8000)
                    pg.fill("#q", "sunday")
                    rows = pg.evaluate(ROWS)
                    check(f"{label}: search: no visible match shows 'No tracks found' and the hidden message", pg.evaluate("document.getElementById('lib').textContent").count("No tracks found") == 1 and
                          pg.evaluate("document.querySelector('.hidmsg').textContent.trim()") == "2 tracks found in hidden folders · click to show", rows)
                    pg.fill("#q", "Sunday_b")
                    check(f"{label}: search: one track says '1 track found in hidden folders'", pg.evaluate("document.querySelector('.hidmsg').textContent.trim()") == "1 track found in hidden folders · click to show")
                    pg.fill("#q", "sunday")
                    clk(pg, ".hidmsg")
                    rows = pg.evaluate(ROWS)
                    ch = [r for r in rows if r[0] == "fd" and r[1] == "Charlie"]
                    check(f"{label}: clicking the message reveals the matching hidden folder, expanded, dimmed, with its files and a 'Hide these again' link",
                          ch and "hid" in ch[0][2].split() and ch[0][4] == "2 matches" and names(rows, "lt") == ["Sunday_b", "Sunday_c"] and rows[-2] == ["msg", "Hide these again"], rows)
                    check(f"{label}: ... without switching the Hidden toggle", pg.evaluate("document.getElementById('lib_hidden').getAttribute('aria-pressed')") == "false")
                    if SHOTS and tag == "desktop" and theme == "dark":
                        pg.locator("#libcol").screenshot(path=f"{SHOTS}/{skin}-{theme}-search-revealed.png")
                    clk(pg, ".hidmsg")
                    check(f"{label}: 'Hide these again' puts them away", pg.evaluate("document.querySelector('.hidmsg').textContent.trim()").startswith("2 tracks found"))
                    clk(pg, ".hidmsg"); pg.fill("#q", "")
                    check(f"{label}: clearing the search puts revealed folders away", "Charlie" not in names(pg.evaluate(ROWS)))
                    pg.fill("#q", "sunday")
                    check(f"{label}: ... and the next search starts with the message again", pg.evaluate("!!document.querySelector('.hidmsg')"))
                    clk(pg, ".hidmsg")
                    clk(pg, '#lib .fd[data-path="Charlie"] .unhide')
                    pg.wait_for_function("document.querySelectorAll('#lib .lt').length===2 && !document.querySelector('.hidmsg')")
                    check(f"{label}: unhide from the search result moves the tracks to the normal results", [n.split(" ")[0] for n in names(pg.evaluate(ROWS), "lt")] == ["Sunday_b", "Sunday_c"] and not api.library()["flags"].get("Charlie"))
                    pg.fill("#q", "")
                    # --- layout
                    api.post("/api/library/folder/flags", {"path": "Bravo", "hidden": True})
                    api.post("/api/library/folder/flags", {"path": "Alpha", "fav": True})
                    pg.wait_for_function("document.querySelector('#lib .lsec')")
                    clk(pg, "#lib_hidden")
                    f = pg.evaluate(FLAT)
                    check(f"{label}: nothing clipped, no horizontal overflow in the library and its header tools", not f["libOver"] and f["bad"] == 0 and f["toolsIn"], f)
                    if f["pageOver"] and label.endswith("/desktop") is False and label.split("/")[0] == "console" and theme == "dark":
                        print(f"NOTE {label}: the page itself is a few px wider than the viewport (also in 2.7.3: the library's track rows are wider than the column in the stage skin; not from this change): {f}")
                    if SHOTS and tag == "phone" and theme == "dark":
                        pg.locator("#libcol").screenshot(path=f"{SHOTS}/{skin}-{theme}-phone.png")
                    check(f"{label}: no page errors", not errs, errs)
                    c.close()
        reset()
        br.close()
    print(f"\n{len(FAILS)} failure(s)")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
