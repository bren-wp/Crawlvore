import http.cookiejar
import json
import re
import subprocess
import sys
import tempfile
import unittest
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

class LanguageTests(unittest.TestCase):
    def test_croatian_dark_overrides_legacy_preferences(self):
        with tempfile.TemporaryDirectory() as directory:
            from core import Store
            store=Store(Path(directory)/'companies.sqlite3')
            with store.db() as db:
                db.executemany("INSERT INTO meta(key,value) VALUES (?,?)",[('ui_language','en'),('ui_theme','light')])
            p=subprocess.Popen([sys.executable,str(ROOT/'src/tvrtk_scraper.py'),'--worker','--port','0','--data-dir',directory],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            try:
                with ThreadPoolExecutor(max_workers=1) as executor:
                    future=executor.submit(p.stdout.readline)
                    try: line=future.result(timeout=60)
                    except TimeoutError: p.kill(); raise
                url=line.strip().split(' ',1)[1]
                base=url.split('/session/',1)[0]
                opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
                with opener.open(url,timeout=5) as response: html=response.read().decode()
                self.assertIn('data-language="hr"',html)
                token=re.search(r'name="local-token" content="([0-9a-f]+)"',html).group(1)
                request=urllib.request.Request(base+'/api/preferences/language',data=b'{"language":"en"}',headers={'Content-Type':'application/json','X-Local-Token':token})
                with self.assertRaises(urllib.error.HTTPError) as rejected: opener.open(request,timeout=5)
                self.assertEqual(rejected.exception.code,400)
                with opener.open(base+'/',timeout=5) as response:
                    current=response.read()
                    self.assertIn(b'data-language="hr"',current)
                    self.assertIn(b'data-theme="dark"',current)
                    self.assertNotIn(b'id="settings-light"',current)
                    self.assertNotIn(b'id="language"',current)
                p.stdin.close()
                self.assertEqual(p.wait(timeout=20),0)
            finally:
                if p.poll() is None: p.kill(); p.wait()
                for stream in (p.stdin,p.stdout,p.stderr):
                    if stream and not stream.closed: stream.close()
