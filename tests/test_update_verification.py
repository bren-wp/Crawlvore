import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from update_verification import verify_manifest, verify_payload

class UpdateVerificationTests(unittest.TestCase):
    def setUp(self):
        self.private=Ed25519PrivateKey.generate()
        self.public=self.private.public_key().public_bytes_raw()
        self.payload=b'synthetic installer, not executable'
        self.entry={'platform':'windows','package':'setup','edition':'Online','name':'Setup-HR-Online.exe','size':len(self.payload),'sha256':hashlib.sha256(self.payload).hexdigest()}
        self.manifest={'schema':1,'product':'Crawlvora','version':'8.1.8','assets':[self.entry]}
    def verify(self, installed='8.1.7', edition='Online'):
        raw=json.dumps(self.manifest).encode()
        return verify_manifest(raw,self.private.sign(raw),self.public,installed,'windows','setup',edition)
    def test_signed_matching_payload(self):
        entry=self.verify()
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/entry['name'];path.write_bytes(self.payload)
            self.assertTrue(verify_payload(path,entry)['verified'])
            path.write_bytes(self.payload+b'x')
            with self.assertRaises(ValueError): verify_payload(path,entry)
    def test_wrong_signature(self):
        raw=json.dumps(self.manifest).encode()
        with self.assertRaises(ValueError):
            verify_manifest(raw+b' ',self.private.sign(raw),self.public,'8.1.7','windows','setup','Online')
    def test_no_downgrade_or_edition_switch(self):
        for installed,edition in [('8.1.8','Online'),('8.2.0','Online'),('8.1.7','HR')]:
            with self.assertRaises(ValueError): self.verify(installed,edition)
    def test_no_path_traversal_or_duplicate_targets(self):
        self.entry['name']='../Setup-HR-Online.exe'
        with self.assertRaises(ValueError): self.verify()
        self.entry['name']='Setup-HR-Online.exe'
        self.manifest['assets'].append(dict(self.entry))
        with self.assertRaises(ValueError): self.verify()
    def test_duplicate_json_keys(self):
        raw=b'{"schema":1,"schema":1}'
        with self.assertRaises(ValueError):
            verify_manifest(raw,self.private.sign(raw),self.public,'8.1.7','windows','setup','Online')
