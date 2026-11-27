import io
import json
import tempfile
import unittest
from unittest.mock import patch
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

    def test_csv_roundtrip_keeps_entity_classification(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); original=Store(root/'original.db')
            original.import_json('[{"title":"Synthetic institution","entity_kind":"institution"}]')
            out=root/'out.csv'; export_file(original,out,'csv')
            restored=Store(root/'restored.db')
            self.assertEqual(import_file(restored,out,'csv')['read'],1)
            self.assertEqual(restored.query(entity_kind='institution')['total'],1)

    def test_insufficient_disk_rejected_before_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'upload'
            with patch('bulk_io.shutil.disk_usage',return_value=type('Usage',(),{'free':1})()):
                with self.assertRaisesRegex(ValueError,'Insufficient free disk'):
                    receive(io.BytesIO(b'a'),path,1)
            self.assertFalse(path.exists())

    def test_json_many_records_and_boundary_whitespace(self):
        count=50000
        raw='[ '+','.join('{"title":"Synthetic","index":'+str(i)+'}' for i in range(count))+' ]\r\n'
        self.assertEqual(sum(1 for _ in json_records(io.StringIO(raw))),count)
        with self.assertRaises(ValueError):
            list(json_records(io.StringIO('[{"title":"Synthetic"}, ]')))

    def test_interrupted_receive_removes_only_owned_staging(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); target=root/'upload'
            with self.assertRaises(ValueError):
                receive(io.BytesIO(b'a'),target,2)
            self.assertEqual(list(root.iterdir()),[])
            target.write_bytes(b'original')
            with self.assertRaises(FileExistsError):
                receive(io.BytesIO(b'new'),target,3)
            self.assertEqual(target.read_bytes(),b'original')
            self.assertEqual(list(root.iterdir()),[target])

    def test_export_failure_and_existing_destination(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); store=Store(root/'db')
            store.import_json('[{"title":"Synthetic"}]')
            target=root/'out.json'
            original=b'previous export'
            target.write_bytes(original)
            with self.assertRaises(FileExistsError):
                export_file(store,target,'json')
            self.assertEqual(target.read_bytes(),original)
            self.assertFalse(list(root.glob('.export-*')))
            new=root/'new.json'
            def interrupted(store,path,kind,**filters):
                Path(path).write_text('[',encoding='utf-8')
                raise OSError('injected interrupted export')
            with patch('bulk_io._write_export',side_effect=interrupted):
                with self.assertRaises(OSError):
                    export_file(store,new,'json')
            self.assertFalse(new.exists())
            self.assertFalse(list(root.glob('.export-*')))
            self.assertEqual(target.read_bytes(),original)
            self.assertEqual(store.stats()['total'],1)
