import tempfile, unittest, sqlite3, json, datetime
from pathlib import Path
from unittest.mock import patch
from xml.etree import ElementTree
from openpyxl import load_workbook
from core import Store,Collector
from registry import Registry
from registry_export import export
from automation import Queue
from test_registry import Fake

class V6(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name); self.store=Store(self.root/'db'); self.bot=Collector(self.store); self.reg=Registry(self.store)
    def tearDown(self): self.tmp.cleanup()
    def test_history(self):
        with self.store.db() as c:
            self.store.upsert(c,{'title':'Original','mbs':'000000001'},provider='registry')
            self.store.upsert(c,{'title':'New','mbs':'000000001'},provider='registry')
            self.store.upsert(c,{'title':'New','mbs':'000000001'},provider='registry')
        history=self.store.history(1); self.assertEqual(len(history),1); self.assertEqual(history[0]['changes']['title'],{'before':'Original','after':'New'})
    def test_formats(self):
        self.reg.sync(self.bot,Fake(),1)
        with self.store.db() as c: c.execute('UPDATE registry_rows SET payload=? WHERE category=? AND ordinal=0',(json.dumps({'mbs':1,'text':'=1+1','x':"O'Reilly"}), 'subjekti'))
        for k in ('sql','xml','xlsx'): export(self.reg,'21','subjekti',k,self.root/('out.'+k))
        con=sqlite3.connect(':memory:'); con.executescript((self.root/'out.sql').read_text()); self.assertEqual(con.execute('select count(*) from registry_export').fetchone()[0],2); con.close()
        self.assertEqual(len(ElementTree.parse(self.root/'out.xml').getroot()),2)
        w=load_workbook(self.root/'out.xlsx'); sh=w.active; self.assertEqual(sh['A2'].value,'000000001'); self.assertEqual(sh['B2'].data_type,'s'); w.close()
    def test_queue(self):
        q=Queue(self.store,self.bot,self.reg,lambda:('',''))
        first=q.enqueue('registry',{'permission':True})['id']; second=q.enqueue('registry',{'permission':True})['id']; q.cancel(first)
        q.tick(); self.assertEqual([j['state'] for j in q.summary()['jobs']],['failed','cancelled'])
        with self.assertRaises(ValueError): q.enqueue('html',{'permission':True,'url':'https://example.org/?secret=x'})
        q.schedule(True,3); dt=datetime.datetime(2026,11,25,4); q.tick(dt); count=len(q.summary()['jobs']); q.tick(dt); self.assertEqual(len(q.summary()['jobs']),count)
        self.assertEqual(count,3)
    def test_queue_interruption(self):
        q=Queue(self.store,self.bot,self.reg,lambda:('',''))
        q.enqueue('registry',{'permission':True});
        with self.store.db() as c: c.execute("UPDATE jobs SET state='running'")
        q=Queue(self.store,self.bot,self.reg,lambda:('','')); self.assertEqual(q.summary()['jobs'][0]['state'],'interrupted')
