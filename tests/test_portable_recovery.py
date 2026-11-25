import json
import tempfile
import unittest
from pathlib import Path
from core import Store
from data_safety import RecoveryCenter
from protected_backups import ProtectedBackups
from portable_recovery import recover,verify_manifest

class PortableRecoveryTests(unittest.TestCase):
    def test_replacement_workspace_without_vault(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            original=root/'companies.sqlite3'
            store=Store(original)
            store.import_json('[{"title":"Original synthetic company","phone":"111"},{"title":"Original synthetic company","phone":"222"}]')
            engine=ProtectedBackups(original,RecoveryCenter(original))
            password='synthetic portable recovery passphrase'
            engine.unlock(password,initialize=True)
            name=engine.create()
            archive=engine.root/name
            manifest=root/'recovery.json'
            manifest.write_bytes(engine.portable_manifest(name))
            head=verify_manifest(manifest.read_bytes(),password)['catalog_head']
            engine.lock_session()
            target=recover(manifest,archive,root/'replacement-machine',password,head)
            self.assertEqual(Store(target).detail(1),store.detail(1))
            with self.assertRaises(ValueError): recover(manifest,archive,root/'wrong-head',password,'f'*64)
            with self.assertRaises(ValueError): recover(manifest,archive,root/'wrong-password','incorrect synthetic password')
            altered=json.loads(manifest.read_bytes())
            altered['manifest']['catalog_count']+=1
            manifest.write_text(json.dumps(altered))
            with self.assertRaises(ValueError): recover(manifest,archive,root/'modified',password)
            self.assertFalse((root/'modified').exists())
            self.assertTrue(archive.exists())
