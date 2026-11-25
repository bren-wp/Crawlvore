import json, os, tempfile, unittest
from unittest.mock import patch
from native_vault import VaultUnavailable
from pathlib import Path
from core import Store, Collector
from registry import Registry, catalog, rows_of, normalized_id, credentials, configured, RegistryAccess

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


class CredentialSourceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/'root'
        self.data=Path(self.tmp.name)/'data'
        self.cwd=Path(self.tmp.name)/'cwd'
        for directory in (self.root,self.data,self.cwd):
            directory.mkdir()
        self.environment=patch.dict(os.environ,{},clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def write_pair(self,directory,client_id='file-id',client_secret='file-secret'):
        (directory/'sudreg.private.json').write_text(json.dumps({
            'client_id':client_id,'client_secret':client_secret}),encoding='utf-8')

    def test_partial_environment_never_borrows_file_secret(self):
        self.write_pair(self.data)
        with patch.dict(os.environ,{'SUDREG_CLIENT_ID':'env-id'}):
            self.assertEqual(credentials(self.root,self.data),('env-id',''))
            self.assertFalse(configured(self.root,self.data))

    def test_complete_environment_overrides_file_as_pair(self):
        self.write_pair(self.data)
        with patch.dict(os.environ,{'SUDREG_CLIENT_ID':'env-id','SUDREG_CLIENT_SECRET':'env-secret'}):
            self.assertEqual(credentials(self.root,self.data),('env-id','env-secret'))
            self.assertTrue(configured(self.root,self.data))

    def test_explicit_empty_environment_does_not_fall_back(self):
        self.write_pair(self.data)
        with patch.dict(os.environ,{'SUDREG_CLIENT_ID':'','SUDREG_CLIENT_SECRET':''}):
            self.assertEqual(credentials(self.root,self.data),('',''))
            self.assertFalse(configured(self.root,self.data))

    def test_arbitrary_working_directory_is_not_a_credential_source(self):
        self.write_pair(self.cwd)
        with patch('registry.Path.cwd',return_value=self.cwd):
            self.assertEqual(credentials(self.root,self.data),('',''))

    def test_workspace_configuration_precedes_application_configuration(self):
        self.write_pair(self.root,'root-id','root-secret')
        self.write_pair(self.data,'workspace-id','workspace-secret')
        self.assertEqual(credentials(self.root,self.data),('workspace-id','workspace-secret'))


class MemoryRegistryVault:
    def __init__(self):
        self.record=None
        self.unavailable=False

    def load(self):
        if self.unavailable:
            raise VaultUnavailable('Unavailable')
        return self.record

    def save(self,value):
        if self.unavailable:
            raise VaultUnavailable('Unavailable')
        self.record=dict(value)


class RegistryAccessTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.vault=MemoryRegistryVault()
        environment=patch.dict(os.environ,{},clear=True)
        environment.start()
        self.addCleanup(environment.stop)
        self.data={'client_id':'synthetic-id','client_secret':'synthetic-value'}

    def access(self):
        return RegistryAccess(self.root,self.root,self.vault)

    def test_session_credentials_are_not_persisted(self):
        self.assertTrue(self.access().apply(self.data)['configured'])
        self.assertIsNone(self.vault.record)
        self.assertFalse(self.access().status()['configured'])

    def test_persistent_access_requires_explicit_permission(self):
        with self.assertRaises(ValueError):
            self.access().apply(dict(self.data,persist=True))
        self.assertIsNone(self.vault.record)

    def test_persist_restart_and_remove(self):
        self.access().apply(dict(self.data,persist=True,permission=True))
        reopened=self.access()
        self.assertEqual(reopened.credentials(),('synthetic-id','synthetic-value'))
        self.assertEqual(reopened.status(),{'configured':True,'authorized':True})
        reopened.forget()
        self.assertEqual(self.vault.record,{'authorized':False})
        self.assertFalse(self.access().status()['configured'])

    def test_unavailable_vault_does_not_save_plaintext_or_apply_session(self):
        self.vault.unavailable=True
        access=self.access()
        with self.assertRaises(ValueError):
            access.apply(dict(self.data,persist=True,permission=True))
        self.assertFalse(access.status()['configured'])
        self.assertFalse((self.root/'sudreg.private.json').exists())

    def test_partial_environment_never_uses_saved_secret(self):
        self.access().apply(dict(self.data,persist=True,permission=True))
        with patch.dict(os.environ,{'SUDREG_CLIENT_ID':'external-id'}):
            self.assertEqual(self.access().credentials(),('external-id',''))
            self.assertFalse(self.access().status()['authorized'])

    def test_invalid_persistence_type_rejected(self):
        with self.assertRaises(ValueError):
            self.access().apply(dict(self.data,persist='true',permission=True))
        self.assertIsNone(self.vault.record)
