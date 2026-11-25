import datetime, json, tempfile, unittest, socket
from pathlib import Path
from unittest.mock import patch, MagicMock
from core import Store, Collector
from registry import Registry
from automation import Queue
from snapshot_diff import compare
from detection import inspect_html
from network import public_addresses, PublicHTTPSConnection, public_session
from urllib3.exceptions import NewConnectionError
from test_registry import Fake

class V7(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.store=Store(Path(self.tmp.name)/'db'); self.bot=Collector(self.store); self.reg=Registry(self.store)
    def tearDown(self): self.tmp.cleanup()
    def test_diff(self):
        self.reg.sync(self.bot,Fake(),1)
        with self.store.db() as c:
            c.execute("INSERT INTO registry_runs SELECT '22',manifest,1 FROM registry_runs WHERE snapshot='21'")
            c.execute("INSERT INTO registry_rows SELECT '22',category,ordinal,mbs,payload FROM registry_rows WHERE snapshot='21'")
            c.execute("UPDATE registry_rows SET payload=? WHERE snapshot='22' AND category='subjekti' AND ordinal=0",(json.dumps({'mbs':1,'tvrtka_naziv':'Changed'}),))
        d=compare(self.reg,'21','22'); by={x['category']:x for x in d['categories']}; self.assertEqual((by['subjekti']['added'],by['subjekti']['removed'],by['subjekti']['affected_subjects']),(1,1,1)); self.assertEqual(by['sjedista']['added'],0)
        with self.assertRaises(ValueError): compare(self.reg,'21','23')
    def test_retry(self):
        q=Queue(self.store,self.bot,self.reg,lambda:('x','y')); q.schedule(True,3); now=datetime.datetime(2026,11,25,4)
        def start(*a): self.bot.update(status='running',retryable=False)
        with patch('automation.start_registry',side_effect=start):
            q.tick(now); self.bot.update(status='failed',retryable=True); q.tick(now); self.assertEqual(q.summary()['jobs'][0]['state'],'retry_wait')
            q.tick(now+datetime.timedelta(minutes=14)); self.assertEqual(q.summary()['jobs'][0]['attempts'],1)
            q.tick(now+datetime.timedelta(minutes=15)); self.assertEqual(q.summary()['jobs'][0]['attempts'],2)
            self.bot.update(status='failed',retryable=False); q.tick(now+datetime.timedelta(minutes=16)); self.assertEqual(q.summary()['jobs'][0]['state'],'failed')
    def test_table_detection(self):
        html='<table><thead><tr><th>OIB</th><th>Naziv</th><th>Grad</th></tr></thead><tbody><tr><td>01234567890</td><td>Alpha</td><td>Zagreb</td></tr><tr><td>01234567891</td><td>Beta</td><td>Split</td></tr></tbody></table>'
        r=inspect_html(html); self.assertEqual(r['preview'][0]['title'],'Alpha'); self.assertEqual(r['preview'][0]['oib'],'01234567890')
    def test_dns_private_mixed(self):
        def address(ip): return (socket.AF_INET,socket.SOCK_STREAM,6,'',(ip,443))
        with patch('network.socket.getaddrinfo',return_value=[address('8.8.8.8'),address('127.0.0.1')]):
            with self.assertRaises(ValueError): public_addresses('test.example')
            with self.assertRaises(NewConnectionError): PublicHTTPSConnection('test.example',timeout=1)._new_conn()
    def test_dns_pinned(self):
        a=(socket.AF_INET,socket.SOCK_STREAM,6,'',('8.8.8.8',443)); fake=MagicMock(); fake.getpeername.return_value=('8.8.8.8',443)
        with patch('network.socket.getaddrinfo',return_value=[a]) as dns,patch('network.socket.socket',return_value=fake):
            self.assertIs(PublicHTTPSConnection('example.org',timeout=1)._new_conn(),fake); fake.connect.assert_called_once_with(('8.8.8.8',443)); dns.assert_called_once()
        with public_session() as s: self.assertFalse(s.trust_env); self.assertNotIn('http://',s.adapters)
