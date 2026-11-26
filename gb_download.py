"""Explicit user-initiated UK snapshot acquisition from the official fixed HTTPS origin."""
import re
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

def fetch_snapshot(destination):
    destination=Path(destination)
    if destination.exists(): raise ValueError('UK catalog already installed.')
    destination.parent.mkdir(parents=True,exist_ok=True)
    if shutil.disk_usage(destination.parent).free<20*1024**3: raise ValueError('Insufficient free disk space.')
    with tempfile.TemporaryDirectory(prefix='gb-download-',dir=destination.parent) as tmp, requests.Session() as session:
        session.trust_env=False
        root=Path(tmp)
        with session.get(SOURCE,timeout=(15,60),allow_redirects=False,stream=True) as response:
            if response.status_code!=200: raise ValueError('UK catalog temporarily unavailable.')
            content=b''
            for chunk in response.iter_content(65536):
                content+=chunk
                if len(content)>1024**2: raise ValueError('Unexpected catalog listing size.')
        matches=sorted(set(PATTERN.findall(content.decode('utf-8',errors='replace'))),reverse=True)
        if not matches: raise ValueError('No official snapshot found.')
        snapshot=date.fromisoformat(matches[0]).isoformat()
        if snapshot>date.today().isoformat(): raise ValueError('Invalid snapshot date.')
        name=f'BasicCompanyDataAsOneFile-{snapshot}.zip';archive=root/name
        with session.get(ORIGIN+name,timeout=(15,120),allow_redirects=False,stream=True) as response:
            if response.status_code!=200: raise ValueError('UK download unavailable.')
            count=0
            with archive.open('xb') as output:
                for chunk in response.iter_content(1024*1024):
                    count+=len(chunk)
                    if count>MAX_ARCHIVE: raise ValueError('UK download exceeds limit.')
                    output.write(chunk)
        report=build([archive],root/'database')
        prepare(root/'database',root/'package')
        (root/'package').rename(destination)
        return {'rows':report['rows'],'snapshot':report['snapshot']}

class GBDownload:
    def __init__(self,destination):
        self.destination=Path(destination);self.lock=threading.Lock();self.state={'status':'idle'}
    def status(self):
        with self.lock:return dict(self.state)
    def start(self):
        with self.lock:
            if self.state['status']=='running':return dict(self.state)
            if self.destination.exists():raise ValueError('UK catalog already installed.')
            self.state={'status':'running'}
            threading.Thread(target=self.run,daemon=True).start()
            return dict(self.state)
    def run(self):
        try:result=fetch_snapshot(self.destination)
        except Exception:
            with self.lock:self.state={'status':'failed'}
        else:
            with self.lock:self.state={'status':'complete',**result}
