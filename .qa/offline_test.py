"""Real-time offline test over the Chrome DevTools protocol.
1. first visit online -> service worker installs and caches the app
2. kill the server (by the PID listening on its port)
3. reload with no server -> app must render and build a PDF"""
import json, os, re, signal, subprocess, sys, time, urllib.request
import websocket

PORT, URL = 9333, 'http://localhost:8765/app/index.html'
import re as _re
EXPECTED = len(_re.findall(r"'([^']+)'", _re.search(r"ASSETS = \[(.*?)\]", open('../app/sw.js').read(), _re.S).group(1)))
prof = sys.argv[1]
chrome = subprocess.Popen(['google-chrome', '--headless', '--disable-gpu', '--no-sandbox', f'--user-data-dir={prof}',
                           f'--remote-debugging-port={PORT}', '--remote-allow-origins=*', 'about:blank'],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    for _ in range(100):
        try: tabs = json.load(urllib.request.urlopen(f'http://127.0.0.1:{PORT}/json/list')); break
        except Exception: time.sleep(0.2)
    ws = websocket.create_connection([t for t in tabs if t['type'] == 'page'][0]['webSocketDebuggerUrl'], timeout=90, suppress_origin=True)
    mid = 0
    def cmd(method, **params):
        global mid; mid += 1
        ws.send(json.dumps({'id': mid, 'method': method, 'params': params}))
        while True:
            m = json.loads(ws.recv())
            if m.get('id') == mid:
                if 'error' in m: raise RuntimeError(m['error'])
                return m.get('result', {})
    def ev(expr):
        r = cmd('Runtime.evaluate', expression=expr, awaitPromise=True, returnByValue=True)
        if 'exceptionDetails' in r: raise RuntimeError(r['exceptionDetails'].get('exception', {}).get('description'))
        return r['result'].get('value')
    def settle(t=20):
        end = time.time() + t
        while time.time() < end:
            try:
                if ev('document.readyState') == 'complete': return True
            except Exception: pass
            time.sleep(0.3)
        return False

    SW = """(async()=>{const r=await navigator.serviceWorker.getRegistration();
      const k=(await caches.keys())[0]; const n=k?(await (await caches.open(k)).keys()).length:0;
      return {active:!!(r&&r.active), cached:n};})()"""

    print('1. online first visit')
    cmd('Page.navigate', url=URL); settle()
    for _ in range(60):
        s = ev(SW)
        if s['active'] and s['cached'] >= EXPECTED: break
        time.sleep(0.5)
    print(f"   service worker active={s['active']}  files cached={s['cached']}/{EXPECTED}")

    print('2. killing the server')
    out = subprocess.run(['ss', '-ltnpH', 'sport = :8765'], capture_output=True, text=True).stdout
    pid = re.search(r'pid=(\d+)', out)
    if pid: os.kill(int(pid.group(1)), signal.SIGTERM); time.sleep(1)
    try: urllib.request.urlopen(URL, timeout=3); print('   server STILL UP')
    except Exception: print('   server unreachable')

    print('3. reload with no server')
    ev('window.__old = 1')                 # marks the pre-reload document
    cmd('Page.reload')
    ok = False
    for _ in range(80):                      # wait for the NEW document to finish running app.js
        try:
            if ev("!window.__old && document.readyState === 'complete' && typeof RxApp !== 'undefined'"): ok = True; break
        except Exception: pass
        time.sleep(0.25)
    r = ev("({title:document.title, drugInputs:document.querySelectorAll('[data-name]').length, controlled:!!navigator.serviceWorker.controller})")
    print(f"   page loaded={ok}  title={r['title']!r}  drug inputs={r['drugInputs']}  served by worker={r['controlled']}")

    size = ev("""(async()=>{document.getElementById('p-name').value='Offline Test'; document.getElementById('chief').value='Floaters, right eye';const d=RxApp.newDrug(); d.name='Predforte eye drops'; d.steps[0]=Object.assign(RxApp.newStep(),{freq:'دن میں 4 بار',eye:'دائیں آنکھ میں',dur:'7'}); d.end='پھر بند کر دیں';RxApp.S.drugs[0]=d; RxApp.renderDrugs();
      await RxApp.openPreview();
      for(let i=0;i<400&&!RxApp.pdf();i++) await new Promise(r=>setTimeout(r,100));
      return RxApp.pdf()?RxApp.pdf().size:0;})()""")
    print(f"   PDF built offline: {size // 1024} KB" if size else "   PDF built offline: FAILED")
    b64 = ev("(async()=>{const b=RxApp.pdf(); if(!b) return ''; const u=new Uint8Array(await b.arrayBuffer()); let s=''; for(let i=0;i<u.length;i+=32768) s+=String.fromCharCode.apply(null,u.subarray(i,i+32768)); return btoa(s);})()")
    if b64:
        import base64; pathlib_path = 'out-offline.pdf'; open(pathlib_path, 'wb').write(base64.b64decode(b64)); print('   saved out-offline.pdf')
    fonts = ev("[...document.fonts].filter(f=>f.status==='loaded').map(f=>f.family.replace(/\"/g,'')+' '+f.weight).join(', ')")
    print(f"   fonts loaded offline: {fonts}")
finally:
    chrome.terminate()
