#!/usr/bin/env python3
"""Settings chips: is the text centred in its pill?  (2.7.5 rc4)

For every chip in Settings (This browser only, Sending to, File check in each state, FFmpeg found / not found, the time-warning chips, the prefix result chip)
two measures against the pill's own box, horizontally and vertically:
  box  the text's line box (a DOM Range) against the pill             must differ by <= 1 px
  ink  the pixels the text really draws (element screenshot, the text colour against the pill's background) against the pill     must differ by <= 1.5 px, or 2 device pixels
                                                                      when that is more (zoom 125 % puts one device pixel at 0.8 CSS px); only for text with capitals,
                                                                      digits or ascenders and no descenders (those move the ink box off the middle of any centred line)
Matrix: browsers (chromium, firefox, webkit) x device pixel ratio 1 / 1.5 / 2 x page zoom 100 / 125 / 150 % x skin x theme (default font), and the font stacks of a Linux
machine (DejaVu Sans, Liberation Sans, the generic sans-serif; fonts are loaded from CP_FONT_DIR when it holds DejaVuSans.ttf and LiberationSans-Regular.ttf) x browsers x
skin x theme x dpr 1.   Zoom is made like a browser makes it: the CSS viewport shrinks by the factor and the pixel ratio grows by it.
    python tests/test_chips_matrix.py [--quick] [--shots DIR] [--project DIR]      (needs playwright with chromium, firefox and webkit installed, and pillow)"""
import argparse
import io
import re
import os
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from harness.instance import Instance, PROJECT   # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--quick", action="store_true", help="chromium only, dpr 1 and 2, zoom 100 and 150, no font variants")
ap.add_argument("--shots", default=None)
ap.add_argument("--project", default=os.environ.get("PP_PROJECT") or PROJECT)
ap.add_argument("--browsers", default="chromium,firefox,webkit")
ARGS = ap.parse_args()

BOX_TOL, INK_TOL = 1.0, 1.5
ERR = []
ROWS = []          # (label, chip, box dx, box dy, ink dx, ink dy)

# every chip in a state worth testing: (selector, text, class)
SETUP = """()=>{
  const set=(id,t,c)=>{const e=document.getElementById(id);if(e){e.textContent=t;e.className='chipb'+(c?' '+c:'')}};
  window.__states={
   fmt:[['All files look fine','ok'],['1 file needs attention','bad'],['3 files need attention: a very long result text that has to wrap onto a second line','bad'],['Checking… 12 of 40',''],['Needs ffmpeg','']],
   ff:[['8.1.1 found','ok'],['Not found','bad']]};
  return true}"""
CHIPS = """()=>{document.querySelectorAll('[data-cm]').forEach(e=>e.removeAttribute('data-cm'));return [...document.querySelectorAll('#settings .chipb, #settings .dotc')].filter(e=>{const r=e.getBoundingClientRect();return r.width>0&&r.height>0&&!e.closest('[hidden]')&&getComputedStyle(e).visibility!=='hidden'}).map((e,i)=>{e.setAttribute('data-cm',i);return {i,id:e.id||e.className,txt:e.textContent.trim().slice(0,28)}})}"""
BOXM = """i=>{const e=document.querySelector(`[data-cm="${i}"]`),r=e.getBoundingClientRect(),g=document.createRange();g.selectNodeContents(e);const t=g.getBoundingClientRect();
  return [((t.left+t.right)/2-(r.left+r.right)/2),((t.top+t.bottom)/2-(r.top+r.bottom)/2),r.width,r.height]}"""


def ink_offset(png, dpr):
    """Offset (dx, dy) in CSS px of the drawn text's box from the pill's centre; None when no text pixels were found."""
    from PIL import Image
    import numpy as np
    im = np.asarray(Image.open(io.BytesIO(png)).convert("RGB")).astype(int)
    h, w, _ = im.shape
    inset = int(round(7 * dpr))
    if h <= 2 * inset + 2 or w <= 2 * inset + 2:
        inset = max(2, int(round(3 * dpr)))
    inner = im[inset:h - inset, inset:w - inset]
    bg = np.median(inner.reshape(-1, 3), axis=0)
    diff = np.abs(inner - bg).sum(axis=2)
    mask = diff > 90
    if not mask.any():
        return None
    ys, xs = np.nonzero(mask)
    cx, cy = (xs.min() + xs.max() + 1) / 2 + inset, (ys.min() + ys.max() + 1) / 2 + inset
    return (cx - w / 2) / dpr, (cy - h / 2) / dpr


