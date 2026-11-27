"""Opt-in isolated bulk HTTP import acceptance, with synthetic data only."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlsplit

import requests

ROOT=Path(__file__).resolve().parents[1]
MAX_SIZE=2*1024**3


def make_fixture(path,size,count):
    # Equal-size synthetic records, except for a final byte adjustment.
    # Padding is intentionally not a directory field: this measures large-file
    # transport/parsing and record insertion, not retention of 2 GiB of text.
    with path.open('xb') as stream:
        stream.write(b'[')
        for i in range(count):
            prefix=((',' if i else '')+'{"title":"Synthetic bulk %06d","city":"QA","padding":"' % i).encode()
            suffix=b'"}'
            budget=(size-2)//count if i<count-1 else size-stream.tell()-1
            padding=budget-len(prefix)-len(suffix)
            if not 0<=padding<=7*1024**2: raise ValueError('Choose a compatible record count and fixture size.')
            stream.write(prefix);stream.write(b'x'*padding);stream.write(suffix)
        stream.write(b']')
    if path.stat().st_size!=size: raise RuntimeError('Fixture length mismatch')


def run(size=MAX_SIZE,count=20000):
    if not 1<=count<=1000000 or not 1<=size<=MAX_SIZE: raise ValueError('Invalid acceptance test dimensions.')
    if shutil.disk_usage(tempfile.gettempdir()).free<3*size+512*1024**2:
        raise RuntimeError('Insufficient disk space for acceptance test.')
    with tempfile.TemporaryDirectory(prefix='cv-e2e-') as tmp:
        folder=Path(tmp);source=folder/'bulk.json';data=folder/'workspace'
        make_fixture(source,size,count)
        env={k:v for k,v in os.environ.items() if not k.startswith(('SUDREG_','CRAWLVORA_'))}
        with (folder/'worker.log').open('w+b') as log:
            worker=subprocess.Popen([sys.executable,str(ROOT/'src/tvrtk_scraper.py'),'--worker','--port','0','--data-dir',str(data)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=log,text=True,env=env,cwd=tmp)  # nosec B603 -- fixed local program and arguments
            try:
                with ThreadPoolExecutor(max_workers=1) as pool:
                    future=pool.submit(worker.stdout.readline)
                    try: line=future.result(timeout=180)
                    except TimeoutError: worker.kill();raise
                if not line.startswith('CRAWLVORA_READY '): raise RuntimeError('Worker handshake failed')
                session=line.strip().split(' ',1)[1]
                parsed=urlsplit(session)
                if parsed.scheme!='http' or parsed.hostname!='127.0.0.1' or not parsed.path.startswith('/session/'):
                    raise RuntimeError('Unexpected worker address')
                base=f'{parsed.scheme}://{parsed.netloc}'; token=parsed.path.rsplit('/',1)[-1]
                with requests.Session() as client:
                    client.trust_env=False
                    if client.get(session,allow_redirects=False,timeout=15).status_code!=303:
                        raise RuntimeError('Session initialization failed')
                    start=time.perf_counter()
                    with source.open('rb') as stream:
                        response=client.post(base+'/api/import-json',data=stream,headers={'X-Local-Token':token,'Content-Type':'application/json'},timeout=(10,900))
                    response.raise_for_status()
                    result=response.json()
                    if result.get('read')!=count or result.get('added')!=count: raise RuntimeError('Import count mismatch')
                    elapsed=time.perf_counter()-start
                    response=client.get(base+'/api/export-json',params={'q':'Synthetic bulk'},timeout=(10,180))
                    response.raise_for_status()
                    records=response.json()
                    if len(records)!=count or len({r['title'] for r in records})!=count: raise RuntimeError('Export count mismatch')
                with closing(sqlite3.connect(data/'companies.sqlite3')) as db:
                    if db.execute('PRAGMA quick_check').fetchall()!=[('ok',)] or db.execute('PRAGMA foreign_key_check').fetchone() is not None:
                        raise RuntimeError('SQLite integrity failed')
                report={'input_bytes':size,'records':count,'import_seconds':round(elapsed,3),'http_status':200,'export_records':len(records),'sqlite_integrity':'ok','scope':'source worker HTTP; synthetic padding not retained'}
            finally:
                if worker.stdin: worker.stdin.close()
                try: worker.wait(timeout=30)
                except subprocess.TimeoutExpired: worker.kill();worker.wait()
                if worker.stdout: worker.stdout.close()
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bytes',type=int,default=MAX_SIZE)
    parser.add_argument('--records',type=int,default=20000)
    args=parser.parse_args()
    print(json.dumps(run(args.bytes,args.records)),flush=True)
