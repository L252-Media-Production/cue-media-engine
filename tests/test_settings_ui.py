#!/usr/bin/env python3
"""Settings rework (2.7.5): four tabs on a desktop, collapsible sections with live summaries and a search box on a phone (one open at a time),
no Save button and no Refresh devices button, Companion address checked on leaving the field (the address in use stays), Send test with its result box,
Time warnings with any number of rows (sorted by time, First / Warning N / Final labels), Layout More menu.    python tests/test_settings_ui.py  (needs playwright)"""
import os
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from harness import client                       # noqa: E402
from harness.instance import Instance, PROJECT   # noqa: E402

FAILS = []


def check(name, ok, info=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"   {info}"))
    if not ok:
        FAILS.append(name)


def opened(br, w, h, touch=False):
    c = br.new_context(viewport={"width": w, "height": h}, has_touch=touch, is_mobile=touch)
    c.add_init_script("localStorage.setItem('cp_tour','1')")
    pg = c.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    return c, pg, errs

LOOKJS = "s=>s"
# elements of #settings that stick out of the dialog's right edge (visible ones only), as [selector-ish, right overflow px]
OVERFLOW = """()=>{const d=document.getElementById('settings'),r=d.getBoundingClientRect(),out=[];
  d.querySelectorAll('*').forEach(e=>{const b=e.getBoundingClientRect();if(!b.width||!b.height||e.closest('[hidden]'))return;const cs=getComputedStyle(e);
   if(cs.display==='none'||cs.visibility==='hidden'||e.closest('.cbsel')&&e.classList.contains('cbsel'))return;
   if(b.right>r.right+1||b.left<r.left-1)out.push((e.id?'#'+e.id:e.className||e.tagName)+' '+Math.round(b.right-r.right))});return out.slice(0,6)}"""
# WCAG contrast of the text colour against the composited background, for every visible element matched; "bad" below 4.5 (3 for text over 24px)
CONTRAST = r"""sels=>{
  const num=s=>(s.match(/-?[\d.]+(?:e-?\d+)?/g)||[]).map(Number);
  const parse=s=>{if(!s||s==='transparent')return null;const n=num(s);if(s.startsWith('color(')){return n.length<3?null:[n[0]*255,n[1]*255,n[2]*255,n.length>3?n[3]:1]}
    if(s.startsWith('rgb')){return [n[0],n[1],n[2],n.length>3?n[3]:1]}return null};
  const over=(top,bot)=>{const a=top[3];return [top[0]*a+bot[0]*(1-a),top[1]*a+bot[1]*(1-a),top[2]*a+bot[2]*(1-a),1]};
  const bg=el=>{const chain=[];for(let e=el;e;e=e.parentElement){const c=parse(getComputedStyle(e).backgroundColor);if(c&&c[3]>0)chain.push(c)}
    let base=[255,255,255,1];for(let i=chain.length-1;i>=0;i--)base=over(chain[i],base);return base};
  const lum=c=>{const f=v=>{v/=255;return v<=0.03928?v/12.92:Math.pow((v+0.055)/1.055,2.4)};return 0.2126*f(c[0])+0.7152*f(c[1])+0.0722*f(c[2])};
  const out=[];
  for(const sel of sels)document.querySelectorAll(sel).forEach(e=>{const b=e.getBoundingClientRect();if(!b.width||!b.height||e.closest('[hidden]'))return;
    const cs=getComputedStyle(e);if(cs.display==='none'||cs.visibility==='hidden')return;
    const fg=parse(cs.color);if(!fg)return;let back=bg(e);if(e.tagName==='INPUT'||e.tagName==='SELECT')back=bg(e);
    const f=fg[3]<1?over(fg,back):fg,l1=lum(f),l2=lum(back),r=(Math.max(l1,l2)+0.05)/(Math.min(l1,l2)+0.05);
    const big=parseFloat(cs.fontSize)>=24;out.push({sel,text:(e.textContent||e.value||'').trim().slice(0,24),ratio:Math.round(r*10)/10,bad:r<(big?3:4.5)})});
  return out}"""

