import json
import tempfile
import unittest
from pathlib import Path
from core import Store
from data_safety import RecoveryCenter
from workspace_selection import WorkspaceSelection

class WorkspaceSearchTests(unittest.TestCase):
    def test_selection_is_durable_without_replacing_original(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            store=Store(root/'companies.sqlite3')
            store.import_json('[{"title":"Original"}]')
            center=RecoveryCenter(root/'companies.sqlite3')
            identifier=center.restore(center.create())
            store.import_json('[{"title":"New record"}]')
            catalog=WorkspaceSelection(root)
            self.assertEqual(catalog.chosen(),'primary')
            catalog.choose(identifier)
            reopened=WorkspaceSelection(root)
            self.assertEqual(reopened.chosen(),identifier)
            self.assertEqual(Store(reopened.resolve(identifier)/'companies.sqlite3').stats()['total'],1)
            self.assertEqual(store.stats()['total'],2)
            with self.assertRaises(ValueError): reopened.choose('../anything')
            self.assertEqual(reopened.chosen(),identifier)
            reopened.choose('primary')
            self.assertEqual(reopened.resolve(reopened.chosen()),root)

    def test_fts_maintenance_and_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=Store(Path(tmp)/'db.sqlite')
            self.assertTrue(store.fts_available,'FTS5 required in supported distribution')
            store.import_json('[{"title":"Čelik Rijeka","mbs":"123"},{"title":"Other company"}]')
            self.assertEqual(store.query(q='fts:čelik')['total'],1)
            self.assertEqual(store.query(q='fts:celik')['total'],1)
            self.assertEqual(len(json.loads(store.export_json(q='fts:čelik'))),1)
            with store.db() as c:
                store.upsert(c,{'title':'New name','mbs':'123'},provider='registry')
            self.assertEqual(store.query(q='fts:čelik')['total'],0)
            self.assertEqual(store.query(q='fts:new name')['total'],1)
            self.assertEqual(store.query(q='fts:" OR *')['total'],0)
            with store.db() as c:
                c.execute("INSERT INTO company_fts(company_fts,rank) VALUES('integrity-check',1)")
