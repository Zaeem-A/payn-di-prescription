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


    txt = "(s => document.querySelector(s)?.textContent.trim())"
    # ---------------- 1. patient fields ----------------
    ev("""T.set('p-name','Muhammad Aslam'); T.set('p-rel','Rahim Bakhsh'); T.set('p-age','58 F');
      T.set('p-addr','Chak 42/EB, Arifwala'); T.set('p-mr','TN-04182'); T.set('chief','Floaters right eye, 6 weeks');
      T.$$('[data-single="rel"] .chip')[0].click();""")
    check('no Sex chips left in the form', ev("!document.querySelector('[data-single=\"p-sex\"]') && !/>\\s*Sex\\s*</.test(document.body.innerHTML)"))
    check('age field takes letters (full keyboard)', ev("!$('#p-age').getAttribute('inputmode')") in (True, None), ev("String($('#p-age').getAttribute('inputmode'))"))

    # ---------------- 2. IOP final = pre + cf ----------------
    ev("T.set('iop-r-pre','15')"); ev("T.set('iop-r-cf','2')")
    a = ev("$('#iop-r-final').value")
    ev("$('[data-sign=\"iop-r-cf\"]').click()"); time.sleep(0.15)
    b = ev("$('#iop-r-final').value")
    check('Final auto-adds Pre + CF, and follows the ± button', a == '17' and b == '13', f'+2 -> {a!r}   -2 -> {b!r}')
    ev("T.set('iop-r-final','20')"); ev("T.set('iop-r-pre','16')")
    c = ev("$('#iop-r-final').value")
    ev("T.set('iop-r-final','')"); ev("T.set('iop-r-pre','17')")
    d = ev("$('#iop-r-final').value")
    check('a typed Final is left alone, clearing it resumes the sum', c == '20' and d == '15', f'typed stays {c!r}; after clearing {d!r}')
    ev("T.set('iop-l-pre','16'); T.set('iop-l-pachy','540'); T.set('iop-l-cf','1')")

    # ---------------- 3. hidayat ----------------
    ev("T.$$('#hid-sets .chip')[0].click()")
    n1 = ev("$('#hid').value.split('\\n').filter(Boolean).length")
    ev("T.$$('#hid-sets .chip')[0].click()")
    n2 = ev("$('#hid').value.split('\\n').filter(Boolean).length")
    check('a Hidayat set fills the box, tapping it twice does not duplicate', n1 > 2 and n1 == n2, f'{n1} lines, still {n2} after a second tap')
    ev("T.$$('#hid-sets .chip')[2].click()")
    n3 = ev("$('#hid').value.split('\\n').filter(Boolean).length")
    check('a second set is added below the first', n3 > n1, f'{n1} -> {n3} lines')
    ev("$('#hid').value = $('#hid').value + '\\nڈاکٹر کی اپنی لکھی ہوئی ہدایت'")

    # ---------------- 4. the sheet ----------------
    ev("""(()=>{const d=RxApp.newDrug(); d.name='Predforte eye drops'; d.steps[0]=Object.assign(RxApp.newStep(),{freq:'دن میں 4 بار',eye:'دائیں آنکھ میں',dur:'7'}); d.end='پھر بند کر دیں'; RxApp.S.drugs[0]=d; RxApp.renderDrugs();})()""")
    ev("T.$('#preview').click()"); ev("T.pdf()")
    pt = ev("[...document.querySelectorAll('#live .pg1 .s-pt .s-f')].map(f=>(f.querySelector('.k')?.textContent||'—')+'='+f.querySelector('.v').textContent).join(' | ')")
    check('patient bar: S/o chosen, age as typed, address, no sex', 'S/o=Rahim Bakhsh' in pt and 'AGE=58 F' in pt and 'ADDRESS=' in pt and 'SEX' not in pt, pt)
    check('patient name is bold', ev("getComputedStyle(document.querySelector('#live .pg1 .s-pt .nm .v')).fontWeight") in ('700', 700), str(ev("getComputedStyle(document.querySelector('#live .pg1 .s-pt .nm .v')).fontWeight")))
    iop = ev("[...document.querySelectorAll('#live .s-iop tr')].map(r=>[...r.children].map(c=>c.textContent.trim()).join('/')).join('  ')")
    check('IOP table prints the CF sign and the final', '+1' in iop or '-' in iop, iop)
    hid = ev("document.querySelector('#live .pg1 .s-hid')")
    hl = ev("document.querySelectorAll('#live .pg1 .s-hid .v div').length")
    hh = ev("document.querySelector('#live .pg1 .s-hid .h b')?.textContent")
    order = ev("[...document.querySelectorAll('#live .pg1 .sheet-body > *')].filter(e=>!e.hidden).map(e=>e.className.split(' ')[0]).join(' > ')")
    check('Hidayat block prints under Rx, above refraction', hh == 'ہدایات' and hl == n3 + 1 and 's-rx > s-hid' in order, f'{hl} lines · {order}')
    check('no letter-spacing on the Urdu heading (would break Nastaliq)', ev("getComputedStyle(document.querySelector('#live .pg1 .s-hid .h b')).letterSpacing") in ('normal', '0px'), str(ev("getComputedStyle(document.querySelector('#live .pg1 .s-hid .h b')).letterSpacing")))
    check('still one page', ev("RxApp.pages()") == 1, f"pages={ev('RxApp.pages()')}")
    save_pdf('6-changes')
    ev("history.back()"); time.sleep(0.3)

    # ---------------- 5. plain number age, no relation chosen ----------------
    ev("T.set('p-age','58'); T.$$('[data-single=\"rel\"] .chip')[0].click()")
    ev("T.$('#preview').click()"); ev("T.pdf()")
    pt2 = ev("[...document.querySelectorAll('#live .pg1 .s-pt .s-f')].map(f=>(f.querySelector('.k')?.textContent||'—')+'='+f.querySelector('.v').textContent).join(' | ')")
    check('bare number gets "y"; unchosen relation prints with no label', 'AGE=58 y' in pt2 and '—=Rahim Bakhsh' in pt2, pt2)
    ev("history.back()"); time.sleep(0.3)

    # ---------------- 6. offline still installs ----------------
    sw = "(async()=>{const r=await navigator.serviceWorker.getRegistration(); const k=await caches.keys(); let n=0; for(const c of k) n+=(await (await caches.open(c)).keys()).length; return {active:!!(r&&r.active), cached:n, names:k.join(',')};})()"
    s = {}
    for _ in range(60):
        s = ev(sw)
        if s['active'] and s['cached'] >= 14: break
        time.sleep(0.5)
    check('service worker installs the new version', s.get('active') and s.get('cached', 0) >= 14, str(s))
finally:
    try: chrome.terminate(); chrome.wait(5)
    except Exception: pass
    if server.poll() is None: server.terminate()
    shutil.rmtree(prof, ignore_errors=True)

print('\nJS errors:', errors or 'none')
print(f"\n{sum(ok for _, ok, _ in results)}/{len(results)} passed")
