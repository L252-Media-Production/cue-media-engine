"""Live card output controls: the Live output is the speaker button after Mute and Solo under the Live meters (2.7.5 rc1: it left the transport row); the Mirror select stays in the
   transport row. No overlap, the Mirror name in full whenever there is room, the tooltip of the speaker holds the full device name, in every skin and width.
   python tests/test_live_output.py [SHOT_DIR]     (see test_devices.py for the requirements)"""
import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_devices import Box, check, FAILS            # noqa: E402

LONG1 = "DVS Transmit 11-12 (Dante Virtual Soundcard)"
LONG2 = "Speakers (Blackmagic DeckLink 8K Pro (1) Audio)"
HUGE = "Line (Very Long Vendor Name Professional Multichannel Audio Interface Series Pro) 1-2 (Dante Virtual Soundcard)"
DEV = [LONG1, LONG2, "Dante USB I/O (Audinate)", HUGE, "Out 2"]
SHOTS = Path(sys.argv[1]) if len(sys.argv) > 1 else None

JS = """()=>{
 const R=e=>{const r=e.getBoundingClientRect();return {l:r.left,r:r.right,t:r.top,b:r.bottom}};
 const x=(a,b)=>a.l<b.r-0.5&&b.l<a.r-0.5&&a.t<b.b-0.5&&b.t<a.b-0.5;
 const out=document.querySelector('#dev_out'),mir=document.querySelector('#mdev_cb'),sl=document.querySelector('#livevol');
 const vis=e=>e&&e.offsetParent!==null;
 const o={};
 const sp=e=>e.querySelector('span');
 o.outTrunc=false;o.outText=out.title;o.outTitle=out.title;
 o.mirOn=vis(mir);if(o.mirOn){o.mirTrunc=sp(mir).scrollWidth>sp(mir).clientWidth+1;o.mirText=sp(mir).textContent;o.mirTitle=mir.title}
 const ro=R(out),rs=R(sl),vr=R(document.querySelector('#cl .ctrl')),m=document.querySelector('#cl .vm,#cl .meters,#cl .msb');
 o.overlapSlider=x(ro,rs)||(o.mirOn&&x(R(mir),rs));o.overlapOutMir=o.mirOn&&x(ro,R(mir));
 o.sliderW=sl.getBoundingClientRect().width;o.sameLine=false;
 const lv=R(document.querySelector('#lvl'));o.outInRow=ro.l>=lv.l-1&&ro.r<=lv.r+1&&ro.b<=lv.b+1&&(!o.mirOn||(R(mir).r<=vr.r+1));
 const cl=document.querySelector('#cl').getBoundingClientRect();o.inCard=ro.r<=cl.right+1;
 o.pageOverflow=[...document.querySelectorAll('#cl *')].some(e=>e.offsetParent!==null&&e.getBoundingClientRect().right>cl.right+1);   // (the header's own overflow at 420px is older and not part of this card)
 const mt=document.querySelector('#cl .meter, #cl .vmwrap, #cl .mcol');o.meterL=mt?mt.getBoundingClientRect().left:null;o.rowR=vr.r;
 return o}"""


def main():
    from playwright.sync_api import sync_playwright
    box = Box(devices=DEV, state={"audio_device": LONG1, "mirror_device": LONG2, "mirror_enabled": False}).start()
    try:
        with sync_playwright() as p:
            br = p.chromium.launch()
            for skin in ("console", "studio", "stage"):
                for theme in ("light", "dark"):
                    for w in (420, 820, 1150, 1400):
                        for mirror in (False, True):
                            for wave in (True, False):
                                if theme == "dark" and not (w in (420, 1400) and wave):
                                    continue
                                box.post("/api/mirror/enable", {"on": mirror})
                                c = br.new_context(viewport={"width": w, "height": 900})
                                c.add_init_script(f"localStorage.setItem('cp_tour','1');localStorage.setItem('cp_theme','{theme}');localStorage.setItem('cp_skin','{skin}');localStorage.setItem('cp_wave','{1 if wave else 0}')")
                                pg = c.new_page(); pg.goto(box.url()); pg.wait_for_function("document.querySelector('#dev_out').title.length>14")
                                if mirror:
                                    pg.wait_for_selector("#mdev_cb:visible")
                                if not wave:
                                    pg.evaluate("typeof setWave==='function'&&setWave(false)")
                                time.sleep(0.4)
                                o = pg.evaluate(JS); tag = f"{skin}/{theme}/{w}px/mirror={'on' if mirror else 'off'}/wave={'on' if wave else 'off'}"
                                check(f"{tag}: no overlap, inside the Live meters, no page overflow", not o["overlapSlider"] and not o["overlapOutMir"] and o["outInRow"] and not o["pageOverflow"], o)
                                check(f"{tag}: slider >= 8rem (128px)", o["sliderW"] >= 127, o["sliderW"])
                                if w >= 820:
                                    check(f"{tag}: full names shown (not truncated)", not o["outTrunc"] and (not o["mirOn"] or not o["mirTrunc"]), o)
                                check(f"{tag}: tooltip holds the full name", LONG1 in o["outTitle"] and (not o["mirOn"] or LONG2 in o["mirTitle"]), o)
                                if SHOTS and ((theme == "light") or (w in (420, 1400))):
                                    SHOTS.mkdir(parents=True, exist_ok=True)
                                    r = pg.evaluate("(()=>{const r=document.querySelector('#cl').getBoundingClientRect();return {x:0,y:Math.max(0,r.top-6),width:innerWidth,height:r.height+12}})()")
                                    pg.screenshot(path=str(SHOTS / f"{skin}-{theme}-{w}-m{int(mirror)}-w{int(wave)}.png"), clip=r)
                                c.close()
            # a name too long for the row: ellipsis + full text in tooltip and in the open list
            box2 = box
            box2.post("/api/device", {"name": HUGE})
            c = br.new_context(viewport={"width": 420, "height": 900}); c.add_init_script("localStorage.setItem('cp_tour','1')")
            pg = c.new_page(); pg.goto(box.url()); pg.wait_for_function("document.querySelector('#dev_out').title.length>14")
            o = pg.evaluate(JS)
            check("huge name: the speaker button stays in place, the tooltip holds the full name", o["outInRow"] and not o["pageOverflow"] and HUGE in o["outTitle"], o)
            pg.click("#dev_out"); pg.wait_for_selector("#cbo:popover-open")
            rows = pg.evaluate("[...document.querySelectorAll('#cbo_l .cbo-i')].map(e=>({t:e.textContent,sw:e.firstChild.scrollWidth,cw:e.firstChild.clientWidth,title:e.title}))")
            check("open list shows the full text of every device (wraps, not cut)", all(r["sw"] <= r["cw"] + 1 for r in rows) and any(r["t"] == LONG2 for r in rows) and any(r["title"] == HUGE for r in rows), rows)
            if SHOTS:
                pg.screenshot(path=str(SHOTS / "huge-open-420.png"))
            c.close(); br.close()
    finally:
        box.cleanup()
    print("\n%d failure(s)" % len(FAILS))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
