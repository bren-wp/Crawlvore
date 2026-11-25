import csv
from contextlib import closing
import io
import sqlite3
import tempfile
import unittest
from pathlib import Path
from core import Store, FIELDS
from data_safety import verified_backup, workspace_lock, restore_workspace

class DataSafetyTests(unittest.TestCase):
    def test_online_backup_contains_committed_wal_and_preserves_old_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'companies.sqlite3'
            store=Store(path)
            with store.db() as connection:
                store.upsert(connection,{'title':'Original','phone':'111'})
                connection.commit()
                first=verified_backup(path)
                store.upsert(connection,{'title':'Second','phone':'222'})
                connection.commit()
                second=verified_backup(path)
            self.assertNotEqual(first,second)
            for backup,count in ((first,1),(second,2)):
                with closing(sqlite3.connect(backup)) as c:
                    self.assertEqual(c.execute('SELECT count(*) FROM companies').fetchone()[0],count)
                    self.assertEqual(c.execute('PRAGMA integrity_check').fetchone()[0],'ok')

    def test_exclusive_workspace_and_release(self):
        with tempfile.TemporaryDirectory() as tmp:
            with workspace_lock(tmp):
                with self.assertRaises(RuntimeError):
                    with workspace_lock(tmp): self.fail('Second lock unexpectedly acquired')
            with workspace_lock(tmp): pass

    def test_seed_is_atomic_on_malformed_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'seed.csv'
            stream=io.StringIO(newline='')
            writer=csv.writer(stream)
            writer.writerow(FIELDS)
            writer.writerow(['First']+['']*(len(FIELDS)-1))
            writer.writerow(['Malformed'])
            path.write_text(stream.getvalue(),encoding='utf-8')
            store=Store(Path(tmp)/'db.sqlite')
            with self.assertRaises(ValueError): store.seed(path)
            self.assertEqual(store.stats()['total'],0)
            with store.db() as c:
                self.assertIsNone(c.execute("SELECT value FROM meta WHERE key='seeded'").fetchone())

    def test_conflicting_contacts_are_retained_idempotently(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=Store(Path(tmp)/'db.sqlite')
            with store.db() as c:
                store.upsert(c,{'title':'Example','city':'Rijeka','phone':'111'})
                for _ in range(3):
                    store.upsert(c,{'title':'Example','city':'Rijeka','phone':'222'})
                self.assertEqual(c.execute('SELECT phone FROM companies').fetchone()[0],'111')
                self.assertEqual([tuple(r) for r in c.execute('SELECT field,value FROM alternate_values')],[('phone','222')])
            self.assertEqual(store.stats()['total'],1)

    def test_alternatives_in_profile_and_filtered_json(self):
        import json
        with tempfile.TemporaryDirectory() as tmp:
            store=Store(Path(tmp)/'db.sqlite')
            with store.db() as c:
                store.upsert(c,{'title':'Example','city':'Rijeka','phone':'111'})
                store.upsert(c,{'title':'Example','city':'Rijeka','phone':'222'})
                store.upsert(c,{'title':'Other','city':'Split','phone':'333'})
            detail=store.detail(1)
            self.assertEqual(detail['alternate_values'][0]['value'],'222')
            self.assertEqual(detail['phone'],'111')
            exported=json.loads(store.export_json(city='Rijeka'))
            self.assertEqual(len(exported),1)
            self.assertEqual(exported[0]['alternate_values'],detail['alternate_values'])
            self.assertEqual(exported[0]['sources'],detail['sources'])
            self.assertEqual(json.loads(store.export_json(city='Missing')),[])

    def test_restore_is_non_destructive_and_preserves_metadata(self):
        import hashlib
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            original=root/'companies.sqlite3'
            store=Store(original)
            store.import_json('[{"title":"Recovery example","phone":"111"},{"title":"Recovery example","phone":"222"}]')
            backup=verified_backup(original)
            before=hashlib.sha256(backup.read_bytes()).hexdigest()
            target=restore_workspace(backup,root/'recovered')
            restored=Store(target)
            self.assertEqual(restored.detail(1),store.detail(1))
            with self.assertRaises(FileExistsError):
                restore_workspace(backup,root/'recovered')
            self.assertEqual(hashlib.sha256(backup.read_bytes()).hexdigest(),before)
            self.assertEqual(store.stats()['total'],1)

    def test_invalid_backup_never_creates_recovered_workspace(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            bad=root/'unrelated.sqlite3'
            with closing(sqlite3.connect(bad)) as c:
                c.execute('CREATE TABLE unrelated (id INTEGER)')
                c.commit()
            with self.assertRaises(ValueError): restore_workspace(bad,root/'recovered')
            self.assertFalse((root/'recovered').exists())

    def test_abrupt_process_exit_preserves_only_committed_transactions(self):
        import subprocess
        import sys
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            path=root/'companies.sqlite3'
            store=Store(path)
            script="""import os,sys
from core import Store
from data_safety import workspace_lock
from pathlib import Path
path=Path(sys.argv[1])
with workspace_lock(path.parent):
    store=Store(path)
    with store.db() as c:
        store.upsert(c,{'title':'Committed company','phone':'111'})
        c.commit()
        store.upsert(c,{'title':'Uncommitted company','phone':'222'})
        os._exit(23)
"""
            result=subprocess.run([sys.executable,'-c',script,str(path)],cwd=Path(__file__).resolve().parents[1],timeout=30,check=False)
            self.assertEqual(result.returncode,23)
            with workspace_lock(root):
                backup=verified_backup(path)
                recovered=Store(restore_workspace(backup,root/'recovered'))
                self.assertEqual(recovered.stats()['total'],1)
                self.assertEqual(recovered.detail(1)['title'],'Committed company')
                self.assertEqual(store.query(q='Uncommitted company')['total'],0)
                with store.db() as c:
                    self.assertEqual(c.execute('PRAGMA integrity_check').fetchone()[0],'ok')

    def test_recovery_center_rejects_paths_and_preserves_active_data(self):
        from data_safety import RecoveryCenter
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            store=Store(root/'companies.sqlite3')
            store.import_json('[{"title":"Original"}]')
            center=RecoveryCenter(root/'companies.sqlite3')
            identifier=center.create()
            self.assertEqual(center.summary()['backups'][0]['id'],identifier)
            for invalid in ('../companies.sqlite3','/etc/passwd','companies-invalid.sqlite3'):
                with self.assertRaises(ValueError): center.backup_path(invalid)
            store.import_json('[{"title":"New company"}]')
            recovered=center.restore(identifier)
            self.assertEqual(center.inspect(recovered)['total'],1)
            self.assertEqual(store.stats()['total'],2)
            self.assertEqual(center.summary()['recovered'][0]['id'],recovered)
            with self.assertRaises(ValueError): center.inspect('../companies.sqlite3')

    def test_exact_mbs_search_and_export_preserve_text_search(self):
        import json
        with tempfile.TemporaryDirectory() as tmp:
            store=Store(Path(tmp)/'companies.sqlite3')
            store.import_json('[{"title":"Example company","mbs":"123"},{"title":"Other company","mbs":"1234"}]')
            self.assertEqual(store.query(q='company')['total'],2)
            self.assertEqual(store.query(q='mbs:123')['total'],1)
            self.assertEqual(store.query(q='mbs:000000123')['rows'][0]['title'],'Example company')
            self.assertEqual(len(json.loads(store.export_json(q='mbs:123'))),1)
