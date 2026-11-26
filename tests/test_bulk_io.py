import io
import json
import tempfile
import unittest
from pathlib import Path
from core import Store
from registry import Registry
from bulk_io import receive,json_records,import_file,export_file,company_registry,MAX_IMPORT

class BulkIOTests(unittest.TestCase):
    def test_receive_and_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'data'
            receive(io.BytesIO(b'abc'),p,3)
            self.assertEqual(p.read_bytes(),b'abc')
            with self.assertRaises(ValueError): receive(io.BytesIO(),Path(tmp)/'oversize',MAX_IMPORT+1)
            with self.assertRaises(ValueError): receive(io.BytesIO(b'a'),Path(tmp)/'short',2)

    def test_stream_json_and_rollback(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'data.json';store=Store(Path(tmp)/'db')
            p.write_text('[{"title":"Alpha","description":"'+('a'*1100000)+'"},{"title":"Beta"}]',encoding='utf-8')
            self.assertEqual(import_file(store,p,'json')['read'],2)
            p.write_text('[{"title":"Gamma"},]',encoding='utf-8')
            with self.assertRaises(ValueError): import_file(store,p,'json')
            self.assertEqual(store.stats()['total'],2)
            for text in ('[]x','[{}]','[{"title":"a"}','[{"title":"a"},]'):
                with self.assertRaises(ValueError): list(json_records(io.StringIO(text)))
            for kind in ('csv','json','xlsx'):
                out=Path(tmp)/('out.'+kind);export_file(store,out,kind)
                self.assertGreater(out.stat().st_size,0)
            self.assertEqual(len(json.loads((Path(tmp)/'out.json').read_text())),2)

    def test_related_registry_rows_are_paged_and_isolated(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=Store(Path(tmp)/'db');Registry(store)
            store.import_json('[{"title":"Alpha","mbs":"123456789"}]')
            with store.db() as db:
                i=db.execute('SELECT id FROM companies').fetchone()[0]
                db.execute("INSERT INTO registry_runs VALUES ('1','{}',0)")
                db.executemany("INSERT INTO registry_rows VALUES ('1','subjekti',?,?,?)",[(n,'123456789','{"test":true}') for n in range(27)])
                db.execute("INSERT INTO registry_rows VALUES ('1','subjekti',99,'999999999','{}')")
            self.assertEqual(len(company_registry(store,i)['rows']),25)
            self.assertEqual(len(company_registry(store,i,'1',25)['rows']),2)
            self.assertFalse(company_registry(store,i,'1',25)['next'])
