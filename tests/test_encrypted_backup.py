import hashlib
import tempfile
import unittest
from pathlib import Path
from cryptography.exceptions import InvalidTag
from core import Store
from data_safety import verified_backup,restore_workspace
from encrypted_backup import encrypt_backup,decrypt_backup

class EncryptedBackupTests(unittest.TestCase):
    def test_roundtrip_and_authentication(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            store=Store(root/'companies.sqlite3')
            store.import_json('[{"title":"Private synthetic record","phone":"111"}]')
            backup=verified_backup(root/'companies.sqlite3')
            digest=hashlib.sha256(backup.read_bytes()).hexdigest()
            password='synthetic test passphrase 2026'
            archive=encrypt_backup(backup,root/'backup.cvbackup',password)
            self.assertNotIn(b'Private synthetic record',archive.read_bytes())
            with self.assertRaises(InvalidTag): decrypt_backup(archive,root/'wrong.sqlite3','wrong test passphrase 2026')
            self.assertFalse((root/'wrong.sqlite3').exists())
            raw=bytearray(archive.read_bytes()); raw[-17]^=1
            tampered=root/'tampered.cvbackup'; tampered.write_bytes(raw)
            with self.assertRaises(InvalidTag): decrypt_backup(tampered,root/'tampered.sqlite3',password)
            self.assertFalse((root/'tampered.sqlite3').exists())
            decoded=decrypt_backup(archive,root/'decoded.sqlite3',password)
            self.assertEqual(hashlib.sha256(decoded.read_bytes()).hexdigest(),digest)
            self.assertEqual(Store(restore_workspace(decoded,root/'new')).detail(1),store.detail(1))
            with self.assertRaises(FileExistsError): encrypt_backup(backup,archive,password)
            self.assertEqual(hashlib.sha256(backup.read_bytes()).hexdigest(),digest)
