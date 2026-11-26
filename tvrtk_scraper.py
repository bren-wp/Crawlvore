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
from core import Store, Collector
from sources import NAMES
from bulk_io import MAX_IMPORT, receive, require_free_space, import_file, export_file, company_registry
from registry import Registry, RegistryAccess, start_registry
from registry_seed import accept_packaged_seed, accept_preview_seed, install_seed
import os
import threading
import tempfile
import shutil
from automation import Queue
from snapshot_diff import compare
from data_safety import workspace_lock, verified_backup, RecoveryCenter
from registry_export import export as registry_export
from field_export import export_selected, selected_fields
from national_catalog import NationalCatalog
from gb_download import GBDownload
from workspace_selection import WorkspaceSelection
from backup_transfer import BackupTransfer
from protected_backups import ProtectedBackups
from workspace_integrity import WorkspaceIntegrity, inspect_database, check_search_index
from cryptography.exceptions import InvalidTag
from urllib.parse import unquote

ROOT=Path(__file__).resolve().parent
TOKEN=secrets.token_hex(32)

def token_matches(value,expected):
    return isinstance(value,str) and value.isascii() and secrets.compare_digest(value,expected)

def main():
    ap=argparse.ArgumentParser(description='Crawlvora — lokalni poslovni imenik')
    ap.add_argument('--port',type=int,default=0 if getattr(sys,'frozen',False) else 8765)
    ap.add_argument('--data-dir',type=Path,default=(Path(os.environ.get('LOCALAPPDATA',str(Path.home())))/'Crawlvora' if getattr(sys,'frozen',False) else ROOT/'data'))
    ap.add_argument('--primary-workspace',action='store_true',help='Open the original workspace without changing the saved selection')
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
                    page=browser.new_page(); page.set_content('<h1>Crawlvora</h1>')
                    if page.locator('h1').inner_text()!='Crawlvora': raise RuntimeError('Browser smoke test failed.')
                finally: browser.close()
            Workbook().close(); result={'ok':True,'records':26261,'browser':True}
        except Exception as e: result={'ok':False,'error':type(e).__name__}
        args.self_test.write_text(json.dumps(result),encoding='utf-8'); return 0 if result['ok'] else 1
    root=args.data_dir
    with workspace_lock(root):
        selection=WorkspaceSelection(root)
        active='primary' if args.primary_workspace else selection.chosen()
        args.data_dir=selection.resolve(active)
        if active=='primary': return run_workspace(args,selection,active)
        with workspace_lock(args.data_dir):
            return run_workspace(args,selection,active)

