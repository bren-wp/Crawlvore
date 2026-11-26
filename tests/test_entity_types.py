import json
import tempfile
import unittest
from pathlib import Path
from core import Store

class EntityTypeTests(unittest.TestCase):
    def test_classification_is_explicit_and_conflicts_rollback(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=Store(Path(tmp)/'test.db')
            records=[{'title':'Synthetic company','entity_kind':'company'},{'title':'Synthetic charity','entity_kind':'nonprofit'},{'title':'Synthetic unknown'}]
            store.import_json(json.dumps(records))
            self.assertEqual(store.query(entity_kind='company')['total'],1)
            self.assertEqual(store.query(entity_kind='nonprofit')['total'],1)
            self.assertEqual(store.query(entity_kind='unknown')['total'],1)
            self.assertEqual(store.query(q='Synthetic',entity_kind='company')['total'],1)
            with self.assertRaises(ValueError):
                store.import_json(json.dumps([{'title':'Synthetic company','entity_kind':'institution'}]))
            self.assertEqual(store.query(entity_kind='company')['total'],1)
            with self.assertRaises(ValueError):
                store.query(entity_kind='unknown SQL')
