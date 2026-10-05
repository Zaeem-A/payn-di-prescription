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


    chips = ev("[...document.querySelectorAll('[data-single=\"ageunit\"] .chip')].map(c=>c.textContent.trim()+(c.classList.contains('on')?'*':''))")
    check('two chips beside age, Y chosen by default', chips == ['M', 'Y*'], ' '.join(chips))

    def age_prints(typed, unit):
        ev(f"T.set('p-age', {json.dumps(typed)})")
        ev(f"[...document.querySelectorAll('[data-single=\"ageunit\"] .chip')].find(c=>c.textContent.trim()==='{unit}').click()")
        ev("T.set('p-name','Muhammad Aslam'); T.set('chief','Review')")
        ev("T.$('#preview').click()")
        out = ev("[...document.querySelectorAll('#live .pg1 .s-pt .s-f')].map(f=>(f.querySelector('.k')?.textContent||'')+'='+f.querySelector('.v').textContent).find(t=>t.startsWith('AGE'))")
        ev("history.back()"); time.sleep(0.25)
        return out

    check('adult in years', age_prints('58', 'Y') == 'AGE=58 y', age_prints('58', 'Y'))
    check('infant in months', age_prints('6', 'M') == 'AGE=6 m', age_prints('6', 'M'))
    check('sex typed in the same box still prints after the unit', age_prints('58 F', 'Y') == 'AGE=58 y F', age_prints('58 F', 'Y'))
    check('months with sex', age_prints('9 M', 'M') == 'AGE=9 m M', age_prints('9 M', 'M'))
    check('anything non-numeric prints as typed', age_prints('adult', 'Y') == 'AGE=adult', age_prints('adult', 'Y'))

    ev("[...document.querySelectorAll('[data-single=\"ageunit\"] .chip')].find(c=>c.textContent.trim()==='Y').click()")
    ev("[...document.querySelectorAll('[data-single=\"ageunit\"] .chip')].find(c=>c.textContent.trim()==='Y').click()")
    check('tapping the chosen unit again cannot leave it unset', ev("[...document.querySelectorAll('[data-single=\"ageunit\"] .chip')].filter(c=>c.classList.contains('on')).length") == 1)
    ev("T.$$('[data-single=\"rel\"] .chip')[0].click(); T.$$('[data-single=\"rel\"] .chip')[0].click()")
    check('S/o still clears on a second tap', ev("[...document.querySelectorAll('[data-single=\"rel\"] .chip')].filter(c=>c.classList.contains('on')).length") == 0)

    ev("T.set('p-age','6'); [...document.querySelectorAll('[data-single=\"ageunit\"] .chip')].find(c=>c.textContent.trim()==='M').click()")
    ev("T.set('p-mr','TN-04182'); T.set('p-addr','Arifwala'); T.set('ex-fundus-r','Immature ROP zone II'); T.set('ex-rapd','Absent')")
    ev("T.$('#preview').click()"); ev("T.pdf()")
    check('prints fine end to end', ev("document.getElementById('pv-warn').hidden"))
    save_pdf('17-age-unit')
finally:
    try: chrome.terminate(); chrome.wait(5)
    except Exception: pass
    if server.poll() is None: server.terminate()
    shutil.rmtree(prof, ignore_errors=True)

print('\nJS errors:', errors or 'none')
print(f"\n{sum(ok for _, ok, _ in results)}/{len(results)} passed")
