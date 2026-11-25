import tempfile, unittest, json
from pathlib import Path
from unittest.mock import patch
from core import Store,Collector
from sources import parse_json,parse_html,validated_url,run_external

class SourcesTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.store=Store(Path(self.tmp.name)/'db.sqlite')
    def tearDown(self): self.tmp.cleanup()
    def test_mapping(self):
        self.assertEqual(list(parse_json({'data':{'items':[{'name':'Test','address':{'city':'Rijeka'}}]}},'data.items',{'title':'name','city':'address.city'})),[{'title':'Test','city':'Rijeka'}])
        self.assertEqual(list(parse_html('<article><h2>Test</h2><a href="https://example.org">Web</a></article>','article',{'title':'h2','website':'a::attr(href)'})),[{'title':'Test','website':'https://example.org'}])
    def test_provenance_and_export(self):
        with self.store.db() as c:
            self.assertTrue(self.store.upsert(c,{'title':'Test','city':'Rijeka'},provider='companywall',origin='https://companywall.hr/api'))
            self.assertFalse(self.store.upsert(c,{'title':'Test','city':'Rijeka','email':'office@example.org'},provider='registry'))
        self.assertEqual(self.store.query(provider='registry')['total'],1)
        item=json.loads(self.store.export_json())[0]; self.assertEqual(len(item['sources']),2); self.assertEqual(item['email'],'office@example.org')
        self.assertIn('companywall',self.store.export().decode())
    def test_url_rules(self):
        for url in ('http://example.com','https://user:pass@example.com','https://127.0.0.1','https://localhost'):
            with self.assertRaises(ValueError): validated_url(url)
        with self.assertRaises(ValueError): validated_url('https://example.com','companywall')
        with self.assertRaises(ValueError): validated_url('https://www.companywall.hr/','html')
    def test_api_run(self):
        bot=Collector(self.store)
        class Response:
            status_code=200
            def __enter__(self): return self
            def __exit__(self,*a): pass
            def iter_content(self,*a): yield b'{"items":[{"name":"Test","city":"Rijeka"}]}'
        with patch('sources.validated_url'),patch('requests.Session.get',return_value=Response()):
            run_external(bot,'companywall','https://www.companywall.hr/api','items',{'title':'name','city':'city'},'test',3,1)
        self.assertEqual(bot.snapshot()['status'],'completed'); self.assertEqual(self.store.query(provider='companywall')['total'],1)
    def test_denied_api(self):
        bot=Collector(self.store)
        class Response:
            status_code=403
            def __enter__(self): return self
            def __exit__(self,*a): pass
        with patch('sources.validated_url'),patch('requests.Session.get',return_value=Response()):
            run_external(bot,'companywall','https://www.companywall.hr/api','items',{'title':'name'},'test',3,1)
        self.assertEqual(bot.snapshot()['status'],'failed'); self.assertEqual(self.store.stats()['total'],0)
