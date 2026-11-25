"""Local data durability: process lock and verified, non-destructive SQLite backups."""
import os
import sqlite3
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

@contextmanager
def workspace_lock(directory):
    directory=Path(directory)
    directory.mkdir(parents=True,exist_ok=True)
    # Never unlink the lock file: doing so can create two independently locked inodes.
    with (directory/'.workspace.lock').open('a+b') as handle:
        handle.seek(0,os.SEEK_END)
        if not handle.tell():
            handle.write(b'0'); handle.flush()
        handle.seek(0)
        if os.name=='nt':
            import msvcrt
            try: msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
            except OSError: raise RuntimeError('Crawlvora is already using this workspace.') from None
        else:
            import fcntl
            try: fcntl.flock(handle.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
            except OSError: raise RuntimeError('Crawlvora is already using this workspace.') from None
        # Closing the descriptor releases the OS lock even after an abnormal exit.
        yield

def verified_backup(database):
    database=Path(database)
    if not database.is_file(): return None
    directory=database.parent/'backups'
    directory.mkdir(mode=0o700,exist_ok=True)
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    fd,temporary=tempfile.mkstemp(prefix='pending-',suffix='.sqlite3',dir=directory)
    os.close(fd)
    pending=Path(temporary)
    try:
        source=sqlite3.connect(database.resolve().as_uri()+'?mode=ro',uri=True,timeout=20)
        try:
            dest=sqlite3.connect(pending,timeout=20)
            try:
                source.backup(dest,pages=256,sleep=.05)
                if dest.execute('PRAGMA quick_check').fetchall()!=[('ok',)]:
                    raise RuntimeError('Database backup integrity check failed.')
            finally: dest.close()
        finally: source.close()
        # Windows FlushFileBuffers requires a writable descriptor; do not truncate the backup.
        with pending.open('r+b') as stream: os.fsync(stream.fileno())
        # Unique name, exclusive creation; never replace a previous backup.
        final=directory/('companies-'+stamp+'-'+pending.stem+'.sqlite3')
        os.rename(pending,final)
        if os.name!='nt':
            fd=os.open(directory,os.O_RDONLY)
            try: os.fsync(fd)
            finally: os.close(fd)
        return final
    finally:
        if pending.exists(): pending.unlink()


def restore_workspace(backup, destination):
    """Restore a verified database into an exclusively created NEW workspace.

    Never opens the active workspace for writing or overwrites a previous recovery.
    Private credential files are deliberately not copied.
    """
    backup=Path(backup).resolve(strict=True)
    destination=Path(destination)
    if not backup.is_file(): raise ValueError('Backup must be a file.')
    # Read-only connection, including committed WAL if present.
    source=sqlite3.connect(backup.as_uri()+'?mode=ro',uri=True,timeout=20)
    try:
        source.execute('BEGIN')
        if source.execute('PRAGMA integrity_check').fetchall()!=[('ok',)]:
            raise ValueError('Backup failed integrity check.')
        if source.execute('PRAGMA foreign_key_check').fetchone() is not None:
            raise ValueError('Backup contains broken references.')
        tables={r[0] for r in source.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not {'companies','meta','origins'}<=tables:
            raise ValueError('Not a supported Crawlvora database.')
        # mkdir without exist_ok rejects existing paths including symlinks.
        destination.mkdir(mode=0o700)
        fd,name=tempfile.mkstemp(prefix='recovery-',suffix='.pending',dir=destination)
        os.close(fd)
        pending=Path(name)
        target=destination/'companies.sqlite3'
        try:
            out=sqlite3.connect(pending,timeout=20)
            try:
                source.backup(out,pages=256,sleep=.05)
                if out.execute('PRAGMA integrity_check').fetchall()!=[('ok',)] or out.execute('PRAGMA foreign_key_check').fetchone() is not None:
                    raise ValueError('Recovered copy failed validation.')
            finally: out.close()
            with pending.open('r+b') as stream: os.fsync(stream.fileno())
            # Hard link is atomic and fails if any target already exists.
            os.link(pending,target)
            pending.unlink()
            if os.name!='nt':
                fd=os.open(destination,os.O_RDONLY)
                try: os.fsync(fd)
                finally: os.close(fd)
            return target
        finally:
            if pending.exists(): pending.unlink()
    finally: source.close()


class RecoveryCenter:
    """Only server-generated identifiers can select local backups or recovered copies."""
    def __init__(self,database):
        import threading
        self.database=Path(database)
        self.backups=self.database.parent/'backups'
        self.recovered=self.database.parent/'recovered'
        self.lock=threading.Lock()

    def backup_path(self,name):
        import re
        if not isinstance(name,str) or not re.fullmatch(r'companies-[0-9]{8}T[0-9]{12}Z-pending-[a-zA-Z0-9_-]+\.sqlite3',name):
            raise ValueError('Invalid backup identifier.')
        path=self.backups/name
        if self.backups.is_symlink() or path.is_symlink() or not path.is_file():
            raise ValueError('Backup unavailable.')
        return path

    def recovered_path(self,name):
        import re
        if not isinstance(name,str) or not re.fullmatch(r'recovery-[a-f0-9]{32}',name):
            raise ValueError('Invalid recovery identifier.')
        directory=self.recovered/name
        path=directory/'companies.sqlite3'
        if self.recovered.is_symlink() or directory.is_symlink() or path.is_symlink() or not path.is_file():
            raise ValueError('Recovered workspace unavailable.')
        return path

    def summary(self):
        backups=[]
        if not self.backups.is_symlink():
            for path in sorted(self.backups.glob('companies-*.sqlite3'),reverse=True):
                try:
                    item=self.backup_path(path.name)
                    backups.append({'id':item.name,'bytes':item.stat().st_size})
                except (OSError,ValueError): continue
        recovered=[]
        if not self.recovered.is_symlink():
            for path in sorted(self.recovered.glob('recovery-*'),reverse=True):
                try:
                    self.recovered_path(path.name)
                    recovered.append({'id':path.name})
                except (OSError,ValueError): continue
        return {'backups':backups,'recovered':recovered}

    def create(self):
        with self.lock:
            if self.backups.is_symlink(): raise ValueError('Invalid backup directory.')
            return verified_backup(self.database).name

    def restore(self,name):
        import uuid
        with self.lock:
            backup=self.backup_path(name)
            if self.recovered.is_symlink(): raise ValueError('Invalid recovery directory.')
            self.recovered.mkdir(mode=0o700,exist_ok=True)
            identifier='recovery-'+uuid.uuid4().hex
            restore_workspace(backup,self.recovered/identifier)
            return identifier

    def inspect(self,name):
        path=self.recovered_path(name)
        with self.lock:
            c=sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True,timeout=20)
            try:
                c.execute('BEGIN')
                total=c.execute('SELECT count(*) FROM companies').fetchone()[0]
                rows=[{'title':r[0],'city':r[1]} for r in c.execute('SELECT title,city FROM companies ORDER BY title COLLATE NOCASE,id LIMIT 10')]
                return {'id':name,'total':total,'rows':rows}
            finally: c.close()