CHIPS = """()=>{const out=[];document.querySelectorAll('#settings .chipb, #settings .dotc').forEach(e=>{const r=e.getBoundingClientRect();if(!r.width||e.closest('[hidden]'))return;
  const g=document.createRange();g.selectNodeContents(e);const t=g.getBoundingClientRect();
  const dx=Math.abs((t.left+t.right)/2-(r.left+r.right)/2),dy=Math.abs((t.top+t.bottom)/2-(r.top+r.bottom)/2);if(dx>1.5||dy>1.5)out.push((e.id||e.className)+' '+dx.toFixed(1)+','+dy.toFixed(1))});return out}"""


def main():
    from playwright.sync_api import sync_playwright
    with Instance(wav_only=True, project_dir=os.environ.get("PP_PROJECT") or PROJECT) as inst, sync_playwright() as p:
        api = client.Api(inst.base_url, osc_port=inst.osc_port)
        br = p.chromium.launch()
        orig = api.get("/api/settings").json

        # ---------------- desktop: tabs
        c, pg, errs = opened(br, 1280, 900)
        pg.goto(inst.base_url); pg.wait_for_selector("#setbtn"); pg.click("#setbtn"); pg.wait_for_selector("#settings[open]")
        vis = lambda sel: pg.is_visible(sel)          # noqa: E731
        check("four tabs", pg.locator("#set_tabs button").all_inner_texts() == ["Look", "Audio", "Companion", "System"])
        check("no Save button", pg.locator("#settings button", has_text="Save").count() == 0)
        check("no Refresh devices button", pg.locator("#set_refdev").count() == 0 and "Refresh devices" not in pg.inner_text("#settings"))
        pg.click("#set_tabs [data-tab=look]")
        check("Look shows appearance + layout", vis("#set_skin") and vis("#set_wave") and vis("#wn_toggle") and vis("#dfi_cur") and vis("#lay_more") and not vis("#set_host"))
        check("This browser only chips on Appearance and Layout", pg.locator("#settings .chipb", has_text="This browser only").filter(visible=True).count() == 2)
        check("waveforms is a switch", pg.eval_on_selector("#set_wave", "e=>e.parentElement.classList.contains('swl')"))

        # time warnings: any number, sorted, labels
        pg.click("#wn_toggle")
        for _ in range(9):
            pg.click("#wn_add")
        pg.wait_for_function("document.querySelectorAll('#wn_rows .wr').length===11")
        labs = pg.locator("#wn_rows .wnn").all_inner_texts()
        check("11 warnings: First / Warning N / Final", labs[0] == "First warning" and labs[1] == "Warning 2" and labs[-1] == "Final warning" and len(labs) == 11, labs)
        got = api.get("/api/settings/warning").json["warnings"]
        check("the player holds all 11, longest first", len(got) == 11 and [w["t"] for w in got] == sorted([w["t"] for w in got], reverse=True), got)
        pg.locator("#wn_rows .wr").nth(3).locator("input[data-k=t]").fill("20:00"); pg.keyboard.press("Tab"); time.sleep(0.5)
        got = api.get("/api/settings/warning").json["warnings"]
        check("a time edited past the others moves to the top", got[0]["t"] == 1200, got[:3])
        check("closed row summarises the colours", pg.locator("#wn_sum .dotc").count() == 11)
        while pg.locator("#wn_rows .wr").count() > 2:
            pg.locator("#wn_rows .wnx").last.click(); time.sleep(0.1)
        check("remove works down to two", len(api.get("/api/settings/warning").json["warnings"]) == 2)

        # layout More menu
        check("More menu closed, three actions inside", not vis("#lay_menu") and pg.locator("#lay_menu button").all_inner_texts() == ["Reset layout", "Export layout", "Import layout"])
        pg.click("#lay_more"); check("More opens the menu", vis("#lay_menu"))
        pg.keyboard.press("Escape"); check("Esc closes the menu, not Settings", not vis("#lay_menu") and vis("#settings"))
        pg.click("#lay_more"); pg.click("#lay_menu >> text=Reset layout"); check("menu closes after a choice", not vis("#lay_menu"))
        if not vis("#settings"):
            pg.click("#setbtn"); pg.wait_for_selector("#settings[open]")      # Reset layout closes Settings, as before

        # audio tab
        pg.click("#set_tabs [data-tab=audio]")
        check("Audio: preview, output, mirror, transitions", vis("#set_pvt") and vis("#set_pv_cb") and vis("#set_mir") and vis("#tr_seg") and vis("#tr_ms") and vis("#tr_fd") and vis("#tr_fi"))
        check("Mirror device row hidden while off", not vis("#set_mdev_cb"))
        pg.check("#set_mir", force=True); time.sleep(1.0)
        check("Mirror device menu appears under the switch", vis("#set_mdev_cb") and api.get("/api/devices").json["mirror_enabled"])
        pg.uncheck("#set_mir", force=True); time.sleep(0.6)
        check("Preview line describes the chosen option only", "speakers or headphones" in pg.inner_text("#set_pvnote"), pg.inner_text("#set_pvnote"))
        pg.fill("#tr_ms", "4.5"); pg.press("#tr_ms", "Tab"); time.sleep(0.5)
        check("transition changes save at once", api.get("/api/settings/transition").json["crossfade_ms"] == 4500)
        pg.fill("#tr_ms", "3"); pg.press("#tr_ms", "Tab")

        # (i) tips
        pg.locator("#settings .ib2:visible").first.click()
        check("an (i) opens one sentence under its row", pg.locator("#settings .tipbox").count() == 1)

        # companion tab
        pg.click("#set_tabs [data-tab=companion]")
        chip0 = pg.inner_text("#cmp_to")
        pg.fill("#set_host", "192.168.1."); pg.press("#set_host", "Tab"); time.sleep(0.4)
        check("an incomplete address shows the warning and a red field", vis("#cmp_warn") and "Incomplete" in pg.inner_text("#cmp_warn") and "bad" in (pg.get_attribute("#set_host", "class") or ""))
        check("  'Sending to' keeps the old address", pg.inner_text("#cmp_to") == chip0 and api.get("/api/settings").json["target"] == orig["target"])
        # variable prefix
        check("Variable prefix shows the current one and an example", pg.input_value("#set_prefix") == api.state()["variable_prefix"] and "Example:" in pg.inner_text("#pfx_ex"))
        pg.fill("#set_prefix", "1x"); pg.press("#set_prefix", "Tab"); time.sleep(0.3)
        check("an invalid prefix shows the red warning, no dialog, the old one stays", vis("#pfx_warn") and not vis("#pfxdlg") and api.state()["variable_prefix"] == "mp_" and "bad" in (pg.get_attribute("#set_prefix", "class") or ""))
        pg.fill("#set_prefix", "zz_"); check("live preview under the field", pg.inner_text("#pfx_ex") == "Example: zz_remaining", pg.inner_text("#pfx_ex"))
        pg.press("#set_prefix", "Tab"); pg.wait_for_selector("#pfxdlg[open]")
        check("a changed prefix asks first, naming both prefixes and the consequence", pg.inner_text("#pfx_old").startswith("mp_") and pg.inner_text("#pfx_new").startswith("zz_") and "must be updated" in pg.inner_text("#pfxdlg") and api.state()["variable_prefix"] == "mp_")
        pg.click("#pfxdlg button[value=cancel]"); time.sleep(0.3)
        check("Cancel changes nothing and puts the old prefix back", api.state()["variable_prefix"] == "mp_" and pg.input_value("#set_prefix") == "mp_")
        pg.fill("#set_prefix", "zz_"); pg.press("#set_prefix", "Tab"); pg.wait_for_selector("#pfxdlg[open]"); pg.click("#pfxdlg #pfx_ok"); time.sleep(0.8)
        check("confirming applies it and shows a result chip", api.state()["variable_prefix"] == "zz_" and vis("#pfx_res") and "zz_" in pg.inner_text("#pfx_res"))
        check("the Variables row and the test text follow the prefix", pg.inner_text("#cmp_vars").startswith("zz_live_name"))
        pg.click("#cmp_test"); pg.wait_for_selector("#cmp_res:visible")
        check("Send test names the new variable", "zz_test" in pg.inner_text("#cmp_res"), pg.inner_text("#cmp_res"))
        # the Variables page and a second Settings page follow a prefix change without a reload
        vp = c.new_page(); vp.goto(inst.base_url + "/variables"); vp.wait_for_selector("#rows code"); time.sleep(0.8)
        check("the Variables page shows the current prefix", vp.inner_text("#rows code").startswith("zz_"), vp.inner_text("#rows code"))
        other = c.new_page(); other.goto(inst.base_url); other.wait_for_selector("#setbtn"); other.evaluate("openSettings()"); other.wait_for_selector("#settings[open]"); other.click("#set_tabs [data-tab=companion]"); time.sleep(0.5)
        check("a second browser page shows it too", other.input_value("#set_prefix") == "zz_")
        pg.fill("#set_prefix", "mp_"); pg.press("#set_prefix", "Tab"); pg.wait_for_selector("#pfxdlg[open]"); pg.click("#pfxdlg #pfx_ok"); time.sleep(0.6)
        time.sleep(1.5)
        check("the Variables page followed the change back without a reload", vp.inner_text("#rows code").startswith("mp_"), vp.inner_text("#rows code"))
        check("the second Settings page followed too (field and Send test text)", other.input_value("#set_prefix") == "mp_" and "mp_live_name" in other.inner_text("#cmp_vars"), (other.input_value("#set_prefix"), other.inner_text("#cmp_vars")))
        vp.close(); other.close()
        check("back to the default prefix", api.state()["variable_prefix"] == "mp_")
        pg.click("#cmp_test"); pg.wait_for_selector("#cmp_res:visible")
        check("  Send test still uses the address in use", "Test sent" in pg.inner_text("#cmp_res") and orig["target"].replace(":", " : ") in pg.inner_text("#cmp_res"), pg.inner_text("#cmp_res"))
        pg.fill("#set_host", "localhost"); pg.press("#set_host", "Tab"); time.sleep(0.6)
        check("a complete address clears the warning and is saved", not vis("#cmp_warn") and api.get("/api/settings").json["companion_host"] == "localhost" and "localhost" in pg.inner_text("#cmp_to"))
        pg.fill("#set_host", "no-such-host.invalid"); pg.press("#set_host", "Tab"); time.sleep(1.5)
        check("a well-formed name that does not resolve is saved, with an amber note (not the red warning)",
              api.get("/api/settings").json["companion_host"] == "no-such-host.invalid" and vis("#cmp_note") and not vis("#cmp_warn") and "bad" not in (pg.get_attribute("#set_host", "class") or ""))
        check("  'Sending to' shows the new address", "no-such-host.invalid" in pg.inner_text("#cmp_to"))
        pg.click("#cmp_test"); pg.wait_for_selector("#cmp_res.bad")
        check("  Send test says Couldn't send, Host not found, Still using host : port", all(x in pg.inner_text("#cmp_res") for x in ("Couldn't send", "Host not found", f"Still using no-such-host.invalid : {orig['companion_osc_port']}")), pg.inner_text("#cmp_res"))
        pg.fill("#set_host", orig["companion_host"]); pg.press("#set_host", "Tab"); time.sleep(0.8)
        check("a resolvable address again hides the amber note", not vis("#cmp_note"))
        pg.evaluate("(()=>{const f=window.fetch;window.fetch=(u,o)=>String(u).includes('companion/test')?new Promise(r=>setTimeout(()=>r(f(u,o)),700)):f(u,o)})()")
        pg.click("#cmp_test"); time.sleep(0.2)
        check("Send test is disabled while it is sending", pg.is_disabled("#cmp_test"))
        pg.wait_for_function("!document.querySelector('#cmp_test').disabled")
        check("  result box shows the time and mp_test", "Test sent" in pg.inner_text("#cmp_res") and "mp_test" in pg.inner_text("#cmp_res"))
        check("Variables row has View and Resend now", pg.locator("#settings button", has_text="Resend now").is_visible())

        # system tab
        pg.click("#set_tabs [data-tab=system]")
        check("System: rescan, file check chip, help, ffmpeg chip, restart, version", vis("#fmt_chip") and vis("#ff_chip") and pg.locator("#settings button", has_text="Restart player").is_visible() and "Cue Media Engine" in pg.inner_text("#appver"))
        pg.evaluate("fmt_chip.textContent='3 files need attention: a very long result text that has to wrap onto a second line'")
        off = pg.evaluate(CHIPS)
        check("every chip in System has its text centred, also a long wrapping one", not off, off)
        pg.evaluate("fmtLoad()"); time.sleep(0.8)
        check("File check chip says something", pg.inner_text("#fmt_chip").strip() not in ("", "…"), pg.inner_text("#fmt_chip"))
        check("no page errors (desktop)", not errs, errs)
        c.close()

        # ---------------- phone: sections
        c, pg, errs = opened(br, 390, 844, True)
        pg.goto(inst.base_url); pg.wait_for_selector("#setbtn"); pg.click("#setbtn"); pg.wait_for_selector("#settings[open]")
        check("phone: no tab bar, search box", not pg.is_visible("#set_tabs") and pg.is_visible("#set_search"))
        heads = pg.locator("#settings .ss:visible > .sh b").all_inner_texts()
        check("phone: eight sections, in order (2.8.0 added Health and alerts)", heads == ["Appearance", "Layout", "Audio", "Transitions", "Companion", "Library", "Health and alerts", "Maintenance"], heads)
        check("phone: all closed", pg.locator("#settings .ss.open").count() == 0 and not pg.is_visible("#set_skin"))
        sums = pg.locator("#settings .ss > .sh .ssum").all_inner_texts()
        check("phone: each section has a one-line summary", all(s.strip() and s.strip() != "…" for s in sums[:5]), sums)
        pg.click("[data-sec=audio] .sh"); check("phone: tapping opens a section", pg.is_visible("#set_pvt_cb"))
        pg.click("[data-sec=transitions] .sh")
        check("phone: only one open at a time", pg.locator("#settings .ss.open").count() == 1 and not pg.is_visible("#set_pvt_cb") and pg.is_visible("#tr_ms"))
        pg.click("#tr_seg [data-v=crossfade]"); time.sleep(0.5)
        check("phone: summary follows the change", pg.inner_text("#sum_transitions").startswith("Crossfade"), pg.inner_text("#sum_transitions"))
        pg.click("#tr_seg [data-v=cut]"); time.sleep(0.3)
        pg.fill("#set_search", "mirror")
        check("phone: search shows only matching sections, opened", pg.locator("#settings .ss:visible").count() == 1 and pg.is_visible("#set_mir"), pg.locator("#settings .ss:visible").count())
        pg.fill("#set_search", "")
        check("phone: clearing the search closes everything", pg.locator("#settings .ss.open").count() == 0 and pg.locator("#settings .ss:visible").count() == 8)
        pg.click("[data-sec=companion] .sh"); pg.fill("#set_host", "10.0."); pg.press("#set_host", "Tab"); time.sleep(0.3)
        check("phone: incomplete address says 'Still using' in the summary", pg.inner_text("#sum_companion").startswith("Still using"), pg.inner_text("#sum_companion"))
        check("no page errors (phone)", not errs, errs)
        c.close()
        api.post("/api/settings", {"companion_host": orig["companion_host"], "companion_osc_port": orig["companion_osc_port"]})

        # ---------------- phone, every skin and theme: no overflow, readable, screenshots
        shots = os.environ.get("SETTINGS_SHOTS") or (sys.argv[1] if len(sys.argv) > 1 else None)
        if shots:
            os.makedirs(shots, exist_ok=True)
        for skin in ("console", "studio", "stage"):
            for theme in ("light", "dark"):
                c = br.new_context(viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True)
                c.add_init_script(f"localStorage.setItem('cp_tour','1');localStorage.setItem('cp_skin','{skin}');localStorage.setItem('cp_theme','{theme}')")
                pg = c.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
                tag = f"{skin}/{theme} phone"
                pg.goto(inst.base_url); pg.wait_for_selector("#setbtn"); pg.click("#setbtn"); pg.wait_for_selector("#settings[open]"); time.sleep(0.4)
                shot = lambda n: pg.screenshot(path=f"{shots}/phone-{skin}-{theme}-{n}.png") if shots else None   # noqa: E731
                shot("1-closed")
                look = lambda sel: pg.evaluate(LOOKJS, sel)     # noqa: E731
                check(f"{tag}: the page really uses {skin}/{theme}", pg.evaluate("[document.documentElement.dataset.skin,document.documentElement.dataset.theme]") == [skin, pg.evaluate("document.documentElement.dataset.theme")] and pg.evaluate("document.documentElement.dataset.skin") == skin)
                check(f"{tag}: closed sections: summaries visible and readable", not [b for b in pg.evaluate(CONTRAST, [".ss > .sh .ssum", ".ss > .sh b"]) if b["bad"]], pg.evaluate(CONTRAST, [".ss > .sh .ssum", ".ss > .sh b"]))
                pg.click("[data-sec=appearance] .sh"); pg.click("#wn_toggle"); time.sleep(0.3)
                shot("2-appearance")
                check(f"{tag}: Appearance: no horizontal overflow", pg.evaluate(OVERFLOW) == [], pg.evaluate(OVERFLOW))
                bad = [b for b in pg.evaluate(CONTRAST, ["#settings .sr label", "#settings .lb2", "#settings .wr .wnn", "#settings .wr em", "#settings .wnh", "#settings .seg button", "#settings .dotc"]) if b["bad"]]
                check(f"{tag}: Appearance: text contrast", not bad, bad)
                pg.click("[data-sec=companion] .sh")
                pg.fill("#set_host", "192.168.1."); pg.press("#set_host", "Tab"); time.sleep(0.3)
                pg.click("#cmp_test"); pg.wait_for_selector("#cmp_res:visible"); time.sleep(0.2)
                shot("3-companion-incomplete-test-ok")
                check(f"{tag}: Companion (red warning + test result): no overflow", pg.evaluate(OVERFLOW) == [], pg.evaluate(OVERFLOW))
                bad = [b for b in pg.evaluate(CONTRAST, ["#cmp_warn", "#cmp_res", "#cmp_to", "#set_host", "#settings .sr label", "#settings .lb2", "#settings .ss.open .ssum"]) if b["bad"]]
                check(f"{tag}: Companion: warning, result, chip and field contrast", not bad, bad)
                check(f"{tag}: the red warning and the result box are visible", pg.is_visible("#cmp_warn") and pg.is_visible("#cmp_res") and pg.evaluate("document.querySelector('#cmp_warn').getBoundingClientRect().height") > 20)
                pg.fill("#set_host", "no-such-host.invalid"); pg.press("#set_host", "Tab"); time.sleep(1.5)
                pg.click("#cmp_test"); pg.wait_for_selector("#cmp_res.bad"); time.sleep(0.2)
                shot("4-companion-amber-test-failed")
                check(f"{tag}: amber note + failed test: visible, no overflow", pg.is_visible("#cmp_note") and pg.is_visible("#cmp_res") and pg.evaluate(OVERFLOW) == [], pg.evaluate(OVERFLOW))
                bad = [b for b in pg.evaluate(CONTRAST, ["#cmp_note", "#cmp_res", "#cmp_to"]) if b["bad"]]
                check(f"{tag}: amber note and failed result contrast", not bad, bad)
                check(f"{tag}: no horizontal scroll inside Settings", pg.evaluate("(()=>{const d=document.getElementById('settings');return d.scrollWidth<=d.clientWidth+1})()"))
                check(f"{tag}: no page errors", not errs, errs)
                c.close()
                api.post("/api/settings", {"companion_host": orig["companion_host"], "companion_osc_port": orig["companion_osc_port"]})
        br.close()
    print(f"\n{len(FAILS)} failed" if FAILS else "\nall passed")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
