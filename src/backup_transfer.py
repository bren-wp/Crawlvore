"""Bounded local encrypted transfer; no browser Blob or arbitrary filesystem path."""
import os
import secrets
import shutil
import tempfile
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from encrypted_backup import encrypt_backup,decrypt_backup
from data_safety import restore_workspace

CHUNK=1024*1024
MAX_ARCHIVE=32*1024**3

def receive(stream,out,length):
    if not 54<length<=MAX_ARCHIVE: raise ValueError('Invalid encrypted archive size.')
    remaining=length
    while remaining:
        block=stream.read(min(CHUNK,remaining))
        if not block: raise ValueError('Incomplete encrypted archive.')
        out.write(block)
        remaining-=len(block)

class BackupTransfer:
    def __init__(self,recovery):
        self.recovery=recovery
        self.lock=threading.Lock()
        self.pending=None

    def close(self):
        with self.lock:
            if self.pending:
                self.pending[1].cleanup()
                self.pending=None

    def prepare(self,identifier,password):
        with self.lock:
            if self.pending:
                self.pending[1].cleanup()
                self.pending=None
            with self.recovery.lock:
                source=self.recovery.backup_path(identifier)
                if source.stat().st_size>MAX_ARCHIVE-53: raise ValueError('Backup exceeds encrypted export size limit.')
                if shutil.disk_usage(source.parent).free<source.stat().st_size+53: raise ValueError('Insufficient disk space.')
                directory=tempfile.TemporaryDirectory(prefix='cv-encrypted-',dir=source.parent)
                try:
                    path=encrypt_backup(source,Path(directory.name)/'backup.cvbackup',password)
                    ticket=secrets.token_urlsafe(32)
                    self.pending=(ticket,directory,path,source.stem+'.cvbackup',time.monotonic()+300)
                    return ticket
                except BaseException:
                    directory.cleanup()
                    raise

    @contextmanager
    def download(self,ticket):
        with self.lock:
            item=self.pending
            if not item or not secrets.compare_digest(item[0],ticket): raise ValueError('Download unavailable.')
            self.pending=None
        try:
            if time.monotonic()>item[4]: raise ValueError('Download expired.')
            yield item[2],item[3]
        finally: item[1].cleanup()

    def restore(self,stream,length,password):
        if not 54<length<=MAX_ARCHIVE: raise ValueError('Invalid encrypted archive size.')
        with self.recovery.lock:
            root=self.recovery.recovered
            if root.is_symlink(): raise ValueError('Invalid recovery directory.')
            root.mkdir(mode=0o700,exist_ok=True)
            if shutil.disk_usage(root).free<3*length: raise ValueError('Insufficient disk space for recovery.')
            with tempfile.TemporaryDirectory(prefix='.cv-restore-',dir=root) as directory:
                archive=Path(directory)/'incoming.cvbackup'
                with archive.open('xb') as out:
                    receive(stream,out,length)
                    out.flush(); os.fsync(out.fileno())
                decoded=decrypt_backup(archive,Path(directory)/'authenticated.sqlite3',password)
                identifier='recovery-'+uuid.uuid4().hex
                restore_workspace(decoded,root/identifier)
                return identifier
