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

    def test_fts_rebuild_from_existing_records_and_rollback(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'db.sqlite'
            store=Store(path)
            store.import_json('[{"title":"Existing synthetic company","mbs":"123"}]')
            with store.db() as c:
                for trigger in ('company_fts_insert','company_fts_delete','company_fts_update'):
                    c.execute('DROP TRIGGER '+trigger)
                c.execute('DROP TABLE company_fts')
                c.execute("DELETE FROM meta WHERE key='fts_v1'")
            reopened=Store(path)
            self.assertEqual(reopened.query(q='fts:existing synthetic')['total'],1)
            with self.assertRaises(RuntimeError):
                with reopened.db() as c:
                    reopened.upsert(c,{'title':'Rollback name','mbs':'123'},provider='registry')
                    raise RuntimeError('Abort test transaction')
            self.assertEqual(reopened.query(q='fts:rollback')['total'],0)
            self.assertEqual(reopened.query(q='fts:existing synthetic')['total'],1)

    def test_actual_worker_restart_switches_without_modifying_original(self):
        import http.cookiejar
        import os
        import re
        import subprocess
        import sys
        import urllib.request
        from concurrent.futures import ThreadPoolExecutor
        from contextlib import contextmanager
        project=Path(__file__).resolve().parents[1]
        env={k:v for k,v in os.environ.items() if k not in ('SUDREG_CLIENT_ID','SUDREG_CLIENT_SECRET')}
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            store=Store(root/'companies.sqlite3')
            store.import_json('[{"title":"Original synthetic record"}]')
            with store.db() as c: c.execute("INSERT INTO meta(key,value) VALUES('seeded','1')")
            recovery=RecoveryCenter(root/'companies.sqlite3')
            recovered=recovery.restore(recovery.create())
            store.import_json('[{"title":"New synthetic record"}]')

            @contextmanager
            def worker():
                process=subprocess.Popen([sys.executable,str(project/'src/tvrtk_scraper.py'),'--worker','--port','0','--data-dir',str(root)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=env,cwd=root)
                try:
                    with ThreadPoolExecutor(max_workers=1) as pool:
                        future=pool.submit(process.stdout.readline)
                        try: line=future.result(timeout=60)
                        except TimeoutError: process.kill(); raise
                    self.assertTrue(line.startswith('CRAWLVORA_READY '))
                    url=line.strip().split(' ',1)[1]
                    base=url.split('/session/',1)[0]
                    opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
                    with opener.open(url,timeout=10) as r: html=r.read().decode()
                    token=re.search(r'name="local-token" content="([0-9a-f]+)"',html).group(1)
                    def request(path,data=None):
                        req=urllib.request.Request(base+path,data=None if data is None else json.dumps(data).encode(),headers={'X-Local-Token':token,'Content-Type':'application/json'})
                        with opener.open(req,timeout=20) as r: return json.load(r)
                    yield request
                    process.stdin.close()
                    self.assertEqual(process.wait(timeout=25),0)
                finally:
                    if process.poll() is None: process.kill(); process.wait()
                    for stream in (process.stdin,process.stdout,process.stderr):
                        if stream and not stream.closed: stream.close()

            with worker() as api:
                self.assertEqual(api('/api/stats')['total'],2)
                self.assertEqual(api('/api/recovery/select',{'id':recovered,'confirmed':True})['selected'],recovered)
                self.assertEqual(api('/api/recovery')['active'],'primary')
                self.assertEqual(api('/api/stats')['total'],2)
            with worker() as api:
                self.assertEqual(api('/api/recovery')['active'],recovered)
                self.assertEqual(api('/api/stats')['total'],1)
                api('/api/recovery/select',{'id':'primary','confirmed':True})
            with worker() as api:
                self.assertEqual(api('/api/recovery')['active'],'primary')
                self.assertEqual(api('/api/stats')['total'],2)
