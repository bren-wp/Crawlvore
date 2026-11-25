import tempfile
import unittest
from pathlib import Path
from core import Store
from registry import Registry

class SQLSafetyTests(unittest.TestCase):
    def test_filters_and_sort_are_bound(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=Store(Path(tmp)/'test.sqlite3')
            with store.db() as db:
                store.upsert(db,{'title':'Example Ltd','city':'Zagreb'},provider='csv')
            attack="x' OR 1=1; DROP TABLE companies; --"
            for name in ('q','city','provider'):
                self.assertEqual(store.query(**{name:attack})['total'],0)
                self.assertEqual(len(store.export(**{name:attack}).decode('utf-8-sig').splitlines()),1)
                self.assertEqual(store.export_json(**{name:attack}).decode().strip(),'[]')
            self.assertEqual(store.query(sort=attack)['total'],1)
            self.assertEqual(store.stats()['total'],1)
            registry=Registry(store)
            self.assertEqual(registry.browse('1','subjekti',q=attack)['total'],0)
