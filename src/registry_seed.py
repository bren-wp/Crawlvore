"""Initialize a fresh workspace from a verified, embedded registry database."""
import gzip
import hashlib
import lzma
import json
import sqlite3
import shutil
from contextlib import closing
import os
import tempfile
from pathlib import Path


CHUNK=1024*1024
XZ_MEMORY_LIMIT=32*1024*1024

def seed_chunks(source):
    """Stream one XZ member with explicit decoder memory and output limits."""
    if source.suffix=='.xz':
        decoder=lzma.LZMADecompressor(format=lzma.FORMAT_XZ,memlimit=XZ_MEMORY_LIMIT)
        with source.open('rb') as stream:
            while not decoder.eof:
                data=stream.read(CHUNK) if decoder.needs_input else b''
                if decoder.needs_input and not data:
                    raise ValueError('Truncated registry XZ seed.')
                try:
                    chunk=decoder.decompress(data,max_length=CHUNK)
                except lzma.LZMAError:
                    raise ValueError('Invalid registry XZ seed or decoder memory limit exceeded.') from None
                if chunk: yield chunk
            if decoder.unused_data or stream.read(1):
                raise ValueError('Unexpected trailing registry XZ data.')
    else:
        with (gzip.open(source,'rb') if source.suffix=='.gz' else source.open('rb')) as stream:
            while chunk:=stream.read(CHUNK):
                yield chunk


def install_seed(root, destination):
    root=Path(root)
    raw=root/'registry-seed.sqlite3'
    xz=root/'registry-seed.sqlite3.xz'
    packed=root/'registry-seed.sqlite3.gz'
    source=xz if xz.exists() else packed if packed.exists() else raw
    compressed=source!=raw
    checksums=Path(root)/'registry-seed.sha256'
    destination=Path(destination)
    if destination.exists() or not source.exists():
        return False
    if source.is_symlink() or not source.is_file():
        raise ValueError('Invalid registry seed file.')
    if compressed:
        size_path=root/'registry-seed.size'
        if not size_path.is_file() or size_path.is_symlink() or size_path.stat().st_size>32:
            raise ValueError('Missing compressed registry size.')
        declared=size_path.read_text(encoding='ascii').strip()
        if not declared.isascii() or not declared.isdigit():
            raise ValueError('Invalid compressed registry size.')
        size=int(declared)
        if not 0<size<=16*1024**3:
            raise ValueError('Invalid compressed registry size.')
    else:
        size=source.stat().st_size
    if shutil.disk_usage(destination.parent).free < size + 64*1024**2:
        raise ValueError('Insufficient free disk space for registry seed.')
    if not checksums.is_file():
        raise ValueError('Registry seed checksum is missing.')
    expected=checksums.read_text(encoding='ascii').strip()
    if len(expected)!=64 or any(ch not in '0123456789abcdef' for ch in expected):
        raise ValueError('Invalid registry seed checksum.')
    fd,name=tempfile.mkstemp(prefix='registry-seed-',dir=destination.parent)
    try:
        with os.fdopen(fd,'wb') as output:
            digest=hashlib.sha256()
            copied=0
            for chunk in seed_chunks(source):
                copied+=len(chunk)
                if copied>size: raise ValueError('Registry seed size mismatch.')
                digest.update(chunk)
                output.write(chunk)
            output.flush()
            os.fsync(output.fileno())
        if copied!=size: raise ValueError('Registry seed size mismatch.')
        if digest.hexdigest()!=expected:
            raise ValueError('Embedded registry seed checksum mismatch.')
        # Atomic exclusive publication: never replace an existing workspace.
        try:
            os.link(name,destination)
        except FileExistsError:
            return False
        if os.name!='nt':
            directory=os.open(destination.parent,os.O_RDONLY)
            try:os.fsync(directory)
            finally:os.close(directory)
        return True
    finally:
        os.unlink(name)


def _acceptance_manifest(root, installed, expected_sha, *, preview):
    root=Path(root)
    if not installed:
        raise ValueError('Preview registry seed not installed.' if preview else 'Complete packaged registry seed was not installed.')
    report=json.loads((root/'registry-seed.json').read_text(encoding='utf-8'))
    declared=(root/'registry-seed.sha256').read_text(encoding='ascii').strip()
    if not expected_sha or expected_sha!=declared or report.get('database_sha256')!=expected_sha:
        raise ValueError('Preview registry checksum mismatch.' if preview else 'Packaged registry SHA-256 does not match accepted snapshot.')
    return report


def accept_packaged_seed(root, database, installed, expected_sha):
    """Smoke acceptance of the actual offline seed, never the legacy CSV fallback."""
    report=_acceptance_manifest(root,installed,expected_sha,preview=False)
    if report.get('complete') is False:
        raise ValueError('Incomplete preview cannot pass complete registry acceptance.')
    # install_seed verified every copied byte against declared before publication.
    with closing(sqlite3.connect(Path(database).resolve().as_uri()+'?mode=ro',uri=True)) as db:
        runs=db.execute('SELECT snapshot,complete FROM registry_runs').fetchall()
        if runs!=[(report['snapshot'],1)]:
            raise ValueError('Packaged registry snapshot is incomplete.')
        progress=dict(db.execute('SELECT category,total FROM registry_progress WHERE snapshot=? AND done=1 AND next_offset=total',(report['snapshot'],)))
        if len(progress)<36 or progress!=report['categories'] or len(progress)!=report['category_count']:
            raise ValueError('Packaged registry categories are incomplete.')
        if report.get('scope')!='all-status' or progress.get('subjekti')!=report['subjects'] or sum(progress.values())!=report['rows']:
            raise ValueError('Packaged registry counts do not match manifest.')
    return report


def accept_preview_seed(root, database, installed, expected_sha):
    """Validate captured partial snapshot without claiming full registry coverage."""
    report=_acceptance_manifest(root,installed,expected_sha,preview=True)
    if report.get('complete') is not False or report.get('scope')!='all-status':
        raise ValueError('Expected explicitly incomplete registry snapshot.')
    with closing(sqlite3.connect(Path(database).resolve().as_uri()+'?mode=ro',uri=True)) as db:
        if db.execute('SELECT snapshot,complete FROM registry_runs').fetchall()!=[(report['snapshot'],0)]:
            raise ValueError('Preview snapshot identity mismatch.')
        progress={name:{'rows':offset,'done':bool(done),'total':total} for name,offset,done,total in db.execute('SELECT category,next_offset,done,total FROM registry_progress WHERE snapshot=?',(report['snapshot'],))}
        if progress!=report['progress'] or sum(p['rows'] for p in progress.values())!=report['rows']:
            raise ValueError('Preview category checkpoint mismatch.')
        if db.execute('SELECT count(*) FROM registry_rows').fetchone()[0]!=report['rows']:
            raise ValueError('Preview row count mismatch.')
        if db.execute('SELECT count(*) FROM companies').fetchone()[0]!=report['directory_companies']:
            raise ValueError('Preview directory count mismatch.')
    return report
