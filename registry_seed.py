"""Initialize a fresh workspace from a verified, embedded registry database."""
import hashlib
import os
import tempfile
from pathlib import Path


def install_seed(root, destination):
    source=Path(root)/'registry-seed.sqlite3'
    checksums=Path(root)/'registry-seed.sha256'
    destination=Path(destination)
    if destination.exists() or not source.exists():
        return False
    if not checksums.is_file():
        raise ValueError('Registry seed checksum is missing.')
    expected=checksums.read_text(encoding='ascii').strip()
    if len(expected)!=64 or any(ch not in '0123456789abcdef' for ch in expected):
        raise ValueError('Invalid registry seed checksum.')
    fd,name=tempfile.mkstemp(prefix='registry-seed-',dir=destination.parent)
    try:
        with os.fdopen(fd,'wb') as output,source.open('rb') as data:
            digest=hashlib.sha256()
            while chunk:=data.read(1024*1024):
                digest.update(chunk)
                output.write(chunk)
            output.flush()
            os.fsync(output.fileno())
        if digest.hexdigest()!=expected:
            raise ValueError('Embedded registry seed checksum mismatch.')
        # Atomic exclusive publication: never replace an existing workspace.
        try:
            os.link(name,destination)
        except FileExistsError:
            return False
        return True
    finally:
        os.unlink(name)
