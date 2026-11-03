"""Real-time UI test of app/ over the Chrome DevTools protocol (no virtual time).
Serves the project on its own port so it can't collide with .qa/ runs.
usage: python3 run.py            -> writes out/*.pdf, out/*.png, prints a report"""
import base64, json, json, os, shutil, subprocess, sys, time, urllib.request
import websocket

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(HERE, 'out'); os.makedirs(OUT, exist_ok=True)
HTTP, CDP = 8777, 9444
URL = f'http://localhost:{HTTP}/app/index.html'

SERVER = r'''
import http.server, sys
class H(http.server.SimpleHTTPRequestHandler):
    def end_headers(self): self.send_header('Cache-Control','no-store'); super().end_headers()
    def log_message(self,*a): pass
http.server.ThreadingHTTPServer(('127.0.0.1', int(sys.argv[1])), H).serve_forever()
'''
server = subprocess.Popen([sys.executable, '-c', SERVER, str(HTTP)], cwd=ROOT)
prof = os.path.join(HERE, f'prof-{os.getpid()}')
chrome = subprocess.Popen(['google-chrome', '--headless=new', '--disable-gpu', '--no-sandbox', f'--user-data-dir={prof}',
                           f'--remote-debugging-port={CDP}', '--remote-allow-origins=*', '--window-size=412,915', 'about:blank'],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
errors, results = [], []

def check(name, ok, detail=''):
    results.append((name, ok, detail)); print(('PASS ' if ok else 'FAIL ') + name + (f'  — {detail}' if detail else ''), flush=True)

try:
    for _ in range(100):
        try: tabs = json.load(urllib.request.urlopen(f'http://127.0.0.1:{CDP}/json/list')); break
        except Exception: time.sleep(0.2)
    ws = websocket.create_connection([t for t in tabs if t['type'] == 'page'][0]['webSocketDebuggerUrl'], timeout=120, suppress_origin=True)
    mid = 0
    def cmd(method, **params):
        global mid; mid += 1
        ws.send(json.dumps({'id': mid, 'method': method, 'params': params}))
        while True:
            m = json.loads(ws.recv())
            if m.get('method') == 'Runtime.exceptionThrown':
                errors.append(m['params']['exceptionDetails'].get('exception', {}).get('description', '?')[:200])
            elif m.get('method') == 'Runtime.consoleAPICalled' and m['params']['type'] == 'error':
                errors.append('console: ' + ' '.join(str(a.get('value', a.get('description', ''))) for a in m['params']['args'])[:200])
            if m.get('id') == mid:
                if 'error' in m: raise RuntimeError(m['error'])
                return m.get('result', {})
    def ev(expr):
        r = cmd('Runtime.evaluate', expression=expr, awaitPromise=True, returnByValue=True)
        if 'exceptionDetails' in r: raise RuntimeError(r['exceptionDetails'].get('exception', {}).get('description'))
        return r['result'].get('value')
    def wait(expr, t=30):
        end = time.time() + t
        while time.time() < end:
            try:
                if ev(expr): return True
            except Exception: pass
            time.sleep(0.2)
        return False
    def typeinto(sel, text):
        ev(f"(()=>{{const e=document.querySelector({json.dumps(sel)}); e.focus(); e.select && e.select();}})()")
        cmd('Input.insertText', text=text)
    def save_pdf(tag):
        b64 = ev("(async()=>{const b=RxApp.pdf(); if(!b) return ''; const u=new Uint8Array(await b.arrayBuffer()); let s=''; for(let i=0;i<u.length;i+=32768) s+=String.fromCharCode.apply(null,u.subarray(i,i+32768)); return btoa(s);})()")
        if not b64: return None
        p = os.path.join(OUT, f'{tag}.pdf'); open(p, 'wb').write(base64.b64decode(b64))
        subprocess.run(['pdftoppm', '-r', '110', '-png', p, os.path.join(OUT, tag)], check=True)
        return p

    cmd('Runtime.enable'); cmd('Page.enable')
    cmd('Emulation.setDeviceMetricsOverride', width=412, height=915, deviceScaleFactor=2.625, mobile=True)
    cmd('Emulation.setTouchEmulationEnabled', enabled=True)
    cmd('Page.navigate', url=URL)
    check('app loads, RxApp defined', wait("typeof RxApp !== 'undefined' && document.readyState === 'complete'"))

    ev("""window.T = {
      $: s => document.querySelector(s), $$: s => [...document.querySelectorAll(s)],
      set(id, v){ const e = document.getElementById(id); e.value = v; e.dispatchEvent(new Event('input', {bubbles:true})); },
      tap(sel, text){ const e = T.$$(sel).find(x => x.textContent.trim() === text); if (!e) throw new Error('no chip ' + text); e.click(); },
      async pdf(){ for (let i = 0; i < 600 && !RxApp.pdf() && T.$('#pv-send').textContent !== 'Failed'; i++) await new Promise(r => setTimeout(r, 50)); return !!RxApp.pdf(); },
      p2over(){ const p = T.$('#live .pg2'); if (!p || p.hidden) return null;
        const b = p.querySelector('.sheet-body').getBoundingClientRect().bottom;
        return Math.max(...[...p.querySelectorAll('.sheet-body *')].map(n => n.getBoundingClientRect().bottom)) - b; },
      p1over(){ const p = T.$('#live .pg1'); const b = p.querySelector('.sheet-body').getBoundingClientRect().bottom;
        return Math.max(...[...p.querySelectorAll('.sheet-body *')].map(n => n.getBoundingClientRect().bottom)) - b; },
    }; 1""")


    def toast_after(js, wait=1.2):
        ev("document.getElementById('toast').textContent=''")
        ev(js); time.sleep(wait)
        return ev("document.getElementById('toast').textContent")
    def stats(): return ev("Records.stats()")
    def preview():
        ev("T.$('#preview').click()"); ev("T.pdf()")
    def close_preview():
        ev("history.back()"); time.sleep(0.35)
    def printed(label):
        return ev(f"[...document.querySelectorAll('#live .s-f')].filter(f=>f.querySelector('.k')?.textContent==={json.dumps(label)}).map(f=>f.querySelector('.v').textContent)[0] || null")
    def fill_new():
        ev("""(()=>{T.set('p-name','Muhammad Aslam'); T.set('p-rel','Rahim Bakhsh'); T.set('p-age','58 M');
          T.set('p-phone','0300-1234567'); T.set('p-addr','Chak 42/EB, Arifwala'); T.set('chief','Floaters right eye');
          T.$$('[data-single="rel"] .chip')[0].click();
          const c=document.getElementById('p-cnic'); c.value='3520212345671'; c.dispatchEvent(new Event('input',{bubbles:true}));
          const d=RxApp.newDrug(); d.name='Predforte eye drops';
          d.steps[0]=Object.assign(RxApp.newStep(),{freq:'دن میں 4 بار',eye:'دائیں آنکھ میں',dur:'7'});
          RxApp.S.drugs[0]=d; RxApp.renderDrugs();})()""")
    def reload(url=None):
        ev("leaving = true; window.__old = 1")
        if url: cmd('Page.navigate', url=url)
        else: cmd('Page.reload')
        wait("!window.__old && typeof Records !== 'undefined' && document.readyState === 'complete'", 30)
        time.sleep(0.4)
        ev(T_HELPERS)

    T_HELPERS = """window.T = {
      $: s => document.querySelector(s), $$: s => [...document.querySelectorAll(s)],
      set(id, v){ const e = document.getElementById(id); e.value = v; e.dispatchEvent(new Event('input', {bubbles:true})); },
      async pdf(){ for (let i = 0; i < 600 && !RxApp.pdf() && T.$('#pv-send').textContent !== 'Failed' && T.$('#pv-send').textContent !== 'Too long'; i++) await new Promise(r => setTimeout(r, 50)); return !!RxApp.pdf(); },
    }; 1"""

    # ---------------- 1. records are available ----------------
    check('records available: no warning, buttons live',
          ev("document.getElementById('rec-warn').hidden && !document.getElementById('p-find').disabled && !document.getElementById('mr-new').disabled"))

    # ---------------- 2. MR numbers ----------------
    a = ev("Records.reserveMr()"); b = ev("Records.reserveMr()")
    ev("""Records.saveVisit({session:'hand-typed', visitNo:1, snapshot:{}, patient:{mr:'000003', name:'Paper Patient', phone:'0321-7654321'}})""")
    c = ev("Records.reserveMr()")
    check('MR numbers run 000001, 000002, then skip a hand-typed 000003', [a, b, c] == ['000001', '000002', '000004'], f'{a}, {b}, {c}')

    # ---------------- 3. a new patient: MR assigned at preview, Visit Number 1 ----------------
    fill_new()
    check('MR box starts empty', ev("document.getElementById('p-mr').value") == '')
    preview()
    mr = ev("document.getElementById('p-mr').value")
    check('a new patient gets the next MR at preview', mr == '000005', mr)
    check('sheet prints Visit Number 1', printed('VISIT NUMBER') == '1', str(printed('VISIT NUMBER')))
    check('sheet prints the contact number', printed('CONTACT') == '0300-1234567', str(printed('CONTACT')))
    st0 = stats()
    check('previewing alone records nothing', st0['visits'] == 1, f"visits={st0['visits']} (only the hand-typed one)")
    t = toast_after("T.$('#pv-send').click()")
    check('sending records the visit', 'saved as visit 1' in t and stats()['visits'] == 2, t)
    t2 = toast_after("T.$('#pv-send').click()")
    check('re-sending the same prescription does not count twice', stats()['visits'] == 2 and 'visit 1' in t2, f"visits={stats()['visits']} · {t2}")
    close_preview(); preview()
    check('re-previewing the sent prescription keeps Visit Number 1', printed('VISIT NUMBER') == '1', str(printed('VISIT NUMBER')))
    save_pdf('21-visit-1')
    close_preview()

    # ---------------- 4. a cancelled share is not a visit ----------------
    reload()
    ev("""navigator.canShare = () => true; navigator.share = () => Promise.reject(new DOMException('cancelled', 'AbortError'))""")
    fill_new(); ev("T.set('p-mr', '000005')"); preview()
    before = stats()['visits']
    ev("T.$('#pv-send').click()"); time.sleep(1)
    check('a cancelled share records nothing', stats()['visits'] == before, f"visits {before} → {stats()['visits']}")
    close_preview()

    # ---------------- 5. search ----------------
    reload()
    def hits(q):
        ev(f"T.set('p-find', {json.dumps(q)})"); time.sleep(0.45)
        return ev("[...document.querySelectorAll('#p-hits .hit')].map(h=>h.dataset.mr)")
    for q in ['0300-1234567', '03001234567', '+92 300 1234567', '1234567']:
        r = hits(q); check(f'phone search "{q}"', r == ['000005'], str(r))
    r = hits('aSLAM'); check('name search ignores case', r == ['000005'], str(r))
    r = hits('00000'); check('partial MR finds both stored patients', sorted(r) == ['000003', '000005'], str(r))
    r = hits('nobody'); check('no match says so', r == [] and 'No patient found' in ev("document.getElementById('p-hits').textContent"))

    # ---------------- 6. a returning patient: fields fill, Visit Number 2 ----------------
    hits('Aslam'); ev("document.querySelector('#p-hits .hit').click()"); time.sleep(0.4)
    got = ev("""({name:T.$('#p-name').value, rel:T.$('#p-rel').value, age:T.$('#p-age').value, mr:T.$('#p-mr').value,
                 phone:T.$('#p-phone').value, cnic:T.$('#p-cnic').value, addr:T.$('#p-addr').value,
                 relchip:T.$('[data-single="rel"] .chip.on')?.textContent, unit:T.$('[data-single="ageunit"] .chip.on')?.textContent,
                 line:T.$('#p-ret').hidden ? '' : T.$('#p-ret span').textContent})""")
    check('picking a result fills every field and chip',
          got['name'] == 'Muhammad Aslam' and got['mr'] == '000005' and got['phone'] == '0300-1234567' and got['cnic'] == '35202-1234567-1'
          and got['relchip'] == 'S/o' and got['unit'] == 'Y' and got['addr'] == 'Chak 42/EB, Arifwala', str(got))
    check('returning line says this is visit 2', 'this is visit 2' in got['line'], got['line'])
    ev("T.set('chief','Review after 1 week')")
    ev("""(()=>{const d=RxApp.newDrug(); d.name='Vigamox eye drops'; d.steps[0]=Object.assign(RxApp.newStep(),{freq:'دن میں 4 بار',dur:'5'}); RxApp.S.drugs[0]=d; RxApp.renderDrugs();})()""")
    preview()
    check('second visit prints Visit Number 2', printed('VISIT NUMBER') == '2', str(printed('VISIT NUMBER')))
    t = toast_after("T.$('#pv-send').click()")
    p = ev("Records.get('000005')")
    check('second visit saved; patient shows 2 visits', 'saved as visit 2' in t and p['last_visit_no'] == 2, t)
    save_pdf('22-visit-2')
    close_preview()

    # ---------------- 7. a mistyped MR is caught ----------------
    reload()
    ev("window.confirm = m => { window.__asked = m; return false; }")
    fill_new(); ev("T.set('p-name','Someone Else'); T.set('p-mr','000005')")
    ev("T.$('#preview').click()"); time.sleep(0.8)
    asked = ev("window.__asked || ''")
    check('another patient\'s MR asks before overwriting', 'belongs to Muhammad Aslam' in asked and not ev("T.$('#pv').classList.contains('on')"), asked.replace('\n', ' ')[:80])
    check('and nothing was changed', ev("Records.get('000005')")['name'] == 'Muhammad Aslam')

    # ---------------- 8. backup: export here, restore on "another PC" ----------------
    dump = ev("Records.exportAll().then(b => b.text())")
    here = stats()
    ev("T.$('#records').click()"); time.sleep(0.4)
    panel = ev("document.getElementById('recs-stats').textContent")
    check('Records panel: counts and last backup', f"{here['patients']} patients" in panel and 'today' in panel, panel)
    ev("T.$('#recs-close').click()")
    reload(URL.replace('localhost', '127.0.0.1'))          # a different origin = an empty browser, like a new PC
    check('the other origin starts empty', stats()['patients'] == 0)
    r1 = ev(f"Records.importAll({json.dumps(dump)})")
    s1 = stats()
    check('import restores every patient and visit', s1['patients'] == here['patients'] and s1['visits'] == here['visits'], f"{s1} vs {here}")
    r2 = ev(f"Records.importAll({json.dumps(dump)})")
    check('importing twice adds no duplicates', r2 == {'patients': 0, 'visits': 0} and stats()['visits'] == here['visits'], str(r2))
    n = ev("Records.reserveMr()")
    check('the restored MR counter continues, no reuse', n == '000006', n)
    rp = ev("Records.get('000005')")
    check('restored patient keeps visit count 2', rp['last_visit_no'] == 2, str(rp['last_visit_no']))
    bad = ev("Records.importAll('{\"not\":\"ours\"}').then(()=> 'accepted', e => e.message)")
    check('a file that is not a backup is refused', 'not a records backup' in bad, bad)

    # ---------------- 9. no IndexedDB: warn, but never block ----------------
    cmd('Page.addScriptToEvaluateOnNewDocument', source="Object.defineProperty(window, 'indexedDB', { value: undefined });")
    reload(URL)
    check('no IndexedDB → warning bar, record controls off',
          not ev("document.getElementById('rec-warn').hidden") and ev("document.getElementById('p-find').disabled && document.getElementById('records').disabled"))
    fill_new(); preview()
    check('the prescription still builds, with no visit number', ev("!!RxApp.pdf()") and printed('VISIT NUMBER') is None)
    t = toast_after("T.$('#pv-send').click()")
    check('and still sends', 'PDF downloaded' in t, t)
finally:
    try: chrome.terminate(); chrome.wait(5)
    except Exception: pass
    if server.poll() is None: server.terminate()
    shutil.rmtree(prof, ignore_errors=True)

print('\nJS errors:', errors or 'none')
print(f"\n{sum(ok for _, ok, _ in results)}/{len(results)} passed")
