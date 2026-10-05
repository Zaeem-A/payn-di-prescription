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


    # ---------------- A. realistic exam-heavy visit (typical clinic wording) ----------------
    ev("""(()=>{const d=RxApp.newDrug(); d.name='Predforte eye drops'; d.steps=[Object.assign(RxApp.newStep(),{freq:'دن میں 4 بار',eye:'دائیں آنکھ میں',dur:'7'})]; RxApp.S.drugs[0]=d;
      const d2=RxApp.newDrug(); d2.name='Vigamox eye drops'; d2.steps=[Object.assign(RxApp.newStep(),{freq:'دن میں 4 بار',eye:'دائیں آنکھ میں',dur:'7'})]; RxApp.S.drugs.push(d2); RxApp.renderDrugs();
      T.set('p-name','Muhammad Aslam'); T.set('p-age','58'); T.set('p-mr','TN-04182');
      T.set('chief','Sudden painless loss of vision, right eye — 6 weeks'); T.set('va-r','CF 2m'); T.set('va-l','6/9');
      ['pre','final'].forEach(c=>{T.set('iop-r-'+c,'18'); T.set('iop-l-'+c,'16');});
      T.set('h-sys','DM 12 yrs on insulin, HTN on amlodipine, IHD'); T.set('h-ocu','PRP OU 2022, phaco + IOL RE 2024'); T.set('h-pres','Floaters and drop in vision RE x 5 days');
      const ex={lens:['PCIOL in bag','NS grade 2'],ac:['Deep, cells 1+','Deep, quiet'],cornea:['Clear','Clear'],conj:['Quiet','Quiet'],vit:['Dense VH, no view of disc','PVD, clear'],fundus:['No view, B-scan: attached retina','PRP scars, few DBH, no NVE']};
      Object.entries(ex).forEach(([k,[r,l]])=>{T.set('ex-'+k+'-r',r); T.set('ex-'+k+'-l',l);});
      T.set('a-inv','B-scan RE · HbA1c · RFTs · CBC · Coagulation profile'); T.set('a-proc','23G PPV + endolaser RE under LA, next week');
      T.set('fu','2026-09-28');})()""")
    ev("T.$('#preview').click()"); ev("T.pdf()")
    check('realistic exam-heavy visit fits one page', ev("RxApp.pages()") == 1 and ev("T.p1over()") <= 1, f"pages={ev('RxApp.pages()')} p1 overflow={ev('T.p1over()'):.0f}px")
    save_pdf('5-realistic')
    ev("history.back()"); time.sleep(0.4)

    # ---------------- B. offline, with a clean form so no leave-page prompt ----------------
    sw = "(async()=>{const r=await navigator.serviceWorker.getRegistration(); const k=await caches.keys(); let n=0; for(const c of k) n+=(await (await caches.open(c)).keys()).length; return {active:!!(r&&r.active), cached:n};})()"
    s = {}
    for _ in range(60):
        s = ev(sw)
        if s['active'] and s['cached'] >= 15: break
        time.sleep(0.5)
    check('service worker installs and caches the app', s.get('active') and s.get('cached', 0) >= 15, str(s))
    ev("T.$$('main input, main textarea').forEach(e=>e.value=''); RxApp.S.drugs.length=0; RxApp.S.drugs.push(RxApp.newDrug()); window.__old=1")
    server.terminate(); server.wait(5)
    try: urllib.request.urlopen(URL, timeout=2); down = False
    except Exception: down = True
    check('test server stopped', down)
    cmd('Page.reload')
    loaded = wait("!window.__old && typeof RxApp !== 'undefined' && document.readyState === 'complete'", 30)
    check('app reloads with no server', loaded, ev("document.title + ' | ' + location.href") if not loaded else '')
    if loaded:
        ev("""(()=>{const set=(id,v)=>{const e=document.getElementById(id); e.value=v; e.dispatchEvent(new Event('input',{bubbles:true}));};
          set('p-name','Offline Test'); set('chief','Floaters, right eye');
          const d=RxApp.newDrug(); d.name='Predforte eye drops'; d.steps[0]=Object.assign(RxApp.newStep(),{freq:'دن میں 4 بار',eye:'دائیں آنکھ میں',dur:'7'}); d.end='پھر بند کر دیں';
          RxApp.S.drugs[0]=d; RxApp.renderDrugs(); document.getElementById('preview').click();})()""")
        built = wait("!!RxApp.pdf() || document.getElementById('pv-send').textContent === 'Failed'", 60) and ev("!!RxApp.pdf()")
        check('PDF builds offline', built, ev("document.getElementById('toast').textContent") if not built else '')
        if built: save_pdf('4-offline')
        fonts = ev("[...document.fonts].filter(f=>f.status==='loaded').map(f=>f.family.replace(/\"/g,'')+' '+f.weight).join(', ')")
        check('fonts loaded offline', 'Nastaliq' in fonts and 'Montserrat' in fonts, fonts)
finally:
    try: chrome.terminate(); chrome.wait(5)
    except Exception: pass
    if server.poll() is None: server.terminate()
    shutil.rmtree(prof, ignore_errors=True)

print('\nJS errors:', errors or 'none')
print(f"\n{sum(ok for _, ok, _ in results)}/{len(results)} passed")
