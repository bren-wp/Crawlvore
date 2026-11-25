"""Launch the local Crawlvora dashboard."""
import argparse
import json
import secrets
import sys
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from http.cookies import SimpleCookie, CookieError
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
import io
from core import Store, Collector
from sources import NAMES
from studio import excel
from registry import Registry, credentials, start_registry
import os
import threading
import tempfile
import shutil
from automation import Queue
from snapshot_diff import compare
from registry_export import export as registry_export

ROOT=Path(__file__).resolve().parent
TOKEN=secrets.token_hex(32)

def main():
    ap=argparse.ArgumentParser(description='Crawlvora — lokalni poslovni imenik')
    ap.add_argument('--port',type=int,default=0 if getattr(sys,'frozen',False) else 8765)
    ap.add_argument('--data-dir',type=Path,default=(Path(os.environ.get('LOCALAPPDATA',str(Path.home())))/'Crawlvora' if getattr(sys,'frozen',False) else ROOT/'data'))
    ap.add_argument('--registry-sync',action='store_true')
    ap.add_argument('--registry-limit',type=int,default=500)
    ap.add_argument('--desktop',action='store_true')
    ap.add_argument('--worker',action='store_true',help='Run the authenticated desktop worker on loopback')
    ap.add_argument('--self-test',type=Path,help='Write packaged runtime smoke test result and exit')
    ap.add_argument('--no-browser',action='store_true')
    if getattr(sys,'frozen',False): os.environ.setdefault('PLAYWRIGHT_BROWSERS_PATH','0')
    args=ap.parse_args()
    if args.worker and (args.desktop or args.registry_sync or args.self_test):
        ap.error('Worker mode cannot be combined with other modes.')
    if args.self_test:
        result={'ok':False}
        try:
            from playwright.sync_api import sync_playwright
            from openpyxl import Workbook
            if getattr(sys,'frozen',False): import webview
            with tempfile.TemporaryDirectory() as td:
                test_store=Store(Path(td)/'smoke.db'); test_store.seed(ROOT/'tvrtk_output.csv')
                if test_store.stats()['total']!=26261: raise RuntimeError('Bundled data failed')
            if not all((ROOT/'static'/f).is_file() for f in ('index.html','style.css','app.js','locale.js','logo.svg')): raise RuntimeError('Missing assets')
            with sync_playwright() as pw:
                browser=pw.chromium.launch(headless=True,executable_path=None if getattr(sys,'frozen',False) else os.getenv('CRAWLVORA_TEST_CHROMIUM'))
                try:
                    page=browser.new_page(); page.set_content('<h1>Crawlvora</h1>'); assert page.locator('h1').inner_text()=='Crawlvora'
                finally: browser.close()
            Workbook().close(); result={'ok':True,'records':26261,'browser':True}
        except Exception as e: result={'ok':False,'error':type(e).__name__}
        args.self_test.write_text(json.dumps(result),encoding='utf-8'); return 0 if result['ok'] else 1
    args.data_dir.mkdir(parents=True,exist_ok=True)
    store=Store(args.data_dir/'companies.sqlite3'); collector=Collector(store); registry=Registry(store)
    seed=ROOT/'tvrtk_output.csv'
    if seed.exists(): store.seed(seed)
    if args.registry_sync:
        if not 1 <= args.registry_limit <= 1000: ap.error('Invalid registry page size.')
        start_registry(collector,registry,credentials(ROOT,args.data_dir),args.registry_limit)
        last=None
        try:
            while True:
                state=collector.snapshot()
                if state!=last: print(json.dumps(state,ensure_ascii=False),flush=True); last=state
                if state['status'] not in ('running','stopping'): return 0 if state['status']=='completed' else 1
                time.sleep(0.5)
        except KeyboardInterrupt:
            collector.stop()
            while collector.snapshot()['status']=='stopping': time.sleep(0.2)
            return 130
    session_credentials=None
    credentials_lock=threading.Lock()
    def registry_credentials():
        with credentials_lock:
            return session_credentials or credentials(ROOT,args.data_dir)
    def registry_configured():
        try: return all(registry_credentials())
        except ValueError: return False
    queue=Queue(store,collector,registry,registry_credentials); queue.start()
    class Handler(BaseHTTPRequestHandler):
        def send_data(self,data,kind='application/json; charset=utf-8',status=200,extra=None):
            if not isinstance(data,bytes): data=json.dumps(data,ensure_ascii=False).encode()
            self.send_response(status); self.send_header('Content-Type',kind); self.send_header('Content-Length',str(len(data)))
            self.send_header('Cache-Control','no-store'); self.send_header('X-Content-Type-Options','nosniff'); self.send_header('Referrer-Policy','no-referrer'); self.send_header('X-Frame-Options','DENY')
            self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'")
            for k,v in (extra or {}).items(): self.send_header(k,v)
            self.end_headers(); self.wfile.write(data)
        def authorized(self):
            return self.headers.get('Host') in (f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}')
        def cookie_name(self):
            return 'crawlvora_session_'+str(self.server.server_port)
        def session_authorized(self):
            if not args.worker: return True
            try:
                cookie=SimpleCookie(self.headers.get('Cookie',''))
                value=cookie.get(self.cookie_name())
                return value is not None and secrets.compare_digest(value.value,TOKEN)
            except (CookieError,TypeError):
                return False
        def do_GET(self):
            if not self.authorized(): return self.send_data({'error':'Nedopušten host.'},status=403)
            p=urlsplit(self.path)
            if args.worker and p.path.startswith('/session/'):
                if not secrets.compare_digest(p.path,'/session/'+TOKEN):
                    return self.send_data({'error':'Access denied.'},status=403)
                return self.send_data(b'',status=303,extra={'Location':'/','Set-Cookie':self.cookie_name()+'='+TOKEN+'; Path=/; HttpOnly; SameSite=Strict'})
            if not self.session_authorized(): return self.send_data({'error':'Access denied.'},status=403)
            params=parse_qs(p.query); get=lambda k,d='':params.get(k,[d])[0]
            filters={k:get(k) for k in ('q','city','contact','provider')}
            try:
                if p.path=='/':
                    with store.db() as db:
                        preferred=db.execute("SELECT value FROM meta WHERE key='ui_language'").fetchone()
                    lang='hr' if preferred and preferred[0]=='hr' else 'en'
                    return self.send_data((ROOT/'static/index.html').read_text(encoding='utf-8').replace('__TOKEN__',TOKEN).replace('__LANGUAGE__',lang).encode(),'text/html; charset=utf-8')
                if p.path in ('/app.js','/locale.js','/style.css','/logo.svg'):
                    return self.send_data((ROOT/'static'/p.path[1:]).read_bytes(),'text/javascript; charset=utf-8' if p.path.endswith('js') else ('image/svg+xml' if p.path.endswith('svg') else 'text/css; charset=utf-8'))
                if p.path=='/api/registry/diff': return self.send_data(compare(registry,get('before'),get('after')))
                if p.path=='/api/jobs': return self.send_data(queue.summary())
                if p.path.startswith('/api/history/'): return self.send_data(store.history(int(p.path.rsplit('/',1)[1])))
                if p.path in ('/api/registry/export-xlsx','/api/registry/export-xml','/api/registry/export-sql'):
                    kind=p.path.rsplit('-',1)[1]; snapshot,category=get('snapshot'),get('category')
                    with tempfile.TemporaryDirectory() as directory:
                        out=Path(directory)/('export.'+kind); registry_export(registry,snapshot,category,kind,out)
                        self.send_response(200); self.send_header('Content-Type',{'xlsx':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet','xml':'application/xml','sql':'application/sql'}[kind]); self.send_header('Content-Length',str(out.stat().st_size)); self.send_header('Content-Disposition',f'attachment; filename="sudreg-{snapshot}-{category}.{kind}"'); self.send_header('Cache-Control','no-store'); self.send_header('X-Content-Type-Options','nosniff'); self.end_headers()
                        with out.open('rb') as f: shutil.copyfileobj(f,self.wfile)
                    return
                if p.path=='/api/registry': return self.send_data(dict(registry.summary(),configured=registry_configured()))
                if p.path in ('/api/registry/export','/api/registry/export-csv'):
                    import re
                    snapshot,category=get('snapshot'),get('category')
                    if not snapshot.isdigit() or not re.fullmatch(r'[a-z][a-z0-9_]*',category): raise ValueError('Neispravna kategorija.')
                    is_csv=p.path.endswith('-csv'); extension='csv' if is_csv else 'jsonl'
                    self.send_response(200); self.send_header('Content-Type','text/csv; charset=utf-8' if is_csv else 'application/x-ndjson; charset=utf-8'); self.send_header('Content-Disposition',f'attachment; filename="sudreg-{snapshot}-{category}.{extension}"'); self.send_header('Cache-Control','no-store'); self.send_header('X-Content-Type-Options','nosniff'); self.end_headers()
                    for chunk in (registry.export_csv(snapshot,category) if is_csv else registry.export_rows(snapshot,category)): self.wfile.write(chunk)
                    return
                if p.path=='/api/registry/rows': return self.send_data(registry.browse(get('snapshot'),get('category'),max(1,min(10000000,int(get('page','1')))),q=get('q')))
                if p.path=='/api/export-xlsx': return self.send_data(excel(store,**filters),'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',extra={'Content-Disposition':'attachment; filename="crawlvora_export.xlsx"'})
                if p.path=='/api/analytics': return self.send_data(store.analytics())
                if p.path=='/api/stats': return self.send_data(store.stats())
                if p.path=='/api/providers': return self.send_data([dict(x,label=NAMES.get(x['provider'],x['provider'])) for x in store.providers()])
                if p.path=='/api/export-json': return self.send_data(store.export_json(**filters),'application/json; charset=utf-8',extra={'Content-Disposition':'attachment; filename="crawlvora_export.json"'})
                if p.path=='/api/cities': return self.send_data(store.cities())
                if p.path=='/api/status': return self.send_data(collector.snapshot())
                if p.path=='/api/companies': return self.send_data(store.query(**filters,page=max(1,min(100000,int(get('page','1')))),limit=max(1,min(100,int(get('limit','25')))),sort=get('sort','title')))
                if p.path.startswith('/api/company/'):
                    item=store.detail(int(p.path.rsplit('/',1)[1])); return self.send_data(item or {'error':'Zapis nije pronađen.'},status=200 if item else 404)
                if p.path=='/api/export': return self.send_data(store.export(**filters),'text/csv; charset=utf-8',extra={'Content-Disposition':'attachment; filename="crawlvora_export.csv"'})
                return self.send_data({'error':'Nepoznata adresa.'},status=404)
            except (ValueError,OverflowError): self.send_data({'error':'Neispravan parametar.'},status=400)
            except (BrokenPipeError,ConnectionResetError): pass
            except Exception as e: print(type(e).__name__,file=sys.stderr); self.send_data({'error':'Interna pogreška.'},status=500)
        def do_POST(self):
            nonlocal session_credentials
            if not self.authorized() or not self.session_authorized() or not secrets.compare_digest(self.headers.get('X-Local-Token',''),TOKEN): return self.send_data({'error':'Nedopušten zahtjev.'},status=403)
            try:
                n=int(self.headers.get('Content-Length','0'))
                if n<0 or n>64*1024*1024: return self.send_data({'error':'Datoteka je prevelika (64 MB).'},status=413)
                raw=self.rfile.read(n)
                if self.path=='/api/import-json': return self.send_data(store.import_json(raw.decode('utf-8-sig')))
                if self.path=='/api/import': return self.send_data(store.import_csv(io.StringIO(raw.decode('utf-8-sig'),newline='')))
                data=json.loads(raw or b'{}')
                if self.path=='/api/preferences/language':
                    lang=data.get('language') if isinstance(data,dict) else None
                    if lang not in ('en','hr'): raise ValueError('Invalid language.')
                    with store.db() as db:
                        db.execute("INSERT INTO meta(key,value) VALUES('ui_language',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(lang,))
                    return self.send_data({'ok':True,'language':lang})
                if self.path=='/api/registry/credentials':
                    if not isinstance(data,dict): raise ValueError('Invalid credentials.')
                    client_id,client_secret=(data.get(k) for k in ('client_id','client_secret'))
                    if not all(isinstance(v,str) and 0<len(v.strip())<=512 and not any(ord(ch)<32 for ch in v) for v in (client_id,client_secret)):
                        raise ValueError('Enter valid Client ID and Client Secret.')
                    with credentials_lock: session_credentials=(client_id.strip(),client_secret.strip())
                    return self.send_data({'ok':True,'configured':True})
                if self.path=='/api/jobs/add': return self.send_data(queue.enqueue(data.get('kind'),data.get('config',{})))
                if self.path=='/api/jobs/cancel': return self.send_data(queue.cancel(data.get('id')))
                if self.path=='/api/jobs/schedule':
                    if data.get('enabled') and data.get('permission') is not True: raise ValueError('Potvrdite dopuštenje API-ja.')
                    return self.send_data(queue.schedule(data.get('enabled'),int(data.get('hour',3))))
                if self.path in ('/api/registry/start','/api/registry/check'):
                    if data.get('permission') is not True: raise ValueError('Potvrdite korištenje javnog API-ja.')
                    queue.direct(lambda: start_registry(collector,registry,registry_credentials(),int(data.get('limit',500)),check=self.path.endswith('/check'))); return self.send_data({'ok':True})
                if self.path=='/api/stop': collector.stop(); return self.send_data({'ok':True})
                return self.send_data({'error':'Nepoznata adresa.'},status=404)
            except (ValueError,TypeError,UnicodeError) as e: self.send_data({'error':str(e)},status=400)
            except Exception as e: print(type(e).__name__,file=sys.stderr); self.send_data({'error':'Operacija nije uspjela.'},status=500)
        def log_message(self,*args): pass
    server=ThreadingHTTPServer(('127.0.0.1',args.port),Handler); url=f'http://127.0.0.1:{server.server_port}'
    if args.worker:
        # The parent receives this secret over a private stdout pipe. Never log it.
        print('CRAWLVORA_READY '+url+'/session/'+TOKEN,flush=True)
        def parent_watch():
            try:
                if sys.stdin is not None: sys.stdin.buffer.read(1)
            finally:
                server.shutdown()
        threading.Thread(target=parent_watch,daemon=True).start()
        try: server.serve_forever()
        finally:
            queue.close(); collector.stop(); server.server_close()
        return 0
    if sys.stdout is not None: print(f'Crawlvora: {url}\nPodaci: {args.data_dir}\nZa izlaz pritisnite Ctrl+C.')
    if args.desktop or getattr(sys,'frozen',False):
        import webview
        webview.settings['ALLOW_DOWNLOADS']=True
        threading.Thread(target=server.serve_forever,daemon=True).start()
        try:
            webview.create_window('Crawlvora',url,width=1440,height=900,min_size=(900,620))
            webview.start(gui='edgechromium')
        finally:
            queue.close(); collector.stop(); server.shutdown(); server.server_close()
        return 0
    if not args.no_browser: webbrowser.open(url)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: queue.close(); collector.stop(); server.server_close()
if __name__=='__main__': sys.exit(main())
