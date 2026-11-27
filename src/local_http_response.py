"""Response encoding and fixed security headers for the local HTTP server."""
import json
from http.server import BaseHTTPRequestHandler


class LocalResponseHandler(BaseHTTPRequestHandler):
    def send_data(self,data,kind='application/json; charset=utf-8',status=200,extra=None):
        if not isinstance(data,bytes): data=json.dumps(data,ensure_ascii=False).encode()
        self.send_response(status); self.send_header('Content-Type',kind); self.send_header('Content-Length',str(len(data)))
        self.send_header('Cache-Control','no-store'); self.send_header('X-Content-Type-Options','nosniff'); self.send_header('Referrer-Policy','no-referrer'); self.send_header('X-Frame-Options','DENY')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'")
        for k,v in (extra or {}).items(): self.send_header(k,v)
        self.end_headers(); self.wfile.write(data)
