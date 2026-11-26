"""Explicit user-initiated UK snapshot acquisition from the official fixed HTTPS origin."""
import re
import time
import os
import shutil
import tempfile
import threading
from pathlib import Path
from datetime import date
import requests
from tools.import_companies_house import build, SOURCE
from tools.prepare_national_bundle import prepare

MAX_ARCHIVE=2*1024**3
ORIGIN='https://download.companieshouse.gov.uk/'
PATTERN=re.compile(r'BasicCompanyDataAsOneFile-(\d{4}-\d{2}-\d{2})\.zip')

class DownloadCancelled(Exception):
    pass


def fetch_snapshot(destination,check=lambda:None,progress=lambda **kw:None):
    destination=Path(destination)
    if destination.exists(): raise ValueError('UK catalog already installed.')
    destination.parent.mkdir(parents=True,exist_ok=True)
    if shutil.disk_usage(destination.parent).free<20*1024**3: raise ValueError('Insufficient free disk space.')
    with tempfile.TemporaryDirectory(prefix='gb-download-',dir=destination.parent) as tmp, requests.Session() as session:
        session.trust_env=False
        root=Path(tmp)
        check(); progress(phase='listing')
        with session.get(SOURCE,timeout=(15,20),allow_redirects=False,stream=True) as response:
            if response.status_code!=200: raise ValueError('UK catalog temporarily unavailable.')
            content=b''
            for chunk in response.iter_content(65536):
                check()
                content+=chunk
                if len(content)>1024**2: raise ValueError('Unexpected catalog listing size.')
        matches=sorted(set(PATTERN.findall(content.decode('utf-8',errors='replace'))),reverse=True)
        if not matches: raise ValueError('No official snapshot found.')
        snapshot=date.fromisoformat(matches[0]).isoformat()
        if snapshot>date.today().isoformat(): raise ValueError('Invalid snapshot date.')
        name=f'BasicCompanyDataAsOneFile-{snapshot}.zip';archive=root/name
        for attempt in range(3):
            check()
            try:
                with session.get(ORIGIN+name,timeout=(15,20),allow_redirects=False,stream=True,headers={'Accept-Encoding':'identity'}) as response:
                    if response.status_code!=200: raise ValueError('UK download unavailable.')
                    length=response.headers.get('Content-Length')
                    total=int(length) if length is not None else None
                    if total is not None and not 0<total<=MAX_ARCHIVE: raise ValueError('Invalid download size.')
                    count=0
                    with archive.open('wb') as output:
                        for chunk in response.iter_content(1024*1024):
                            check()
                            count+=len(chunk)
                            if count>MAX_ARCHIVE: raise ValueError('UK download exceeds limit.')
                            output.write(chunk)
                            progress(phase='download',bytes=count,total=total)
                        output.flush();os.fsync(output.fileno())
                    if not count or (total is not None and count!=total): raise ValueError('Incomplete UK download.')
                break
            except requests.RequestException:
                if attempt==2: raise
                archive.unlink(missing_ok=True)
                progress(phase='retry',attempt=attempt+2)
                for _ in range(10*(attempt+1)):
                    check();time.sleep(.1)
        check();progress(phase='indexing')
        report=build([archive],root/'database',check=check)
        check();progress(phase='verifying')
        prepare(root/'database',root/'package',check=check)
        check()
        if destination.exists(): raise ValueError('UK catalog already installed.')
        (root/'package').rename(destination)
        return {'rows':report['rows'],'snapshot':report['snapshot']}

class GBDownload:
    def __init__(self,destination):
        self.destination=Path(destination);self.lock=threading.Lock();self.state={'status':'idle'};self.cancel=threading.Event();self.thread=None
    def status(self):
        with self.lock:return dict(self.state)
    def start(self):
        with self.lock:
            if self.state['status']=='running':return dict(self.state)
            if self.destination.exists():raise ValueError('UK catalog already installed.')
            self.cancel.clear()
            self.state={'status':'running','phase':'listing'}
            self.thread=threading.Thread(target=self.run,daemon=True)
            self.thread.start()
            return dict(self.state)
    def check(self):
        if self.cancel.is_set():raise DownloadCancelled()
    def progress(self,**values):
        with self.lock:self.state.update(values)
    def close(self):
        self.cancel.set()
        if self.thread is not None:self.thread.join(timeout=2)
    def run(self):
        try:result=fetch_snapshot(self.destination,self.check,self.progress)
        except DownloadCancelled:
            with self.lock:self.state={'status':'cancelled'}
        except Exception:
            with self.lock:self.state={'status':'failed'}
        else:
            with self.lock:self.state={'status':'complete',**result}
