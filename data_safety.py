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
        with pending.open('rb') as stream: os.fsync(stream.fileno())
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
