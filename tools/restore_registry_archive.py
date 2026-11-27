"""Rebuild an isolated HR database from the verified private data release."""
import argparse
import gzip
import hashlib
import json
import re
import sqlite3
import sys
from contextlib import closing
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from core import Store, Collector
from registry import Registry
from registry_bundle import verify_bundle

def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f,'sha256').hexdigest()

def restore(source,destination):
    source=Path(source)
    destination=Path(destination)
    manifest=json.loads((source/'REGISTRY-MANIFEST.json').read_text(encoding='utf-8'))
    receipts=json.loads((source/'REGISTRY-PAGE-RECEIPTS.json').read_text(encoding='utf-8'))
    snap=manifest['snapshot']
    categories=manifest['source_manifest']
    if snap!='1370' or len(categories)!=36 or 'scope:all' not in categories['subjekti']:
        raise ValueError('Unexpected archive scope')
    if manifest['raw_category_verification']!='passed' or manifest['rows']!=11831255 or manifest['subjects']!=392785:
        raise ValueError('Unexpected archive identity')
    records={x['category']:x for x in manifest['categories']}
    if set(categories)!=set(records) or set(categories)!=set(receipts):
        raise ValueError('Incomplete category archive')
    destination.mkdir(parents=True,exist_ok=False)
    path=destination/'registry-seed.sqlite3'
    store=Store(path)
    registry=Registry(store)
    with store.db() as db:
        db.execute('INSERT INTO registry_runs VALUES (?,?,0)',(snap,json.dumps(categories,sort_keys=True)))
        for cat,item in sorted(records.items()):
            if not re.fullmatch('[a-z_]+',cat) or item['file']!=cat+'.jsonl.gz':
                raise ValueError('Invalid category filename')
            f=source/item['file']
            if f.stat().st_size!=item['bytes'] or sha(f)!=item['sha256']:
                raise ValueError('Archive checksum mismatch: '+cat)
            offset=0
            with gzip.open(f,'rt',encoding='utf-8') as stream:
                batch=[]
                for line in stream:
                    ordinal,mbs,payload=json.loads(line)
                    if ordinal!=offset or not isinstance(mbs,str) or not isinstance(payload,str):
                        raise ValueError('Archive row mismatch')
                    batch.append((snap,cat,ordinal,mbs,payload))
                    offset+=1
                    if len(batch)==5000:
                        db.executemany('INSERT INTO registry_rows VALUES (?,?,?,?,?)',batch)
                        batch.clear()
                if batch: db.executemany('INSERT INTO registry_rows VALUES (?,?,?,?,?)',batch)
            if offset!=item['rows']: raise ValueError('Archive count mismatch')
            db.executemany('INSERT INTO registry_pages VALUES (?,?,?,?,?)',[(snap,cat,*x) for x in receipts[cat]])
            db.execute('INSERT INTO registry_progress VALUES (?,?,?,?,?)',(snap,cat,offset,1,offset))
            print('RESTORED',cat,offset,flush=True)
    preliminary=verify_bundle(path,allow_partial=True)
    if preliminary['rows']!=manifest['rows'] or preliminary['subjects']!=manifest['subjects'] or preliminary['completed_categories']!=36:
        raise ValueError('Rebuilt raw mirror mismatch')
    registry.merge(snap,Collector(store))
    with store.db() as db:
        missing=db.execute("SELECT count(*) FROM registry_rows r WHERE r.snapshot=? AND r.category='subjekti' AND NOT EXISTS (SELECT 1 FROM companies c WHERE c.mbs=r.mbs)",(snap,)).fetchone()[0]
        if missing: raise ValueError('Directory projection missing subjects: '+str(missing))
        db.execute('UPDATE registry_runs SET complete=1 WHERE snapshot=?',(snap,))
    with closing(sqlite3.connect(path)) as db:
        if db.execute('PRAGMA wal_checkpoint(TRUNCATE)').fetchone()[0]: raise ValueError('Checkpoint busy')
        if db.execute('PRAGMA journal_mode=DELETE').fetchone()[0]!='delete': raise ValueError('Cannot finalize database')
    report=verify_bundle(path)
    (destination/'registry-seed.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    (destination/'registry-seed.sha256').write_text(report['database_sha256']+'\n',encoding='ascii')
    (destination/'SHA256SUMS.txt').write_text(''.join(sha(destination/n)+'  '+n+'\n' for n in ('registry-seed.sqlite3','registry-seed.json')),encoding='ascii')
    print(json.dumps(report),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('source')
    p.add_argument('destination')
    a=p.parse_args()
    restore(a.source,a.destination)
