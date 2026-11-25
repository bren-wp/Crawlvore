import csv
import io
import sqlite3
import tempfile
import unittest
from pathlib import Path
from core import Store, FIELDS
from data_safety import verified_backup, workspace_lock

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
                with sqlite3.connect(backup) as c:
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
