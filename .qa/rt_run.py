"""Drive harness.html in REAL time over the DevTools protocol (virtual time
gives false font results). usage: rt_run.py <shot> <scen> [screenshot.png]"""
import base64, json, subprocess, sys, time, urllib.request, shutil, os
import websocket
shot, scen = sys.argv[1], sys.argv[2]
png = sys.argv[3] if len(sys.argv) > 3 else None
PORT, prof = 9334, os.path.abspath(f'prof-rt-{shot}-{scen}')
shutil.rmtree(prof, ignore_errors=True); os.makedirs(prof)
chrome = subprocess.Popen(['google-chrome', '--headless', '--disable-gpu', '--no-sandbox', f'--user-data-dir={prof}',
    f'--remote-debugging-port={PORT}', '--remote-allow-origins=*', '--hide-scrollbars', 'about:blank'],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    for _ in range(100):
        try: tabs = json.load(urllib.request.urlopen(f'http://127.0.0.1:{PORT}/json/list')); break
        except Exception: time.sleep(0.2)
    ws = websocket.create_connection([t for t in tabs if t['type'] == 'page'][0]['webSocketDebuggerUrl'], timeout=120, suppress_origin=True)
    mid = 0
    def cmd(method, **params):
        global mid; mid += 1
        ws.send(json.dumps({'id': mid, 'method': method, 'params': params}))
        while True:
            m = json.loads(ws.recv())
            if m.get('id') == mid:
                if 'error' in m: raise RuntimeError(m['error'])
                return m.get('result', {})
    cmd('Emulation.setDeviceMetricsOverride', width=412, height=915, deviceScaleFactor=2.625, mobile=True)
    cmd('Page.navigate', url=f'http://127.0.0.1:8765/.qa/harness.html?shot={shot}&scen={scen}')
    title = ''
    for _ in range(240):
        time.sleep(0.5)
        title = cmd('Runtime.evaluate', expression='document.title', returnByValue=True)['result'].get('value', '')
        if title.startswith(('DONE', 'ERR', 'APPERR')): break
    if shot == 'preview': time.sleep(0.5)
    print(title)
    if png:
        open(png, 'wb').write(base64.b64decode(cmd('Page.captureScreenshot', format='png')['data']))
finally:
    chrome.terminate(); time.sleep(0.3); shutil.rmtree(prof, ignore_errors=True)
