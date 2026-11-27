import http.cookiejar
import http.client
from urllib.parse import urlsplit
import json
import subprocess
import sys
import tempfile
import unittest
import urllib.error
import urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

class DesktopWorkerTests(unittest.TestCase):
    def test_source_mode_requires_authentication_and_does_not_log_session(self):
        from concurrent.futures import ThreadPoolExecutor
        with tempfile.TemporaryDirectory() as directory:
            with tempfile.TemporaryFile(mode='w+b') as log:
                p=subprocess.Popen([sys.executable,str(ROOT/'src/tvrtk_scraper.py'),'--no-browser','--port','0','--data-dir',directory],stdout=subprocess.PIPE,stderr=log,text=True,encoding='utf-8',env=dict(__import__('os').environ,PYTHONIOENCODING='utf-8'))
                try:
                    with ThreadPoolExecutor(max_workers=1) as pool:
                        def session_line():
                            for line in p.stdout:
                                if '/session/' in line:return line.strip()
                        future=pool.submit(session_line)
                        try: url=future.result(timeout=30)
                        except TimeoutError:p.kill();raise
                    self.assertRegex(url,r'^http://127\.0\.0\.1:[0-9]+/session/[a-f0-9]{64}$')
                    base,token=url.split('/session/')
                    with self.assertRaises(urllib.error.HTTPError) as denied:urllib.request.urlopen(base+'/api/stats',timeout=5)
                    self.assertEqual(denied.exception.code,403)
                    denied.exception.close()
                    opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
                    with opener.open(url,timeout=5) as response:self.assertIn(b'Tvrtke',response.read())
                    with self.assertRaises(urllib.error.HTTPError) as denied:opener.open(base+'/api/stats?'+('&'.join('x'+str(i)+'=1' for i in range(65))),timeout=5)
                    self.assertEqual(denied.exception.code,400)
                    denied.exception.close()
                    log.seek(0)
                    self.assertNotIn(token.encode(),log.read())
                finally:
                    if p.poll() is None:p.terminate();p.wait(timeout=10)
                    p.stdout.close()

    def test_worker_requires_session_and_exits_on_parent_eof(self):
        with tempfile.TemporaryDirectory() as directory:
            p=subprocess.Popen([sys.executable,str(ROOT/'src/tvrtk_scraper.py'),'--worker','--port','0','--data-dir',directory],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            try:
                # Use a bounded wait so failed initialization cannot hang the suite.
                from concurrent.futures import ThreadPoolExecutor
                with ThreadPoolExecutor(max_workers=1) as executor:
                    future=executor.submit(p.stdout.readline)
                    try: line=future.result(timeout=60)
                    except TimeoutError:
                        p.kill()
                        raise
                self.assertTrue(line.startswith('CRAWLVORA_READY '))
                url=line.strip().split(' ',1)[1]
                base=url.split('/session/',1)[0]
                with self.assertRaises(urllib.error.HTTPError) as rejected:
                    urllib.request.urlopen(base+'/api/stats',timeout=5)
                self.assertEqual(rejected.exception.code,403)
                opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
                with opener.open(url,timeout=5) as response:
                    self.assertEqual(response.geturl(),base+'/')
                    self.assertIn(b'Tvrtke',response.read())
                with opener.open(base+'/api/stats',timeout=5) as response:
                    self.assertEqual(json.load(response)['total'],0)
                import re
                with opener.open(base+'/',timeout=5) as response:
                    html=response.read().decode()
                token=re.search(r'name="local-token" content="([0-9a-f]+)"',html).group(1)
                def post(path, payload):
                    req=urllib.request.Request(base+path,data=json.dumps(payload).encode(),headers={'X-Local-Token':token,'Content-Type':'application/json'})
                    with opener.open(req,timeout=5) as response: return json.load(response)
                for invalid in ('wrong-token','caf\u00e9'):
                    req=urllib.request.Request(base+'/api/preferences/theme',data=b'{}',headers={'X-Local-Token':invalid,'Content-Type':'application/json'})
                    with self.assertRaises(urllib.error.HTTPError) as denied:
                        opener.open(req,timeout=5)
                    self.assertEqual(denied.exception.code,403)
                parsed=urlsplit(base)
                cookie_name='crawlvora_session_'+str(parsed.port)
                for headers in ([('Content-Length','2'),('Content-Length','2')],[('Transfer-Encoding','chunked'),('Content-Length','2')],[('Content-Length','-1')],[]):
                    conn=http.client.HTTPConnection(parsed.hostname,parsed.port,timeout=5)
                    try:
                        conn.putrequest('POST','/api/preferences/theme')
                        conn.putheader('Cookie',cookie_name+'='+token)
                        conn.putheader('X-Local-Token',token)
                        conn.putheader('Content-Type','application/json')
                        for key,value in headers: conn.putheader(key,value)
                        conn.endheaders()
                        response=conn.getresponse()
                        self.assertEqual(response.status,400)
                        response.read()
                    finally: conn.close()
                # Browser cross-origin and ambiguous security headers must fail closed.
                for name, value in (('Origin','https://example.invalid'),('Host',parsed.netloc),
                                    ('Cookie',cookie_name+'='+token),('X-Local-Token',token)):
                    conn=http.client.HTTPConnection(parsed.hostname,parsed.port,timeout=5)
                    try:
                        conn.putrequest('POST','/api/preferences/theme')
                        conn.putheader('Cookie',cookie_name+'='+token)
                        conn.putheader('X-Local-Token',token)
                        conn.putheader('Content-Length','2')
                        conn.putheader(name,value)
                        conn.endheaders(b'{}')
                        with conn.getresponse() as response:
                            self.assertEqual(response.status,403)
                            response.read()
                    finally: conn.close()
                for payload in ([],None,'invalid'):
                    with self.assertRaises(urllib.error.HTTPError) as rejected:
                        post('/api/preferences/theme',payload)
                    self.assertEqual(rejected.exception.code,400)
                credentials={'client_id':'synthetic-audit-id','client_secret':'synthetic-audit-secret'}
                self.assertEqual(post('/api/registry/credentials',credentials),{'ok':True,'configured':True,'authorized':False})
                with opener.open(base+'/api/registry',timeout=5) as response:
                    raw=response.read()
                    self.assertNotIn(credentials['client_id'].encode(),raw)
                    self.assertNotIn(credentials['client_secret'].encode(),raw)
                    self.assertTrue(json.loads(raw)['configured'])
                self.assertEqual(post('/api/preferences/theme',{'theme':'dark'})['theme'],'dark')
                with opener.open(base+'/',timeout=5) as response:
                    self.assertIn(b'data-theme="dark"',response.read())
                self.assertTrue(post('/api/ui-ready',{})['ok'])
                with ThreadPoolExecutor(max_workers=1) as executor:
                    future=executor.submit(p.stdout.readline)
                    try: self.assertEqual(future.result(timeout=5).strip(),'CRAWLVORA_UI_READY')
                    except TimeoutError: p.kill(); raise
                p.stdin.close()
                self.assertEqual(p.wait(timeout=20),0)
            finally:
                if p.poll() is None: p.kill(); p.wait()
                for stream in (p.stdin,p.stdout,p.stderr):
                    if stream and not stream.closed: stream.close()
