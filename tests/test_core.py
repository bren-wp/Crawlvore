import io, tempfile, unittest, csv
from pathlib import Path
from unittest.mock import patch
from core import Store, Collector, parse_listing, parse_detail, FIELDS, formula_safe, source_url

class CoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.store=Store(Path(self.tmp.name)/'test.sqlite')
    def tearDown(self): self.tmp.cleanup()
    def test_import_export(self):
        stream=io.StringIO(); w=csv.writer(stream); w.writerow(FIELDS); row=['']*18; row[0]='Čelik'; row[6]='Zagreb'; row[8]='+385'; w.writerow(row); stream.seek(0)
        self.assertEqual(self.store.import_csv(stream),{'read':1,'added':1}); stream.seek(0); self.assertEqual(self.store.import_csv(stream)['added'],0)
        self.assertEqual(self.store.query(q='čelik',city='Zagreb')['total'],1); self.assertIn("'+385",self.store.export().decode('utf-8-sig'))
    def test_parser(self):
        items,pages=parse_listing('<div class="divItemSlide2 roundCorners2 divShadow divInline txtLeft"><a href="/test" title="Test">Test</a><a href="https://other.example/" title="Other">Other</a></div><div class="divPager"><a class="pager2">2</a></div>'); self.assertEqual((len(items),pages),(1,2))
        row=parse_detail('<div id="FirmaPodaci_divMjesto"><span itemprop="addressLocality">Zagreb</span></div><div id="FirmaPodaci_divWeb"><a class="linkWWW" href="https://example.com">Web</a></div>','Test'); self.assertEqual(row['city'],'Zagreb'); self.assertEqual(row['website'],'https://example.com')
        with self.assertRaises(ValueError): parse_detail('<html>blocked</html>','Test')
        with self.assertRaises(ValueError): source_url('https://other.example/')
    def test_crawler_and_resume(self):
        c=Collector(self.store); listing='<div class="divItemSlide2 roundCorners2 divShadow divInline txtLeft"><a href="/test" title="Test">Test</a></div>'; detail='<div id="FirmaPodaci_divMjesto"><span itemprop="addressLocality">Zagreb</span></div>'
        with patch.object(c,'fetch',side_effect=['User-agent: *\nAllow: /',listing,detail]): c.run('a',1,1,3,True)
        self.assertEqual(c.snapshot()['status'],'completed'); self.assertEqual(self.store.stats()['total'],1)
        with patch.object(c,'fetch',side_effect=['User-agent: *\nAllow: /',listing]): c.run('a',1,1,3,True)
        self.assertEqual(c.snapshot()['skipped'],1)
    def test_denied(self):
        c=Collector(self.store)
        with patch.object(c,'fetch',side_effect=PermissionError('denied')): c.run('a',1,1,3,True)
        self.assertEqual(c.snapshot()['status'],'failed'); self.assertEqual(self.store.stats()['total'],0)
if __name__=='__main__': unittest.main()
