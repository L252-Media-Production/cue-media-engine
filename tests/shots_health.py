#!/usr/bin/env python3
"""Screenshots for docs/screenshots/2.8.0-health/: desktop, one tablet width, the dot in its four states (3 skins), the panel and the Health and alerts block.
    python tests/shots_health.py [OUT_DIR]"""
import json, os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "harness"))
from harness.instance import Instance, PROJECT   # noqa: E402
import test_health_ui as T                        # noqa: E402

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "docs" / "screenshots" / "2.8.0-health")


def main():
    from playwright.sync_api import sync_playwright
    OUT.mkdir(parents=True, exist_ok=True)
    with Instance(wav_only=True, project_dir=PROJECT) as inst, sync_playwright() as p:
        br = p.chromium.launch()
        ctx = br.new_context(viewport={"width": 1280, "height": 900})
        ctx.add_init_script("try{localStorage.setItem('cp_tour','1')}catch(e){}")
        pg = ctx.new_page()
        pg.goto(inst.base_url + "/")
        pg.wait_for_selector("#hdot")
        pg.wait_for_timeout(1500)
        pg.evaluate("window.render=async()=>{}")
        pg.wait_for_timeout(1200)
        for skin in ("console", "studio", "stage"):
            pg.evaluate(f"setLook('skin','{skin}');setLook('theme','dark')")
            for name, h in T.CASES.items():
                pg.evaluate("h=>healthSync(h)", h)
                pg.screenshot(path=str(OUT / f"dot-{name}-{skin}.png"), clip={"x": 0, "y": 0, "width": 330, "height": 60})
        pg.evaluate("setLook('skin','console');setLook('theme','dark');healthSync(" + json.dumps(T.CASES["degraded"]) + ")")
        pg.screenshot(path=str(OUT / "desktop-degraded.png"))
        pg.evaluate("hpOpen()")
        pg.screenshot(path=str(OUT / "desktop-panel-degraded.png"), clip={"x": 0, "y": 0, "width": 760, "height": 560})
        pg.evaluate("healthSync(" + json.dumps(T.CASES["problem"]) + ")")
        pg.screenshot(path=str(OUT / "desktop-panel-problem.png"), clip={"x": 0, "y": 0, "width": 760, "height": 600})
        pg.evaluate("hpClose(false)")
        pg.set_viewport_size({"width": 820, "height": 1100})
        pg.evaluate("hpOpen()")
        pg.screenshot(path=str(OUT / "tablet-panel-problem.png"), clip={"x": 0, "y": 0, "width": 820, "height": 640})
        pg.evaluate("hpClose(false)")
        pg.set_viewport_size({"width": 1280, "height": 900})
        pg.evaluate("setLook('theme','light')")
        pg.evaluate("hpOpen()")
        pg.screenshot(path=str(OUT / "desktop-panel-problem-light.png"), clip={"x": 0, "y": 0, "width": 760, "height": 600})
        pg.evaluate("hpClose(false)")
        pg.evaluate("setLook('theme','dark');openSettings()")
        pg.wait_for_selector("#settings[open]")
        pg.evaluate("setTab('system')")
        pg.wait_for_timeout(600)
        pg.screenshot(path=str(OUT / "settings-health-and-alerts.png"))
        br.close()
    print("shots in", OUT)


if __name__ == "__main__":
    main()
