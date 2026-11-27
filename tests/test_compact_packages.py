import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from tools.package_sizes import report
from tools.compress_registry_seed import prepare
from registry_seed import install_seed
import hashlib

class CompactPackageTests(unittest.TestCase):
    def test_compression_roundtrip_and_reuse(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            data=b"registry synthetic row\n"*10000
            source=root/"registry-seed.sqlite3"
            source.write_bytes(data)
            (root/"registry-seed.sha256").write_text(hashlib.sha256(data).hexdigest())
            prepare(root)
            prepare(root)
            self.assertLess((root/"registry-seed.sqlite3.xz").stat().st_size,len(data))
            self.assertTrue(install_seed(root,root/"installed.sqlite3"))
            self.assertEqual((root/"installed.sqlite3").read_bytes(),data)
            self.assertEqual(source.read_bytes(),data)
    def test_size_budget_and_missing_asset(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for name in ("Setup-Online.exe","Portable-Online.exe"):
                (root/name).write_bytes(b"test")
            self.assertEqual(len(report(root,"Online","Windows")["packages"]),2)
            with patch.dict("tools.package_sizes.LIMITS",{"Online":3}):
                with self.assertRaises(ValueError): report(root,"Online","Windows")
            with self.assertRaises(ValueError):report(root,"HR","Windows")
