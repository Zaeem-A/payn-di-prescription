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


    ORDER = ['Lid / Adnexa', 'Conjunctiva', 'Sclera', 'Cornea', 'AC', 'Iris', 'Lens', 'Vitreous', 'Fundus']
    form = ev("[...document.querySelectorAll('#exam .f > label')].map(l=>l.textContent.trim())")
    check('form shows every row plus RAPD, in order', form == ORDER + ['RAPD'], ' → '.join(form))
    ids = ev("[...document.querySelectorAll('#exam input')].map(i=>i.id)")
    want = [f'ex-{k}-{e}' for k in ['lid','conj','sclera','cornea','ac','iris','lens','vit','fundus'] for e in ('r','l')] + ['ex-rapd']
    check('nine R/L pairs plus the single RAPD box', ids == want, f'{len(ids)} inputs' + ('' if ids == want else ' — got ' + ', '.join(ids)))

    # fill every row, both eyes, and check the printed order
    ev("""(()=>{const keys=['lid','conj','sclera','cornea','ac','iris','lens','vit','fundus'];
      keys.forEach((k,i)=>{['r','l'].forEach(e=>{const el=document.getElementById('ex-'+k+'-'+e);
        el.value = k.toUpperCase()+'-'+e.toUpperCase(); el.dispatchEvent(new Event('input',{bubbles:true}));});});
      T.set('p-name','Muhammad Aslam'); T.set('p-age','58 M'); T.set('p-mr','TN-04182');
      T.set('chief','Routine review'); T.set('va-r','6/9'); T.set('va-l','6/12');
      const d=RxApp.newDrug(); d.name='Predforte eye drops';
      d.steps[0]=Object.assign(RxApp.newStep(),{freq:'دن میں 4 بار',eye:'دائیں آنکھ میں',dur:'7'});
      RxApp.S.drugs[0]=d; RxApp.renderDrugs();})()""")
    ev("T.$('#preview').click()"); ev("T.pdf()")
    printed = ev("[...document.querySelectorAll('#live .pg1 .s-row .k')].map(k=>k.textContent.trim()).filter(t=>!['SYSTEMIC','OCULAR'].includes(t))")
    check('printed sheet keeps that order', printed == [x.upper() for x in ORDER], ' → '.join(printed))
    check('every row prints with both eyes', ev("[...document.querySelectorAll('#live .pg1 .s-eyes')].filter(e=>e.textContent.includes('-R')&&e.textContent.includes('-L')).length") == 9)
    check('it still fits', ev("document.getElementById('pv-warn').hidden"), f"pages={ev('RxApp.pages()')}")
    save_pdf('15-exam-order')
    ev("history.back()"); time.sleep(0.3)

    # RAPD: one box, printed under Fundus
    ev("T.set('ex-rapd','+ve right eye')")
    ev("T.$('#preview').click()"); ev("T.pdf()")
    rows = ev("[...document.querySelectorAll('#live .pg1 .s-row .k')].map(k=>k.textContent.trim()).filter(t=>!['SYSTEMIC','OCULAR'].includes(t))")
    check('RAPD prints last, under Fundus', rows[-2:] == ['FUNDUS', 'RAPD'], ' → '.join(rows[-3:]))
    check('RAPD prints as one value, not an R/L pair', ev("document.querySelector('#live .pg1 .s-row:last-child .v')?.textContent.trim()") == '+ve right eye' and ev("!document.querySelector('#live .pg1 .s-row:last-child .s-eyes')"))
    check('one RAPD box in the form, below Fundus', ev("[...document.querySelectorAll('#exam .f > label')].at(-1).textContent.trim()") == 'RAPD' and ev("document.querySelectorAll('#ex-rapd').length") == 1)
    save_pdf('16-rapd')
    ev("history.back()"); time.sleep(0.3)

    # a normal visit only fills a few rows: the rest must not print
    ev("""(()=>{['lid','conj','sclera','cornea','ac','iris','lens','vit','fundus'].forEach(k=>['r','l'].forEach(e=>{
        const el=document.getElementById('ex-'+k+'-'+e); el.value=''; el.dispatchEvent(new Event('input',{bubbles:true}));}));
      T.set('ex-lens-r','PCIOL in bag'); T.set('ex-fundus-r','Attached, PRP scars'); T.set('ex-cornea-l','Clear');})()""")
    ev("T.$('#preview').click()"); ev("T.pdf()")
    few = ev("[...document.querySelectorAll('#live .pg1 .s-row .k')].map(k=>k.textContent.trim()).filter(t=>!['SYSTEMIC','OCULAR'].includes(t))")
    check('empty rows stay off the patient copy', few == ['CORNEA', 'LENS', 'FUNDUS', 'RAPD'], ' → '.join(few))
finally:
    try: chrome.terminate(); chrome.wait(5)
    except Exception: pass
    if server.poll() is None: server.terminate()
    shutil.rmtree(prof, ignore_errors=True)

print('\nJS errors:', errors or 'none')
print(f"\n{sum(ok for _, ok, _ in results)}/{len(results)} passed")
