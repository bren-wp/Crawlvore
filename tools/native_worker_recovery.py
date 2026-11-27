"""Restart the real packaged worker after a forced process kill, using a fresh workspace."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing, contextmanager
import json
import http.client
import time
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
from urllib.parse import urlsplit
import requests

ROOT=Path(__file__).resolve().parents[1]
TITLE='Synthetic native recovery acceptance 7c9a'
PARTIAL='Synthetic uncommitted import 7c9a'

@contextmanager
def worker(command,workspace,log):
    env={k:v for k,v in os.environ.items() if not k.startswith(('CRAWLVORA_','SUDREG_'))}
    process=subprocess.Popen([*command,'--worker','--port','0','--primary-workspace','--data-dir',str(workspace)],
                             stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=log,text=True,env=env)
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            future=pool.submit(process.stdout.readline)
            try:line=future.result(timeout=180)
            except TimeoutError:
                process.kill();raise
        if not line.startswith('CRAWLVORA_READY '):raise RuntimeError('Worker startup failed.')
        url=line.strip().split(' ',1)[1]
        parsed=urlsplit(url)
        if parsed.scheme!='http' or parsed.hostname!='127.0.0.1' or not parsed.path.startswith('/session/'):
            raise RuntimeError('Invalid worker handshake.')
        base=f'http://{parsed.netloc}'
        with requests.Session() as client:
            client.trust_env=False
            response=client.get(url,allow_redirects=False,timeout=20)
            if response.status_code!=303:raise RuntimeError('Session setup failed.')
            client.headers['X-Local-Token']=parsed.path.rsplit('/',1)[1]
            yield process,client,base
    finally:
        if process.stdin:process.stdin.close()
        if process.poll() is None:
            try:process.wait(timeout=30)
            except subprocess.TimeoutExpired:process.kill();process.wait(timeout=15)
        if process.stdout:process.stdout.close()

def interrupt_import(process,client,base):
    # Hold a real authenticated upload open, then prove the import lock is held.
    parsed=urlsplit(base)
    conn=http.client.HTTPConnection(parsed.hostname,parsed.port,timeout=10)
    try:
        conn.putrequest('POST','/api/import-json')
        conn.putheader('X-Local-Token',client.headers['X-Local-Token'])
        conn.putheader('Cookie','; '.join(k+'='+v for k,v in client.cookies.get_dict().items()))
        conn.putheader('Content-Type','application/json')
        conn.putheader('Content-Length',str(2*1024**2))
        conn.endheaders()
        prefix=json.dumps([{'title':PARTIAL,'city':'QA'}]).encode()[:-1]+b','
        conn.send(prefix+b' '*(1024**2-len(prefix)))
        for _ in range(40):
            # A malformed probe cannot create records even if it races the first request.
            response=client.post(base+'/api/import-json',data=b'[',headers={'Content-Type':'application/json'},timeout=10)
            if response.status_code==409:break
            if response.status_code!=400:raise RuntimeError('Unexpected import probe status.')
            time.sleep(.1)
        else:raise RuntimeError('Active upload was not observed.')
        process.kill();process.wait(timeout=15)
    finally:
        conn.close()


def run(command):
    with tempfile.TemporaryDirectory(prefix='cv-native-recovery-') as tmp:
        root=Path(tmp);workspace=root/'workspace'
        with (root/'worker.log').open('w+b') as log:
            with worker(command,workspace,log) as (process,client,base):
                response=client.post(base+'/api/import-json',json=[{'title':TITLE,'city':'QA'}],timeout=120)
                response.raise_for_status()
                if response.json().get('added')!=1:raise RuntimeError('Synthetic record was not committed.')
                response=client.post(base+'/api/preferences/theme',json={'theme':'dark'},timeout=20)
                response.raise_for_status()
                interrupt_import(process,client,base)
                if process.returncode==0:raise RuntimeError('Forced termination was not observed.')
            with closing(sqlite3.connect(workspace/'companies.sqlite3')) as db:
                if db.execute('PRAGMA integrity_check').fetchall()!=[('ok',)] or db.execute('PRAGMA foreign_key_check').fetchone() is not None:
                    raise RuntimeError('Database integrity failed after forced termination.')
            with worker(command,workspace,log) as (process,client,base):
                response=client.get(base+'/api/export-json',params={'q':TITLE},timeout=120)
                response.raise_for_status()
                records=response.json()
                if len(records)!=1 or records[0]['title']!=TITLE:raise RuntimeError('Committed record lost or duplicated.')
                response=client.get(base+'/api/export-json',params={'q':PARTIAL},timeout=120)
                response.raise_for_status()
                if response.json()!=[]:raise RuntimeError('Interrupted upload committed a partial record.')
                response=client.get(base+'/',timeout=20);response.raise_for_status()
                if 'data-theme="dark"' not in response.text:raise RuntimeError('Saved preferences lost.')
                process.stdin.close()
                if process.wait(timeout=30)!=0:raise RuntimeError('Graceful shutdown failed.')
    print(json.dumps({'forced_termination':'PASS','interrupted_upload_atomicity':'PASS','restart':'PASS','sqlite_integrity':'PASS','record_preserved':'PASS','preferences_preserved':'PASS','graceful_shutdown':'PASS'}),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker',type=Path)
    args=parser.parse_args()
    run([str(args.worker.resolve())] if args.worker else [sys.executable,str(ROOT/'src/tvrtk_scraper.py')])
