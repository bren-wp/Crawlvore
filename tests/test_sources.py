import tempfile, unittest, json
from pathlib import Path
from core import Store

class SourcesTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.store=Store(Path(self.tmp.name)/'db.sqlite')
    def tearDown(self): self.tmp.cleanup()
    def test_provenance_and_export(self):
        with self.store.db() as c:
            self.assertTrue(self.store.upsert(c,{'title':'Test','city':'Rijeka'},provider='companywall',origin='https://companywall.hr/api'))
            self.assertFalse(self.store.upsert(c,{'title':'Test','city':'Rijeka','email':'office@example.org'},provider='registry'))
        self.assertEqual(self.store.query(provider='registry')['total'],1)
        item=json.loads(self.store.export_json())[0]; self.assertEqual(len(item['sources']),2); self.assertEqual(item['email'],'office@example.org')
        self.assertIn('companywall',self.store.export().decode())
