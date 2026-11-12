#!/usr/bin/env python3
"""One Trim icon everywhere (2.7.2-rc3): the Cue panel's Trim button (no more "A-B" text) and the playlist-row Trim buttons render the same icon
(IC.trim), are not clipped, and open the trim dialog for their track. 3 skins x dark/light x desktop / phone / touch.
    python tests/test_trim_icon.py      (needs playwright; starts its own disposable player)"""
import os
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


JS = """()=>{const q=s=>document.querySelector(s),r=e=>e.getBoundingClientRect(),cue=q('#foctrbtn'),row=q('#lists li.t .ib.tr');
  const ds=b=>[...b.querySelectorAll('path')].map(p=>p.getAttribute('d')).join('|');
  const clip=b=>{const s=b.querySelector('svg'),sr=r(s),br=r(b);return sr.width>0&&sr.left>=br.left-0.5&&sr.right<=br.right+0.5&&sr.top>=br.top-0.5&&sr.bottom<=br.bottom+0.5&&b.scrollWidth<=b.clientWidth+1};
  return {cueD:ds(cue),rowD:ds(row),iconD:IC.trim.match(/d="[^"]*"/g).map(x=>x.slice(3,-1)).join('|'),cueTxt:cue.textContent.trim(),cueSvg:!!cue.querySelector('svg'),
    cueClip:clip(cue),rowClip:clip(row),cueW:r(cue).width,cueH:r(cue).height,label:cue.getAttribute('aria-label'),title:cue.title}}"""


def main():
    from playwright.sync_api import sync_playwright
    with Instance(wav_only=True, project_dir=os.environ.get("TI_PROJECT") or PROJECT) as inst, sync_playwright() as p:
        api = client.Api(inst.base_url, osc_port=inst.osc_port)
        api.post("/api/playlists", {"name": "T"}); api.post("/api/playlists/0/add", {"files": ["long_120s.wav"]})
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
                    pg.goto(inst.base_url); pg.wait_for_selector("#lists li.t .ib.tr")
                    d = pg.evaluate(JS)
                    check(f"{label}: Cue Trim button has the icon and no A-B text", d["cueSvg"] and "A–B" not in d["cueTxt"] and d["cueTxt"] == "", d)
                    check(f"{label}: Cue and row Trim icons are the same IC.trim paths", d["cueD"] == d["rowD"] == d["iconD"] != "", d)
                    check(f"{label}: neither icon is clipped", d["cueClip"] and d["rowClip"], d)
                    check(f"{label}: Cue button keeps a title and gets an aria-label", d["label"] == "Set A and B points" and "A and B" in d["title"], d)
                    # click behaviour: cue the track, the Cue button opens the trim dialog for it
                    api.get("/api/0/0/focus")
                    pg.wait_for_function("/\\d+\\/\\d+/.test(focid.textContent)&&focnm.textContent!=='-'", timeout=5000)
                    pg.click("#foctrbtn"); pg.wait_for_selector("#trdlg[open]")
                    check(f"{label}: Cue Trim button opens the dialog for the cued track", pg.evaluate("TR.p===0&&TR.k===0&&TR.fid==='long_120s.wav'"))
                    pg.evaluate("trdlg.close()")
                    pg.evaluate("document.querySelector('#lists li.t .ib.tr').click()"); pg.wait_for_selector("#trdlg[open]")
                    check(f"{label}: row Trim button opens the dialog", pg.evaluate("trdlg.open"))
                    pg.evaluate("trdlg.close()")
                    check(f"{label}: no page errors", not errs, errs)
                    c.close()
        br.close()
    print(f"\n{len(FAILS)} failure(s)")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
