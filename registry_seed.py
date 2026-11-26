"""Initialize a fresh workspace from a verified, embedded registry database."""
import hashlib
import json
import sqlite3
from contextlib import closing
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


def accept_packaged_seed(root, database, installed, expected_sha):
    """Smoke acceptance of the actual offline seed, never the legacy CSV fallback."""
    root=Path(root)
    if not installed:
        raise ValueError('Complete packaged registry seed was not installed.')
    report=json.loads((root/'registry-seed.json').read_text(encoding='utf-8'))
    declared=(root/'registry-seed.sha256').read_text(encoding='ascii').strip()
    if not expected_sha or expected_sha!=declared or report.get('database_sha256')!=expected_sha:
        raise ValueError('Packaged registry SHA-256 does not match accepted snapshot.')
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
