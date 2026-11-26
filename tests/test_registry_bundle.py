import json
import tempfile
import unittest
from pathlib import Path
from core import Collector, Store
from registry import Registry
from registry_bundle import verify_bundle
from test_registry import Fake, spec


class AllStatus(Fake):
    def spec(self):
        result=spec()
        result['paths']['/subjekti']['get']['parameters'].append({'in':'query','name':'only_active'})
        return result


class BundleTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'seed.sqlite3'
        self.store=Store(self.path)
        Registry(self.store).sync(Collector(self.store),AllStatus(),1)

    def test_valid_bundle(self):
        report=verify_bundle(self.path,min_categories=2)
        self.assertEqual(report['subjects'],2)
        self.assertEqual(report['scope'],'all-status')
        self.assertEqual(report['category_count'],2)
        self.assertRegex(report['database_sha256'],r'^[0-9a-f]{64}

    def test_partial_bundle(self):
        with self.store.db() as db:
            db.execute('UPDATE registry_runs SET complete=0')
        with self.assertRaises(ValueError):
            verify_bundle(self.path,min_categories=2)

    def test_corrupt_payload(self):
        with self.store.db() as db:
            db.execute("UPDATE registry_rows SET payload=? WHERE category='subjekti' AND ordinal=0",(json.dumps({'mbs':1}),))
        with self.assertRaises(ValueError):
            verify_bundle(self.path,min_categories=2)

    def test_non_registry_company(self):
        self.store.import_json('[{"title":"Synthetic private contact"}]')
        with self.assertRaises(ValueError):
            verify_bundle(self.path,min_categories=2)

    def test_missing_directory_subject(self):
        with self.store.db() as db:
            db.execute("UPDATE companies SET mbs='' WHERE mbs='000000001'")
        with self.assertRaises(ValueError):
            verify_bundle(self.path,min_categories=2)
)

    def test_unexpected_category(self):
        with self.store.db() as db:
            snapshot=db.execute('SELECT snapshot FROM registry_runs').fetchone()[0]
            db.execute('INSERT INTO registry_rows VALUES (?,?,?,?,?)',(snapshot,'unlisted',0,'','{}'))
        with self.assertRaisesRegex(ValueError,'Unexpected registry category'):
            verify_bundle(self.path,min_categories=2)

    def test_mixed_snapshot_progress(self):
        with self.store.db() as db:
            db.execute("INSERT INTO registry_progress VALUES ('999999','subjekti',0,1,0)")
        with self.assertRaisesRegex(ValueError,'Mixed snapshot data'):
            verify_bundle(self.path,min_categories=2)

    def test_partial_bundle(self):
        with self.store.db() as db:
            db.execute('UPDATE registry_runs SET complete=0')
        with self.assertRaises(ValueError):
            verify_bundle(self.path,min_categories=2)

    def test_corrupt_payload(self):
        with self.store.db() as db:
            db.execute("UPDATE registry_rows SET payload=? WHERE category='subjekti' AND ordinal=0",(json.dumps({'mbs':1}),))
        with self.assertRaises(ValueError):
            verify_bundle(self.path,min_categories=2)

    def test_non_registry_company(self):
        self.store.import_json('[{"title":"Synthetic private contact"}]')
        with self.assertRaises(ValueError):
            verify_bundle(self.path,min_categories=2)

    def test_missing_directory_subject(self):
        with self.store.db() as db:
            db.execute("UPDATE companies SET mbs='' WHERE mbs='000000001'")
        with self.assertRaises(ValueError):
            verify_bundle(self.path,min_categories=2)
