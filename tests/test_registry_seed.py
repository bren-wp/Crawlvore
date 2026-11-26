import hashlib
import tempfile
import unittest
from pathlib import Path
from registry_seed import install_seed


class SeedTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.source=self.root/'registry-seed.sqlite3'
        self.source.write_bytes(b'synthetic test data')
        self.check=self.root/'registry-seed.sha256'
        self.check.write_text(hashlib.sha256(self.source.read_bytes()).hexdigest(),encoding='ascii')
        self.dest=self.root/'companies.sqlite3'

    def test_fresh_seed(self):
        self.assertTrue(install_seed(self.root,self.dest))
        self.assertEqual(self.dest.read_bytes(),self.source.read_bytes())

    def test_existing_workspace_preserved(self):
        self.dest.write_bytes(b'existing user database')
        self.assertFalse(install_seed(self.root,self.dest))
        self.assertEqual(self.dest.read_bytes(),b'existing user database')

    def test_corrupted_seed_rejected(self):
        self.source.write_bytes(b'changed')
        with self.assertRaises(ValueError):
            install_seed(self.root,self.dest)
        self.assertFalse(self.dest.exists())
