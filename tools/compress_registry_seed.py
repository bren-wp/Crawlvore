"""Prepare a bounded compressed seed for packaging large SQLite files."""
import argparse
import gzip
import hashlib
import os
import tempfile
from pathlib import Path

def prepare(root):
    root=Path(root)
    source=root/'registry-seed.sqlite3'
    expected=(root/'registry-seed.sha256').read_text(encoding='ascii').strip()
    size=source.stat().st_size
    if not 0<size<=16*1024**3:
        raise ValueError('Unsupported seed size')
    dest=root/'registry-seed.sqlite3.gz'
    sizefile=root/'registry-seed.size'
    if dest.exists() and sizefile.is_file():
        with gzip.open(dest,'rb') as stream:
            digest=hashlib.file_digest(stream,'sha256').hexdigest()
        if digest!=expected or int(sizefile.read_text(encoding='ascii'))!=size:
            raise ValueError('Existing compressed seed mismatch')
        return
    if dest.exists() or sizefile.exists():raise ValueError('Partial compressed seed staging exists')
    fd,tmp=tempfile.mkstemp(dir=root,prefix='seed-compress-')
    try:
        with os.fdopen(fd,'wb') as output,gzip.GzipFile(fileobj=output,mode='wb',compresslevel=3,mtime=0) as zipped,source.open('rb') as data:
            digest=hashlib.sha256()
            count=0
            while chunk:=data.read(1024*1024):
                digest.update(chunk);count+=len(chunk);zipped.write(chunk)
        if digest.hexdigest()!=expected or count!=size:raise ValueError('Seed changed during compression')
        os.link(tmp,dest)
        with sizefile.open('x',encoding='ascii') as f:f.write(str(size)+'\n')
    finally:
        Path(tmp).unlink(missing_ok=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('root');prepare(p.parse_args().root)
