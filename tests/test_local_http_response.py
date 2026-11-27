import io
import json
import unittest
from unittest.mock import Mock

from local_http_response import LocalResponseHandler


class LocalHttpResponseTests(unittest.TestCase):
    def handler(self):
        handler = object.__new__(LocalResponseHandler)
        handler.send_response = Mock()
        handler.send_header = Mock()
        handler.end_headers = Mock()
        handler.wfile = io.BytesIO()
        return handler

    def test_json_encoding_and_security_headers(self):
        handler = self.handler()
        handler.send_data({"name": "?eljko"}, status=400)
        body = handler.wfile.getvalue()
        self.assertEqual(json.loads(body), {"name": "?eljko"})
        handler.send_response.assert_called_once_with(400)
        headers = dict(call.args for call in handler.send_header.call_args_list)
        self.assertEqual(headers["Content-Length"], str(len(body)))
        self.assertEqual(headers["Content-Type"], "application/json; charset=utf-8")
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(headers["X-Frame-Options"], "DENY")
        self.assertEqual(headers["Referrer-Policy"], "no-referrer")
        self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])
        self.assertIn("script-src 'self'", headers["Content-Security-Policy"])
        handler.end_headers.assert_called_once()

    def test_binary_redirect_preserves_headers_and_body(self):
        handler = self.handler()
        handler.send_data(b"", status=303, extra={"Location": "/"})
        self.assertEqual(handler.wfile.getvalue(), b"")
        handler.send_response.assert_called_once_with(303)
        handler.send_header.assert_any_call("Location", "/")
        handler.send_header.assert_any_call("Content-Length", "0")
