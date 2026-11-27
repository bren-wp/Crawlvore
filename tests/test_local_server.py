import http.client
import socket
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler
from local_server import LocalServer

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Length","2")
        self.end_headers()
        self.wfile.write(b"ok")
    def log_message(self,*args): pass

class TinyServer(LocalServer):
    max_requests=1
    idle_timeout=0.35

class ServerTests(unittest.TestCase):
    def test_only_loopback(self):
        with self.assertRaises(ValueError): LocalServer(("0.0.0.0",0),Handler)
    def test_concurrency_is_bounded_and_idle_slot_recovers(self):
        server=TinyServer(("127.0.0.1",0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        port=server.server_port
        with socket.create_connection(("127.0.0.1",port),timeout=2) as idle:
            idle.sendall(b"GET / HTTP/1.1\r\n")
            deadline=time.monotonic()+1
            while time.monotonic()<deadline:
                if not server.slots.acquire(blocking=False): break
                server.slots.release()
                time.sleep(.005)
            else: self.fail("idle request did not acquire slot")
            conn=http.client.HTTPConnection("127.0.0.1",port,timeout=2)
            try:
                conn.request("GET","/")
                with conn.getresponse() as r: self.assertEqual(r.status,503)
            finally:conn.close()
            # Idle incomplete headers expire; the worker remains usable.
            time.sleep(.5)
            conn=http.client.HTTPConnection("127.0.0.1",port,timeout=2)
            try:
                conn.request("GET","/")
                with conn.getresponse() as r:
                    self.assertEqual(r.status,200)
                    self.assertEqual(r.read(),b"ok")
            finally:conn.close()
