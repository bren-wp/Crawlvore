"""Append a verified worker to a freshly linked Windows launcher, without huge compiler constants."""
import argparse
import hashlib
import os
from pathlib import Path
import shutil
import tempfile

def pack(host,worker,dest,expected,size):
    host,worker,dest=map(Path,(host,worker,dest))
    if dest.exists() or dest.is_symlink(): raise FileExistsError(dest)
    if size<=0 or worker.stat().st_size!=size: raise ValueError('Worker length mismatch')
    with worker.open('rb') as stream:
        if hashlib.file_digest(stream,'sha256').hexdigest()!=expected: raise ValueError('Worker checksum mismatch')
    host_size=host.stat().st_size
    if host_size+size>=2147483648: raise ValueError('Combined portable exceeds 2 GiB release limit')
    if shutil.disk_usage(dest.parent).free<host_size+size+64*1024**2: raise ValueError('Insufficient free space for portable assembly')
    # Each invocation owns exactly one staging file; never remove another builder's partial.
    fd,name=tempfile.mkstemp(prefix=dest.name+'.',suffix='.incomplete',dir=dest.parent)
    pending=Path(name)
    try:
        with os.fdopen(fd,'wb') as output,host.open('rb') as launcher,worker.open('rb') as payload:
            shutil.copyfileobj(launcher,output,1024*1024)
            shutil.copyfileobj(payload,output,1024*1024)
            output.flush();os.fsync(output.fileno())
        if pending.stat().st_size!=host_size+size: raise ValueError('Combined portable size mismatch')
        with pending.open('rb') as stream:
            stream.seek(host_size)
            if hashlib.file_digest(stream,'sha256').hexdigest()!=expected: raise ValueError('Appended payload checksum mismatch')
        # Atomic exclusive publication on NTFS/POSIX. If unsupported, fail closed.
        os.link(pending,dest)
        if os.name!='nt':
            directory=os.open(dest.parent,os.O_RDONLY)
            try:os.fsync(directory)
            finally:os.close(directory)
    finally:
        pending.unlink(missing_ok=True)
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for arg in ('host','worker','destination','sha256'):p.add_argument(arg)
    p.add_argument('size',type=int)
    a=p.parse_args();pack(a.host,a.worker,a.destination,a.sha256,a.size)
