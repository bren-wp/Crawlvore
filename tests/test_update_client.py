import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, Mock
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from update_client import download, fetch, safe_url, install_staged

class Response:
    def __init__(self,data=b"",status=200,headers=None):
        self.data=data;self.status_code=status;self.headers=headers or {}
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def raise_for_status(self):pass
    def iter_content(self,chunk_size):yield self.data

class ClientTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        self.key=Ed25519PrivateKey.generate()
        self.pin=patch("update_client.TRUSTED_KEY_HEX",self.key.public_key().public_bytes_raw().hex())
        self.pin.start();self.addCleanup(self.pin.stop)
        self.payload=b"test payload"
        self.raw=json.dumps({"schema":1,"product":"Crawlvora","version":"8.1.8","assets":[{"platform":"windows","package":"setup","edition":"Online","name":"Setup-HR-Online.exe","size":len(self.payload),"sha256":hashlib.sha256(self.payload).hexdigest()}]}).encode()
    def session(self,payload=None):
        session=Mock()
        session.get.side_effect=[Response(self.raw),Response(self.key.sign(self.raw)),Response(self.payload if payload is None else payload)]
        return session
    def test_signed_download_stage_and_reverify(self):
        staging=self.root/"stage"
        session=self.session()
        result=download("v8.1.8-online","8.1.7","windows","setup","Online",staging,session)
        self.assertTrue(result["staged"])
        self.assertEqual((staging/"Setup-HR-Online.exe").read_bytes(),self.payload)
        self.assertEqual(session.get.call_count,3)
        with patch("update_client.subprocess.run") as run:
            run.return_value.returncode=0
            self.assertEqual(install_staged(staging,"8.1.7","windows","setup","Online"),0)
            run.assert_called_once_with([str(staging/"Setup-HR-Online.exe")],check=False)
            (staging/"Setup-HR-Online.exe").write_bytes(b"tampered")
            with self.assertRaises(ValueError):install_staged(staging,"8.1.7","windows","setup","Online")
            self.assertEqual(run.call_count,1)
    def test_invalid_payload_no_staged_file(self):
        staging=self.root/"stage"
        with self.assertRaises(ValueError):download("v8.1.8-online","8.1.7","windows","setup","Online",staging,self.session(b"bad"))
        self.assertFalse(staging.exists())
    def test_redirect_allowlist_and_limit(self):
        for url in ("http://github.com/x","https://github.com.evil.invalid/x","https://github.com:444/x","https://a@github.com/x"):
            self.assertFalse(safe_url(url))
        session=Mock();session.get.return_value=Response(status=302,headers={"Location":"https://evil.invalid/x"})
        with self.assertRaises(ValueError):fetch(session,"https://github.com/x",16)
        session.get.assert_called_once()
        session=Mock();session.get.return_value=Response(b"abc",headers={"Content-Length":"100"})
        with self.assertRaises(ValueError):fetch(session,"https://github.com/x",2)
    def test_no_downgrade_or_wrong_edition(self):
        session=Mock()
        for tag in ("v8.1.7-online","v8.1.8-hr","../v8.1.8-online"):
            with self.assertRaises(ValueError):download(tag,"8.1.7","windows","setup","Online",self.root/"stage",session)
        session.get.assert_not_called()