def run_workspace(args,selection,active):
    national=NationalCatalog(ROOT,args.data_dir)
    gb_download=GBDownload(national.downloaded)
    database=args.data_dir/'companies.sqlite3'
    edition_path=ROOT/'edition.json'
    if edition_path.is_file():
        edition=json.loads(edition_path.read_text(encoding='utf-8'))['edition']
        if edition not in ('Full','HR','GB','Online'): raise ValueError('Invalid edition.')
        if os.environ.get('CRAWLVORA_NATIVE_SMOKE')=='1':
            if (ROOT/'registry-seed.sqlite3').is_file()!=(edition in ('Full','HR')) or (ROOT/'national-data/GB/manifest.json').is_file()!=(edition in ('Full','GB')) or (ROOT/'tvrtk_output.csv').exists():
                raise ValueError('Edition payload mismatch.')
    installed=active=='primary' and install_seed(ROOT,database)
    expected=os.environ.get('CRAWLVORA_EXPECTED_REGISTRY_SHA256')
    if os.environ.get('CRAWLVORA_NATIVE_SMOKE')=='1' and expected:
        if os.environ.get('CRAWLVORA_PRIVATE_PREVIEW')=='1':
            accept_preview_seed(ROOT,database,installed,expected)
        else:
            accept_packaged_seed(ROOT,database,installed,expected)
    if os.environ.get('CRAWLVORA_NATIVE_SMOKE')=='1' and os.environ.get('CRAWLVORA_EXPECTED_GB_SHA256'):
        _,gb_report=national.database()
        if gb_report['database_sha256']!=os.environ['CRAWLVORA_EXPECTED_GB_SHA256']:
            raise ValueError('Embedded GB snapshot mismatch.')
        if not national.search()['rows']:
            raise ValueError('Embedded GB catalog is empty.')
    # Fail closed before schema changes or seed imports if a backup cannot be verified.
    if database.exists() and inspect_database(database)!='ok': raise RuntimeError('Active workspace integrity check failed. Original preserved.')
    if not installed: verified_backup(database)
    store=Store(database); collector=Collector(store); registry=Registry(store)
    recovery=RecoveryCenter(database,root=selection.root)
    transfers=BackupTransfer(recovery)
    protected=ProtectedBackups(database,recovery)
    integrity=WorkspaceIntegrity(selection,recovery)
    seed=ROOT/'tvrtk_output.csv'
    # Full registry distributions use the verified snapshot, not the legacy CSV.
    if active=='primary' and seed.exists() and not (ROOT/'registry-seed.sqlite3').exists(): store.seed(seed)
    search_integrity=check_search_index(store,repair=True)
    integrity.start()
    registry_access=RegistryAccess(ROOT,args.data_dir)
    try:
        if not registry_access.provision_from_environment():
            registry_access.provision_from_package()
    except ValueError:
        # Preserve offline workspace availability without accepting an invalid pair.
        print('Registry provisioning failed; authorized secure storage required.',file=sys.stderr)
    if args.registry_sync:
        if not 1 <= args.registry_limit <= 1000: raise ValueError('Invalid registry page size.')
        start_registry(collector,registry,registry_access.credentials(),args.registry_limit)
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
    import_lock=threading.Lock()
    ui_ready=threading.Event()
    ui_ready_lock=threading.Lock()
    queue=Queue(store,collector,registry,registry_access.credentials); queue.start()
    protected.start()
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
                return value is not None and token_matches(value.value,TOKEN)
            except (CookieError,TypeError):
                return False
        def do_GET(self):
            if not self.authorized(): return self.send_data({'error':'Nedopušten host.'},status=403)
            p=urlsplit(self.path)
            if args.worker and p.path.startswith('/session/'):
                if not token_matches(p.path,'/session/'+TOKEN):
                    return self.send_data({'error':'Access denied.'},status=403)
                return self.send_data(b'',status=303,extra={'Location':'/','Set-Cookie':self.cookie_name()+'='+TOKEN+'; Path=/; HttpOnly; SameSite=Strict'})
            if not self.session_authorized(): return self.send_data({'error':'Access denied.'},status=403)
            params=parse_qs(p.query); get=lambda k,d='':params.get(k,[d])[0]
            filters={k:get(k) for k in ('q','city','contact','provider','entity_kind')}
            try:
                if p.path=='/':
                    with store.db() as db:
                        preferred=db.execute("SELECT value FROM meta WHERE key='ui_language'").fetchone()
                        theme_row=db.execute("SELECT value FROM meta WHERE key='ui_theme'").fetchone()
                    lang='hr' if preferred and preferred[0]=='hr' else 'en'
                    theme='light' if theme_row and theme_row[0]=='light' else 'dark'
                    return self.send_data((ROOT/'static/index.html').read_text(encoding='utf-8').replace('__TOKEN__',TOKEN).replace('__LANGUAGE__',lang).replace('data-theme="dark"','data-theme="'+theme+'"',1).encode(),'text/html; charset=utf-8')
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
                if p.path=='/api/registry': return self.send_data(dict(registry.summary(),**registry_access.status()))
                if p.path in ('/api/registry/export','/api/registry/export-csv'):
                    import re
                    snapshot,category=get('snapshot'),get('category')
                    if not snapshot.isdigit() or not re.fullmatch(r'[a-z][a-z0-9_]*',category): raise ValueError('Neispravna kategorija.')
                    is_csv=p.path.endswith('-csv'); extension='csv' if is_csv else 'jsonl'
                    self.send_response(200); self.send_header('Content-Type','text/csv; charset=utf-8' if is_csv else 'application/x-ndjson; charset=utf-8'); self.send_header('Content-Disposition',f'attachment; filename="sudreg-{snapshot}-{category}.{extension}"'); self.send_header('Cache-Control','no-store'); self.send_header('X-Content-Type-Options','nosniff'); self.end_headers()
                    for chunk in (registry.export_csv(snapshot,category) if is_csv else registry.export_rows(snapshot,category)): self.wfile.write(chunk)
                    return
                if p.path=='/api/registry/rows': return self.send_data(registry.browse(get('snapshot'),get('category'),max(1,min(10000000,int(get('page','1')))),q=get('q')))
                if p.path=='/api/export-fields':
                    fields=selected_fields(get('fields'))
                    kind=get('format','csv')
                    types={'csv':'text/csv; charset=utf-8','json':'application/json; charset=utf-8','xlsx':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'}
                    if kind not in types: raise ValueError('Invalid format.')
                    with tempfile.TemporaryDirectory() as directory:
                        out=Path(directory)/('selected.'+kind)
                        export_selected(store,out,fields,kind,omit_empty=get('omit_empty','1')=='1',distinct=get('distinct')=='1',**filters)
                        self.send_response(200); self.send_header('Content-Type',types[kind]); self.send_header('Content-Length',str(out.stat().st_size)); self.send_header('Content-Disposition',f'attachment; filename="crawlvora-selected.{kind}"'); self.send_header('Cache-Control','no-store'); self.send_header('X-Content-Type-Options','nosniff'); self.end_headers()
                        with out.open('rb') as stream: shutil.copyfileobj(stream,self.wfile,1024*1024)
                    return
                if p.path in ('/api/export','/api/export-json','/api/export-xlsx'):
                    kind={'/api/export':'csv','/api/export-json':'json','/api/export-xlsx':'xlsx'}[p.path]
                    types={'csv':'text/csv; charset=utf-8','json':'application/json; charset=utf-8','xlsx':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'}
                    with tempfile.TemporaryDirectory() as directory:
                        out=Path(directory)/('crawlvora_export.'+kind)
                        export_file(store,out,kind,**filters)
                        self.send_response(200); self.send_header('Content-Type',types[kind]); self.send_header('Content-Length',str(out.stat().st_size)); self.send_header('Content-Disposition',f'attachment; filename="{out.name}"'); self.send_header('Cache-Control','no-store'); self.send_header('X-Content-Type-Options','nosniff'); self.end_headers()
                        with out.open('rb') as stream: shutil.copyfileobj(stream,self.wfile,1024*1024)
                    return
                if p.path=='/api/recovery': return self.send_data(dict(recovery.summary(),active=active,selected=selection.chosen()))
                if p.path=='/api/recovery/protected': return self.send_data(protected.snapshot())
                if p.path=='/api/recovery/protected-manifest':
                    identifier=get('id')
                    raw=protected.portable_manifest(identifier)
                    return self.send_data(raw,kind='application/json',extra={'Content-Disposition':f'attachment; filename="{identifier}.manifest.json"'})
                if p.path=='/api/recovery/protected-download':
                    with protected.download(get('id')) as path:
                        self.send_response(200); self.send_header('Content-Type','application/octet-stream'); self.send_header('Content-Length',str(path.stat().st_size)); self.send_header('Content-Disposition',f'attachment; filename="{path.name}"'); self.send_header('Cache-Control','no-store'); self.send_header('X-Content-Type-Options','nosniff'); self.end_headers()
                        with path.open('rb') as stream: shutil.copyfileobj(stream,self.wfile,1024*1024)
                    return
                if p.path=='/api/recovery/integrity': return self.send_data(dict(integrity.snapshot(),search=search_integrity))
                if p.path=='/api/recovery/encrypted-download':
                    with transfers.download(get('ticket')) as (path,name):
                        self.send_response(200); self.send_header('Content-Type','application/octet-stream'); self.send_header('Content-Length',str(path.stat().st_size)); self.send_header('Content-Disposition',f'attachment; filename="{name}"'); self.send_header('Cache-Control','no-store'); self.send_header('Referrer-Policy','no-referrer'); self.send_header('X-Content-Type-Options','nosniff'); self.end_headers()
                        with path.open('rb') as stream: shutil.copyfileobj(stream,self.wfile,1024*1024)
                    return
                if p.path=='/api/recovery/inspect': return self.send_data(recovery.inspect(get('id')))
                if p.path=='/api/recovery/download':
                    path=recovery.backup_path(get('id'))
                    with path.open('rb') as stream:
                        self.send_response(200); self.send_header('Content-Type','application/octet-stream'); self.send_header('Content-Length',str(os.fstat(stream.fileno()).st_size)); self.send_header('Content-Disposition',f'attachment; filename="{path.name}"'); self.send_header('Cache-Control','no-store'); self.send_header('X-Content-Type-Options','nosniff'); self.end_headers()
                        shutil.copyfileobj(stream,self.wfile)
                    return
                if p.path=='/api/national/status': return self.send_data(national.status())
                if p.path=='/api/national/gb/download': return self.send_data(gb_download.status())
                if p.path=='/api/national/gb/search': return self.send_data(national.search(get('q'),int(get('page','1'))))
                if p.path=='/api/national/gb/detail':
                    record=national.detail(get('number'))
                    return self.send_data(record if record else {'error':'Record not found.'},status=200 if record else 404)
                if p.path=='/api/analytics': return self.send_data(store.analytics())
                if p.path=='/api/stats': return self.send_data(store.stats())
                if p.path=='/api/providers': return self.send_data([dict(x,label=NAMES.get(x['provider'],x['provider'])) for x in store.providers()])
                if p.path=='/api/cities': return self.send_data(store.cities())
                if p.path=='/api/status': return self.send_data(collector.snapshot())
                if p.path=='/api/companies': return self.send_data(store.query(**filters,page=max(1,min(100000,int(get('page','1')))),limit=max(1,min(100,int(get('limit','25')))),sort=get('sort','title')))
                if p.path.startswith('/api/company-registry/'):
                    result=company_registry(store,int(p.path.rsplit('/',1)[1]),get('snapshot'),int(get('offset','0')))
                    return self.send_data(result if result is not None else {'error':'Record not found.'},status=200 if result is not None else 404)
                if p.path.startswith('/api/company/'):
                    item=store.detail(int(p.path.rsplit('/',1)[1])); return self.send_data(item or {'error':'Zapis nije pronađen.'},status=200 if item else 404)
                return self.send_data({'error':'Nepoznata adresa.'},status=404)
            except (ValueError,OverflowError): self.send_data({'error':'Neispravan parametar.'},status=400)
            except (BrokenPipeError,ConnectionResetError): pass
            except Exception as e: print(type(e).__name__,file=sys.stderr); self.send_data({'error':'Interna pogreška.'},status=500)
        def do_POST(self):
            if not self.authorized() or not self.session_authorized() or not token_matches(self.headers.get('X-Local-Token',''),TOKEN): return self.send_data({'error':'Nedopušten zahtjev.'},status=403)
            try:
                lengths=self.headers.get_all('Content-Length',[])
                if self.headers.get('Transfer-Encoding') is not None or len(lengths)!=1 or not lengths[0].isascii() or not lengths[0].isdigit() or len(lengths[0])>12:
                    self.close_connection=True
                    return self.send_data({'error':'Invalid request framing.'},status=400)
                n=int(lengths[0])
                if self.path=='/api/recovery/encrypted-restore':
                    password=unquote(self.headers.get('X-Backup-Passphrase',''),errors='strict')
                    if not 16<=len(password)<=1024: raise ValueError('Use a backup passphrase of at least 16 characters.')
                    self.connection.settimeout(120)
                    try: identifier=transfers.restore(self.rfile,n,password)
                    except InvalidTag: raise ValueError('Incorrect passphrase or damaged encrypted backup.') from None
                    integrity.start()
                    return self.send_data({'id':identifier})
                if self.path in ('/api/import-json','/api/import'):
                    if not 0<n<=MAX_IMPORT: return self.send_data({'error':'Datoteka je prevelika (2 GiB).'},status=413)
                    if not import_lock.acquire(blocking=False):
                        self.close_connection=True
                        return self.send_data({'error':'Another import is already running.'},status=409)
                    try:
                        self.connection.settimeout(120)
                        # Conservative preflight for backup, transaction and SQLite growth.
                        require_free_space(database.parent,database.stat().st_size+n+64*1024**2)
                        with tempfile.TemporaryDirectory() as directory:
                            staged=Path(directory)/'upload'
                            receive(self.rfile,staged,n)
                            require_free_space(database.parent,database.stat().st_size+n+64*1024**2)
                            protected.before_import()
                            return self.send_data(import_file(store,staged,'json' if self.path=='/api/import-json' else 'csv'))
                    finally:
                        import_lock.release()
                if n<0 or n>64*1024*1024: return self.send_data({'error':'Datoteka je prevelika (64 MB).'},status=413)
                self.connection.settimeout(120)
                raw=self.rfile.read(n)
                if len(raw)!=n: raise ValueError('Incomplete request body.')
                data=json.loads(raw or b'{}')
                if not isinstance(data,dict): raise ValueError('Invalid request body.')
                if self.path=='/api/national/gb/download':
                    if data.get('confirmed') is not True: raise ValueError('Confirm UK catalog download.')
                    if national.status()['GB']['available']: raise ValueError('UK catalog already installed.')
                    return self.send_data(gb_download.start())
                if self.path=='/api/recovery/encrypt':
                    if not isinstance(data,dict): raise ValueError('Invalid encryption request.')
                    password=data.get('password')
                    if not isinstance(password,str) or not 16<=len(password)<=1024: raise ValueError('Use a backup passphrase of at least 16 characters.')
                    return self.send_data({'ticket':transfers.prepare(data.get('id'),password)})
                if self.path=='/api/recovery/protected-unlock':
                    return self.send_data(protected.unlock(data.get('password'),initialize=data.get('initialize') is True))
                if self.path=='/api/recovery/protected-enroll':
                    if data.get('confirmed') is not True: raise ValueError('Confirm secure vault enrollment first.')
                    return self.send_data(protected.enroll_vault())
                if self.path=='/api/recovery/protected-replica':
                    if data.get('confirmed') is not True: raise ValueError('Confirm replica destination first.')
                    return self.send_data(protected.configure_replica(data.get('directory')))
                if self.path=='/api/recovery/protected-replicate': return self.send_data(protected.replicate())
                if self.path=='/api/recovery/protected-restore-test': return self.send_data(protected.verify_restore(data.get('id')))
                if self.path=='/api/recovery/protected-lock':
                    protected.lock_session()
                    return self.send_data(protected.snapshot())
                if self.path=='/api/recovery/protected-create':
                    return self.send_data({'id':protected.create()})
                if self.path=='/api/recovery/protected-verify':
                    return self.send_data(protected.verify())
                if self.path=='/api/recovery/protected-restore':
                    if data.get('confirmed') is not True: raise ValueError('Confirm recovery first.')
                    identifier=protected.restore(data.get('id'))
                    integrity.start()
                    return self.send_data({'id':identifier})
                if self.path=='/api/recovery/integrity':
                    integrity.start(full=True)
                    return self.send_data({'ok':True})
                if self.path=='/api/recovery/select':
                    if not isinstance(data,dict) or data.get('confirmed') is not True: raise ValueError('Confirm workspace selection first.')
                    return self.send_data({'selected':selection.choose(data.get('id'))})
                if self.path=='/api/recovery/create': return self.send_data({'id':recovery.create()})
                if self.path=='/api/recovery/restore':
                    if not isinstance(data,dict) or data.get('confirmed') is not True: raise ValueError('Confirm recovery first.')
                    identifier=recovery.restore(data.get('id'))
                    integrity.start()
                    return self.send_data({'id':identifier})
                if self.path=='/api/ui-ready':
                    if args.worker:
                        with ui_ready_lock:
                            if not ui_ready.is_set():
                                ui_ready.set()
                                print('CRAWLVORA_UI_READY',flush=True)
                    return self.send_data({'ok':True})
                if self.path=='/api/preferences/theme':
                    theme=data.get('theme') if isinstance(data,dict) else None
                    if theme not in ('dark','light'): raise ValueError('Invalid theme.')
                    with store.db() as db:
                        db.execute("INSERT INTO meta(key,value) VALUES('ui_theme',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(theme,))
                    return self.send_data({'ok':True,'theme':theme})
                if self.path=='/api/preferences/language':
                    lang=data.get('language') if isinstance(data,dict) else None
                    if lang not in ('en','hr'): raise ValueError('Invalid language.')
                    with store.db() as db:
                        db.execute("INSERT INTO meta(key,value) VALUES('ui_language',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(lang,))
                    return self.send_data({'ok':True,'language':lang})
                if self.path=='/api/registry/credentials':
                    def apply_access():
                        if collector.snapshot()['status'] in ('running','stopping'):
                            raise ValueError('Zaustavite sinkronizaciju prije promjene pristupa.')
                        return registry_access.apply(data)
                    return self.send_data(dict(queue.direct(apply_access),ok=True))
                if self.path=='/api/registry/forget':
                    def forget_access():
                        if collector.snapshot()['status'] in ('running','stopping'):
                            raise ValueError('Zaustavite sinkronizaciju prije uklanjanja pristupa.')
                        return registry_access.forget()
                    return self.send_data(dict(queue.direct(forget_access),ok=True))
                if self.path=='/api/jobs/add': return self.send_data(queue.enqueue(data.get('kind'),data.get('config',{})))
                if self.path=='/api/jobs/cancel': return self.send_data(queue.cancel(data.get('id')))
                if self.path=='/api/jobs/schedule':
                    if data.get('enabled') and data.get('permission') is not True: raise ValueError('Potvrdite dopuštenje API-ja.')
                    return self.send_data(queue.schedule(data.get('enabled'),int(data.get('hour',3))))
                if self.path in ('/api/registry/start','/api/registry/check'):
                    def synchronize():
                        pair,authorized=registry_access.current()
                        if not authorized and data.get('permission') is not True:
                            raise ValueError('Potvrdite korištenje javnog API-ja.')
                        return start_registry(collector,registry,pair,int(data.get('limit',500)),check=self.path.endswith('/check'))
                    queue.direct(synchronize); return self.send_data({'ok':True})
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
            queue.close(); collector.stop(); server.server_close(); transfers.close(); protected.close()
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
            queue.close(); collector.stop(); server.shutdown(); server.server_close(); transfers.close(); protected.close()
        return 0
    if not args.no_browser: webbrowser.open(url)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: queue.close(); collector.stop(); server.server_close(); transfers.close(); protected.close()
if __name__=='__main__': sys.exit(main())