def measure(pg, label, dpr, shot_name=None):
    chips = pg.evaluate(CHIPS)
    for c in chips:
        bx = pg.evaluate(BOXM, c["i"])
        el = pg.locator(f'[data-cm="{c["i"]}"]')
        ink = None
        try:
            ink = ink_offset(el.screenshot(timeout=4000), dpr)
        except Exception as e:
            ERR.append(f'{c["id"]}: {type(e).__name__} {str(e)[:60]}')
        # the ink box only says something about centring when the text has capitals, digits or ascenders (a line of x-height letters such as "zz_…" has its ink
        # below the middle of any correctly centred line box: that is the font, not the layout)
        # and none with descenders (g j p q y , ; _): those pull the ink box below a correctly centred line box
        if ink is not None and (not re.search(r"[A-Zbdfhklt0-9]", c["txt"]) or re.search(r"[gjpqy,;_]", c["txt"])):
            ink = None
        ROWS.append((label, f'{c["id"]}: {c["txt"]}', bx[0], bx[1], None if ink is None else ink[0], None if ink is None else ink[1], bx[2], bx[3], dpr))
    if shot_name and ARGS.shots:
        pg.screenshot(path=f"{ARGS.shots}/{shot_name}.png")


def tabs_and_states(pg, label, dpr, shot=None):
    """Walk the tabs; put the File check and ffmpeg chips through their states; measure everything visible."""
    for tab in ("look", "companion", "system"):
        pg.click(f"#set_tabs [data-tab={tab}]"); time.sleep(0.15)
        if tab == "companion":
            pg.evaluate("(()=>{if(window.pfx_res){pfx_res.textContent='Mp_…';pfx_resrow.hidden=false}})()")
        if tab == "system":
            for t, c in ((("All files look fine", "ok")), ("1 file needs attention", "bad"), ("3 files need attention: a very long result text that has to wrap onto a second line", "bad"), ("Checking… 12 of 40", ""), ("Needs ffmpeg", "")):
                pg.evaluate("([t,c])=>{fmt_chip.textContent=t;fmt_chip.className='chipb'+(c?' '+c:'')}", [t, c]); time.sleep(0.05)
                measure(pg, f"{label} | file check '{t[:14]}'", dpr, f"{shot}-file-check-{c or 'plain'}-{len(t)}" if shot else None)
            for t, c in (("8.1.1 found", "ok"), ("Not found", "bad")):
                pg.evaluate("([t,c])=>{ff_chip.textContent=t;ff_chip.className='chipb'+(c?' '+c:'')}", [t, c]); time.sleep(0.05)
                measure(pg, f"{label} | ffmpeg '{t}'", dpr)
        else:
            measure(pg, f"{label} | {tab}", dpr)


