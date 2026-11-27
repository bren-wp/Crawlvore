import gzip
import hashlib
import json
import sqlite3
from contextlib import closing
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from registry_seed import accept_packaged_seed, accept_preview_seed, install_seed


class SeedTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.source=self.root/'registry-seed.sqlite3'
        self.source.write_bytes(b'synthetic test data')
        self.check=self.root/'registry-seed.sha256'
        self.check.write_text(hashlib.sha256(self.source.read_bytes()).hexdigest(),encoding='ascii')
        self.dest=self.root/'companies.sqlite3'

    def test_fresh_seed(self):
        self.assertTrue(install_seed(self.root,self.dest))
        self.assertEqual(self.dest.read_bytes(),self.source.read_bytes())

    def test_insufficient_space_preserves_seed(self):
        from collections import namedtuple
        usage=namedtuple('Usage','total used free')
        with patch('registry_seed.shutil.disk_usage',return_value=usage(100,100,0)):
            with self.assertRaisesRegex(ValueError,'Insufficient free disk space'):
                install_seed(self.root,self.dest)
        self.assertFalse(self.dest.exists())
        self.assertEqual(self.source.read_bytes(),b'synthetic test data')

    def test_compressed_seed_is_bounded_and_verified(self):
        raw=self.source.read_bytes()
        (self.root/'registry-seed.sqlite3.gz').write_bytes(gzip.compress(raw))
        self.source.unlink()
        size=self.root/'registry-seed.size'
        size.write_text(str(len(raw)),encoding='ascii')
        self.assertTrue(install_seed(self.root,self.dest))
        self.assertEqual(self.dest.read_bytes(),raw)
        self.dest.unlink()
        size.write_text(str(len(raw)-1),encoding='ascii')
        with self.assertRaisesRegex(ValueError,'size mismatch'):
            install_seed(self.root,self.dest)
        self.assertFalse(self.dest.exists())

    def test_existing_workspace_preserved(self):
        self.dest.write_bytes(b'existing user database')
        self.assertFalse(install_seed(self.root,self.dest))
        self.assertEqual(self.dest.read_bytes(),b'existing user database')

    def test_corrupted_seed_rejected(self):
        self.source.write_bytes(b'changed')
        with self.assertRaises(ValueError):
            install_seed(self.root,self.dest)
        self.assertFalse(self.dest.exists())

    def test_packaged_snapshot_acceptance(self):
        self.source.unlink()
        with closing(sqlite3.connect(self.source)) as db:
            db.execute('CREATE TABLE registry_runs(snapshot TEXT,complete INTEGER)')
            db.execute('CREATE TABLE registry_progress(snapshot TEXT,category TEXT,total INTEGER,done INTEGER,next_offset INTEGER)')
            db.execute("INSERT INTO registry_runs VALUES ('1',1)")
            categories={'subjekti':2,**{'category_'+str(i):0 for i in range(35)}}
            db.executemany('INSERT INTO registry_progress VALUES (?,?,?,?,?)',[('1',name,total,1,total) for name,total in categories.items()])
            db.commit()
        digest=hashlib.sha256(self.source.read_bytes()).hexdigest()
        self.check.write_text(digest,encoding='ascii')
        manifest={'snapshot':'1','scope':'all-status','subjects':2,'category_count':36,'categories':categories,'rows':2,'database_sha256':digest}
        (self.root/'registry-seed.json').write_text(json.dumps(manifest),encoding='utf-8')
        self.assertTrue(install_seed(self.root,self.dest))
        self.assertEqual(accept_packaged_seed(self.root,self.dest,True,digest),manifest)
        with self.assertRaisesRegex(ValueError,'not installed'):
            accept_packaged_seed(self.root,self.dest,False,digest)
        with self.assertRaisesRegex(ValueError,'SHA-256'):
            accept_packaged_seed(self.root,self.dest,True,'0'*64)
        with closing(sqlite3.connect(self.dest)) as db:
            db.execute("UPDATE registry_progress SET done=0 WHERE category='subjekti'")
            db.commit()
        with self.assertRaisesRegex(ValueError,'categories'):
            accept_packaged_seed(self.root,self.dest,True,digest)

    def test_partial_acceptance_is_separate(self):
        self.source.unlink()
        with closing(sqlite3.connect(self.source)) as db:
            db.execute('CREATE TABLE registry_runs(snapshot TEXT,complete INTEGER)')
            db.execute('CREATE TABLE registry_progress(snapshot TEXT,category TEXT,total INTEGER,done INTEGER,next_offset INTEGER)')
            db.execute('CREATE TABLE registry_rows(payload TEXT)')
            db.execute('CREATE TABLE companies(title TEXT)')
            db.execute("INSERT INTO registry_runs VALUES ('1',0)")
            db.execute("INSERT INTO registry_progress VALUES ('1','subjekti',2,0,1)")
            db.execute("INSERT INTO registry_rows VALUES ('{}')")
            db.commit()
        digest=hashlib.sha256(self.source.read_bytes()).hexdigest()
        self.check.write_text(digest,encoding='ascii')
        manifest={'snapshot':'1','complete':False,'scope':'all-status','database_sha256':digest,'progress':{'subjekti':{'rows':1,'done':False,'total':2}},'rows':1,'directory_companies':0}
        (self.root/'registry-seed.json').write_text(json.dumps(manifest),encoding='utf-8')
        self.assertTrue(install_seed(self.root,self.dest))
        self.assertEqual(accept_preview_seed(self.root,self.dest,True,digest),manifest)
        with self.assertRaises(ValueError):
            accept_packaged_seed(self.root,self.dest,True,digest)
