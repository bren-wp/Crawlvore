"""Append a verified worker to a freshly linked Windows launcher, without huge compiler constants."""
import argparse
import hashlib
import os
from pathlib import Path
import shutil

def pack(host,worker,dest,expected,size):
    host,worker,dest=map(Path,(host,worker,dest))
    if dest.exists(): raise FileExistsError(dest)
    if size<=0 or worker.stat().st_size!=size: raise ValueError('Worker length mismatch')
    with worker.open('rb') as stream:
        if hashlib.file_digest(stream,'sha256').hexdigest()!=expected: raise ValueError('Worker checksum mismatch')
    if host.stat().st_size+size>=2147483648: raise ValueError('Combined portable exceeds 2 GiB release limit')
    pending=dest.with_suffix('.exe.incomplete')
    try:
        with pending.open('xb') as output,host.open('rb') as launcher,worker.open('rb') as payload:
            shutil.copyfileobj(launcher,output,1024*1024)
            shutil.copyfileobj(payload,output,1024*1024)
            output.flush();os.fsync(output.fileno())
        with pending.open('rb') as stream:
            stream.seek(host.stat().st_size)
            if hashlib.file_digest(stream,'sha256').hexdigest()!=expected: raise ValueError('Appended payload checksum mismatch')
        pending.rename(dest)
    except BaseException:
        pending.unlink(missing_ok=True)
        raise
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for arg in ('host','worker','destination','sha256'):p.add_argument(arg)
    p.add_argument('size',type=int)
    a=p.parse_args();pack(a.host,a.worker,a.destination,a.sha256,a.size)
