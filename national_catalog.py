"""Read-only national catalogs, isolated from the Croatian user workspace."""
import gzip
import hashlib
import json
import os
import re
import sqlite3
import stat
import shutil
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
        self.embedded=Path(package_root)/'national-data'/'GB'
        self.root=Path(workspace_root)/'national-data'/'GB'
        self.lock=threading.Lock()
        self.ready=None
        self.downloaded=self.root/'installed'

    @property
    def package(self):
        return self.downloaded if (self.downloaded/'manifest.json').is_file() else self.embedded

    def manifest(self):
        path=self.package/'manifest.json'
        if path.is_file(): return self.read_manifest(path)
        # An edition switch must not hide a previously extracted GB database.
        retained=[]
        for path in self.root.glob('*.manifest.json'):
            try:
                report=self.read_manifest(path)
                if path.name!=report['database_sha256']+'.manifest.json' or not self.cached_file(report):continue
                retained.append(report)
            except (OSError,ValueError,TypeError):continue
        return max(retained,key=lambda r:r['snapshot'],default=None)

    @staticmethod
    def read_manifest(path):
        if path.is_symlink() or path.stat().st_size>1024*1024:raise ValueError('Invalid national snapshot manifest.')
        report=json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(report,dict):raise ValueError('Invalid national snapshot manifest.')
        digest=report.get('database_sha256','')
        size=report.get('database_bytes')
        if report.get('country')!='GB' or report.get('complete') is not True or not isinstance(digest,str) or not re.fullmatch(r'[a-f0-9]{64}',digest) or type(size) is not int or not 0<size<=MAX_DATABASE or type(report.get('rows')) is not int or report['rows']<1:
            raise ValueError('Invalid national snapshot manifest.')
        if report.get('source')!=GB_SOURCE: raise ValueError('Invalid national source.')
        snapshot=report.get('snapshot')
        if not isinstance(snapshot,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',snapshot):raise ValueError('Invalid national snapshot date.')
        return report

    @staticmethod
    def file_identity(path):
        """Detect changed cached files without hashing gigabytes on every search."""
        try:
            info=path.lstat()
        except FileNotFoundError:
            return None
        if not stat.S_ISREG(info.st_mode):
            return None
        return (info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_ctime_ns)

    def cached_file(self,report):
        path=self.root/(report['database_sha256']+'.sqlite3')
        return path.is_file() and not path.is_symlink() and path.stat().st_size==report['database_bytes']

    def retain_manifest(self,report):
        path=self.root/(report['database_sha256']+'.manifest.json')
        if path.exists():
            if self.read_manifest(path)!=report:raise ValueError('Retained national manifest mismatch.')
            return
        fd,name=tempfile.mkstemp(dir=self.root,prefix='manifest-')
        try:
            with os.fdopen(fd,'w',encoding='utf-8') as output:
                json.dump(report,output,ensure_ascii=False);output.flush();os.fsync(output.fileno())
            try:os.link(name,path)
            except FileExistsError:
                if self.read_manifest(path)!=report:raise ValueError('Retained national manifest mismatch.')
        finally:Path(name).unlink(missing_ok=True)

    def status(self):
        report=self.manifest()
        return {'HR':{'available':True},'GB':{'available':bool(report and ((self.package/(GB_FILE+'.gz')).is_file() or self.cached_file(report))),'rows':report['rows'] if report else None,'snapshot':report['snapshot'] if report else None}}

    def database(self):
        with self.lock:
            report=self.manifest()
            if not report: raise ValueError('United Kingdom snapshot is not installed.')
            digest=report['database_sha256']
            if self.ready and self.ready[0]==report:
                path,identity=self.ready[1:]
                if identity is not None and self.file_identity(path)==identity:
                    return path,report
            self.ready=None
            self.root.mkdir(parents=True,exist_ok=True)
            destination=self.root/(digest+'.sqlite3')
            if not destination.exists():
                if shutil.disk_usage(self.root).free<report['database_bytes']+64*1024**2: raise ValueError('Insufficient free disk space for UK catalog.')
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
            identity=self.file_identity(destination)
            if identity is None or identity[2]!=report['database_bytes']: raise ValueError('Invalid local national snapshot.')
            with destination.open('rb') as stream:
                if hashlib.file_digest(stream,'sha256').hexdigest()!=digest: raise ValueError('Local national snapshot checksum mismatch.')
            with closing(sqlite3.connect(destination.resolve().as_uri()+'?mode=ro&immutable=1',uri=True)) as db:
                metadata=dict(db.execute('SELECT key,value FROM metadata'))
                if json.loads(metadata['country'])!='GB' or json.loads(metadata['rows'])!=report['rows'] or json.loads(metadata['snapshot'])!=report['snapshot']: raise ValueError('National snapshot identity mismatch.')
            self.retain_manifest(report)
            if self.file_identity(destination)!=identity:
                raise ValueError('National snapshot changed during verification.')
            self.ready=(report,destination,identity)
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
