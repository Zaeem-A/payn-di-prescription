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


    ev("window.HID = n => [...document.querySelectorAll('#hid-sets [data-hid]')].find(b=>b.textContent.includes(n)).click(); 1")
    labels = ev("[...document.querySelectorAll('#hid-sets [data-hid]')].map(b=>b.textContent.trim())")
    check('five buttons, General precautions among them',
          labels == ['+ Cataract', '+ General precautions', '+ PRK', '+ CXL', '+ LASIK'], str(labels))

    ev("$('#hid').value=''; HID('General precautions')")
    gp = ev("$('#hid').value")
    lines = [l for l in gp.split('\n') if l.strip()]
    check('8 complete lines, no headings', len(lines) == 8 and not any(l.endswith(':') for l in lines), f'{len(lines)} lines')

    dropped = {'swimming pool': 'سوئمنگ پول', 'follow-up appointments': 'فالو اپ', 'prescribed drops': 'تجویز کردہ قطرے',
               'cold compress': 'ٹھنڈی پٹی', 'sunglasses': 'دھوپ کے چشمے', 'sharing towels/makeup': 'تولیے',
               'humidifier': 'ہیومیڈیفائر', 'pollen': 'پولن', 'old word for pollen': 'جرگ',
               'heading یہ کریں': 'یہ کریں', 'heading پرہیز': 'ان سے پرہیز', 'fragment "دورے کے دوران"': 'دورے کے دوران'}
    left_in = [k for k, v in dropped.items() if v in gp]
    check('every point you asked me to drop is gone', not left_in, ('still there: ' + ', '.join(left_in)) if left_in else 'all six gone')

    kept = {'wash face and hands': 'چہرہ اور ہاتھ', 'bedding': 'بستر کی چادریں',
            'no rubbing': 'نہ ملیں اور نہ دبائیں', 'dust and pets': 'گرد و غبار، پالتو جانوروں',
            'contact lenses': 'کانٹیکٹ لینز', 'screens': 'موبائل، ٹی وی یا کمپیوٹر',
            'no self-prescribed drops': 'خود استعمال نہ کریں'}
    missing = [k for k, v in kept.items() if v not in gp]
    check('every point you asked me to keep is there', not missing, ('missing: ' + ', '.join(missing)) if missing else 'all eight kept')

    check('the doctor line is one line, at the end', sum(1 for l in lines if 'رجوع' in l) == 1 and lines[-1].endswith('رجوع کریں'), lines[-1][:55] + '…')
    import re as _re
    verb = _re.compile('(کریں|رکھیں|دھوئیں|بچیں|دیکھیں|دیں|ملیں|دبائیں|جائیں|لگائیں|پہنیں)')
    noverb = [l for l in lines if not verb.search(l)]
    check('every line carries its own instruction verb', not noverb, ('no verb in: ' + ' | '.join(noverb)) if noverb else 'all 8 lines')

    # cataract: sajda clause gone, the rest intact and grammatical
    ev("$('#hid').value=''; HID('Cataract')")
    cat = ev("$('#hid').value")
    cl = [l for l in cat.split('\n') if l.strip()]
    check('cataract: "سجدہ نہ کریں" removed, prayer line kept', 'سجدہ' not in cat and 'ایک ماہ تک نماز اشاروں سے ادا کریں' in cl, [l for l in cl if 'نماز' in l or 'وزن' in l])
    check('cataract still has its 12 lines', len(cl) == 12, f'{len(cl)} lines')
    ev("$('#hid').value=''; HID('General precautions')")

    # a realistic VKC visit
    ev("T.set('p-name','Muhammad Aslam'); T.set('p-age','19 M'); T.set('p-mr','TN-05511')")
    ev("T.set('chief','Itchy eyes both, worse in spring'); T.set('va-r','6/6'); T.set('va-l','6/6')")
    ev("T.set('ex-conj-r','Papillae upper tarsus'); T.set('ex-conj-l','Papillae upper tarsus')")
    ev("T.set('h-ocu','Recurrent allergic conjunctivitis, 3 seasons')")
    ev("""(()=>{const d=RxApp.newDrug(); d.name='Patanol eye drops';
      d.steps[0]=Object.assign(RxApp.newStep(),{freq:'دن میں 2 بار',eye:'دونوں آنکھوں میں',dur:'1',unit:'mahina'});
      RxApp.S.drugs[0]=d; RxApp.renderDrugs();})()""")
    ev("T.$('#preview').click()"); ev("T.pdf()")
    check('it prints without a fit warning', ev("document.getElementById('pv-warn').hidden"), f"pages={ev('RxApp.pages()')}")
    bullets = ev("document.querySelectorAll('#live .s-hid .li').length")
    subs = ev("document.querySelectorAll('#live .s-hid .sub').length")
    check('printed as 8 bulleted lines, no headings', bullets == 8 and subs == 0, f'{bullets} bullets, {subs} headings')
    save_pdf('14-general')
finally:
    try: chrome.terminate(); chrome.wait(5)
    except Exception: pass
    if server.poll() is None: server.terminate()
    shutil.rmtree(prof, ignore_errors=True)

print('\nJS errors:', errors or 'none')
print(f"\n{sum(ok for _, ok, _ in results)}/{len(results)} passed")
