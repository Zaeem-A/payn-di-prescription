"""Real-time UI test of app/ over the Chrome DevTools protocol (no virtual time).
Serves the project on its own port so it can't collide with .qa/ runs.
usage: python3 run.py            -> writes out/*.pdf, out/*.png, prints a report"""
import base64, json, os, shutil, subprocess, sys, time, urllib.request
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


    ev("""window.OV = pg => { const b = pg.querySelector('.sheet-body');
      const last = [...b.children].filter(e=>!e.hidden).at(-1);
      return last ? Math.round(last.getBoundingClientRect().bottom - b.getBoundingClientRect().bottom) : 0; };
      window.PG = () => [...document.querySelectorAll('#live .sheet')].filter(p=>!p.hidden);
      window.STATE = () => ({pages: RxApp.pages(), over: PG().map(OV),
        send: document.getElementById('pv-send').textContent, disabled: document.getElementById('pv-send').disabled,
        blocks: PG().map(p => [...(p.querySelector('.p2c') || p.querySelector('.sheet-body')).children]
          .filter(e=>!e.hidden).map(e=>e.className.split(' ')[0]).join(','))}); 1""")

    def load(drugs, hid_set, exam_words, clinical=True):
        ev("""(()=>{const taper=['دن میں 4 بار','دن میں 3 بار','دن میں 2 بار','دن میں ایک بار'].map(f=>Object.assign(RxApp.newStep(),{freq:f,eye:'دونوں آنکھوں میں',dur:'1',unit:'hafta'}));
          RxApp.S.drugs.length=0;
          for(let i=0;i<%d;i++){const d=RxApp.newDrug(); d.name='Drug number '+(i+1)+' eye drops'; d.steps=taper.slice(0,2).map(s=>({...s})); d.end='پھر بند کر دیں'; RxApp.S.drugs.push(d);}
          RxApp.renderDrugs();
          document.getElementById('hid').value='';
          %s
          const w=%s; ['lens','ac','cornea','conj','vit','fundus'].forEach(k=>{T.set('ex-'+k+'-r',w); T.set('ex-'+k+'-l',w);});})()"""
          % (drugs,
             ('[%s].forEach(i=>document.querySelectorAll("#hid-sets [data-hid]")[i].click());' % ','.join(str(i) for i in range(hid_set))) if hid_set else '',
             ("'Detailed finding '.repeat(%d)" % exam_words) if clinical else "''"))
        ev("T.$('#preview').click()"); ev("T.pdf()")
        st = ev("STATE()"); st['hid'] = ev("[...document.querySelectorAll('#live .sheet')].filter(p=>!p.hidden).map(p=>p.querySelectorAll('.s-hid .li').length).join('/')")
        st['warn'] = ev("!document.getElementById('pv-warn').hidden")
        return st

    ev("""T.set('p-name','Muhammad Aslam'); T.set('p-age','58 M'); T.set('p-mr','TN-04182');
      T.set('chief','Post-op review'); T.set('h-sys','DM 12 yrs on insulin, HTN, IHD with CABG 2019');
      T.set('a-proc','23G PPV + endolaser + silicone oil RE under LA'); T.set('fu','2026-10-03');""")

    # ---- the case that used to clip silently ----
    st = load(8, 2, 2)
    check('the clipping case now fits every page', all(o <= 1 for o in st['over']), f"pages={st['pages']} overflow={st['over']}")
    check('Rx and clinical stay on page 1, Hidayat sits on page 2', 's-hid' not in st['blocks'][0] and 's-rx' in st['blocks'][0] and 's-hid' in st['blocks'][1], ' | '.join(st['blocks']))
    check('every Hidayat line is on one page, none lost', st['hid'].split('/')[0] == '0', f"lines per page: {st['hid']}")
    ev("history.back()"); time.sleep(0.3)

    # ---- one page's worth: nothing moves ----
    st1 = load(2, 0, 1)
    check('a short prescription is still one page', st1['pages'] == 1 and st1['over'][0] <= 1, f"pages={st1['pages']}")
    ev("history.back()"); time.sleep(0.3)

    # ---- hidayat alone pushes it over: prescription keeps page 1 ----
    st2 = load(6, 1, 2)
    check('adding Hidayat moves only the Hidayat', st2['pages'] == 2 and 's-hid' not in st2['blocks'][0] and 's-rx' in st2['blocks'][0] and st2['blocks'][1].startswith('s-hid') and all(o <= 1 for o in st2['over']),
          f"pages={st2['pages']} | " + ' | '.join(st2['blocks']))
    save_pdf('11-hidayat-page2')
    ev("history.back()"); time.sleep(0.3)

    # ---- absurd: 8 drugs, all four sets, huge exam ----
    st3 = load(8, 4, 12)
    check('extreme content: every page still fits, or Send is blocked',
          all(o <= 1 for o in st3['over']) or (st3['disabled'] and st3['warn']),
          f"pages={st3['pages']} overflow={st3['over']} send={st3['send']!r} disabled={st3['disabled']} warned={st3['warn']}")
    save_pdf('12-extreme')
    ev("history.back()"); time.sleep(0.3)

    # ---- beyond any page count: must block, never send a cut sheet ----
    ev("document.getElementById('h-sys').value = 'Systemic history. '.repeat(700); document.getElementById('h-sys').dispatchEvent(new Event('input',{bubbles:true}))")
    st4 = load(8, 4, 30)
    check('impossible content: Send is refused and the reason is shown', st4['disabled'] and st4['warn'], f"send={st4['send']!r} disabled={st4['disabled']} warning shown={st4['warn']}")
finally:
    try: chrome.terminate(); chrome.wait(5)
    except Exception: pass
    if server.poll() is None: server.terminate()
    shutil.rmtree(prof, ignore_errors=True)

print('\nJS errors:', errors or 'none')
print(f"\n{sum(ok for _, ok, _ in results)}/{len(results)} passed")
