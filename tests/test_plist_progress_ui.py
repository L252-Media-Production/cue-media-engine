#!/usr/bin/env python3
"""Playlist progress UI (2.7.3 Phase 3): header text (Track N of M, played, left, end time, mode chip), segmented bar (one segment per track, proportional,
continuous above 40 tracks), played rows (dimmed, no check since 2.7.4), the playing row (elapsed / length, 3 px line), other-playlist and nothing-live states, each play mode,
the RAM line on its own small line, no clipping. The page's own refresh is frozen so forced live state stays put.
3 skins x dark/light x desktop / phone / touch.    python tests/test_plist_progress_ui.py [SHOT_DIR]      (needs playwright; own disposable player)"""
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


# durations 60, 120, 180, 240 s (600 total); the 2nd track is live at 30 s
SET = """cfg=>{render=async()=>{};PL[0].tracks.forEach((t,k)=>{t.dur_eff=[60,120,180,240][k];t.end='default'});PL[0].mode=cfg.mode;PL[0].shuffle_left=cfg.left||null;
  if(cfg.loopcur)PL[0].tracks[1].end='loop';
  PL[1].mode='stop';PL[1].tracks.forEach(t=>t.dur_eff=100);
  LASTS.live_id=cfg.live;LASTS.live_pass=1;LASTS.live_passes=1;LIVE={fid:'x',pos:30,dur:120,lo:0,hi:120,playing:false,t0:performance.now()};
  lastHtml='';PGD={};renderLists(LASTS);plProgTick(true);return 0}"""
READ = """i=>{const el=document.querySelector(`#lists .plprog[data-i="${i}"]`),pl=el.closest('.pl'),r=e=>e.getBoundingClientRect(),
  segs=[...el.querySelectorAll('.seg')],plh=el.closest('.plh').getBoundingClientRect();
  const rows=[...pl.querySelectorAll('li.t')];const live=pl.querySelector('li.t.live');
  return {txt:el.querySelector('.ppt').textContent,chip:el.querySelector('.ppm').textContent,n:segs.length,one:el.querySelector('.pbar').classList.contains('one'),
    cls:segs.map(s=>s.classList.contains('cur')?'cur':s.classList.contains('done')?'done':'up'),fill:segs.map(s=>s.firstChild.style.width),
    flex:segs.map(s=>+getComputedStyle(s).flexGrow),w:segs.map(s=>r(s).width),barH:r(el.querySelector('.pbar')).height,
    done:rows.map(li=>li.classList.contains('done')),chk:rows.map(li=>!!li.querySelector('.rck')),rpe:live&&live.querySelector('.rpe')?live.querySelector('.rpe').textContent:null,
    rpl:live&&live.querySelector('.rpl b')?live.querySelector('.rpl b').style.width:null,rplH:live&&live.querySelector('.rpl')?r(live.querySelector('.rpl')).height:null,
    inside:r(el).left>=plh.left-1&&r(el).right<=plh.right+1,over:el.scrollWidth>el.clientWidth+1||pl.scrollWidth>pl.clientWidth+1,
    ram:el.querySelector('.plram')?{txt:el.querySelector('.plram').textContent,top:r(el.querySelector('.plram')).top,bar:r(el.querySelector('.pbar')).bottom,fs:parseFloat(getComputedStyle(el.querySelector('.plram')).fontSize)}:null}}"""


