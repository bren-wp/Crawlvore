import unittest
from email.message import Message

from local_http_security import (InvalidFraming, allowed_host, content_length,
                                 session_cookie_name, token_matches, valid_session_cookie)


class LocalHttpSecurityTests(unittest.TestCase):
    def test_loopback_host(self):
        for host in ("127.0.0.1:49152", "localhost:49152"):
            self.assertTrue(allowed_host(host, 49152))
        for host in (None, "localhost", "localhost:1", "localhost.evil:49152",
                     "127.0.0.1:49152.evil", "[::1]:49152"):
            self.assertFalse(allowed_host(host, 49152))

    def test_session_and_ascii_token(self):
        name = session_cookie_name(49152)
        token = "a" * 64
        self.assertTrue(valid_session_cookie(name + "=" + token, name, token))
        self.assertFalse(valid_session_cookie("other=" + token, name, token))
        self.assertFalse(valid_session_cookie(name + "=wrong", name, token))
        self.assertFalse(token_matches("?", token))
        self.assertFalse(token_matches(None, token))

    def test_exact_content_length(self):
        for value in ("0", "42", "00042", "999999999999"):
            headers = Message()
            headers["Content-Length"] = value
            self.assertEqual(content_length(headers), int(value))
        for values in ((), ("1", "1"), ("-1",), ("+1",), ("1,2",),
                       ("1 ",), ("??",), ("1234567890123",), ("",)):
            with self.subTest(values=values):
                headers = Message()
                for value in values:
                    headers["Content-Length"] = value
                with self.assertRaises(InvalidFraming):
                    content_length(headers)
        headers = Message()
        headers["Content-Length"] = "1"
        headers["Transfer-Encoding"] = "chunked"
        with self.assertRaises(InvalidFraming):
            content_length(headers)
