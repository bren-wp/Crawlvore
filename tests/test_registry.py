import tempfile, unittest
from pathlib import Path
from core import Store, Collector
from registry import Registry, catalog, rows_of, normalized_id

def spec():
    def p(n): return {'in':'query','name':n,'required':False}
    return {'paths':{'/subjekti':{'get':{'parameters':[p('snapshot_id'),p('offset'),p('limit')]}},'/sjedista':{'get':{'parameters':[p('snapshot_id')]}},'/detalji_subjekta':{'get':{'parameters':[p('snapshot_id')]}},'/v1/legacy':{'get':{'parameters':[p('snapshot_id')]}}}}
class Fake:
    def __init__(self,bad=False): self.bad=bad; self.calls=[]
    def spec(self): return spec()
    def get(self,name,q=None):
        self.calls.append((name,q))
        if name=='snapshots': return {},[{'id':21,'staleness':1}]
        h={'X-Snapshot-Id':'22' if self.bad else '21'}
        if name=='subjekti':
            h.update({'X-Total-Count':'2','X-Rows-Returned':'1'}); off=q['offset']; return h,[{'mbs':off+1,'tvrtka_naziv':'Test '+str(off)}]
        return h,[{'mbs':1,'naziv':'Zagreb'}]
class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.store=Store(Path(self.tmp.name)/'test.db'); self.bot=Collector(self.store); self.reg=Registry(self.store)
    def tearDown(self): self.tmp.cleanup()
    def test_catalog(self): self.assertEqual(list(catalog(spec())),['subjekti','sjedista']); self.assertEqual(normalized_id(123,9),'000000123')
    def test_mirror(self):
        f=Fake(); self.reg.sync(self.bot,f,1); self.assertEqual(self.reg.browse('21','subjekti')['total'],2); self.assertEqual(self.store.stats()['total'],2); self.assertEqual(self.reg.summary()['runs'][0]['complete'],1)
        self.reg.sync(self.bot,f,1); self.assertEqual(self.reg.browse('21','subjekti')['total'],2)
    def test_mismatch(self):
        with self.assertRaises(ValueError): self.reg.sync(self.bot,Fake(True),1)
        self.assertEqual(self.reg.browse('21','subjekti')['total'],0)
    def test_resume(self):
        class Fail(Fake):
            def get(self,name,q=None):
                if name=='subjekti' and q['offset']==1: raise ValueError('interrupt')
                return super().get(name,q)
        with self.assertRaises(ValueError): self.reg.sync(self.bot,Fail(),1)
        f=Fake(); self.reg.sync(self.bot,f,1); self.assertNotIn(('subjekti',{'snapshot_id':'21','offset':0,'limit':1}),f.calls); self.assertEqual(self.reg.browse('21','subjekti')['total'],2)
    def test_shape(self):
        self.assertEqual(rows_of({'items':[{'a':1}]}),[{'a':1}]); self.assertRaises(ValueError,rows_of,{'a':[],'b':[]})

class UpgradeTests(unittest.TestCase):
    setUp=RegistryTests.setUp
    tearDown=RegistryTests.tearDown
    def test_new_snapshot_refreshes_official_fields(self):
        self.reg.sync(self.bot,Fake(),1)
        class New(Fake):
            def get(self,name,q=None):
                if name=='snapshots': return {},[{'id':22,'staleness':1}]
                h,b=super().get(name,q); h['X-Snapshot-Id']='22'
                if name=='subjekti': b[0]['tvrtka_naziv']='Updated '+str(q['offset'])
                return h,b
        self.reg.sync(self.bot,New(),1)
        self.assertEqual(self.store.stats()['total'],2)
        self.assertEqual(self.store.query(q='Updated')['total'],2)
    def test_csv_and_search(self):
        self.reg.sync(self.bot,Fake(),1)
        self.assertEqual(self.reg.browse('21','subjekti',q='000000001')['total'],1)
        text=b''.join(self.reg.export_csv('21','subjekti')).decode('utf-8-sig')
        self.assertIn('000000001',text); self.assertIn('tvrtka_naziv',text)
    def test_resume_previous_available_snapshot(self):
        class Fail(Fake):
            def get(self,name,q=None):
                if name=='subjekti' and q['offset']==1: raise ValueError('interrupt')
                return super().get(name,q)
        with self.assertRaises(ValueError): self.reg.sync(self.bot,Fail(),1)
        class New(Fake):
            def get(self,name,q=None):
                if name=='snapshots': return {},[{'id':22,'staleness':1},{'id':21,'staleness':2}]
                return super().get(name,q)
        self.reg.sync(self.bot,New(),1)
        self.assertEqual(self.reg.summary()['runs'],[{'snapshot':'21','complete':1}])
