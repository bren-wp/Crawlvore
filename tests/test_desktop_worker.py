import http.cookiejar
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
    def test_worker_requires_session_and_exits_on_parent_eof(self):
        with tempfile.TemporaryDirectory() as directory:
            p=subprocess.Popen([sys.executable,str(ROOT/'tvrtk_scraper.py'),'--worker','--port','0','--data-dir',directory],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
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
                    self.assertIn(b'Crawlvora',response.read())
                with opener.open(base+'/api/stats',timeout=5) as response:
                    self.assertEqual(json.load(response)['total'],26261)
                p.stdin.close()
                self.assertEqual(p.wait(timeout=20),0)
            finally:
                if p.poll() is None: p.kill(); p.wait()
                for stream in (p.stdin,p.stdout,p.stderr):
                    if stream and not stream.closed: stream.close()
