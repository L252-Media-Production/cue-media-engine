#!/usr/bin/env python3
"""The Live input block in a custom layout (2.7.5 input-layout-fit), desktop only, 3 skins x dark / light:

  * a FRESH custom layout (first "Edit layout": the page is measured as drawn, the card is collapsed) gives the block room for the OPEN card: no inner scrollbar at 1400, 1100 and
    860 px (the block is overflow:auto with a fixed height; the default is 5 rows, measured: the open card needs 4 rows in console / studio and 5 in stage),
  * the default layout (Reset layout) has the same height,
  * a layout saved BEFORE the change (the card block 3 rows high) loads with its height unchanged (not migrated), the open card scrolls in it as before, and the block's "fit height"
    button (`layFitH`) makes it fit,
  * the collapsed card still looks right in the taller block (header inside the block, no scrollbar; screenshots with --shots),
  * the `#lay>*` rule is unchanged for the other blocks (overflow:auto).
    python tests/test_input_layout_fit.py [--shots DIR]      (needs playwright; starts its own disposable player)"""
import json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "api"))
from harness.instance import Instance            # noqa: E402
from test_live_input import make_env, set_feed   # noqa: E402

FAILS = []
SHOTS = sys.argv[sys.argv.index("--shots") + 1] if "--shots" in sys.argv else None
LONG = "Dante USB I/O Module, USB Audio Interface Rev 2 (32 in / 32 out)"
ROW = 24 + 8


def check(name, ok, info=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"   {info}"))
    if not ok:
        FAILS.append(name)


M = """()=>{const e=document.getElementById('inpc'),r=e.getBoundingClientRect(),h=document.querySelector('.inphead').getBoundingClientRect(),open=!e.classList.contains('ic');
  return {sc:e.scrollHeight-e.clientHeight,h:r.height,rows:Math.round((r.height+8)/32),open,headIn:h.top>=r.top-0.5&&h.bottom<=r.bottom+0.5,parent:e.parentElement.id,
   ovf:getComputedStyle(document.getElementById('cl')).overflowY,lay:typeof LAY!=='undefined'&&LAY?LAY.b.inpc.h:null}}"""
OPEN = "()=>{if(document.getElementById('inpc').classList.contains('ic'))inpTog(true)}"
SHUT = "()=>{if(!document.getElementById('inpc').classList.contains('ic'))inpTog(false)}"


def main():
    from playwright.sync_api import sync_playwright
    d, env = make_env()
    (d / "mock_inputs.json").write_text(json.dumps([LONG, "Fake input"]))
    set_feed(d, state="run", db=-40.0, channels=64)
    cfg = {"input_device": LONG, "input_armed": True}
    with Instance(wav_only=True, extra_config=cfg, extra_env=env) as inst, sync_playwright() as p:
        br = p.chromium.launch()
        for skin in ("console", "studio", "stage"):
            for theme in ("dark", "light"):
                tag = f"{skin}/{theme}"
                for w in (1400, 1100, 860):
                    c = br.new_context(viewport={"width": w, "height": 1000})
                    c.add_init_script(f"localStorage.setItem('cp_tour','1');localStorage.setItem('cp_theme','{theme}');localStorage.setItem('cp_skin','{skin}')")
                    pg = c.new_page(); errs = []
                    pg.on("pageerror", lambda e: errs.append(str(e)))
                    pg.goto(inst.base_url); pg.wait_for_selector("#inpc"); time.sleep(0.6)
                    # --- a fresh custom layout: the first Edit layout measures the page as drawn (card collapsed)
                    pg.evaluate("()=>layEdit()"); time.sleep(0.5)
                    m = pg.evaluate(M)
                    check(f"{tag} {w}: fresh custom layout: the card is in the grid and its block is at least 5 rows ({m['lay']})", m["parent"] == "lay" and m["lay"] is not None and m["lay"] >= 5, m)
                    check(f"{tag} {w}: collapsed card: header inside the block, no scrollbar", not m["open"] and m["headIn"] and m["sc"] <= 1, m)
                    pg.evaluate(OPEN); time.sleep(1.0)
                    m = pg.evaluate(M)
                    check(f"{tag} {w}: fresh custom layout: the OPEN card fits, no inner scrollbar (scroll {m['sc']}, block {m['h']:.0f} px)", m["open"] and m["sc"] <= 1, m)
                    check(f"{tag} {w}: the other blocks keep overflow:auto (#lay>* unchanged)", m["ovf"] == "auto", m)
                    pg.evaluate("()=>layDone()")
                    if w == 1400:
                        # --- the default layout (Reset layout) has the same height
                        pg.evaluate("()=>{localStorage.setItem('cp_layout',JSON.stringify(layDefault()))}"); pg.reload(); pg.wait_for_selector("#inpc"); pg.evaluate(SHUT); time.sleep(0.6)
                        if SHOTS:
                            pg.locator("#inpc").screenshot(path=f"{SHOTS}/fit-collapsed-{skin}-{theme}.png")
                        pg.evaluate(OPEN); time.sleep(1.0)
                        if SHOTS:
                            pg.locator("#inpc").screenshot(path=f"{SHOTS}/fit-open-{skin}-{theme}.png")
                        m = pg.evaluate(M)
                        check(f"{tag}: the default layout: block {m['lay']} rows, the open card fits", m["lay"] == 5 and m["sc"] <= 1, m)
                        # --- a layout saved before this change (card block 3 rows): not migrated; fit height fixes it
                        pg.evaluate("()=>{const l=layDefault();l.b.inpc.h=3;localStorage.setItem('cp_layout',JSON.stringify(l))}"); pg.reload(); pg.wait_for_selector("#inpc"); pg.evaluate(SHUT); time.sleep(0.6)
                        m = pg.evaluate(M)
                        check(f"{tag}: an old saved layout loads with its own height (3 rows, not migrated)", m["lay"] == 3 and m["rows"] == 3, m)
                        pg.evaluate(OPEN); time.sleep(1.0)
                        m = pg.evaluate(M)
                        check(f"{tag}: in that old layout the open card scrolls as it did (the saved height is kept)", m["lay"] == 3 and m["sc"] > 1, m)
                        pg.evaluate("()=>{layEdit();layFitH('inpc')}"); time.sleep(0.5)
                        m = pg.evaluate(M)
                        check(f"{tag}: the block's fit height still works (now {m['lay']} rows, no scrollbar)", m["lay"] in (4, 5) and m["sc"] <= 1, m)
                        pg.evaluate("()=>layDone()")
                        pg.evaluate("()=>{localStorage.removeItem('cp_layout')}")
                    check(f"{tag} {w}: no script errors", not errs, errs)
                    c.close()
        br.close()
    print(f"\n{len(FAILS)} failed" if FAILS else "\nall passed")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
