"""Bounded authenticated loopback request server."""
import threading
from http.server import ThreadingHTTPServer

class LocalServer(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 32
    max_requests = 16
    idle_timeout = 15

    def __init__(self, address, handler):
        if address[0] != "127.0.0.1":
            raise ValueError("Worker must bind to loopback.")
        self.slots = threading.BoundedSemaphore(self.max_requests)
        super().__init__(address, handler)

    def get_request(self):
        connection, address = super().get_request()
        connection.settimeout(self.idle_timeout)
        return connection, address

    def process_request(self, request, client_address):
        if not self.slots.acquire(blocking=False):
            try:
                request.settimeout(0.5)
                request.sendall(b"HTTP/1.1 503 Service Unavailable\r\n"
                                b"Connection: close\r\nContent-Length: 0\r\n\r\n")
            except OSError:
                pass
            finally:
                self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self.slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.slots.release()
