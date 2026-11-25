import tempfile
import unittest
from pathlib import Path
from core import Store, Collector
from registry import Registry
from automation import Queue

class RegistryOnlyTests(unittest.TestCase):
    def test_legacy_jobs_cancelled_and_sources_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=Store(Path(tmp)/'db.sqlite')
            bot=Collector(store)
            registry=Registry(store)
            queue=Queue(store,bot,registry,lambda:('',''))
            with store.db() as c:
                c.execute("INSERT INTO jobs(kind,config,state) VALUES ('html','{}','queued')")
                c.execute("INSERT INTO jobs(kind,config,state) VALUES ('tvrtke','{}','retry_wait')")
            queue=Queue(store,bot,registry,lambda:('',''))
            self.assertEqual([j['state'] for j in queue.summary()['jobs']],['cancelled','cancelled'])
            for source in ('html','tvrtke','json','companywall'):
                with self.assertRaises(ValueError): queue.enqueue(source,{'permission':True})
            self.assertGreater(queue.enqueue('registry',{'permission':True})['id'],0)

    def test_mbs_merge_keeps_contact_and_no_duplicates(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=Store(Path(tmp)/'db.sqlite')
            with store.db() as c:
                self.assertTrue(store.upsert(c,{'title':'Old Name','mbs':'12345678','phone':'0123'},provider='csv'))
                self.assertFalse(store.upsert(c,{'title':'Official Name','mbs':'012345678'},provider='registry'))
                self.assertFalse(store.upsert(c,{'title':'Official Name','mbs':'012345678'},provider='registry'))
            self.assertEqual(store.stats()['total'],1)
            self.assertEqual(store.detail(1)['phone'],'0123')
            self.assertEqual(store.detail(1)['title'],'Official Name')

    def test_conservative_legacy_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=Store(Path(tmp)/'db.sqlite')
            with store.db() as c:
                store.upsert(c,{'title':'Example','city':'Rijeka','address':'Street 1','email':'test@example.com'},provider='csv')
                self.assertFalse(store.upsert(c,{'title':'Example','city':'Rijeka','address':'Street 1','mbs':'000000002'},provider='registry'))
                self.assertTrue(store.upsert(c,{'title':'Example','city':'Rijeka','address':'Street 2','mbs':'000000003'},provider='registry'))
            self.assertEqual(store.stats()['total'],2)
            self.assertEqual(store.detail(1)['email'],'test@example.com')
