"""Real-time UI test of app/ over the Chrome DevTools protocol (no virtual time).
Serves the project on its own port so it can't collide with .qa/ runs.
usage: python3 run.py            -> writes out/*.pdf, out/*.png, prints a report"""
import base64, json, json, os, shutil, subprocess, sys, time, urllib.request
import websocket

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(HERE, 'out'); os.makedirs(OUT, exist_ok=True)
HTTP, CDP = 8777, 9444
URL = 'https://zaeem-a.github.io/payn-di-prescription/'

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


    check('live: https origin, records available', ev("location.origin") == 'https://zaeem-a.github.io' and ev("document.getElementById('rec-warn').hidden"), ev("location.href"))
    fill_new(); preview()
    check('live: new patient gets MR 000001 and Visit Number 1', ev("T.$('#p-mr').value") == '000001' and printed('VISIT NUMBER') == '1',
          f"MR {ev('document.getElementById(\"p-mr\").value')} · visit {printed('VISIT NUMBER')}")
    t = toast_after("T.$('#pv-send').click()")
    check('live: sending saves the visit', 'saved as visit 1' in t, t)
    close_preview()
    reload()
    ev("T.set('p-find','aslam')"); time.sleep(0.5)
    found = ev("[...document.querySelectorAll('#p-hits .hit')].map(h=>h.dataset.mr)")
    check('live: after a reload, search finds the patient', found == ['000001'], str(found))
    ev("document.querySelector('#p-hits .hit').click()"); time.sleep(0.4)
    ev("""(()=>{const d=RxApp.newDrug(); d.name='Vigamox eye drops'; d.steps[0]=Object.assign(RxApp.newStep(),{freq:'دن میں 4 بار',dur:'5'}); RxApp.S.drugs[0]=d; RxApp.renderDrugs(); T.set('chief','Review');})()""")
    preview()
    check('live: second visit prints Visit Number 2', printed('VISIT NUMBER') == '2', str(printed('VISIT NUMBER')))
    sw = ev("navigator.serviceWorker.getRegistration().then(r => r ? r.scope : 'none')")
    check('live: offline worker registered under the site path', sw == 'https://zaeem-a.github.io/payn-di-prescription/', sw)
    save_pdf('23-live')
finally:
    try: chrome.terminate(); chrome.wait(5)
    except Exception: pass
    if server.poll() is None: server.terminate()
    shutil.rmtree(prof, ignore_errors=True)

print('\nJS errors:', errors or 'none')
print(f"\n{sum(ok for _, ok, _ in results)}/{len(results)} passed")
