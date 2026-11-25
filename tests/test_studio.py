import io,tempfile,unittest,json
from pathlib import Path
from unittest.mock import patch
from openpyxl import load_workbook
from core import Store, Collector
from studio import Projects,inspect_html,excel
from sources import run_external
HTML='<main><article class="company"><h2>Alpha</h2><span class="city">Rijeka</span></article><article class="company"><h2>Beta</h2><span class="city">Zagreb</span></article></main>'
class StudioTests(unittest.TestCase):
    def setUp(self): self.tmp=tempfile.TemporaryDirectory(); self.store=Store(Path(self.tmp.name)/'db')
    def tearDown(self): self.tmp.cleanup()
    def test_inspect(self):
        r=inspect_html(HTML); self.assertEqual(r['selector'],'article.company'); self.assertEqual(r['preview'][1]['city'],'Zagreb'); self.assertEqual(r['preview'][0]['title'],'Alpha')
    def test_projects(self):
        p=Projects(self.store); i=p.save({'name':'Test','config':{'provider':'html','url':'https://example.org','token':'secret','permission':True,'mapping':{'title':'h2'}}})['id']; q=Projects(self.store); self.assertNotIn('token',q.list()[0]['config']); self.assertNotIn('permission',q.list()[0]['config']); q.delete(i); self.assertEqual(q.list(),[])
    def test_xlsx(self):
        with self.store.db() as c: self.store.upsert(c,{'title':'=1+1','postal':'00100','city':'Zagreb'})
        ws=load_workbook(io.BytesIO(excel(self.store))).active; self.assertEqual(ws['A2'].data_type,'s'); self.assertEqual(ws['G2'].value,'00100'); self.assertEqual(ws.freeze_panes,'B2'); self.assertEqual(ws.max_row,2)
    def test_cursor(self):
        bot=Collector(self.store); calls=[]
        class R:
            status_code=200
            def __init__(self,body): self.body=body
            def __enter__(self): return self
            def __exit__(self,*a): pass
            def iter_content(self,*a): yield self.body
        def get(url,**kw):
            calls.append(url); return R(json.dumps({'items':[{'name':str(len(calls))}],'next':'abc' if len(calls)==1 else None}).encode())
        with patch('sources.validated_url'),patch('requests.Session.get',side_effect=get),patch.object(bot,'wait'):
            run_external(bot,'json','https://example.org/api','items',{'title':'name'},'',3,3,'cursor',cursor_path='next')
        self.assertEqual(bot.snapshot()['status'],'completed'); self.assertEqual(len(calls),2); self.assertIn('cursor=abc',calls[1]); self.assertEqual(self.store.stats()['total'],2)
    def test_next_link(self):
        bot=Collector(self.store); calls=[]
        class R:
            status_code=200
            def __init__(self,body): self.body=body
            def __enter__(self): return self
            def __exit__(self,*a): pass
            def iter_content(self,*a): yield self.body
        def get(url,**kw):
            calls.append(url); return R(b'User-agent: *\nAllow: /' if url.endswith('robots.txt') else b'<article><h2>A</h2></article><a rel="next" href="/two">Next</a>' if url.endswith('one') else b'<article><h2>B</h2></article>')
        with patch('sources.validated_url'),patch('requests.Session.get',side_effect=get),patch.object(bot,'wait'):
            run_external(bot,'html','https://example.org/one','article',{'title':'h2'},'',3,5,'next','a[rel=next]')
        self.assertEqual(bot.snapshot()['status'],'completed'); self.assertEqual(self.store.stats()['total'],2)
