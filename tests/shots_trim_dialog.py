#!/usr/bin/env python3
"""Screenshots of the trim dialog at the maximum fade value (desktop, and the touch layout).
    python tests/shots_trim_dialog.py OUT_DIR [PROJECT_DIR]       # PROJECT_DIR: another checkout of the app (for a 'before' picture)"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from harness import client                       # noqa: E402
from harness.instance import Instance            # noqa: E402
from test_trim_dialog import open_trim           # noqa: E402


def main():
    from playwright.sync_api import sync_playwright
    out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
    proj = sys.argv[2] if len(sys.argv) > 2 else None
    with (Instance(wav_only=True, project_dir=proj) if proj else Instance(wav_only=True)) as inst, sync_playwright() as p:
        api = client.Api(inst.base_url, osc_port=inst.osc_port)
        api.post("/api/playlists", {"name": "Shots"}); api.post("/api/playlists/0/add", {"files": ["long_120s.wav"]})
        br = p.chromium.launch()
        for name, kw in (("desktop", dict(viewport={"width": 1400, "height": 1000})),
                         ("touch", dict(viewport={"width": 430, "height": 932}, has_touch=True, is_mobile=True, device_scale_factor=2))):
            c = br.new_context(**kw)
            c.add_init_script("localStorage.setItem('cp_tour','1');localStorage.setItem('cp_theme','light');localStorage.setItem('cp_skin','console')")
            pg = c.new_page(); pg.goto(inst.base_url); pg.wait_for_selector("#lists li.t")
            open_trim(pg, fade=10)
            pg.locator("#trdlg").screenshot(path=str(out / f"trim-{name}.png"))
            pg.locator("#tr_fade").screenshot(path=str(out / f"trim-{name}-fade-row.png"))
            c.close()
        br.close()


if __name__ == "__main__":
    main()