def main():
    from playwright.sync_api import sync_playwright
    fonts = Path(os.environ.get("CP_FONT_DIR", ""))
    have_fonts = (fonts / "DejaVuSans.ttf").exists() and (fonts / "LiberationSans-Regular.ttf").exists()
    if ARGS.shots:
        os.makedirs(ARGS.shots, exist_ok=True)
    browsers = ["chromium"] if ARGS.quick else ARGS.browsers.split(",")
    dprs, zooms = ((1, 2), (1, 1.5)) if ARGS.quick else ((1, 1.5, 2), (1, 1.25, 1.5))
    with Instance(wav_only=True, project_dir=ARGS.project) as inst, sync_playwright() as p:
        for bname in browsers:
            br = getattr(p, bname).launch()
            # 1) pixel ratio x zoom x skin x theme, the page's own font stack
            for dpr in dprs:
                for zoom in zooms:
                    ctx = br.new_context(viewport={"width": int(1280 / zoom), "height": int(900 / zoom)}, device_scale_factor=dpr * zoom)
                    ctx.add_init_script("localStorage.setItem('cp_tour','1')")
                    pg = ctx.new_page()
                    pg.goto(inst.base_url); pg.wait_for_selector("#setbtn"); time.sleep(0.6)
                    pg.click("#setbtn"); pg.wait_for_selector("#settings[open]")
                    for skin in ("console", "studio", "stage"):
                        for theme in ("light", "dark"):
                            pg.evaluate("([s,t])=>{setLook('skin',s);setLook('theme',t)}", [skin, theme]); time.sleep(0.15)
                            lab = f"{bname} dpr{dpr} zoom{int(zoom * 100)} {skin}/{theme}"
                            shot = f"{bname}-{skin}-{theme}-dpr{dpr}-zoom{int(zoom * 100)}" if (ARGS.shots and dpr == 1 and zoom == 1 and theme == "light") else None
                            tabs_and_states(pg, lab, dpr * zoom, shot)
                    ctx.close()
            # 2) Linux font stacks (the page's own stack is system-ui, -apple-system, "Segoe UI", Roboto, sans-serif: on Linux whatever that resolves to)
            if have_fonts and not ARGS.quick:
                css = (f"@font-face{{font-family:'DejaVu Sans';src:url('{(fonts / 'DejaVuSans.ttf').as_uri()}')}}"
                       f"@font-face{{font-family:'Liberation Sans';src:url('{(fonts / 'LiberationSans-Regular.ttf').as_uri()}')}}")
                for fname, stack in (("DejaVu Sans", "'DejaVu Sans',sans-serif"), ("Liberation Sans", "'Liberation Sans',sans-serif"), ("generic sans-serif", "sans-serif")):
                    ctx = br.new_context(viewport={"width": 1280, "height": 900}, device_scale_factor=1)
                    ctx.add_init_script("localStorage.setItem('cp_tour','1')")
                    pg = ctx.new_page()
                    pg.goto(inst.base_url); pg.wait_for_selector("#setbtn"); pg.click("#setbtn"); pg.wait_for_selector("#settings[open]")
                    pg.add_style_tag(content=css + f":root{{--font:{stack}!important}}body,button,input,select{{font-family:{stack}}}")
                    pg.evaluate("document.fonts.ready"); time.sleep(0.4)
                    for skin in ("console", "studio", "stage"):
                        for theme in ("light", "dark"):
                            pg.evaluate("([s,t])=>{setLook('skin',s);setLook('theme',t)}", [skin, theme]); time.sleep(0.15)
                            lab = f"{bname} font[{fname}] {skin}/{theme}"
                            shot = f"{bname}-font-{fname.replace(' ', '')}-{skin}-{theme}" if (ARGS.shots and theme == "light") else None
                            tabs_and_states(pg, lab, 1, shot)
                    ctx.close()
            br.close()
    # report
    worst_box = max(ROWS, key=lambda r: max(abs(r[2]), abs(r[3])))
    inks = [r for r in ROWS if r[4] is not None]
    worst_ink = max(inks, key=lambda r: max(abs(r[4]), abs(r[5])))
    bad = [r for r in ROWS if max(abs(r[2]), abs(r[3])) > BOX_TOL or (r[4] is not None and max(abs(r[4]), abs(r[5])) > max(INK_TOL, 2.0 / r[8]))]
    print(f"{len(ROWS)} chip measurements, {len(inks)} with ink, {len(bad)} over the limit (box {BOX_TOL} px, ink {INK_TOL} px)")
    print(f"ink not measured: {len(ERR)} (first: {ERR[:2]})")
    print(f"worst box offset  {max(abs(worst_box[2]), abs(worst_box[3])):.2f} px  {worst_box[0]} | {worst_box[1]}")
    print(f"worst ink offset  {max(abs(worst_ink[4]), abs(worst_ink[5])):.2f} px  {worst_ink[0]} | {worst_ink[1]}")
    by = {}
    for r in ROWS:
        k = r[0].split(" ")[0] + (" font" if "font[" in r[0] else " dpr/zoom")
        d = by.setdefault(k, [0, 0, 0, 0, 0])
        d[0] += 1; d[1] = max(d[1], abs(r[2])); d[2] = max(d[2], abs(r[3]))
        if r[4] is not None: d[3] = max(d[3], abs(r[4])); d[4] = max(d[4], abs(r[5]))
    print("\n| browser / matrix | measurements | box dx | box dy | ink dx | ink dy |\n|---|---|---|---|---|---|")
    for k, d in sorted(by.items()):
        print(f"| {k} | {d[0]} | {d[1]:.2f} | {d[2]:.2f} | {d[3]:.2f} | {d[4]:.2f} |")
    for r in sorted(bad, key=lambda r: -max(abs(r[2]), abs(r[3]), abs(r[4] or 0), abs(r[5] or 0)))[:25]:
        print("FAIL", f"box({r[2]:.2f},{r[3]:.2f}) ink({'-' if r[4] is None else f'{r[4]:.2f},{r[5]:.2f}'}) pill {r[6]:.0f}x{r[7]:.0f}  {r[0]} | {r[1]}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
