"""Verify an isolated official public registry mirror before distribution."""
from contextlib import closing
import hashlib
import json
import sqlite3
from pathlib import Path


def verify_bundle(path, min_categories=36, *, allow_partial=False):
    path=Path(path)
    if not path.is_file() or path.is_symlink():
        raise ValueError('Missing registry bundle.')
    path=path.resolve()
    with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)) as db:
        db.execute('PRAGMA query_only=ON')
        if db.execute('PRAGMA integrity_check').fetchall()!=[('ok',)]:
            raise ValueError('Registry database integrity check failed.')
        if db.execute('PRAGMA foreign_key_check').fetchone() is not None:
            raise ValueError('Registry database relation check failed.')
        runs=db.execute('SELECT snapshot,manifest,complete FROM registry_runs').fetchall()
        if len(runs)!=1 or runs[0][2] not in (0,1) or (not allow_partial and runs[0][2]!=1):
            raise ValueError('Expected one completed isolated snapshot.')
        snapshot,manifest,complete=runs[0]
        categories=json.loads(manifest)
        if not isinstance(categories,dict) or any(not isinstance(name,str) or not isinstance(params,list) for name,params in categories.items()):
            raise ValueError('Invalid registry manifest.')
        if not snapshot.isascii() or not snapshot.isdigit() or len(categories)<min_categories or 'scope:all' not in categories.get('subjekti',[]):
            raise ValueError('Incomplete all-status registry manifest.')
        progress={name:(offset,done,total) for name,offset,done,total in db.execute('SELECT category,next_offset,done,total FROM registry_progress WHERE snapshot=?',(snapshot,))}
        if not set(progress).issubset(categories) or (complete and set(progress)!=set(categories)):
            raise ValueError('Registry categories differ from manifest.')
        for table in ('registry_rows','registry_pages','registry_progress'):
            # Only these fixed table names are permitted; no user-controlled SQL.
            if db.execute(f'SELECT 1 FROM {table} WHERE snapshot<>? LIMIT 1',(snapshot,)).fetchone():  # nosec B608
                raise ValueError('Mixed snapshot data.')
            names={row[0] for row in db.execute(f'SELECT DISTINCT category FROM {table}')}  # nosec B608
            if not names.issubset(categories):
                raise ValueError('Unexpected registry category.')
        if db.execute('SELECT 1 FROM origins WHERE provider<>? LIMIT 1',('registry',)).fetchone():
            raise ValueError('Non-registry provenance in distribution database.')
        if db.execute('SELECT 1 FROM companies WHERE source IS NOT NULL LIMIT 1').fetchone():
            raise ValueError('Non-registry source in distribution database.')
        totals={}
        for name,params in categories.items():
            if 'only_active' in params and 'scope:all' not in params:
                raise ValueError('Active-only category.')
            if name not in progress:
                if db.execute('SELECT 1 FROM registry_rows WHERE category=? UNION ALL SELECT 1 FROM registry_pages WHERE category=? LIMIT 1',(name,name)).fetchone():
                    raise ValueError('Uncheckpointed registry category.')
                continue
            offset,done,total=progress[name]
            if done not in (0,1) or total is None or total<0 or offset<0 or offset>total or bool(done)!=(offset==total) or (complete and not done):
                raise ValueError('Unfinished registry category.')
            pages=db.execute('SELECT offset,n,digest FROM registry_pages WHERE snapshot=? AND category=? ORDER BY offset',(snapshot,name))
            expected=0
            page_count=0
            seen_digests=set()
            for start,count,digest in pages:
                if start!=expected or count<0 or (count==0 and offset!=0):
                    raise ValueError('Noncontiguous registry pages.')
                rows=db.execute('SELECT ordinal,payload FROM registry_rows WHERE snapshot=? AND category=? AND ordinal>=? AND ordinal<? ORDER BY ordinal',(snapshot,name,start,start+count)).fetchall()
                if [row[0] for row in rows]!=list(range(start,start+count)):
                    raise ValueError('Registry row ordinal mismatch.')
                payload=[json.loads(row[1]) for row in rows]
                if hashlib.sha256(json.dumps(payload,sort_keys=True,ensure_ascii=False).encode()).hexdigest()!=digest:
                    raise ValueError('Registry page digest mismatch.')
                if count and digest in seen_digests:
                    raise ValueError('Repeated registry page digest.')
                seen_digests.add(digest)
                expected+=count
                page_count+=1
            actual=db.execute('SELECT count(*) FROM registry_rows WHERE snapshot=? AND category=?',(snapshot,name)).fetchone()[0]
            if not page_count or actual!=offset or expected!=offset:
                raise ValueError('Registry row count mismatch.')
            totals[name]=offset
        total,distinct,invalid=db.execute("SELECT count(*),count(DISTINCT mbs),coalesce(sum(CASE WHEN length(mbs)<>9 OR mbs GLOB '*[^0-9]*' THEN 1 ELSE 0 END),0) FROM registry_rows WHERE snapshot=? AND category='subjekti'",(snapshot,)).fetchone()
        if not total or distinct!=total or invalid:
            raise ValueError('Invalid or duplicate registry subject identifiers.')
        if complete and db.execute("SELECT 1 FROM registry_rows r WHERE r.snapshot=? AND r.category='subjekti' AND NOT EXISTS (SELECT 1 FROM companies c WHERE c.mbs=r.mbs) LIMIT 1",(snapshot,)).fetchone():
            raise ValueError('Some registry subjects are missing from the company directory.')
    with path.open('rb') as source:
        database_sha256=hashlib.file_digest(source,'sha256').hexdigest()
    report={'snapshot':snapshot,'scope':'all-status','subjects':total,'category_count':len(totals),'categories':totals,'rows':sum(totals.values()),'database_sha256':database_sha256,'source':'https://sudreg-data.gov.hr/api/javni','license':'https://www.data.gov.hr/hr/open-license'}
    if not complete:
        report.update(complete=False,registry_bundle_included=True,category_count=len(categories),completed_categories=sum(item[1] for item in progress.values()),progress={name:{'rows':p[0],'done':bool(p[1]),'total':p[2]} for name,p in progress.items()})
    return report
