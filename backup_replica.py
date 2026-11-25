"""Verified non-overwriting replication onto a separately selected filesystem."""
import hashlib
import os
import shutil
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path

def destination_for(source,directory):
    if not isinstance(directory,str) or not directory or len(directory)>4096: raise ValueError('Select an existing separate backup volume.')
    target=Path(directory)
    if not target.is_absolute() or target.is_symlink() or not target.is_dir(): raise ValueError('Select an existing separate backup volume.')
    target=target.resolve(strict=True)
    if target.stat().st_dev==Path(source).stat().st_dev: raise ValueError('Backup destination must be on a different filesystem.')
    a,b=linux_disk(source),linux_disk(target)
    if a is not None and a==b: raise ValueError('Backup destination is on the same physical block device.')
    return target

def file_digest(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        while block:=stream.read(1024*1024): h.update(block)
    return h.hexdigest()

def publish(pending,target):
    with pending.open('r+b') as stream: os.fsync(stream.fileno())
    os.link(pending,target)
    if os.name!='nt':
        fd=os.open(target.parent,os.O_RDONLY)
        try: os.fsync(fd)
        finally: os.close(fd)

def copy_verified(source,target,expected):
    if target.is_symlink(): raise ValueError('Invalid replica file.')
    if target.exists():
        if not target.is_file() or file_digest(target)!=expected: raise ValueError('Existing replica differs; no file overwritten.')
        return
    fd,name=tempfile.mkstemp(prefix='.replica-',dir=target.parent)
    pending=Path(name)
    try:
        with os.fdopen(fd,'wb') as out,source.open('rb') as inp: shutil.copyfileobj(inp,out,1024*1024)
        if file_digest(pending)!=expected: raise ValueError('Replica verification failed.')
        publish(pending,target)
    finally:
        if pending.exists(): pending.unlink()

def catalog_snapshot(source,target):
    if target.is_symlink(): raise ValueError('Invalid replica catalog.')
    fd,name=tempfile.mkstemp(prefix='.catalog-',dir=target.parent)
    os.close(fd)
    pending=Path(name)
    try:
        with closing(sqlite3.connect(source.resolve().as_uri()+'?mode=ro',uri=True,timeout=20)) as src,closing(sqlite3.connect(pending)) as dst:
            src.backup(dst)
            if dst.execute('PRAGMA integrity_check').fetchall()!=[('ok',)]: raise ValueError('Replica catalog verification failed.')
            # Compare logical rows rather than physical page layout.
            expected=list(dst.iterdump())
        if target.exists():
            with closing(sqlite3.connect(target.resolve().as_uri()+'?mode=ro',uri=True,timeout=20)) as existing:
                if existing.execute('PRAGMA integrity_check').fetchall()!=[('ok',)] or list(existing.iterdump())!=expected:
                    raise ValueError('Existing replica catalog differs.')
            return
        publish(pending,target)
    finally:
        if pending.exists(): pending.unlink()

def linux_disk(path):
    """Resolve direct Linux block devices/partitions only; complex storage is unknown."""
    import sys
    if not sys.platform.startswith('linux'): return None
    device=Path(path).stat().st_dev
    try:
        node=(Path('/sys/dev/block')/f'{os.major(device)}:{os.minor(device)}').resolve(strict=True)
        if (node/'partition').is_file(): node=node.parent
        if 'virtual' in node.parts or (node/'slaves').is_dir() and any((node/'slaves').iterdir()): return None
        if not (node/'device').exists(): return None
        return str(node)
    except OSError: return None
