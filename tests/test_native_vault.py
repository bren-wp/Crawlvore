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

    def test_prepared_transaction_rolls_forward_exact_signed_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); path=root/'companies.sqlite3'
            Store(path).import_json('[{"title":"Synthetic record"}]')
            vault=TestVault(); center=RecoveryCenter(path)
            engine=ProtectedBackups(path,center,vault)
            password='synthetic recovery passphrase'
            engine.unlock(password,initialize=True)
            engine.enroll_vault()
            engine.create()
            prior=engine.catalog.read_bytes()
            old=copy.deepcopy(vault.value['committed'])
            name=engine.create()
            with engine.connect() as c:
                entry=dict(c.execute('SELECT * FROM entries ORDER BY seq DESC LIMIT 1').fetchone())
            latest=copy.deepcopy(vault.value['committed'])
            engine.lock_session()
            engine.catalog.write_bytes(prior)
            vault.value.update(committed=old,pending=latest,prepared_entry=entry)
            reopened=ProtectedBackups(path,center,vault)
            reopened.start()
            try:
                self.assertTrue(reopened.snapshot()['unlocked'])
                self.assertEqual(vault.value['committed'],latest)
                self.assertIsNone(vault.value['pending'])
                self.assertEqual(reopened.snapshot()['archives'][-1]['archive'],name)
                self.assertTrue(reopened.verify_restore(name)['verified'])
            finally: reopened.close()

    @unittest.skipUnless(sys.platform.startswith('linux') and os.environ.get('CRAWLVORA_SECRET_SERVICE_TEST')=='1','Real Linux Secret Service session required')
    def test_real_secret_service_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault=NativeVault(Path(tmp)/'workspace')
            record={'password':'synthetic Secret Service passphrase','committed':{'count':0,'head':'0'*64},'pending':None}
            vault.save(record)
            self.assertEqual(vault.load()['password'],record['password'])
            other=NativeVault(Path(tmp)/'other-workspace')
            self.assertIsNone(other.load())


    def test_registry_namespace_preserves_existing_backup_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace=Path(tmp)/'workspace'
            backup=NativeVault(workspace)
            registry=NativeVault(workspace,purpose='registry')
            legacy=hashlib.sha256(os.fsencode(os.path.normcase(str(workspace.resolve())))).hexdigest()
            self.assertEqual(backup.identity,legacy)
            self.assertNotEqual(backup.identity,registry.identity)

    def registry_vault_roundtrip(self,workspace):
        backup=NativeVault(workspace)
        registry=NativeVault(workspace,purpose='registry')
        backup.save({'password':'synthetic backup value'})
        registry.save({'client_id':'synthetic-id','client_secret':'synthetic-value','authorized':True})
        reopened=NativeVault(workspace,purpose='registry')
        self.assertEqual(reopened.load()['client_secret'],'synthetic-value')
        self.assertEqual(backup.load()['password'],'synthetic backup value')
        reopened.save({'authorized':False})
        self.assertNotIn('client_secret',registry.load())
        self.assertEqual(backup.load()['password'],'synthetic backup value')

    @unittest.skipUnless(sys.platform=='win32','Windows DPAPI integration')
    def test_real_dpapi_registry_namespace(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'LOCALAPPDATA':tmp}):
            self.registry_vault_roundtrip(Path(tmp)/'workspace')

    @unittest.skipUnless(sys.platform.startswith('linux') and os.environ.get('CRAWLVORA_SECRET_SERVICE_TEST')=='1','Real Linux Secret Service session required')
    def test_real_secret_service_registry_namespace(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.registry_vault_roundtrip(Path(tmp)/'workspace')
