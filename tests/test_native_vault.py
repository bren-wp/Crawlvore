import copy
import hashlib
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from native_vault import NativeVault
from core import Store
from data_safety import RecoveryCenter
from protected_backups import ProtectedBackups
from backup_replica import copy_verified,destination_for

class TestVault:
    backend='test'
    identity='test-workspace'
    def __init__(self): self.value=None
    def load(self): return copy.deepcopy(self.value)
    def save(self,value): self.value=copy.deepcopy(value)

class NativeVaultTests(unittest.TestCase):
    def test_external_checkpoint_rejects_catalog_rollback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); path=root/'companies.sqlite3'
            Store(path).import_json('[{"title":"Synthetic record"}]')
            vault=TestVault(); center=RecoveryCenter(path)
            engine=ProtectedBackups(path,center,vault)
            password='synthetic recovery passphrase'
            engine.unlock(password,initialize=True)
            engine.enroll_vault()
            first=engine.create()
            previous=engine.catalog.read_bytes()
            second=engine.create()
            self.assertEqual(vault.value['committed']['count'],2)
            self.assertTrue(engine.verify_restore(second)['verified'])
            engine.lock_session()
            engine.catalog.write_bytes(previous)
            reopened=ProtectedBackups(path,center,vault)
            reopened.start()
            try:
                self.assertFalse(reopened.snapshot()['unlocked'])
                self.assertEqual(reopened.snapshot()['vault'],'attention')
                with self.assertRaises(ValueError): reopened.unlock(password)
                self.assertTrue((engine.root/first).exists())
                self.assertTrue((engine.root/second).exists())
            finally: reopened.close()

    def test_missing_enrolled_vault_rejects_manual_unlock(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'companies.sqlite3'
            Store(path)
            vault=TestVault(); engine=ProtectedBackups(path,RecoveryCenter(path),vault)
            password='synthetic recovery passphrase'
            engine.unlock(password,initialize=True)
            engine.enroll_vault(); engine.lock_session()
            vault.value=None
            reopened=ProtectedBackups(path,RecoveryCenter(path),vault)
            reopened.start()
            try:
                with self.assertRaises(ValueError): reopened.unlock(password)
            finally: reopened.close()

    def test_replica_never_overwrites(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); source=root/'source'; target=root/'copy'
            source.write_bytes(b'authenticated synthetic archive')
            digest=hashlib.sha256(source.read_bytes()).hexdigest()
            copy_verified(source,target,digest)
            self.assertEqual(target.read_bytes(),source.read_bytes())
            copy_verified(source,target,digest)
            target.write_bytes(b'preserve this different file')
            with self.assertRaises(ValueError): copy_verified(source,target,digest)
            self.assertEqual(target.read_bytes(),b'preserve this different file')
            with self.assertRaises(ValueError): destination_for(root,str(root))

    @unittest.skipUnless(sys.platform=='win32','Windows DPAPI integration')
    def test_real_dpapi_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'LOCALAPPDATA':tmp}):
            vault=NativeVault(Path(tmp)/'workspace')
            record={'password':'synthetic DPAPI passphrase','committed':{'count':0,'head':'0'*64},'pending':None}
            vault.save(record)
            self.assertEqual(vault.load()['password'],record['password'])
            self.assertNotIn(record['password'].encode(),vault.windows_path().read_bytes())
            other=NativeVault(Path(tmp)/'other-workspace')
            self.assertIsNone(other.load())
