"""Launch the local Crawlvora dashboard."""
import argparse
import json
import secrets
import sys
import time
import webbrowser
from local_server import LocalServer
from pathlib import Path
from core import Store, Collector
from local_http_routes import make_handler
from registry import Registry, RegistryAccess, start_registry
from registry_seed import accept_packaged_seed, accept_preview_seed, install_seed
import os
import threading
import tempfile
from automation import Queue
from data_safety import workspace_lock, verified_backup, RecoveryCenter
from workspace_selection import WorkspaceSelection
from backup_transfer import BackupTransfer
from protected_backups import ProtectedBackups
from workspace_integrity import WorkspaceIntegrity, inspect_database, check_search_index

# Frozen workers resolve assets inside the PyInstaller bundle. Source runs
# retain the repository root, including the original default data directory.
ROOT=Path(sys._MEIPASS) if getattr(sys,'frozen',False) else Path(__file__).resolve().parents[1]
TOKEN=secrets.token_hex(32)

def main():
    ap=argparse.ArgumentParser(description='Crawlvora — lokalni poslovni imenik')
    ap.add_argument('--port',type=int,default=0 if getattr(sys,'frozen',False) else 8765)
    ap.add_argument('--data-dir',type=Path,default=(Path(os.environ.get('LOCALAPPDATA',str(Path.home())))/'Crawlvora' if getattr(sys,'frozen',False) else ROOT/'data'))
    ap.add_argument('--primary-workspace',action='store_true',help='Open the original workspace without changing the saved selection')
    ap.add_argument('--registry-sync',action='store_true')
    ap.add_argument('--registry-limit',type=int,default=500)
    ap.add_argument('--registry-full-refresh',action='store_true',help='Explicitly allow downloading a different full registry snapshot')
    ap.add_argument('--worker',action='store_true',help='Run the authenticated desktop worker on loopback')
    ap.add_argument('--self-test',type=Path,help='Write packaged runtime smoke test result and exit')
    ap.add_argument('--no-browser',action='store_true')
    args=ap.parse_args()
    if args.worker and (args.registry_sync or args.self_test):
        ap.error('Worker mode cannot be combined with other modes.')
    if args.self_test:
        result={'ok':False}
        try:
            from openpyxl import Workbook
            with tempfile.TemporaryDirectory() as td:
                test_store=Store(Path(td)/'smoke.db')
                with test_store.db() as db: test_store.upsert(db,{'title':'Synthetic smoke record','mbs':'000000001'},provider='registry')
                if test_store.stats()['total']!=1: raise RuntimeError('Database smoke failed')
            if not all((ROOT/'static'/f).is_file() for f in ('index.html','style.css','app.js','locale.js','logo.svg')): raise RuntimeError('Missing assets')
            Workbook().close(); result={'ok':True,'records':1}
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
    database=args.data_dir/'companies.sqlite3'
    edition=None
    default_language='hr'
    edition_path=ROOT/'edition.json'
    if edition_path.is_file():
        edition_config=json.loads(edition_path.read_text(encoding='utf-8'))
        edition=edition_config['edition']
        default_language=edition_config.get('language','hr')
        if default_language != 'hr': raise ValueError('Invalid edition language.')
        if edition not in ('HR','Online'): raise ValueError('Invalid edition.')
        if os.environ.get('CRAWLVORA_NATIVE_SMOKE')=='1':
            if ((ROOT/'registry-seed.sqlite3').is_file() or (ROOT/'registry-seed.sqlite3.gz').is_file() or (ROOT/'registry-seed.sqlite3.xz').is_file())!=(edition=='HR') or (ROOT/'tvrtk_output.csv').exists():
                raise ValueError('Edition payload mismatch.')
    installed=active=='primary' and install_seed(ROOT,database)
    expected=os.environ.get('CRAWLVORA_EXPECTED_REGISTRY_SHA256')
    if os.environ.get('CRAWLVORA_NATIVE_SMOKE')=='1' and expected:
        if os.environ.get('CRAWLVORA_PRIVATE_PREVIEW')=='1':
            accept_preview_seed(ROOT,database,installed,expected)
        else:
            accept_packaged_seed(ROOT,database,installed,expected)
    # Fail closed before schema changes or seed imports if a backup cannot be verified.
    if database.exists() and inspect_database(database)!='ok': raise RuntimeError('Active workspace integrity check failed. Original preserved.')
    if not installed: verified_backup(database)
    store=Store(database); collector=Collector(store); registry=Registry(store)
    with store.db() as db:
        db.execute("INSERT OR IGNORE INTO meta(key,value) VALUES('ui_language',?)",(default_language,))
    recovery=RecoveryCenter(database,root=selection.root)
    transfers=BackupTransfer(recovery)
    protected=ProtectedBackups(database,recovery)
    integrity=WorkspaceIntegrity(selection,recovery)
    if os.environ.get('CRAWLVORA_NATIVE_SMOKE')=='1' and edition=='Online' and store.stats()['total']!=0:
        raise ValueError('Database-free Croatian workspace was not empty.')
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
        start_registry(collector,registry,registry_access.credentials(),args.registry_limit,allow_full_refresh=args.registry_full_refresh)
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
    Handler=make_handler(ROOT=ROOT, TOKEN=TOKEN, args=args, active=active,
        collector=collector, database=database,
        import_lock=import_lock, integrity=integrity,
        protected=protected, queue=queue, recovery=recovery, registry=registry,
        registry_access=registry_access, search_integrity=search_integrity,
        selection=selection, store=store, transfers=transfers, ui_ready=ui_ready,
        ui_ready_lock=ui_ready_lock)
    server=LocalServer(('127.0.0.1',args.port),Handler); url=f'http://127.0.0.1:{server.server_port}'
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
    if args.no_browser:
        # The source CLI user explicitly asked for a manually opened session.
        print(url+'/session/'+TOKEN,flush=True)
    else:
        webbrowser.open(url+'/session/'+TOKEN)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: queue.close(); collector.stop(); server.server_close(); transfers.close(); protected.close()
if __name__=='__main__': sys.exit(main())
