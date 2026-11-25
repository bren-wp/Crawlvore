import io
import tempfile
import unittest
from pathlib import Path
from cryptography.exceptions import InvalidTag
from backup_transfer import BackupTransfer,receive,CHUNK
from core import Store
from data_safety import RecoveryCenter
from workspace_integrity import inspect_database,check_search_index

class StreamingRecoveryTests(unittest.TestCase):
    def test_bounded_reads_and_interrupted_upload(self):
        class Bounded(io.BytesIO):
            def read(self,n=-1):
                if not 0<n<=CHUNK: raise AssertionError('Unbounded read')
                return super().read(n)
        source=b'a'*(CHUNK+100)
        target=io.BytesIO()
        receive(Bounded(source),target,len(source))
        self.assertEqual(target.getvalue(),source)
        with self.assertRaises(ValueError):
            receive(Bounded(source),io.BytesIO(),len(source)+1)

    def test_download_one_use_and_recovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            path=root/'companies.sqlite3'
            store=Store(path)
            store.import_json('[{"title":"Original synthetic record"}]')
            center=RecoveryCenter(path)
            transfer=BackupTransfer(center)
            try:
                backup=center.create()
                password='synthetic test passphrase for recovery'
                ticket=transfer.prepare(backup,password)
                with self.assertRaises(ValueError):
                    with transfer.download('incorrect'): pass
                with transfer.download(ticket) as (archive,name):
                    self.assertTrue(name.endswith('.cvbackup'))
                    data=archive.read_bytes()
                with self.assertRaises(ValueError):
                    with transfer.download(ticket): pass
                with self.assertRaises(InvalidTag):
                    transfer.restore(io.BytesIO(data),len(data),'incorrect test passphrase')
                self.assertEqual(center.summary()['recovered'],[])
                with self.assertRaises(ValueError):
                    transfer.restore(io.BytesIO(data[:-1]),len(data),password)
                self.assertEqual(center.summary()['recovered'],[])
                store.import_json('[{"title":"New synthetic record"}]')
                identifier=transfer.restore(io.BytesIO(data),len(data),password)
                self.assertEqual(center.inspect(identifier)['total'],1)
                self.assertEqual(store.stats()['total'],2)
                self.assertEqual(inspect_database(center.recovered_path(identifier),True),'ok')
            finally: transfer.close()

    def test_fts_logical_rebuild_preserves_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=Store(Path(tmp)/'companies.sqlite3')
            store.import_json('[{"title":"Synthetic record"}]')
            self.assertEqual(check_search_index(store),'ok')
            with store.db() as c:
                row=c.execute('SELECT id,search_text FROM companies').fetchone()
                c.execute("INSERT INTO company_fts(company_fts,rowid,search_text) VALUES('delete',?,?)",tuple(row))
            self.assertEqual(check_search_index(store),'failed')
            self.assertEqual(check_search_index(store,repair=True),'rebuilt')
            self.assertEqual(store.query(q='fts:synthetic')['total'],1)
            self.assertEqual(store.stats()['total'],1)
            self.assertEqual(check_search_index(store),'ok')

    def test_invalid_database_is_not_repaired(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'broken.sqlite3'
            path.write_bytes(b'not a sqlite database')
            self.assertNotEqual(inspect_database(path),'ok')
            self.assertEqual(path.read_bytes(),b'not a sqlite database')
