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

    # ---------------- 1. name guard ----------------
    ev("T.$('#preview').click()"); time.sleep(0.3)
    check('Preview without a name is refused', ev("!T.$('#pv').classList.contains('on') && T.$('#toast').textContent.includes('name')"),
          ev("T.$('#toast').textContent"))

    # ---------------- 2. dosage pad through the real UI ----------------
    typeinto('[data-name]', 'Predforte eye drops')
    ev("T.$('[data-dose]').click()")
    check('pad opens', ev("T.$('#padwrap').classList.contains('on')"))
    ev("T.tap('.tline[data-j=\"0\"] .chip', 'دن میں 4 بار'); T.tap('.tline[data-j=\"0\"] .chip', 'دائیں آنکھ میں')")
    typeinto('.tline[data-j="0"] [data-dur]', '7')
    l1 = ev("T.$('.tline[data-j=\"0\"] [data-out]').value")
    check('step 1 composes', l1 == 'ایک قطرہ ۔ دن میں 4 بار ۔ دائیں آنکھ میں ۔ 7 دن', l1)
    ev("T.$('#addline').click()")
    ev("T.tap('.tline[data-j=\"1\"] .chip', 'دن میں 2 بار'); T.tap('.tline[data-j=\"1\"] .chip', 'صبح'); T.tap('.tline[data-j=\"1\"] .chip', 'رات')")
    typeinto('.tline[data-j="1"] [data-dur]', '1')
    ev("T.tap('.tline[data-j=\"1\"] .chip', 'ہفتہ'); T.tap('#pad-end .chip', 'پھر بند کر دیں')")
    l2 = ev("T.$('.tline[data-j=\"1\"] [data-out]').value")
    check('step 2 composes with پھر, singular ہفتہ', l2 == 'پھر ۔ ایک قطرہ ۔ دن میں 2 بار ۔ صبح، رات ۔ 1 ہفتہ', l2)
    # hand edit survives closing the pad
    typeinto('.tline[data-j="1"] [data-out]', 'پھر ۔ ایک قطرہ ۔ صبح، رات ۔ 1 ہفتہ ۔ کھانے کے بعد')
    ev("T.$('.pad [data-close]').click()"); time.sleep(0.4)
    check('Done closes the pad (via history)', ev("!T.$('#padwrap').classList.contains('on')"))
    card = ev("T.$('.drug .lines')?.innerText || ''")
    check('drug card shows hand-edited line + ending', 'کھانے کے بعد' in card and 'پھر بند کر دیں' in card, card.replace('\n', ' / '))
    # form switch drops -> other clears drops-only frequency
    ev("T.$('#adddrug').click()"); typeinto('#drugs .drug:last-child [data-name]', 'Tab Diamox 250mg')
    ev("T.$('#drugs .drug:last-child [data-dose]').click()")
    ev("T.tap('.tline .chip', 'ہر 2 گھنٹے بعد'); T.tap('#pad-form .chip', 'Tablet / Other')")
    check('switching to tablet drops a drops-only frequency', ev("T.$('.tline [data-out]').value") == '' and not ev("!!T.$$('.tline .chip.on').find(c=>c.textContent.includes('گھنٹے'))"))
    ev("T.tap('.tline .chip', 'دن میں 2 بار')"); typeinto('.tline [data-dur]', '3')
    check('tablet line has no drop/eye words', ev("T.$('.tline [data-out]').value") == 'دن میں 2 بار ۔ 3 دن', ev("T.$('.tline [data-out]').value"))

    # ---------------- 3. Android back button ----------------
    ev("history.back()"); time.sleep(0.4)
    check('back closes the pad', ev("!T.$('#padwrap').classList.contains('on')"))

    # ---------------- 4. normal one-page prescription ----------------
    ev("""T.set('p-name','Muhammad Aslam'); T.set('p-rel','Rahim Bakhsh'); T.set('p-age','58'); T.$('[data-single="p-sex"] .chip').click();
      T.set('p-city','Arifwala'); T.set('p-mr','TN-04182'); T.set('chief','Sudden painless loss of vision, right eye — 6 weeks');
      T.set('va-r','FC'); T.set('va-l','6/24'); T.set('iop-r-pre','15'); T.set('iop-l-pre','17');
      T.set('h-sys','BP 140/80, Diabetic 9 yrs'); T.set('h-ocu','Cataract extraction 22/07/26'); T.set('h-pres','Deterioration of vision 08/08/26');
      T.set('ex-lens-r','IOL'); T.set('ex-lens-l','Cataract'); T.set('ex-vit-r','Debris, Haze'); T.set('ex-fundus-r','Hazy view'); T.set('ex-fundus-l','Normal');
      T.set('a-inv','CBC · Blood Sugar · Anti HCV · HBsAg'); T.set('a-proc','PPV + Intravitreal antibiotics — Right Eye');
      T.set('ref-r-sph','2'); T.set('ref-r-cyl','0.5'); T.set('ref-r-axis','95'); T.set('ref-r-va','6/18'); T.set('ref-r-add','2.5');
      T.set('fu','2026-09-28'); 1""")
    t0 = time.time(); ev("T.$('#preview').click()")
    ok = ev("T.pdf()"); dt = time.time() - t0
    check('one-page PDF builds', ok and ev("RxApp.pages()") == 1, f"pages={ev('RxApp.pages()')}  {dt:.1f}s on this desktop  {ev('RxApp.pdf()?.size||0')//1024} KB")
    sph = ev("[...T.$$('#live .s-rt td')].map(t=>t.textContent).join(' ')")
    check('refraction: "2" typed with sign untouched prints as', True, sph)
    save_pdf('1-normal')
    ev("T.$('#pv-send').click()"); time.sleep(0.8)
    check('Send on desktop falls back to download', 'downloaded' in (ev("T.$('#toast').textContent") or ''), ev("T.$('#toast').textContent"))
    ev("history.back()"); time.sleep(0.4)
    check('back closes the preview', ev("!T.$('#pv').classList.contains('on')"))

    # ---------------- 5. long Rx: 8 drugs, 4-step tapers ----------------
    ev("""(()=>{const taper=['دن میں 4 بار','دن میں 3 بار','دن میں 2 بار','دن میں ایک بار'].map(f=>Object.assign(RxApp.newStep(),{freq:f,eye:'دونوں آنکھوں میں',dur:'1',unit:'hafta'}));
      RxApp.S.drugs.length=0;
      ['Predforte','Vigamox','Nevanac','Timolol','Brimonidine','Cyclopen','Tobradex','Hylo'].forEach(n=>{const d=RxApp.newDrug(); d.name=n+' eye drops'; d.steps=taper.map(s=>({...s})); d.end='پھر بند کر دیں'; RxApp.S.drugs.push(d);});
      RxApp.renderDrugs();})()""")
    ev("T.$('#preview').click()"); ev("T.pdf()")
    pages = ev("RxApp.pages()")
    check('8 drugs x 4 steps -> 2 pages', pages == 2, f'pages={pages}')
    o2 = ev("T.p2over()")
    check('page 2 content fits inside the page', o2 is not None and o2 <= 1, f'page-2 overflow = {o2:.0f}px' if o2 is not None else 'no page 2')
    drugs_p1 = ev("T.$$('#live .pg1 .s-drug').length"); drugs_p2 = ev("T.$$('#live .pg2 .s-drug').length")
    check('all 8 drugs present across pages', drugs_p1 + drugs_p2 == 8, f'page1={drugs_p1} page2={drugs_p2}')
    save_pdf('2-long-rx')
    ev("T.$('#pv-send').click()"); time.sleep(0.3)
    check('2-page Send asks first', ev("T.$('#ask').classList.contains('on')"))
    ev("T.$('#ask-no').click()"); ev("history.back()"); time.sleep(0.4)

    # ---------------- 6. left-column heavy: long history + exam, 2 drugs ----------------
    ev("""(()=>{RxApp.S.drugs.length=0; ['Predforte','Vigamox'].forEach(n=>{const d=RxApp.newDrug(); d.name=n; d.steps=[Object.assign(RxApp.newStep(),{freq:'دن میں 4 بار',dur:'7'})]; RxApp.S.drugs.push(d);}); RxApp.renderDrugs();
      const long='Type 2 DM for 14 years on insulin, poorly controlled (HbA1c 9.8). Hypertensive on amlodipine. IHD with CABG 2019. CKD stage 3. ';
      T.set('h-sys', long.repeat(4)); T.set('h-ocu', 'PRP both eyes 2021, 2022. Anti-VEGF x6 right eye. Cataract surgery left eye 2024. '.repeat(3));
      T.set('h-pres', 'Sudden floaters and drop in vision right eye for 5 days. '.repeat(3));
      ['lens','ac','cornea','conj','vit','fundus'].forEach(k=>{T.set('ex-'+k+'-r','Detailed findings noted here for the right eye, several words long'); T.set('ex-'+k+'-l','Detailed findings noted for left eye too, several words');});})()""")
    ev("T.$('#preview').click()"); ev("T.pdf()")
    pages = ev("RxApp.pages()"); o1 = ev("T.p1over()"); o2 = ev("T.p2over()")
    check('long history/exam fits (spills to page 2 if needed)', pages in (1, 2) and o1 <= 1 and (o2 is None or o2 <= 1),
          f'pages={pages}  p1 overflow={o1:.0f}px  p2 overflow={o2}  send button="{ev("T.$(\'#pv-send\').textContent")}"')
    save_pdf('3-long-history')
    ev("history.back()"); time.sleep(0.4)

    # ---------------- 7. offline ----------------
    sw = "(async()=>{const r=await navigator.serviceWorker.getRegistration(); const k=await caches.keys(); let n=0; for(const c of k) n+=(await (await caches.open(c)).keys()).length; return {active:!!(r&&r.active), cached:n, controlled:!!navigator.serviceWorker.controller};})()"
    s = {}
    for _ in range(60):
        s = ev(sw)
        if s['active'] and s['cached'] >= 15: break
        time.sleep(0.5)
    check('service worker installs and caches the app', s.get('active') and s.get('cached', 0) >= 15, str(s))
    server.terminate(); server.wait(5)
    try: urllib.request.urlopen(URL, timeout=2); down = False
    except Exception: down = True
    check('test server stopped', down)
    ev("window.onbeforeunload=null; window.__old=1")
    cmd('Page.reload', ignoreCache=False)
    loaded = wait("!window.__old && typeof RxApp !== 'undefined' && document.readyState === 'complete'", 30)
    check('app reloads with no server', loaded)
    if loaded:
        ev("""window.T = window.T || {}; (()=>{const $=s=>document.querySelector(s); const set=(id,v)=>{const e=document.getElementById(id); e.value=v; e.dispatchEvent(new Event('input',{bubbles:true}));};
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
