"""The 'Move to another playlist' button is gone from track rows; dragging between playlists still moves tracks.
   python tests/test_move_button.py [SHOT_DIR]"""
import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_devices import Box, check, FAILS            # noqa: E402
SHOTS = Path(sys.argv[1]) if len(sys.argv) > 1 else None


def tracks(box):
    return [[t["id"] for t in p["tracks"]] for p in box.get("/api/playlists")["playlists"]] if "playlists" in box.get("/api/playlists") else [[t["id"] for t in p["tracks"]] for p in box.get("/api/playlists")]


def main():
    from playwright.sync_api import sync_playwright
    box = Box().start()
    try:
        box.post("/api/playlists", {"name": "One"}); box.post("/api/playlists", {"name": "Two"})
        box.post("/api/playlists/0/add", {"files": ["a.wav", "b.wav", "c.wav"]})
        with sync_playwright() as p:
            br = p.chromium.launch()
            for theme in ("light", "dark"):
                for skin in ("console", "studio", "stage"):
                    for w in (1400, 420):
                        if skin != "console" and theme == "dark":
                            continue
                        c = br.new_context(viewport={"width": w, "height": 1000})
                        c.add_init_script(f"localStorage.setItem('cp_tour','1');localStorage.setItem('cp_theme','{theme}');localStorage.setItem('cp_skin','{skin}')")
                        pg = c.new_page(); pg.goto(box.url()); pg.wait_for_selector("#lists li.t")
                        n = pg.evaluate("document.querySelectorAll('#lists li.t [title=\"Move to another playlist\"], #lists li.t select').length")
                        check(f"{skin}/{theme}/{w}: no move button or select in track rows", n == 0, n)
                        r = pg.evaluate("""()=>{const l=[...document.querySelectorAll('#lists li.t')][0],a=l.querySelector('.acts').getBoundingClientRect(),li=l.getBoundingClientRect();
                          const bs=[...l.querySelectorAll('.acts > *')].map(e=>e.getBoundingClientRect());let ov=false;for(let i=1;i<bs.length;i++)if(bs[i].left<bs[i-1].right-1&&Math.abs(bs[i].top-bs[i-1].top)<4)ov=true;
                          return {n:bs.length,inRow:a.right<=li.right+1&&a.left>=li.left-1,ov,labels:[...l.querySelectorAll('.acts > *')].map(e=>e.title||e.className)}}""")
                        check(f"{skin}/{theme}/{w}: row buttons inside the row, none overlapping ({r['n']} buttons)", r["inRow"] and not r["ov"], r)
                        if SHOTS and (skin == "console" or w == 1400):
                            SHOTS.mkdir(parents=True, exist_ok=True)
                            pg.locator("#lists").first.screenshot(path=str(SHOTS / f"rows-{skin}-{theme}-{w}.png"))
                        c.close()
            # drag a track from playlist One to playlist Two
            for w in (1400, 420):
                c = br.new_context(viewport={"width": w, "height": 1000}); c.add_init_script("localStorage.setItem('cp_tour','1')")
                pg = c.new_page(); pg.goto(box.url()); pg.wait_for_selector("#lists li.t")
                before = [[t["id"] for t in p["tracks"]] for p in box.get("/api/playlists")["playlists"]] if isinstance(box.get("/api/playlists"), dict) else box.get("/api/playlists")
                src = pg.locator("#lists li.t").first.locator(".grip")
                dst = pg.locator("#lists .pl").nth(1)
                dst.scroll_into_view_if_needed()
                src.scroll_into_view_if_needed()
                src.drag_to(dst, target_position={"x": 60, "y": 30})
                time.sleep(1.2)
                d = box.get("/api/playlists"); d = d["playlists"] if isinstance(d, dict) else d
                after = [[t["id"] for t in p["tracks"]] for p in d]
                check(f"drag between playlists still moves the track ({w}px)", len(after[0]) == 2 and len(after[1]) == 1 and after[1][0] == "a.wav", (before, after))
                if SHOTS:
                    pg.locator("#lists").first.screenshot(path=str(SHOTS / f"after-drag-{w}.png"))
                c.close()
                box.post("/api/move", {"from": [1, 0], "to": [0, 0]})
            br.close()
    finally:
        box.cleanup()
    print("\n%d failure(s)" % len(FAILS)); return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
