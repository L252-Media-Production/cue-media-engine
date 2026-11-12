#!/usr/bin/env python3
"""Screenshots for docs/screenshots/2.8.0-health-followup/: the Player name field (Settings) and the Audio engine row (health panel), desktop and one tablet width.
    python tests/shots_health_followup.py [OUT_DIR]"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from harness import client                       # noqa: E402
from harness.instance import Instance, PROJECT   # noqa: E402

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "docs" / "screenshots" / "2.8.0-health-followup")


def main():
    from playwright.sync_api import sync_playwright
    OUT.mkdir(parents=True, exist_ok=True)
    with Instance(wav_only=True, project_dir=PROJECT) as inst, sync_playwright() as p:
        api = client.Api(inst.base_url, osc_port=inst.osc_port)
        api.post("/api/settings/health", {"player_name": "L252 NUC"})
        br = p.chromium.launch()
        ctx = br.new_context(viewport={"width": 1280, "height": 900})
        ctx.add_init_script("try{localStorage.setItem('cp_tour','1')}catch(e){}")
        pg = ctx.new_page()
        pg.goto(inst.base_url + "/")
        pg.wait_for_selector("#hdot")
        pg.wait_for_timeout(1800)
        for name, size in (("desktop", (1280, 900)), ("tablet", (820, 1100))):
            pg.set_viewport_size({"width": size[0], "height": size[1]})
            pg.evaluate("setLook('skin','console');setLook('theme','dark');hpOpen()")
            pg.wait_for_timeout(400)
            pg.screenshot(path=str(OUT / f"{name}-audio-engine-row.png"), clip={"x": 0, "y": 0, "width": min(size[0], 760), "height": 520})
            pg.evaluate("hpClose(false);openSettings()")
            pg.wait_for_selector("#settings[open]")
            pg.evaluate("setTab('system')")
            pg.wait_for_timeout(500)
            pg.evaluate("document.getElementById('set_pname').scrollIntoView({block:'center'})")
            pg.screenshot(path=str(OUT / f"{name}-player-name.png"))
            pg.evaluate("settings.close()")
        br.close()
    print("shots in", OUT)


if __name__ == "__main__":
    main()
