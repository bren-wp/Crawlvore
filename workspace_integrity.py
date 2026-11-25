"""Check all known workspaces without changing source records."""
import sqlite3
import threading
from contextlib import closing
from pathlib import Path

def inspect_database(path,full=False):
    path=Path(path)
    if path.is_symlink() or not path.is_file(): return 'unavailable'
    try:
        with closing(sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True,timeout=20)) as c:
            c.execute('BEGIN')
            result=c.execute('PRAGMA integrity_check' if full else 'PRAGMA quick_check').fetchall()
            if result!=[('ok',)] or c.execute('PRAGMA foreign_key_check').fetchone() is not None: return 'failed'
            tables={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            return 'ok' if {'companies','meta','origins'}<=tables else 'failed'
    except (sqlite3.Error,OSError): return 'unavailable'

def check_search_index(store,repair=False):
    if not store.fts_available: return 'unavailable'
    with store.db() as c:
        c.execute('BEGIN IMMEDIATE')
        try:
            c.execute("INSERT INTO company_fts(company_fts,rank) VALUES('integrity-check',1)")
            return 'ok'
        except sqlite3.DatabaseError as error:
            # Never try to repair physical SQLite damage or an unrelated I/O failure.
            if getattr(error,'sqlite_errorcode',None)!=sqlite3.SQLITE_CORRUPT_VTAB: raise
            if not repair: return 'failed'
            c.execute("INSERT INTO company_fts(company_fts) VALUES('rebuild')")
            c.execute("INSERT INTO company_fts(company_fts,rank) VALUES('integrity-check',1)")
            return 'rebuilt'

class WorkspaceIntegrity:
    def __init__(self,selection,recovery):
        self.selection=selection
        self.recovery=recovery
        self.lock=threading.Lock()
        self.state={'running':False,'workspaces':[]}

    def snapshot(self):
        with self.lock: return dict(self.state)

    def start(self,full=False):
        with self.lock:
            if self.state['running']: return
            self.state={'running':True,'workspaces':[]}
        threading.Thread(target=self.run,args=(full,),daemon=True).start()

    def run(self,full):
        rows=[]
        try:
            names=['primary']+[x['id'] for x in self.recovery.summary()['recovered']]
            for name in names:
                try: status=inspect_database(self.selection.resolve(name)/'companies.sqlite3',full)
                except (ValueError,OSError): status='unavailable'
                rows.append({'id':name,'status':status})
        finally:
            with self.lock: self.state={'running':False,'workspaces':rows}
