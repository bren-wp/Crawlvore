import io, tempfile, unittest, csv
from pathlib import Path
from core import Store, FIELDS

class CoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.store=Store(Path(self.tmp.name)/'test.sqlite')
    def tearDown(self): self.tmp.cleanup()
    def test_import_export(self):
        stream=io.StringIO(); w=csv.writer(stream); w.writerow(FIELDS); row=['']*18; row[0]='Čelik'; row[6]='Zagreb'; row[8]='+385'; w.writerow(row); stream.seek(0)
        self.assertEqual(self.store.import_csv(stream),{'read':1,'added':1}); stream.seek(0); self.assertEqual(self.store.import_csv(stream)['added'],0)
        self.assertEqual(self.store.query(q='čelik',city='Zagreb')['total'],1); self.assertIn("'+385",self.store.export().decode('utf-8-sig'))
if __name__=='__main__': unittest.main()
