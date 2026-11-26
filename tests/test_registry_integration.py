import json
import sqlite3
from contextlib import closing
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core import Collector, Store
from registry import Registry
from registry_bundle import verify_bundle
from registry_integration import integrate_snapshot
from test_registry_bundle import AllStatus


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root=Path(self.tmp.name)
        self.source=root/'seed.sqlite3'
        seed=Store(self.source)
        Registry(seed).sync(Collector(seed),AllStatus(),1)
        # Match the production bundle builder: flush and close WAL before hashing.
        with closing(sqlite3.connect(self.source)) as db:
            self.assertEqual(db.execute('PRAGMA wal_checkpoint(TRUNCATE)').fetchone()[0],0)
            self.assertEqual(db.execute('PRAGMA journal_mode=DELETE').fetchone()[0],'delete')
        self.manifest=root/'manifest.json'
        self.manifest.write_text(json.dumps(verify_bundle(self.source,min_categories=2)),encoding='utf-8')
        self.target=Store(root/'workspace.sqlite3')
        self.registry=Registry(self.target)
        self.target.import_json('[{"title":"Private original","phone":"123"}]')

    def integrate(self):
        return integrate_snapshot(self.target,self.registry,self.source,self.manifest,min_categories=2)

    def test_import_and_repeat_preserve_original(self):
        with self.target.db() as db:
            original=tuple(db.execute("SELECT id,title,phone FROM companies WHERE title='Private original'").fetchone())
        report=self.integrate()
        self.assertTrue(report['imported'])
        self.assertFalse(self.integrate()['imported'])
        with self.target.db() as db:
            self.assertEqual(tuple(db.execute("SELECT id,title,phone FROM companies WHERE title='Private original'").fetchone()),original)
            self.assertEqual(db.execute('SELECT count(*) FROM companies').fetchone()[0],3)
            self.assertEqual(db.execute('SELECT complete FROM registry_runs').fetchone()[0],1)

    def test_projection_failure_rolls_back(self):
        def fail_after_projection(snap,bot,connection=None):
            original_merge(snap,bot,connection=connection)
            self.assertEqual(connection.execute('SELECT count(*) FROM companies').fetchone()[0],3)
            raise ValueError('synthetic failure after projection')

        original_merge=self.registry.merge
        with patch.object(self.registry,'merge',side_effect=fail_after_projection):
            with self.assertRaisesRegex(ValueError,'after projection'):
                self.integrate()
        with self.target.db() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM companies').fetchone()[0],1)
            self.assertEqual(db.execute('SELECT count(*) FROM registry_runs').fetchone()[0],0)
            self.assertEqual(db.execute('SELECT count(*) FROM registry_rows').fetchone()[0],0)

    def test_manifest_mismatch_is_rejected(self):
        self.manifest.write_text('{}',encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'manifest'):
            self.integrate()
        with self.target.db() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM companies').fetchone()[0],1)

    def test_partial_snapshot_is_replaced(self):
        with closing(sqlite3.connect(self.source.as_uri()+'?mode=ro',uri=True)) as src:
            run=tuple(src.execute('SELECT snapshot,manifest FROM registry_runs').fetchone())
            row=tuple(src.execute("SELECT * FROM registry_rows WHERE category='subjekti' ORDER BY ordinal LIMIT 1").fetchone())
        with self.target.db() as db:
            db.execute('INSERT INTO registry_runs(snapshot,manifest,complete) VALUES (?,?,0)',run)
            db.execute('INSERT INTO registry_rows VALUES (?,?,?,?,?)',row)
        self.assertTrue(self.integrate()['imported'])
        with self.target.db() as db:
            self.assertEqual(db.execute('SELECT complete FROM registry_runs').fetchone()[0],1)
            self.assertEqual(db.execute('SELECT count(*) FROM companies').fetchone()[0],3)

    def test_conflicting_partial_snapshot_is_preserved(self):
        with closing(sqlite3.connect(self.source.as_uri()+'?mode=ro',uri=True)) as src:
            run=tuple(src.execute('SELECT snapshot,manifest FROM registry_runs').fetchone())
            row=list(src.execute("SELECT * FROM registry_rows WHERE category='subjekti' ORDER BY ordinal LIMIT 1").fetchone())
        row[-1]='{}'
        with self.target.db() as db:
            db.execute('INSERT INTO registry_runs(snapshot,manifest,complete) VALUES (?,?,0)',run)
            db.execute('INSERT INTO registry_rows VALUES (?,?,?,?,?)',row)
        with self.assertRaisesRegex(ValueError,'conflict'):
            self.integrate()
        with self.target.db() as db:
            self.assertEqual(db.execute('SELECT payload FROM registry_rows').fetchone()[0],'{}')
            self.assertEqual(db.execute('SELECT complete FROM registry_runs').fetchone()[0],0)

    def test_unfinalized_bundle_is_rejected(self):
        with closing(sqlite3.connect(self.source)) as db:
            self.assertEqual(db.execute('PRAGMA journal_mode=WAL').fetchone()[0],'wal')
            db.execute('BEGIN IMMEDIATE')
            db.execute('UPDATE registry_runs SET complete=0')
            db.commit()
            with self.assertRaisesRegex(ValueError,'finalized and closed'):
                self.integrate()
        with self.target.db() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM companies').fetchone()[0],1)
            self.assertEqual(db.execute('SELECT count(*) FROM registry_runs').fetchone()[0],0)