def main():
    from playwright.sync_api import sync_playwright
    if SHOTS:
        os.makedirs(SHOTS, exist_ok=True)
    with Instance(wav_only=True, project_dir=os.environ.get("PP_PROJECT") or PROJECT) as inst, sync_playwright() as p:
        api = client.Api(inst.base_url, osc_port=inst.osc_port)
        api.post("/api/playlists", {"name": "Show"}); api.post("/api/playlists", {"name": "Encore"})
        api.post("/api/playlists/0/add", {"files": ["tone_a.wav", "tone_b.wav", "tone_c.wav", "short_1s.wav"]})
        api.post("/api/playlists/1/add", {"files": ["short_1s.wav", "short_2s.wav"]})
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
                    pg.goto(inst.base_url); pg.wait_for_selector("#lists li.t"); pg.wait_for_function("document.querySelectorAll('#lists .plprog').length===2")
                    # --- stop at end
                    pg.evaluate(SET, {"mode": "stop", "live": "0/1"}); d = pg.evaluate(READ, 0)
                    check(f"{label}: stop: header text (Track 2 of 4, 1:30 played, 8:30 left, end time)", d["txt"].startswith("Track 2 of 4 · 1:30 played · 8:30 left · ends ") and d["chip"] == "Stop at end", d["txt"])
                    check(f"{label}: stop: one segment per track, proportional to the A-B window", d["n"] == 4 and [round(x) for x in d["flex"]] == [60, 120, 180, 240]
                          and all(abs(d["w"][k] / d["w"][0] - [1, 2, 3, 4][k]) < 0.45 for k in range(4)), d)
                    check(f"{label}: stop: played dark, current outlined with fill to the position, upcoming empty", d["cls"] == ["done", "cur", "up", "up"] and d["fill"][0] == "100%" and d["fill"][1].startswith("25") and d["fill"][2] == "0px" or d["fill"][2] == "0", d)
                    check(f"{label}: stop: bar is 8 px, header inside the playlist, nothing overflows", abs(d["barH"] - 8) < 0.6 and d["inside"] and not d["over"], d)
                    check(f"{label}: stop: the played row is dimmed (no check mark since 2.7.4), the others not", d["done"] == [True, False, False, False] and d["chk"] == [False] * 4, d)
                    check(f"{label}: stop: playing row shows elapsed / length and a 3 px line at 25 %", d["rpe"] == "▶ 0:30 / 2:00" and d["rpl"].startswith("25") and abs(d["rplH"] - 3) < 0.6, d)
                    check(f"{label}: RAM text is on its own small line below the bar", d["ram"] and d["ram"]["top"] >= d["ram"]["bar"] - 0.5 and d["ram"]["fs"] < 14 and "in RAM" in d["ram"]["txt"], d["ram"])
                    if SHOTS and theme == "dark" and tag != "touch":
                        pg.locator("#lists .pl").first.screenshot(path=f"{SHOTS}/prog-stop-{skin}-{tag}.png")
                    # --- loop playlist
                    pg.evaluate(SET, {"mode": "loop_playlist", "live": "0/1"}); d = pg.evaluate(READ, 0)
                    check(f"{label}: loop: chip Loop, time left counted for this lap", d["chip"] == "Loop" and "8:30 left this lap" in d["txt"], d)
                    # --- shuffle: bag still holds only the 4th track, so tracks 0 and 2 are played
                    pg.evaluate(SET, {"mode": "shuffle", "live": "0/1", "left": ["short_1s.wav"]}); d = pg.evaluate(READ, 0)
                    check(f"{label}: shuffle: played = not in the bag; left = this round", d["chip"] == "Shuffle" and d["txt"].startswith("Track 3 of 4 · 4:30 played · 5:30 left this round") and d["cls"] == ["done", "cur", "done", "up"], d)
                    if SHOTS and theme == "dark" and tag != "touch":
                        pg.locator("#lists .pl").first.screenshot(path=f"{SHOTS}/prog-shuffle-{skin}-{tag}.png")
                    # --- next playlist
                    pg.evaluate(SET, {"mode": "next_playlist", "live": "0/1"}); d = pg.evaluate(READ, 0)
                    check(f"{label}: next playlist: chip, end time and the name of the next playlist", d["chip"] == "Next playlist" and d["txt"].endswith("→ Encore") and " ends " in d["txt"], d["txt"])
                    # --- looping track
                    pg.evaluate(SET, {"mode": "stop", "live": "0/1", "loopcur": True}); d = pg.evaluate(READ, 0)
                    check(f"{label}: a looping track shows 'looping this track' instead of a time left", "looping this track" in d["txt"] and "left" not in d["txt"], d["txt"])
                    # --- another playlist is live / nothing live
                    pg.evaluate(SET, {"mode": "stop", "live": "1/0"}); d0, d1 = pg.evaluate(READ, 0), pg.evaluate(READ, 1)
                    check(f"{label}: live in another playlist: this header shows totals only, empty bar", d0["txt"] == "4 tracks · 10:00 total" and d0["cls"] == ["up"] * 4 and d0["rpe"] is None, d0)
                    check(f"{label}: ... and the playing playlist shows its position", d1["txt"].startswith("Track 1 of 2 · 0:30 played · 2:50 left"), d1["txt"])
                    pg.evaluate(SET, {"mode": "stop", "live": "-"}); d = pg.evaluate(READ, 0)
                    check(f"{label}: nothing live: totals only, no current segment, no done rows", d["txt"] == "4 tracks · 10:00 total" and "cur" not in d["cls"] and not any(d["done"]), d)
                    # --- more than 40 tracks: one continuous bar
                    pg.evaluate("""()=>{const t=PL[0].tracks;while(PL[0].tracks.length<45)PL[0].tracks.push(Object.assign({},t[0]));lastHtml='';PGD={};LASTS.live_id='0/1';renderLists(LASTS);plProgTick(true)}""")
                    d = pg.evaluate(READ, 0)
                    check(f"{label}: 45 tracks: one continuous bar, still filled to the position", d["one"] and d["n"] == 1 and d["fill"][0] not in ("", "0px", "0") and not d["over"], d)
                    check(f"{label}: no page errors", not errs, errs)
                    c.close()
        br.close()
    print(f"\n{len(FAILS)} failure(s)")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
