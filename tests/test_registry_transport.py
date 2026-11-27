import unittest
from unittest.mock import Mock,patch
import requests
from registry_client import Client,BASE,TOKEN_URL

class TransportTests(unittest.TestCase):
    def setUp(self):
        self.bot=Mock(last_request=0)
        self.client=Client(self.bot,("fixture","secret"),delay=0)
        self.addCleanup(self.client.close)
        self.client.session=Mock()
    def response(self,code,headers=None,body=b'{}'):
        r=Mock(status_code=code,headers=headers or {})
        r.__enter__=Mock(return_value=r);r.__exit__=Mock(return_value=False)
        r.iter_content.return_value=[body]
        return r
    def test_rate_limit_respects_retry_after(self):
        self.client.session.request.side_effect=[self.response(429,{"Retry-After":"17"}),self.response(200,body=b'[]')]
        self.assertEqual(self.client.request("GET",BASE+"/subjekti")[0],200)
        self.bot.wait.assert_any_call(17)
    def test_long_rate_limit_and_redirect_fail_closed(self):
        for response in (self.response(429,{"Retry-After":"600"}),self.response(302,{"Location":"https://example.invalid"})):
            self.client.session.request.reset_mock()
            self.client.session.request.return_value=response
            with self.assertRaises(PermissionError):self.client.request("GET",BASE+"/subjekti")
            self.assertEqual(self.client.session.request.call_count,1)
    def test_tls_failure_not_retried(self):
        self.client.session.request.side_effect=requests.exceptions.SSLError()
        with self.assertRaises(PermissionError):self.client.request("GET",BASE+"/subjekti")
        self.assertEqual(self.client.session.request.call_count,1)
    def test_401_html_refreshes_token(self):
        self.client.session.request.side_effect=[self.response(200,body=b'{"access_token":"abc","expires_in":300}'),self.response(401,body=b'<html>expired</html>'),self.response(200,body=b'{"access_token":"def","expires_in":300}'),self.response(200,body=b'[]')]
        self.assertEqual(self.client.get("subjekti")[1],[])
        self.assertEqual(self.client.token,"def")
    def test_invalid_token_lifetime_and_path(self):
        self.client.session.request.return_value=self.response(200,body=b'{"access_token":"abc","expires_in":true}')
        with self.assertRaises(ValueError):self.client.auth()
        self.client.session.request.reset_mock()
        with self.assertRaises(ValueError):self.client.get("../oauth/token")
        with self.assertRaises(ValueError):self.client.request("POST",TOKEN_URL+"?other=1")
        self.client.session.request.assert_not_called()
