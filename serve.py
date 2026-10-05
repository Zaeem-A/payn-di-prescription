#!/usr/bin/env python3
"""Serve app/ for testing on a real phone.

    python3 serve.py            # http://localhost:8090
    python3 serve.py 9000       # another port

app/ is served as the site root, so the service worker's scope is '/' and
"Add to Home Screen" behaves exactly as it would on a real host.

Plain HTTP is fine on localhost, but a phone needs HTTPS before Chrome will
allow the share sheet or a service worker — put ngrok in front of this:

    ngrok http 8090
"""
import functools, http.server, mimetypes, socket, sys

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8090
ROOT = __file__.rsplit('/', 1)[0] + '/app'

mimetypes.add_type('application/manifest+json', '.webmanifest')
mimetypes.add_type('font/woff2', '.woff2')


class Handler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        # never cache: the service worker does the caching, and a stale
        # app.js during testing wastes an afternoon
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Service-Worker-Allowed', '/')
        super().end_headers()

    def log_message(self, fmt, *args):
        print(f'  {self.address_string()}  {fmt % args}', flush=True)


def lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        return s.getsockname()[0]
    finally:
        s.close()


if __name__ == '__main__':
    print(f'serving {ROOT}')
    print(f'  this machine   http://localhost:{PORT}')
    try:
        print(f'  same wi-fi     http://{lan_ip()}:{PORT}   (no share sheet: needs HTTPS)')
    except Exception:
        pass
    print(f'  phone          ngrok http {PORT}\n')
    http.server.ThreadingHTTPServer(
        ('0.0.0.0', PORT), functools.partial(Handler, directory=ROOT)).serve_forever()
