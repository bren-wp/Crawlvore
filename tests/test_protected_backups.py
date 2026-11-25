import shutil
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from core import Store
from data_safety import RecoveryCenter
from protected_backups import ProtectedBackups

class ProtectedBackupTests(unittest.TestCase):
    def test_authenticated_catalog_and_recovery_after_reopen(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'companies.sqlite3'
            store=Store(path)
            store.import_json('[{"title":"Original synthetic record"}]')
            recovery=RecoveryCenter(path)
            password='synthetic catalog passphrase for test'
            catalog=ProtectedBackups(path,recovery)
            catalog.unlock(password,initialize=True)
            name=catalog.create()
            catalog.lock_session()
            store.import_json('[{"title":"New synthetic record"}]')
            reopened=ProtectedBackups(path,recovery)
            with self.assertRaises(ValueError): reopened.unlock('incorrect synthetic passphrase')
            self.assertFalse(reopened.snapshot()['unlocked'])
            self.assertEqual(reopened.unlock(password)['archives'][0]['status'],'ok')
            recovered=reopened.restore(name)
            self.assertEqual(recovery.inspect(recovered)['total'],1)
            self.assertEqual(store.stats()['total'],2)
            # Simulate the durable archive/catalog commit gap: keep the orphan.
            orphan=reopened.root/('protected-'+'a'*32+'.cvbackup')
            shutil.copyfile(reopened.root/name,orphan)
            state=reopened.verify()
            self.assertIn(orphan.name,state['orphans'])
            self.assertEqual(state['status'],'attention')
            self.assertTrue(orphan.exists())
            # Alter an authenticated entry; do not accept a new catalog or erase the archive.
            with closing(sqlite3.connect(reopened.catalog)) as c:
                c.execute('UPDATE entries SET bytes=bytes+1')
                c.commit()
            with self.assertRaises(ValueError): reopened.verify()
            reopened.lock_session()
            with self.assertRaises(ValueError): reopened.unlock(password)
            self.assertTrue((reopened.root/name).exists())

    def test_ciphertext_modification_and_missing_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'companies.sqlite3'
            Store(path).import_json('[{"title":"Synthetic data"}]')
            engine=ProtectedBackups(path,RecoveryCenter(path))
            engine.unlock('synthetic catalog passphrase for test',initialize=True)
            identifier=engine.create()
            archive=engine.root/identifier
            with archive.open('r+b') as stream:
                stream.seek(-1,2)
                last=stream.read(1)
                stream.seek(-1,2)
                stream.write(bytes([last[0]^1]))
            self.assertEqual(engine.verify()['archives'][0]['status'],'failed')
            with self.assertRaises(ValueError): engine.restore(identifier)
            archive.rename(archive.with_suffix('.preserved'))
            self.assertEqual(engine.verify()['archives'][0]['status'],'unavailable')
            self.assertTrue(archive.with_suffix('.preserved').exists())
