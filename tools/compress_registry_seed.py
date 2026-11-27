"""Prepare a bounded compressed seed for packaging large SQLite files."""
import argparse
import lzma
import hashlib
import os
import tempfile
import sys
import json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from registry_seed import seed_chunks

def prepare(root):
    root=Path(root)
    source=root/'registry-seed.sqlite3'
    expected=(root/'registry-seed.sha256').read_text(encoding='ascii').strip()
    size=source.stat().st_size
    if not 0<size<=16*1024**3:
        raise ValueError('Unsupported seed size')
    dest=root/'registry-seed.sqlite3.xz'
    sizefile=root/'registry-seed.size'
    if dest.exists() and sizefile.is_file():
        digest=hashlib.sha256(); count=0
        for chunk in seed_chunks(dest):
            count+=len(chunk)
            if count>size: raise ValueError('Existing compressed seed exceeds size')
            digest.update(chunk)
        if count!=size or digest.hexdigest()!=expected or int(sizefile.read_text(encoding='ascii'))!=size:
            raise ValueError('Existing compressed seed mismatch')
        print(json.dumps({'codec':'xz','raw_bytes':size,'compressed_bytes':dest.stat().st_size}))
        return
    if dest.exists():raise ValueError('Partial compressed seed staging exists')
    if sizefile.exists() and sizefile.read_text(encoding='ascii').strip()!=str(size):raise ValueError('Existing seed size mismatch')
    fd,tmp=tempfile.mkstemp(dir=root,prefix='seed-compress-',suffix='.xz')
    try:
        with os.fdopen(fd,'wb') as output,lzma.LZMAFile(output,mode='wb',format=lzma.FORMAT_XZ,preset=6,check=lzma.CHECK_CRC64) as zipped,source.open('rb') as data:
            digest=hashlib.sha256()
            count=0
            while chunk:=data.read(1024*1024):
                digest.update(chunk);count+=len(chunk);zipped.write(chunk)
        if digest.hexdigest()!=expected or count!=size:raise ValueError('Seed changed during compression')
        check=hashlib.sha256(); verified=0
        # Decode the candidate with the same bounded production decoder.
        for chunk in seed_chunks(Path(tmp)):
            verified+=len(chunk)
            if verified>size: raise ValueError('Compressed seed exceeds declared size')
            check.update(chunk)
        if verified!=size or check.hexdigest()!=expected:raise ValueError('Compressed seed verification failed')
        os.link(tmp,dest)
        if not sizefile.exists():
            with sizefile.open('x',encoding='ascii') as f:f.write(str(size)+'\n')
        print(json.dumps({'codec':'xz','raw_bytes':size,'compressed_bytes':dest.stat().st_size}))
    finally:
        Path(tmp).unlink(missing_ok=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('root');prepare(p.parse_args().root)
