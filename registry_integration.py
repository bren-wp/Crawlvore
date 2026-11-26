"""Transactional import of a verified, isolated registry snapshot into an existing store."""
import json
import shutil
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path

from core import Collector
from registry_bundle import verify_bundle


def integrate_snapshot(store, registry, source, manifest, min_categories=36):
    """Caller must hold the workspace lock and retain a verified pre-import backup."""
    source=Path(source)
    if not source.is_file() or source.is_symlink():
        raise ValueError('Registry bundle must be a regular file.')
    if source.resolve()==Path(store.path).resolve():
        raise ValueError('Source and workspace must be separate.')
    if any(Path(str(source)+suffix).exists() for suffix in ('-wal','-shm','-journal')):
        raise ValueError('Registry bundle must be finalized and closed.')
    manifest=Path(manifest)
    if manifest.is_symlink() or not manifest.is_file() or manifest.stat().st_size>1024*1024:
        raise ValueError('Invalid registry manifest file.')
    expected=json.loads(manifest.read_text(encoding='utf-8'))
    if not isinstance(expected,dict):raise ValueError('Invalid registry manifest.')
    # Account for the staged input, SQLite transaction growth and indexes.
    # This is a conservative preflight, not a guarantee against later disk exhaustion.
    workspace=Path(store.path)
    required=3*source.stat().st_size+workspace.stat().st_size+64*1024**2
    if shutil.disk_usage(workspace.parent).free<required:
        raise ValueError('Insufficient free disk space for registry integration.')
    # Stage a private copy; never attach the mutable original or modify it.
    with tempfile.TemporaryDirectory(prefix='registry-import-',dir=Path(store.path).parent) as temporary:
        staged=Path(temporary)/'registry.sqlite3'
        shutil.copyfile(source,staged)
        report=verify_bundle(staged,min_categories=min_categories)
        if expected!=report:
            raise ValueError('Registry manifest does not match verified staged database.')
        snap=report['snapshot']
        with closing(sqlite3.connect(Path(store.path).resolve().as_uri()+'?mode=rw',uri=True,timeout=20)) as db:
            db.row_factory=sqlite3.Row
            db.execute('PRAGMA foreign_keys=ON')
            db.execute('PRAGMA synchronous=FULL')
            db.execute('ATTACH DATABASE ? AS incoming',(staged.as_uri()+'?mode=ro&immutable=1',))
            with db:
                db.execute('BEGIN IMMEDIATE')
                old=db.execute('SELECT manifest,complete FROM main.registry_runs WHERE snapshot=?',(snap,)).fetchone()
                fresh=db.execute('SELECT manifest FROM incoming.registry_runs WHERE snapshot=?',(snap,)).fetchone()
                if old:
                    if json.loads(old['manifest'])!=json.loads(fresh['manifest']):
                        raise ValueError('Existing snapshot has a different registry scope.')
                    # Preserve any prior data when the incoming snapshot disagrees.
                    if db.execute('SELECT category,ordinal,mbs,payload FROM main.registry_rows WHERE snapshot=? EXCEPT SELECT category,ordinal,mbs,payload FROM incoming.registry_rows WHERE snapshot=?',(snap,snap)).fetchone():
                        raise ValueError('Existing snapshot rows conflict with verified bundle.')
                    if old['complete']:
                        if db.execute('SELECT category,ordinal,mbs,payload FROM incoming.registry_rows WHERE snapshot=? EXCEPT SELECT category,ordinal,mbs,payload FROM main.registry_rows WHERE snapshot=?',(snap,snap)).fetchone():
                            raise ValueError('Existing completed snapshot differs from verified bundle.')
                        return {'snapshot':snap,'imported':False,'subjects':report['subjects']}
                # Only the incomplete raw mirror of this exact snapshot is replaced.
                # Other snapshots, company IDs, user data and history remain intact.
                db.execute('DELETE FROM main.registry_rows WHERE snapshot=?',(snap,))
                db.execute('DELETE FROM main.registry_pages WHERE snapshot=?',(snap,))
                db.execute('DELETE FROM main.registry_progress WHERE snapshot=?',(snap,))
                db.execute('DELETE FROM main.registry_runs WHERE snapshot=?',(snap,))
                db.execute('INSERT INTO main.registry_runs(snapshot,manifest,complete) SELECT snapshot,manifest,0 FROM incoming.registry_runs WHERE snapshot=?',(snap,))
                db.execute('INSERT INTO main.registry_rows(snapshot,category,ordinal,mbs,payload) SELECT snapshot,category,ordinal,mbs,payload FROM incoming.registry_rows WHERE snapshot=?',(snap,))
                db.execute('INSERT INTO main.registry_pages(snapshot,category,offset,n,digest) SELECT snapshot,category,offset,n,digest FROM incoming.registry_pages WHERE snapshot=?',(snap,))
                db.execute('INSERT INTO main.registry_progress(snapshot,category,next_offset,done,total) SELECT snapshot,category,next_offset,done,total FROM incoming.registry_progress WHERE snapshot=?',(snap,))
                registry.merge(snap,Collector(store),connection=db)
                if db.execute("SELECT 1 FROM main.registry_rows r WHERE r.snapshot=? AND r.category='subjekti' AND NOT EXISTS (SELECT 1 FROM main.companies c WHERE c.mbs=r.mbs) LIMIT 1",(snap,)).fetchone():
                    raise ValueError('Registry projection incomplete; transaction rolled back.')
                if db.execute('PRAGMA main.foreign_key_check').fetchone():
                    raise ValueError('Workspace foreign key check failed.')
                if [tuple(row) for row in db.execute('PRAGMA main.quick_check')]!=[('ok',)]:
                    raise ValueError('Workspace integrity check failed.')
                db.execute('UPDATE main.registry_runs SET complete=1 WHERE snapshot=?',(snap,))
            return {'snapshot':snap,'imported':True,'subjects':report['subjects']}
