import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from tools.complete_release import REQUIRED, verify
from tools.sign_release_updates import sign
from update_verification import TARGETS

class CompleteReleaseTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        self.key=Ed25519PrivateKey.generate()
        self.public=self.key.public_key().public_bytes_raw()
        for name in set(TARGETS.values())|{"Update.exe","crawlvora-update","Crawlvora-source.zip"}:
            (self.root/name).write_bytes(("synthetic "+name).encode())
        (self.root/"REGISTRY-HR-MANIFEST.json").write_text(json.dumps({"snapshot":"1370","rows":11831255,"subjects":392785}))
        (self.root/"PACKAGE-SIZES.json").write_text(json.dumps({"packages":[{"name":name,"bytes":(self.root/name).stat().st_size} for name in TARGETS.values()]}))
        with patch("tools.sign_release_updates.TRUSTED_KEY_HEX",self.public.hex()):
            sign(self.root,"8.1.7",self.key.private_bytes_raw().hex(),"HR")
        self.checksums()
    def checksums(self):
        (self.root/"SHA256SUMS.txt").write_text("".join(hashlib.sha256((self.root/name).read_bytes()).hexdigest()+"  "+name+"\n" for name in sorted(REQUIRED-{"SHA256SUMS.txt"})),encoding="ascii")
    def test_complete_matrix(self):
        self.assertEqual(verify(self.root,"8.1.7",self.public),16)
    def test_every_artifact_required(self):
        for name in REQUIRED:
            with self.subTest(name=name):
                path=self.root/name
                raw=path.read_bytes()
                path.unlink()
                with self.assertRaises(ValueError):verify(self.root,"8.1.7",self.public)
                path.write_bytes(raw)
    def test_signed_asset_tampering_fails_even_with_new_checksums(self):
        (self.root/"Setup-HR-Full.exe").write_bytes(b"tampered")
        self.checksums()
        with self.assertRaises(ValueError):verify(self.root,"8.1.7",self.public)
    def test_wrong_snapshot(self):
        (self.root/"REGISTRY-HR-MANIFEST.json").write_text(json.dumps({"snapshot":"1371","rows":11831255,"subjects":392785}))
        self.checksums()
        with self.assertRaises(ValueError):verify(self.root,"8.1.7",self.public)

    def test_updater_matrix_cannot_remove_mandatory_package(self):
        with patch.dict(TARGETS,clear=True):
            with self.assertRaisesRegex(ValueError,"Mandatory 16-file"):
                verify(self.root,"8.1.7",self.public)

    def test_extra_or_empty_package_rejected(self):
        extra=self.root/"Unexpected.exe"
        extra.write_bytes(b"extra")
        with self.assertRaises(ValueError):verify(self.root,"8.1.7",self.public)
        extra.unlink()
        (self.root/"Portable-HR-Online.exe").write_bytes(b"")
        with self.assertRaises(ValueError):verify(self.root,"8.1.7",self.public)
