"""Read-only national catalogs, isolated from the Croatian user workspace."""
import gzip
import hashlib
import json
import os
import re
import sqlite3
import tempfile
import threading
from contextlib import closing
from pathlib import Path

GB_SOURCE='https://download.companieshouse.gov.uk/en_output.html'
GB_FILE='united-kingdom.sqlite3'
GB_FIELDS={'name':'CompanyName','registration_number':'CompanyNumber','c06':'RegAddress.PostTown','c10':'CompanyCategory','c11':'CompanyStatus','c14':'IncorporationDate'}
MAX_DATABASE=16*1024**3


class NationalCatalog:
    def __init__(self, package_root, workspace_root):
        self.package=Path(package_root)/'national-data'/'GB'
        self.root=Path(workspace_root)/'national-data'/'GB'
        self.lock=threading.Lock()
        self.ready=None

    def manifest(self):
        path=self.package/'manifest.json'
        if not path.is_file(): return None
        report=json.loads(path.read_text(encoding='utf-8'))
        digest=report.get('database_sha256','')
        size=report.get('database_bytes')
        if report.get('country')!='GB' or report.get('complete') is not True or not isinstance(digest,str) or not re.fullmatch(r'[a-f0-9]{64}',digest) or type(size) is not int or not 0<size<=MAX_DATABASE or type(report.get('rows')) is not int or report['rows']<1:
            raise ValueError('Invalid national snapshot manifest.')
        if report.get('source')!=GB_SOURCE: raise ValueError('Invalid national source.')
        return report

    def status(self):
        report=self.manifest()
        return {'HR':{'available':True},'GB':{'available':bool(report and (self.package/(GB_FILE+'.gz')).is_file()),'rows':report['rows'] if report else None,'snapshot':report['snapshot'] if report else None}}

    def database(self):
        with self.lock:
            report=self.manifest()
            if not report: raise ValueError('United Kingdom snapshot is not installed.')
            digest=report['database_sha256']
            if self.ready and self.ready[0]==digest and self.ready[1].is_file(): return self.ready[1],report
            self.root.mkdir(parents=True,exist_ok=True)
            destination=self.root/(digest+'.sqlite3')
            if not destination.exists():
                source=self.package/(GB_FILE+'.gz')
                fd,tmp=tempfile.mkstemp(dir=self.root,prefix='extract-')
                try:
                    h=hashlib.sha256(); size=0
                    with os.fdopen(fd,'wb') as out,gzip.open(source,'rb') as incoming:
                        while chunk:=incoming.read(1024*1024):
                            size+=len(chunk)
                            if size>report['database_bytes']: raise ValueError('National snapshot size mismatch.')
                            h.update(chunk); out.write(chunk)
                        out.flush(); os.fsync(out.fileno())
                    if size!=report['database_bytes'] or h.hexdigest()!=digest: raise ValueError('National snapshot checksum mismatch.')
                    try: os.link(tmp,destination)
                    except FileExistsError: pass
                finally: Path(tmp).unlink(missing_ok=True)
            # Existing content-addressed files must also match the verified snapshot.
            if destination.is_symlink() or destination.stat().st_size!=report['database_bytes']: raise ValueError('Invalid local national snapshot.')
            with destination.open('rb') as stream:
                if hashlib.file_digest(stream,'sha256').hexdigest()!=digest: raise ValueError('Local national snapshot checksum mismatch.')
            with closing(sqlite3.connect(destination.resolve().as_uri()+'?mode=ro&immutable=1',uri=True)) as db:
                metadata=dict(db.execute('SELECT key,value FROM metadata'))
                if json.loads(metadata['country'])!='GB' or json.loads(metadata['rows'])!=report['rows'] or json.loads(metadata['snapshot'])!=report['snapshot']: raise ValueError('National snapshot identity mismatch.')
            self.ready=(digest,destination)
            return destination,report

    def search(self,q='',page=1):
        path,report=self.database()
        q=q.strip()
        if len(q)>200 or '\x00' in q or not 1<=page<=1000000: raise ValueError('Invalid search.')
        with closing(sqlite3.connect(path.resolve().as_uri()+'?mode=ro&immutable=1',uri=True)) as db:
            db.row_factory=sqlite3.Row
            # Company numbers use the unique index; names use the NOCASE prefix index.
            fields='name,registration_number,c06 AS city,c10 AS category,c11 AS status,c14 AS incorporated'
            if re.fullmatch(r'[A-Za-z0-9]{8}',q) and any(ch.isdigit() for ch in q):
                rows=db.execute('SELECT '+fields+' FROM companies WHERE registration_number=? LIMIT 26 OFFSET ?',(q.upper(),(page-1)*25))  # nosec B608 -- fixed column list
            else:
                pattern=q.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')+'%'
                rows=db.execute("SELECT "+fields+" FROM companies WHERE name LIKE ? ESCAPE '\\' ORDER BY name COLLATE NOCASE LIMIT 26 OFFSET ?",(pattern,(page-1)*25))  # nosec B608 -- fixed column list
            data=[dict(row) for row in rows]
        return {'country':'GB','snapshot':report['snapshot'],'total_snapshot':report['rows'],'rows':data[:25],'next':len(data)>25,'page':page}

    def detail(self,number):
        if not re.fullmatch(r'[A-Z0-9]{8}',number): raise ValueError('Invalid company number.')
        path,report=self.database()
        with closing(sqlite3.connect(path.resolve().as_uri()+'?mode=ro&immutable=1',uri=True)) as db:
            row=db.execute('SELECT * FROM companies WHERE registration_number=?',(number,)).fetchone()
            if row is None: return None
            columns=report['columns']
            if len(row)!=len(columns): raise ValueError('National snapshot schema mismatch.')
            return dict(zip(columns,row))
