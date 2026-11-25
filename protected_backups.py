"""Session-unlocked automatic encrypted backups with authenticated catalog.

The catalog authenticates its ordered entries and head, not the freshness of a
complete filesystem rollback. No existing archive is removed or overwritten.
"""
import hashlib
import hmac
import json
import os
import re
import sqlite3
import tempfile
import threading
import time
import uuid
from contextlib import contextmanager, closing
from pathlib import Path
from encrypted_backup import encrypt_backup, decrypt_backup, key_for
from data_safety import verified_backup, restore_workspace
from workspace_integrity import inspect_database

BACKUP_INTERVAL=6*3600
VERIFY_INTERVAL=24*3600
ARCHIVE_PATTERN=re.compile(r'protected-[a-f0-9]{32}\.cvbackup')
GENESIS='0'*64

def digest(path):
    hasher=hashlib.sha256()
    with path.open('rb') as stream:
        while block:=stream.read(1024*1024): hasher.update(block)
    return hasher.hexdigest()

def mac(key,kind,value):
    payload=json.dumps([kind,value],ensure_ascii=True,separators=(',',':'),sort_keys=True).encode()
    return hmac.new(key,payload,hashlib.sha256).hexdigest()

class ProtectedBackups:
    def __init__(self,database,recovery):
        self.database=Path(database)
        self.recovery=recovery
        self.root=self.database.parent/'protected-backups'
        self.catalog=self.root/'catalog.sqlite3'
        self.lock=threading.RLock()
        self.stop=threading.Event()
        self.password=None
        self.key=None
        self.next_backup=0
        self.next_verify=0
        self.status='locked'
        self.rows=[]
        self.orphans=[]
        self.thread=None

    def start(self):
        self.thread=threading.Thread(target=self.run,daemon=True)
        self.thread.start()

    def close(self):
        self.stop.set()
        if self.thread is not None: self.thread.join()
        self.lock_session()

    def lock_session(self):
        with self.lock:
            self.password=None
            self.key=None
            self.rows=[]
            self.orphans=[]
            self.status='locked'

    def paths_safe(self):
        if self.root.is_symlink() or self.catalog.is_symlink():
            raise ValueError('Invalid protected backup directory.')

    @contextmanager
    def connect(self):
        self.paths_safe()
        with closing(sqlite3.connect(self.catalog,timeout=20)) as c:
            c.execute('PRAGMA synchronous=FULL')
            c.row_factory=sqlite3.Row
            with c: yield c

    def archives(self):
        return sorted(p.name for p in self.root.glob('protected-*.cvbackup') if ARCHIVE_PATTERN.fullmatch(p.name))

    def unlock(self,password,initialize=False):
        if not isinstance(password,str) or not 16<=len(password)<=1024: raise ValueError('Use a backup passphrase of at least 16 characters.')
        with self.lock:
            if self.key is not None: raise ValueError('Lock the current session first.')
            self.paths_safe()
            if not self.catalog.exists():
                if not initialize or self.archives(): raise ValueError('Protected catalog missing; existing archives preserved.')
                self.root.mkdir(mode=0o700,exist_ok=True)
                salt=os.urandom(16)
                key=key_for(password,salt)
                with self.connect() as c:
                    c.execute('BEGIN IMMEDIATE')
                    c.execute('CREATE TABLE catalog_meta(id INTEGER PRIMARY KEY CHECK(id=1), salt BLOB NOT NULL, verifier TEXT NOT NULL, count INTEGER NOT NULL, head TEXT NOT NULL, seal TEXT NOT NULL)')
                    c.execute('CREATE TABLE entries(seq INTEGER PRIMARY KEY, archive TEXT UNIQUE NOT NULL, bytes INTEGER NOT NULL, sha256 TEXT NOT NULL, created INTEGER NOT NULL, previous TEXT NOT NULL, signature TEXT NOT NULL)')
                    c.execute('INSERT INTO catalog_meta VALUES(1,?,?,?,?,?)',(salt,mac(key,'verifier',1),0,GENESIS,mac(key,'head',[0,GENESIS])))
            else:
                with self.connect() as c:
                    m=c.execute('SELECT * FROM catalog_meta WHERE id=1').fetchone()
                    if m is None or len(m['salt'])!=16: raise ValueError('Invalid protected catalog.')
                    key=key_for(password,m['salt'])
                    if not hmac.compare_digest(m['verifier'],mac(key,'verifier',1)): raise ValueError('Incorrect passphrase or damaged catalog.')
            # Authenticate catalog before accepting the passphrase for periodic work.
            self.key=key
            self.password=password
            try:
                self.verify()
            except BaseException:
                self.lock_session()
                raise
            self.next_backup=0
            self.next_verify=time.monotonic()+VERIFY_INTERVAL
            return self.snapshot()

    def validated_rows(self,c):
        if self.key is None: raise ValueError('Protected backups are locked.')
        meta=c.execute('SELECT * FROM catalog_meta WHERE id=1').fetchone()
        if meta is None or not hmac.compare_digest(meta['seal'],mac(self.key,'head',[meta['count'],meta['head']])):
            raise ValueError('Catalog authentication failed.')
        rows=[]; previous=GENESIS
        for row in c.execute('SELECT * FROM entries ORDER BY seq'):
            item=dict(row)
            signature=item.pop('signature')
            if item['seq']!=len(rows)+1 or item['previous']!=previous or not ARCHIVE_PATTERN.fullmatch(item['archive']) or not hmac.compare_digest(signature,mac(self.key,'entry',item)):
                raise ValueError('Catalog authentication failed.')
            previous=signature
            rows.append(dict(item,signature=signature))
        if len(rows)!=meta['count'] or previous!=meta['head']: raise ValueError('Catalog authentication failed.')
        return rows,previous

    def archive_path(self,identifier):
        if not isinstance(identifier,str) or not ARCHIVE_PATTERN.fullmatch(identifier): raise ValueError('Invalid protected archive identifier.')
        path=self.root/identifier
        if path.is_symlink() or not path.is_file(): raise ValueError('Protected archive unavailable.')
        return path

    def verify(self):
        with self.lock:
            if self.key is None or not self.catalog.is_file(): raise ValueError('Protected backups are locked or unavailable.')
            try:
                with self.connect() as c:
                    c.execute('BEGIN')
                    rows,_=self.validated_rows(c)
            except (ValueError,sqlite3.Error,OSError):
                self.rows=[]
                self.orphans=[]
                self.status='attention'
                raise
            results=[]
            for item in rows:
                try:
                    path=self.archive_path(item['archive'])
                    ok=path.stat().st_size==item['bytes'] and hmac.compare_digest(digest(path),item['sha256'])
                    status='ok' if ok else 'failed'
                except (OSError,ValueError): status='unavailable'
                results.append({k:item[k] for k in ('archive','bytes','created')}|{'status':status})
            self.rows=results
            self.orphans=sorted(set(self.archives())-{x['archive'] for x in rows})
            self.status='verified' if all(x['status']=='ok' for x in results) and not self.orphans else 'attention'
            self.next_verify=time.monotonic()+VERIFY_INTERVAL
            return self.snapshot()

    def snapshot(self):
        with self.lock:
            self.paths_safe()
            return {'configured':self.catalog.exists(),'unlocked':self.key is not None,'status':self.status,'archives':list(self.rows),'orphans':list(self.orphans),'interval_hours':6}

    def create(self):
        with self.lock:
            if self.key is None or not self.catalog.is_file(): raise ValueError('Protected backups are locked or unavailable.')
            with self.connect() as c:
                c.execute('BEGIN')
                self.validated_rows(c)
            # Temporary SQLite snapshot remains private, never published as a plain backup.
            with tempfile.TemporaryDirectory(prefix='.cv-stage-',dir=self.root) as tmp:
                plain=verified_backup(self.database,Path(tmp))
                if plain is None or inspect_database(plain,True)!='ok': raise ValueError('Backup validation failed.')
                identifier='protected-'+uuid.uuid4().hex+'.cvbackup'
                archive=encrypt_backup(plain,self.root/identifier,self.password)
                size=archive.stat().st_size
                sha=digest(archive)
            # Archive is durable before its authenticated catalog transaction.
            # A crash in this gap leaves a recoverable orphan, never an overwritten archive.
            with self.connect() as c:
                c.execute('BEGIN IMMEDIATE')
                rows,previous=self.validated_rows(c)
                entry={'seq':len(rows)+1,'archive':identifier,'bytes':size,'sha256':sha,'created':int(time.time()),'previous':previous}
                signature=mac(self.key,'entry',entry)
                c.execute('INSERT INTO entries VALUES(?,?,?,?,?,?,?)',(*entry.values(),signature))
                c.execute('UPDATE catalog_meta SET count=?,head=?,seal=? WHERE id=1',(entry['seq'],signature,mac(self.key,'head',[entry['seq'],signature])))
            self.next_backup=time.monotonic()+BACKUP_INTERVAL
            self.verify()
            return identifier

    def verified_archive(self,identifier):
        if self.key is None or not self.catalog.is_file(): raise ValueError('Protected backups are locked or unavailable.')
        with self.connect() as c:
            c.execute('BEGIN')
            rows,_=self.validated_rows(c)
        entry=next((x for x in rows if x['archive']==identifier),None)
        if entry is None: raise ValueError('Archive is not authenticated by this catalog.')
        path=self.archive_path(identifier)
        if path.stat().st_size!=entry['bytes'] or not hmac.compare_digest(digest(path),entry['sha256']):
            raise ValueError('Protected archive integrity check failed.')
        return path

    def restore(self,identifier):
        with self.lock,self.recovery.lock:
            source=self.verified_archive(identifier)
            root=self.recovery.recovered
            if root.is_symlink(): raise ValueError('Invalid recovery directory.')
            root.mkdir(mode=0o700,exist_ok=True)
            with tempfile.TemporaryDirectory(prefix='.cv-protected-restore-',dir=root) as tmp:
                plain=decrypt_backup(source,Path(tmp)/'authenticated.sqlite3',self.password)
                name='recovery-'+uuid.uuid4().hex
                restore_workspace(plain,root/name)
            return name

    @contextmanager
    def download(self,identifier):
        with self.lock:
            yield self.verified_archive(identifier)

    def before_import(self):
        with self.lock:
            if self.key is not None:
                self.create()
            else:
                # Keep the existing fail-closed safety net while the user key is unavailable.
                verified_backup(self.database)

    def tick(self):
        with self.lock:
            if self.key is None: return
            try:
                now=time.monotonic()
                if now>=self.next_verify: self.verify()
                if now>=self.next_backup: self.create()
            except Exception:
                # Report failure, retain all archives, retry only after a bounded interval.
                self.status='attention'
                self.next_backup=time.monotonic()+300
                self.next_verify=time.monotonic()+300

    def run(self):
        while not self.stop.wait(5):
            self.tick()
