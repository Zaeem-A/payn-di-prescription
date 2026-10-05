# static server for QA; PUT lets the harness save the generated PDF to disk
import http.server, os, sys
os.chdir(sys.argv[1])
class H(http.server.SimpleHTTPRequestHandler):
    def do_PUT(self):
        data = self.rfile.read(int(self.headers['Content-Length']))
        with open(self.translate_path(self.path), 'wb') as f: f.write(data)
        self.send_response(201); self.end_headers()
    def end_headers(self):
        self.send_header('Cache-Control', 'no-store'); super().end_headers()
    def log_message(self, *a): pass
http.server.ThreadingHTTPServer(('127.0.0.1', 8765), H).serve_forever()
