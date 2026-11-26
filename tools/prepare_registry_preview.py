"""Prepare an explicitly incomplete offline registry preview; never modify the source."""
import argparse
import hashlib
import json
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from core import Collector, Store
from registry import Registry
from registry_bundle import verify_bundle


def prepare(source, destination, min_categories=36):
    source=Path(source).resolve(strict=True)
    destination=Path(destination)
    destination.mkdir(mode=0o700)
    path=destination/'registry-seed.sqlite3'
    with closing(sqlite3.connect(source.as_uri()+'?mode=ro',uri=True,timeout=30)) as incoming, closing(sqlite3.connect(path)) as copied:
        incoming.backup(copied,pages=256,sleep=.05)
        if copied.execute('PRAGMA journal_mode=DELETE').fetchone()[0]!='delete':
            raise ValueError('Preview database could not be finalized.')
    report=verify_bundle(path,min_categories=min_categories,allow_partial=True)
    if report.get('complete') is not False:
        raise ValueError('Use the full production pipeline for completed snapshots.')
    store=Store(path)
    registry=Registry(store)
    registry.merge(report['snapshot'],Collector(store))
    with closing(sqlite3.connect(path)) as db:
        if db.execute('PRAGMA wal_checkpoint(TRUNCATE)').fetchone()[0]:
            raise ValueError('Preview checkpoint busy.')
        if db.execute('PRAGMA journal_mode=DELETE').fetchone()[0]!='delete':
            raise ValueError('Preview database could not be finalized.')
        companies=db.execute('SELECT count(*) FROM companies').fetchone()[0]
    report=verify_bundle(path,min_categories=min_categories,allow_partial=True)
    report['directory_companies']=companies
    report['unprojected_subjects']=report['subjects']-companies
    (destination/'registry-seed.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    (destination/'registry-seed.sha256').write_text(report['database_sha256']+'\n',encoding='ascii')
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path)
    parser.add_argument('destination',type=Path)
    args=parser.parse_args()
    print(json.dumps(prepare(args.source,args.destination)),flush=True)


if __name__=='__main__':
    try:
        main()
    except Exception as error:
        print('Registry preview not accepted: '+type(error).__name__,file=sys.stderr)
        raise SystemExit(1) from None
