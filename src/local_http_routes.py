"""Workspace-scoped authenticated HTTP routes; no implicit global workspace."""
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlsplit, parse_qs, unquote
from local_http_response import LocalResponseHandler
from local_http_security import token_matches, allowed_host, session_cookie_name, valid_session_cookie, content_length, InvalidFraming, single_header, allowed_origin
from sources import NAMES
from bulk_io import MAX_IMPORT, receive, require_free_space, import_file, export_file, company_registry
from registry import start_registry
from snapshot_diff import compare
from registry_export import export as registry_export
from field_export import export_selected, selected_fields
from cryptography.exceptions import InvalidTag
from crawlvora_mail import MailService, TEMPLATES


def make_handler(*, ROOT, TOKEN, args, active, collector, database,
                 import_lock, integrity, protected, queue, recovery,
                 registry, registry_access, search_integrity, selection, store,
                 transfers, ui_ready, ui_ready_lock):
    mail=MailService(store,database.parent) if store is not None else None
    class Handler(LocalResponseHandler):
        def authorized(self):
            return allowed_host(single_header(self.headers,'Host'),self.server.server_port)
        def cookie_name(self):
            return session_cookie_name(self.server.server_port)
        def session_authorized(self):
            return not args.worker or valid_session_cookie(single_header(self.headers,'Cookie') or '',self.cookie_name(),TOKEN)
        def do_GET(self):
            if not self.authorized(): return self.send_data({'error':'Nedopušten host.'},status=403)
            try: p=urlsplit(self.path)
            except ValueError: return self.send_data({'error':'Invalid request target.'},status=400)
            if args.worker and p.path.startswith('/session/'):
                if not token_matches(p.path,'/session/'+TOKEN):
                    return self.send_data({'error':'Access denied.'},status=403)
                return self.send_data(b'',status=303,extra={'Location':'/','Set-Cookie':self.cookie_name()+'='+TOKEN+'; Path=/; HttpOnly; SameSite=Strict'})
            if not self.session_authorized(): return self.send_data({'error':'Access denied.'},status=403)
            params=parse_qs(p.query); get=lambda k,d='':params.get(k,[d])[0]
            filters={k:get(k) for k in ('q','city','contact','provider','entity_kind','industry')}
            try:
                if p.path=='/':
                    lang='hr'; theme='dark'
                    return self.send_data((ROOT/'static/index.html').read_text(encoding='utf-8').replace('__TOKEN__',TOKEN).replace('__LANGUAGE__',lang).replace('data-theme="dark"','data-theme="'+theme+'"',1).encode(),'text/html; charset=utf-8')
                if p.path in ('/app.js','/locale.js','/style.css','/logo.svg'):
                    return self.send_data((ROOT/'static'/p.path[1:]).read_bytes(),'text/javascript; charset=utf-8' if p.path.endswith('js') else ('image/svg+xml' if p.path.endswith('svg') else 'text/css; charset=utf-8'))
                if p.path=='/api/registry/diff': return self.send_data(compare(registry,get('before'),get('after')))
                if p.path=='/api/mail/settings': return self.send_data(mail.settings())
                if p.path=='/api/mail/templates': return self.send_data(TEMPLATES)
                if p.path=='/api/mail/history': return self.send_data(mail.history(int(get('company_id','0'))))
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
                if p.path=='/api/analytics': return self.send_data(store.analytics())
                if p.path=='/api/stats': return self.send_data(store.stats())
                if p.path=='/api/providers': return self.send_data([dict(x,label=NAMES.get(x['provider'],x['provider'])) for x in store.providers()])
                if p.path=='/api/cities': return self.send_data(store.cities())
                if p.path=='/api/industries': return self.send_data(store.industries())
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
            if not self.authorized() or not self.session_authorized() or not allowed_origin(self.headers,self.server.server_port) or not token_matches(single_header(self.headers,'X-Local-Token'),TOKEN): return self.send_data({'error':'Nedopušten zahtjev.'},status=403)
            try:
                try:
                    n=content_length(self.headers)
                except InvalidFraming:
                    self.close_connection=True
                    return self.send_data({'error':'Invalid request framing.'},status=400)
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
                if self.path.startswith('/api/mail/') and n>65536:
                    self.close_connection=True
                    return self.send_data({'error':'Prevelik zahtjev e-pošte.'},status=413)
                if n<0 or n>64*1024*1024: return self.send_data({'error':'Datoteka je prevelika (64 MB).'},status=413)
                self.connection.settimeout(120)
                raw=self.rfile.read(n)
                if len(raw)!=n: raise ValueError('Incomplete request body.')
                data=json.loads(raw or b'{}')
                if not isinstance(data,dict): raise ValueError('Invalid request body.')
                if self.path.startswith('/api/mail/'):
                    if n>65536: raise ValueError('Prevelik zahtjev e-pošte.')
                    if self.path=='/api/mail/configure': return self.send_data(mail.configure(data))
                    if self.path=='/api/mail/forget': return self.send_data(mail.forget())
                    if self.path=='/api/mail/block': return self.send_data(mail.block(data))
                    if self.path=='/api/mail/send': return self.send_data(mail.send(data))
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
                    if theme != 'dark': raise ValueError('Invalid theme.')
                    with store.db() as db:
                        db.execute("INSERT INTO meta(key,value) VALUES('ui_theme',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(theme,))
                    return self.send_data({'ok':True,'theme':theme})
                if self.path=='/api/preferences/language':
                    lang=data.get('language') if isinstance(data,dict) else None
                    if lang != 'hr': raise ValueError('Invalid language.')
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
                        return start_registry(collector,registry,pair,int(data.get('limit',500)),check=self.path.endswith('/check'),allow_full_refresh=data.get('full_refresh') is True)
                    queue.direct(synchronize); return self.send_data({'ok':True})
                if self.path=='/api/stop': collector.stop(); return self.send_data({'ok':True})
                return self.send_data({'error':'Nepoznata adresa.'},status=404)
            except (ValueError,TypeError,UnicodeError) as e: self.send_data({'error':str(e)},status=400)
            except Exception as e: print(type(e).__name__,file=sys.stderr); self.send_data({'error':'Operacija nije uspjela.'},status=500)
        def log_message(self,*args): pass
    return Handler
