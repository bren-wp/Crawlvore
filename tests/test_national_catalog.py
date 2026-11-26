import gzip
import csv
import io
import zipfile
import hashlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from contextlib import closing
from national_catalog import NationalCatalog, GB_SOURCE

class NationalCatalogTests(unittest.TestCase):
    def test_isolated_packaged_search(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); package=root/'package/national-data/GB'; package.mkdir(parents=True)
            workspace=root/'workspace'; workspace.mkdir()
            original=workspace/'companies.sqlite3'; original.write_bytes(b'unchanged')
            database=root/'fixture.sqlite3'
            with closing(sqlite3.connect(database)) as db:
                db.execute('CREATE TABLE companies(name TEXT,registration_number TEXT,c06 TEXT,c10 TEXT,c11 TEXT,c14 TEXT)')
                db.execute('CREATE UNIQUE INDEX company_number ON companies(registration_number)')
                db.execute('CREATE INDEX company_name ON companies(name COLLATE NOCASE)')
                db.execute('CREATE TABLE metadata(key TEXT,value TEXT)')
                db.executemany('INSERT INTO metadata VALUES (?,?)',[(k,json.dumps(v)) for k,v in {'country':'GB','rows':2,'snapshot':'2026-11-01'}.items()])
                db.executemany('INSERT INTO companies VALUES (?,?,?,?,?,?)',[('Alpha Ltd','00000001','London','Ltd','Active','2020'),('Beta Ltd','SC000002','Edinburgh','Ltd','Active','2021')]);db.commit()
            data=database.read_bytes()
            report={'country':'GB','complete':True,'source':GB_SOURCE,'database_sha256':hashlib.sha256(data).hexdigest(),'database_bytes':len(data),'rows':2,'snapshot':'2026-11-01','columns':['CompanyName','CompanyNumber','City','Category','Status','Date']}
            (package/'manifest.json').write_text(json.dumps(report),encoding='utf-8')
            (package/'united-kingdom.sqlite3.gz').write_bytes(gzip.compress(data))
            catalog=NationalCatalog(root/'package',workspace)
            self.assertTrue(catalog.status()['GB']['available'])
            self.assertEqual(catalog.search('Al')['rows'][0]['name'],'Alpha Ltd')
            self.assertEqual(catalog.search('sc000002')['rows'][0]['name'],'Beta Ltd')
            self.assertEqual(catalog.search('%')['rows'],[])
            self.assertEqual(catalog.detail('00000001')['CompanyName'],'Alpha Ltd')
            self.assertEqual(original.read_bytes(),b'unchanged')
            self.assertEqual(set(catalog.status()),{'HR','GB'})
            with self.assertRaises(ValueError): catalog.detail('../secret')

    def test_downloaded_onefile_catalog_is_isolated(self):
        from tools.import_companies_house import build
        from tools.prepare_national_bundle import prepare
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);workspace=root/'workspace';workspace.mkdir()
            original=workspace/'companies.sqlite3';original.write_bytes(b'unchanged')
            name='BasicCompanyDataAsOneFile-2026-11-01'
            archive=root/(name+'.zip')
            stream=io.StringIO(newline='')
            writer=csv.writer(stream)
            writer.writerow(['CompanyName','CompanyNumber']+[f'Field{i}' for i in range(2,55)])
            writer.writerow(['Synthetic UK Ltd','AB123456']+['']*53)
            with zipfile.ZipFile(archive,'w') as z:
                z.writestr(name+'.csv',stream.getvalue())
            report=build([archive],root/'database')
            self.assertEqual(report['rows'],1)
            catalog=NationalCatalog(root/'package',workspace)
            self.assertFalse(catalog.status()['GB']['available'])
            prepare(root/'database',catalog.downloaded)
            self.assertTrue(catalog.status()['GB']['available'])
            self.assertEqual(catalog.search('AB123456')['rows'][0]['name'],'Synthetic UK Ltd')
            self.assertEqual(len(catalog.detail('AB123456')),55)
            self.assertEqual(original.read_bytes(),b'unchanged')
