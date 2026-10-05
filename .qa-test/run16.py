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


    def focus_cnic():
        ev("(()=>{const e=document.getElementById('p-cnic'); e.value=''; e.dataset.n='0'; e.focus();})()")
    def backspace():
        for t in ('rawKeyDown', 'keyUp'):
            cmd('Input.dispatchKeyEvent', type=t, key='Backspace', code='Backspace',
                windowsVirtualKeyCode=8, nativeVirtualKeyCode=8)
    def state():
        return ev("(()=>{const e=document.getElementById('p-cnic'); return e.value+' @'+e.selectionStart;})()")
    def caret(n):
        ev(f"document.getElementById('p-cnic').setSelectionRange({n},{n})")

    focus_cnic(); cmd('Input.insertText', text='3520212345671')
    check('typing 13 digits formats as it goes', state().startswith('35202-1234567-1'), state())

    # the review's exact scenario: correct a digit in the middle
    caret(3); backspace()
    midstate = state()
    cmd('Input.insertText', text='2')
    after = ev("document.getElementById('p-cnic').value")
    check('correcting a digit mid-number keeps the caret and restores the right CNIC',
          after == '35202-1234567-1', f'after backspace: {midstate} → typed 2 → {after}')

    # backspace onto an auto-inserted hyphen must eat the digit in front of it
    focus_cnic(); cmd('Input.insertText', text='3520212345671')
    caret(14); before = ev("document.getElementById('p-cnic').value")
    backspace(); one = ev("document.getElementById('p-cnic').value")
    check('backspace on a hyphen deletes a digit, not nothing', one != before and one.replace('-','') == '352021234561',
          f'{before} → {one}')
    backspace(); two = ev("document.getElementById('p-cnic').value")
    check('the next backspace deletes exactly one more digit', len(two.replace('-','')) == 11, f'{one} → {two}')

    # deleting from the end still behaves
    focus_cnic(); cmd('Input.insertText', text='3520212345671')
    caret(15); backspace()
    check('backspace at the end removes the last digit', ev("document.getElementById('p-cnic').value") == '35202-1234567', state())

    # CNIC reaches page 2
    ev("""T.set('p-name','Muhammad Aslam'); T.set('p-age','58 M'); T.set('p-mr','TN-04182'); T.set('chief','Post-op review');
      T.set('ex-lid-r','Meibomian gland dysfunction'); T.set('ex-lid-l','Normal');
      (()=>{const taper=['دن میں 4 بار','دن میں 3 بار','دن میں 2 بار','دن میں ایک بار'].map(f=>Object.assign(RxApp.newStep(),{freq:f,eye:'دونوں آنکھوں میں',dur:'1',unit:'hafta'}));
      RxApp.S.drugs.length=0;
      for(let i=0;i<8;i++){const d=RxApp.newDrug(); d.name='Drug number '+(i+1)+' eye drops'; d.steps=taper.map(s=>({...s})); d.end='پھر بند کر دیں'; RxApp.S.drugs.push(d);}
      RxApp.renderDrugs(); document.getElementById('hid').value='';
      [...document.querySelectorAll('#hid-sets [data-hid]')].find(b=>b.textContent.includes('Cataract')).click();})()""")
    focus_cnic(); cmd('Input.insertText', text='3520212345671')
    ev("T.$('#preview').click()"); ev("T.pdf()")
    heads = ev("""[...document.querySelectorAll('#live .sheet')].filter(p=>!p.hidden)
      .map(p => (p.querySelector('.s-p2h') || p.querySelector('.s-pt')).textContent.replace(/\\s+/g,' ').trim())""")
    check('every page carries the CNIC', all('35202-1234567-1' in h for h in heads), f'{len(heads)} pages: ' + ' || '.join(h[:80] for h in heads))

    # the label column cannot wrap any more
    nowrap = ev("getComputedStyle(document.querySelector('#live .pg1 .s-row .k')).whiteSpace")
    check('examination labels can no longer wrap', nowrap == 'nowrap', nowrap)
    check('still lays out cleanly', ev("document.getElementById('pv-warn').hidden"), f"pages={ev('RxApp.pages()')}")
    save_pdf('20-review-fixes')
finally:
    try: chrome.terminate(); chrome.wait(5)
    except Exception: pass
    if server.poll() is None: server.terminate()
    shutil.rmtree(prof, ignore_errors=True)

print('\nJS errors:', errors or 'none')
print(f"\n{sum(ok for _, ok, _ in results)}/{len(results)} passed")
