"""Durable workspace selection. Switching takes effect only at process restart."""
import sqlite3
from pathlib import Path
from contextlib import closing
from data_safety import RecoveryCenter

class WorkspaceSelection:
    def __init__(self,root):
        self.root=Path(root)
        self.catalog=self.root/'workspace-selection.sqlite3'
        if self.catalog.is_symlink(): raise ValueError('Invalid workspace catalog.')
        with closing(sqlite3.connect(self.catalog,timeout=20)) as c:
            c.execute('PRAGMA synchronous=FULL')
            c.execute("CREATE TABLE IF NOT EXISTS selection(id INTEGER PRIMARY KEY CHECK(id=1), workspace TEXT NOT NULL)")
            c.execute("INSERT OR IGNORE INTO selection VALUES(1,'primary')")
            c.commit()

    def chosen(self):
        with closing(sqlite3.connect(self.catalog,timeout=20)) as c:
            return c.execute('SELECT workspace FROM selection WHERE id=1').fetchone()[0]

    def resolve(self,name):
        if name=='primary': return self.root
        return RecoveryCenter(self.root/'companies.sqlite3').recovered_path(name).parent

    def choose(self,name):
        target=self.resolve(name)
        database=target/'companies.sqlite3'
        if database.is_symlink() or not database.is_file(): raise ValueError('Workspace unavailable.')
        with closing(sqlite3.connect(database.resolve().as_uri()+'?mode=ro',uri=True,timeout=20)) as c:
            if c.execute('PRAGMA integrity_check').fetchall()!=[('ok',)] or c.execute('PRAGMA foreign_key_check').fetchone() is not None:
                raise ValueError('Workspace integrity check failed.')
            tables={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if not {'companies','meta','origins'}<=tables: raise ValueError('Invalid workspace.')
        with closing(sqlite3.connect(self.catalog,timeout=20)) as c:
            c.execute('PRAGMA synchronous=FULL')
            c.execute('BEGIN IMMEDIATE')
            c.execute('UPDATE selection SET workspace=? WHERE id=1',(name,))
            c.commit()
        return name
