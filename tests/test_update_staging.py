import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from update_staging import stage_update

class UpdateStagingTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        self.key=Ed25519PrivateKey.generate()
        self.public=self.key.public_key().public_bytes_raw()
        self.payload=self.root/"Setup-HR-Online.exe"
        self.data=b"synthetic release bytes"*500
        self.payload.write_bytes(self.data)
        self.raw=json.dumps({"schema":1,"product":"Crawlvora","version":"8.1.8","assets":[{"platform":"windows","package":"setup","edition":"Online","name":self.payload.name,"size":len(self.data),"sha256":hashlib.sha256(self.data).hexdigest()}]}).encode()
        self.signature=self.key.sign(self.raw)
        self.staging=self.root/"staged"
    def stage(self):
        return stage_update(self.raw,self.signature,self.public,"8.1.7","windows","setup","Online",self.payload,self.staging)
    def test_exact_signed_payload_and_no_overwrite(self):
        self.assertTrue(self.stage()["staged"])
        self.assertEqual((self.staging/self.payload.name).read_bytes(),self.data)
        self.assertEqual((self.staging/"UPDATE-MANIFEST.json").read_bytes(),self.raw)
        with self.assertRaises(FileExistsError):self.stage()
        self.assertEqual(self.payload.read_bytes(),self.data)
    def test_corruption_and_wrong_key_fail_closed(self):
        self.payload.write_bytes(self.data+b"x")
        with self.assertRaises(ValueError):self.stage()
        self.assertFalse(self.staging.exists())
        self.payload.write_bytes(self.data)
        self.public=Ed25519PrivateKey.generate().public_key().public_bytes_raw()
        with self.assertRaises(ValueError):self.stage()
        self.assertFalse(self.staging.exists())
    def test_never_overwrite_existing_workspace(self):
        self.staging.mkdir()
        sentinel=self.staging/"companies.sqlite3"
        sentinel.write_bytes(b"existing data")
        with self.assertRaises(FileExistsError):self.stage()
        self.assertEqual(sentinel.read_bytes(),b"existing data")
