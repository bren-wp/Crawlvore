"""Create a compressed, verified offline GB snapshot for native build staging."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path

def prepare(source,destination,check=lambda:None):
    source=Path(source); destination=Path(destination)
    report=json.loads((source/'manifest.json').read_text(encoding='utf-8'))
    database=source/'united-kingdom.sqlite3'
    if report.get('country')!='GB' or report.get('complete') is not True: raise ValueError('Not a completed GB snapshot')
    with database.open('rb') as stream:
        if hashlib.file_digest(stream,'sha256').hexdigest()!=report['database_sha256']: raise ValueError('Checksum mismatch')
    destination.mkdir(parents=True,exist_ok=False)
    with database.open('rb') as incoming,gzip.open(destination/'united-kingdom.sqlite3.gz','wb',compresslevel=3) as outgoing:
        while chunk:=incoming.read(1024*1024):
            check();outgoing.write(chunk)
    report['database_bytes']=database.stat().st_size
    (destination/'manifest.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    return {'rows':report['rows'],'database_bytes':report['database_bytes'],'compressed_bytes':(destination/'united-kingdom.sqlite3.gz').stat().st_size}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('source'); p.add_argument('destination'); p.add_argument('--distribution-reviewed',action='store_true',required=True)
    a=p.parse_args(); print(json.dumps(prepare(a.source,a.destination)))
