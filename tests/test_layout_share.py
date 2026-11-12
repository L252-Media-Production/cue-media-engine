"""Layout export / import (player.py UI). Needs playwright + chromium; starts its own player on a spare port.
Run: SHOTS=/some/dir python tests/test_layout_share.py   (SHOTS is optional: also writes screenshots)"""
import json, os, socket, subprocess, sys, tempfile, time, urllib.request, shutil
from playwright.sync_api import sync_playwright
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from harness.appcopy import copy_app   # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = 18140
URL = f'http://127.0.0.1:{PORT}/'
SHOTS = os.environ.get('SHOTS')
FAILS = []


def check(name, cond, info=''):
    print(('PASS ' if cond else 'FAIL ') + name + ('' if cond else '  ' + str(info)))
    if not cond:
        FAILS.append(name)


def start():
    d = tempfile.mkdtemp()
    os.makedirs(d + '/media/library')
    # a dummy listener for the OSC output to Companion (on macOS an unanswered UDP send raises an error at start-up)
    global SINK
    SINK = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    SINK.bind(('127.0.0.1', PORT + 2))
    json.dump({'http_port': PORT, 'osc_in_port': PORT + 1, 'companion_host': '127.0.0.1', 'companion_osc_port': PORT + 2}, open(d + '/config.json', 'w'))
    copy_app(d, ROOT)   # player.py + cpl/ + static/; the player reads config.json and its data from the script's folder
    p = subprocess.Popen([sys.executable, '-u', '-I', d + '/player.py'], cwd=d,
                         env=dict(os.environ, SDL_AUDIODRIVER='dummy'), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(100):
        try:
            urllib.request.urlopen(URL + 'api/state', timeout=1)
            return p, d
        except Exception:
            time.sleep(.3)
    p.kill()
    raise SystemExit('server did not start')


CUSTOM = {'v': 3, 'b': {'cl': {'x': 0, 'y': 0, 'w': 8, 'h': 8}, 'fs': {'x': 8, 'y': 0, 'w': 4, 'h': 5}, 'pv': {'x': 8, 'y': 5, 'w': 4, 'h': 6},
                        'inpc': {'x': 0, 'y': 11, 'w': 12, 'h': 3},
                        'libcol': {'x': 0, 'y': 14, 'w': 6, 'h': 18}, 'plcol': {'x': 6, 'y': 14, 'w': 6, 'h': 18}}, 'hide': ['pv']}   # (6 blocks since the Live input card became one)


def wrap(**kw):
    o = {'app': 'cue-media-engine-layout', 'version': 1, 'name': 'Test', 'layout': CUSTOM}
    o.update(kw)
    return json.dumps(o)


def main():
    srv, tmp = start()
    try:
        with sync_playwright() as pw:
            br = pw.chromium.launch(channel=os.environ.get('PW_CHANNEL') or None)
            ctx = br.new_context(viewport={'width': 1400, 'height': 900}, accept_downloads=True)
            ctx.add_init_script("try{localStorage.setItem('cp_tour','1')}catch(e){}")   # no first-visit tour
            pg = ctx.new_page()
            errs = []
            pg.on('pageerror', lambda e: errs.append(str(e)))
            pg.goto(URL)
            pg.wait_for_function('typeof layParse==="function"')
            ev = pg.evaluate
            # --- round trip
            ev('l=>{LAY=layNorm(l);laySave();layPlace()}', CUSTOM)
            same = ev('''()=>{const a=layExportObj('rt',false).obj;const r=layParse(JSON.stringify(a));return JSON.stringify([r.ok,r.lay,LAY])}''')
            ok, lay, cur = json.loads(same)
            check('round trip: import gives the identical layout', ok and lay == cur, same)
            check('export has app/version/name/exported/layout', ev('''()=>{const o=layExportObj('rt',false).obj;return o.app==='cue-media-engine-layout'&&o.version===1&&o.name==='rt'&&!isNaN(Date.parse(o.exported))&&o.layout.v===3&&!('appearance' in o)}'''))
            check('appearance only when ticked', ev('''()=>{const o=layExportObj('x',true).obj.appearance;return !!o&&'skin' in o&&'theme' in o&&'waveforms' in o}'''))
            old = ev('t=>{const r=layParse(t);return r.ok}', json.dumps({'app': 'companionplayer-layout', 'version': 1, 'layout': CUSTOM}))
            check('the old companionplayer-layout name is still accepted on import', old is True, old)
            check('file name is sanitised', ev('''()=>layExportObj('My Rig/2: <Tour>!',false).fn''') == 'cue-media-engine-layout-My-Rig-2-Tour.json')
            check('empty name falls back to layout', ev('''()=>layExportObj('  ',false).fn''') == 'cue-media-engine-layout-layout.json')
            # --- download
            pg.click('text=Settings') if False else pg.evaluate('settings.showModal()')
            pg.click('#lay_more'); pg.click('#lay_menu button:has-text("Export layout")')
            pg.fill('#lx_name', 'Stage/Left 1')
            with pg.expect_download() as dl:
                pg.click('#lxdlg button.pri')
            f = dl.value
            check('download name', f.suggested_filename == 'cue-media-engine-layout-Stage-Left-1.json', f.suggested_filename)
            data = json.load(open(f.path()))
            check('download content', data['name'] == 'Stage/Left 1' and data['layout']['hide'] == ['pv'] and 'appearance' not in data)
            # --- legacy / damaged layouts inside a wrapper
            for label, lay in [('v1 rows', {'rows': [['cl'], ['fs', 'pv'], ['libcol', 'plcol']]}),
                               ('v2 rows+w', {'rows': [['cl', 'fs'], ['libcol']], 'w': {'cl': 3, 'fs': 1, 'libcol': 4}, 'hide': ['pv', 'zzz']}),
                               ('damaged numbers', {'b': {'cl': {'x': 'a', 'y': -5, 'w': 99, 'h': 0}, 'fs': {'x': 1e9, 'y': 2, 'w': 1, 'h': 1}}, 'hide': 'no'}),
                               ('overlap', {'b': {k: {'x': 0, 'y': 0, 'w': 12, 'h': 5} for k in CUSTOM['b']}})]:
                r = ev('t=>{try{const r=layParse(t);return {ok:r.ok,ids:r.ok?Object.keys(r.lay.b).sort().join():"",v:r.ok?r.lay.v:0}}catch(e){return {ex:String(e)}}}', wrap(layout=lay))
                check('layNorm repairs ' + label, r.get('ok') and r['ids'] == 'cl,fs,inpc,libcol,plcol,pv' and r['v'] == 3, r)
            ov = ev('t=>{const r=layParse(t);const L=Object.values(r.lay.b);for(let i=0;i<L.length;i++)for(let j=i+1;j<L.length;j++)if(lov(L[i],L[j]))return false;return true}', wrap(layout={'b': {k: {'x': 0, 'y': 0, 'w': 12, 'h': 5} for k in CUSTOM['b']}}))
            check('overlapping import is de-overlapped', ov)
            # --- rejections
            cases = [('oversize', 'x' * 70000, '64 KB'), ('not json', 'hello {', 'not valid JSON'),
                     ('wrong app', json.dumps({'app': 'other', 'version': 1, 'layout': CUSTOM}), 'not a Cue Media Engine'),
                     ('newer version', wrap(version=2), 'newer version'), ('no version', wrap(version='1'), 'valid version'),
                     ('array', '[1,2]', 'not a Cue Media Engine'), ('no layout', wrap(layout=None), 'no usable layout'),
                     ('garbage layout', wrap(layout={'foo': 1}), 'no usable layout')]
            for label, text, want in cases:
                pg.evaluate('layImport()')
                pg.fill('#li_txt', text)
                pg.wait_for_timeout(400)
                msg = pg.inner_text('#li_msg')
                check('rejected: ' + label, want in msg and pg.is_disabled('#li_go') and pg.is_hidden('#li_pv'), msg)
                if label == 'newer version' and SHOTS:
                    shot(pg, 'err')
            # oversize file through the file input
            big = os.path.join(tmp, 'big.json'); open(big, 'w').write('x' * 70000)
            pg.evaluate('layImport()'); pg.set_input_files('#li_file', big); pg.wait_for_timeout(300)
            check('oversize file rejected', '64 KB' in pg.inner_text('#li_msg'))
            before = pg.evaluate('localStorage.getItem("cp_layout")')
            # --- XSS name
            evil = '<img src=x onerror="window.__x=1"><script>window.__x=2</script>'
            pg.evaluate('layImport()'); pg.fill('#li_txt', wrap(name=evil)); pg.wait_for_timeout(400)
            xs = [pg.inner_text('#li_name'), pg.evaluate('window.__x'), pg.locator('#lidlg img').count()]
            check('xss name shown as text (cut to 60 characters)', xs[0] == evil[:60] and xs[1] is None and xs[2] == 0, xs)
            check('nothing stored by a preview', pg.evaluate('localStorage.getItem("cp_layout")') == before)
            check('preview has five-block names / hidden list', 'Hidden blocks: Preview' in pg.inner_text('#li_hid') and pg.locator('#li_map div').count() == 5)
            # --- apply + undo
            newlay = dict(CUSTOM, hide=[], b=dict(CUSTOM['b'], cl={'x': 0, 'y': 0, 'w': 12, 'h': 6}))
            pg.evaluate('layImport()'); pg.fill('#li_txt', wrap(name='Wide', layout=newlay)); pg.wait_for_timeout(400)
            if SHOTS: shot(pg, 'import')
            pg.click('#li_go')
            applied = json.loads(pg.evaluate('localStorage.getItem("cp_layout")'))
            check('apply stores the repaired layout', applied['b']['cl']['w'] == 12 and applied['v'] == 3)
            check('confirmation + undo button', 'applied' in pg.inner_text('#li_msg') and pg.locator('#li_msg .lundo').count() == 1)
            check('previous kept in cp_layout_prev', json.loads(pg.evaluate('localStorage.getItem("cp_layout_prev")'))['lay']['hide'] == ['pv'])
            if SHOTS: shot(pg, 'done')
            pg.click('#li_msg .lundo')
            back = json.loads(pg.evaluate('localStorage.getItem("cp_layout")'))
            check('undo restores the previous layout', back == CUSTOM, back)
            check('undo is used up', pg.evaluate('localStorage.getItem("cp_layout_prev")') is None and pg.is_hidden('#li_undo'))
            # undo after reload (from storage)
            pg.evaluate('layImport()'); pg.fill('#li_txt', wrap(layout=newlay)); pg.wait_for_timeout(400); pg.click('#li_go')
            pg.reload(); pg.wait_for_function('typeof layParse==="function"')
            pg.evaluate('layImport()')
            check('undo offered after reload', pg.is_visible('#li_undo'))
            pg.click('#li_undo')
            check('undo after reload works', json.loads(pg.evaluate('localStorage.getItem("cp_layout")')) == CUSTOM)
            # undo back to the standard layout
            pg.evaluate('layReset()')
            pg.evaluate('layImport()'); pg.fill('#li_txt', wrap(layout=newlay)); pg.wait_for_timeout(400); pg.click('#li_go')
            check('standard -> imported', pg.evaluate('localStorage.getItem("cp_layout")') is not None and pg.locator('#lay').count() == 1)
            pg.click('#li_msg .lundo')
            check('undo to the standard layout', pg.evaluate('localStorage.getItem("cp_layout")') is None and pg.locator('#lay').count() == 0)
            # --- appearance
            pg.evaluate('setLook("skin","console");setLook("theme","light");setWave(false)')
            ap = {'skin': 'stage', 'theme': 'dark', 'waveforms': True, 'evil': '<b>'}
            pg.evaluate('layImport()'); pg.fill('#li_txt', wrap(appearance=ap)); pg.wait_for_timeout(400)
            check('appearance offered, default off', pg.is_visible('#li_appf') and not pg.is_checked('#li_app'))
            pg.click('#li_go')
            check('appearance not applied unless ticked', pg.evaluate('LOOK.skin') == 'console')
            pg.click('#li_msg .lundo')
            pg.evaluate('layImport()'); pg.fill('#li_txt', wrap(appearance=ap)); pg.wait_for_timeout(400)
            pg.check('#li_app'); pg.click('#li_go')
            check('appearance applied when ticked', pg.evaluate('[LOOK.skin,LOOK.theme,WAVE]') == ['stage', 'dark', True])
            pg.click('#li_msg .lundo')
            check('undo restores appearance', pg.evaluate('[LOOK.skin,LOOK.theme,WAVE]') == ['console', 'light', False])
            check('bad appearance values are dropped', pg.evaluate('t=>JSON.stringify(layParse(t).app)', wrap(appearance={'skin': 'x', 'theme': 5, 'waveforms': 'yes'})) == 'null')
            pg.evaluate('layReset()')
            # --- drag and drop of text
            pg.evaluate('layImport()')
            pg.evaluate('''t=>{const dt=new DataTransfer();dt.setData('text',t);lidlg.dispatchEvent(new DragEvent('drop',{dataTransfer:dt,bubbles:true,cancelable:true}))}''', wrap(name='Dropped'))
            pg.wait_for_timeout(200)
            check('drop of text previews', pg.inner_text('#li_name') == 'Dropped')
            # drop of a file
            pg.evaluate('''t=>{const dt=new DataTransfer();dt.items.add(new File([t],'l.json',{type:'application/json'}));lidlg.dispatchEvent(new DragEvent('drop',{dataTransfer:dt,bubbles:true,cancelable:true}))}''', wrap(name='DroppedFile'))
            pg.wait_for_timeout(300)
            check('drop of a file previews', pg.inner_text('#li_name') == 'DroppedFile')
            pg.evaluate('lidlg.close()')
            # --- export of the standard layout
            pg.evaluate('layReset()')
            std = ev('()=>{const x=layExportObj("s",false);return {std:x.std,ids:Object.keys(x.obj.layout.b).length}}')
            check('standard layout is exported (measured)', std['std'] and std['ids'] == 6, std)
            pg.evaluate('layExport()')
            check('note says standard layout', pg.is_visible('#lx_note') and 'standard layout' in pg.inner_text('#lx_note'))
            if SHOTS: shot(pg, 'export')
            pg.evaluate('lxdlg.close()')
            # --- editor still works; bar buttons; reset; self-heal
            pg.evaluate('layEdit()')
            check('editor bar has Export/Import', pg.is_visible('#lebar button:has-text("Export layout")') and pg.is_visible('#lebar button:has-text("Import layout")'))
            if SHOTS: shot(pg, 'bar')
            pg.click('#lebar button:has-text("Import layout")')
            pg.fill('#li_txt', wrap(layout=newlay)); pg.wait_for_timeout(400); pg.click('#li_go')
            pg.evaluate('lidlg.close()')
            pg.click('#lebar .pri')
            check('import during edit survives Done', json.loads(pg.evaluate('localStorage.getItem("cp_layout")'))['b']['cl']['w'] == 12)
            pg.evaluate('layEdit()'); pg.click('#lebar button:has-text("Reset")')
            check('Reset layout still works', pg.evaluate('localStorage.getItem("cp_layout")') is None and pg.locator('#lay').count() == 0)
            pg.evaluate('localStorage.setItem("cp_layout",JSON.stringify({b:{cl:{x:"q",y:-3,w:50,h:0}}}))')
            pg.reload(); pg.wait_for_function('typeof layParse==="function"')
            healed = json.loads(pg.evaluate('localStorage.getItem("cp_layout")'))
            check('self-heal repairs damaged storage', healed['v'] == 3 and len(healed['b']) == 6)
            pg.evaluate('layReset()')
            # --- narrow screen
            pg.set_viewport_size({'width': 600, 'height': 900})
            pg.evaluate('layImport()'); pg.fill('#li_txt', wrap(layout=newlay)); pg.wait_for_timeout(400)
            check('narrow note shown', pg.is_visible('#li_narrow'))
            pg.click('#li_go')
            check('narrow: stored, not applied yet', 'wider screen' in pg.inner_text('#li_msg') and pg.evaluate('localStorage.getItem("cp_layout")') is not None and pg.locator('#lay').count() == 0)
            pg.evaluate('lidlg.close()')
            pg.set_viewport_size({'width': 1400, 'height': 900}); pg.wait_for_timeout(300)
            check('applies after widening', pg.locator('#lay').count() == 1)
            pg.set_viewport_size({'width': 600, 'height': 900})
            pg.evaluate('layReset()')
            std2 = ev('()=>{const x=layExportObj("n",false);return [x.std,Object.keys(x.obj.layout.b).length]}')
            check('narrow export falls back to default grid', std2 == [True, 6], std2)
            pg.evaluate('layEdit()')
            check('editing stays wide-only', pg.evaluate('LEDIT') is False)
            check('no page errors', not errs, errs)
            br.close()
    finally:
        srv.kill(); shutil.rmtree(tmp, ignore_errors=True)
    print('\n%d failed' % len(FAILS) if FAILS else '\nall passed')
    sys.exit(1 if FAILS else 0)


def shot(pg, name):
    th = pg.evaluate('document.documentElement.dataset.theme')
    pg.screenshot(path=f'{SHOTS}/{name}-{th}.png')


if __name__ == '__main__':
    main()
