"""Durable single-worker job queue; credentials are resolved only at execution."""
import json, threading
from datetime import datetime
from registry import start_registry

class Queue:
    def __init__(self,store,bot,registry,credentials,app_version=None,authorized=None):
        self.store,self.bot,self.registry,self.credentials=store,bot,registry,credentials
        self.app_version=app_version
        self.authorized=authorized or (lambda:False)
        self.stop_event=threading.Event(); self.active=None; self.dispatch_lock=threading.Lock()
        with store.db() as c:
            c.executescript('''CREATE TABLE IF NOT EXISTS jobs(id INTEGER PRIMARY KEY,kind TEXT NOT NULL,config TEXT NOT NULL,state TEXT NOT NULL DEFAULT 'queued',created TEXT DEFAULT CURRENT_TIMESTAMP,finished TEXT);
            CREATE TABLE IF NOT EXISTS schedules(id INTEGER PRIMARY KEY CHECK(id=1), enabled INTEGER NOT NULL DEFAULT 0, hour INTEGER NOT NULL DEFAULT 3, last_day TEXT NOT NULL DEFAULT '');
            INSERT OR IGNORE INTO schedules(id) VALUES(1);
            CREATE TABLE IF NOT EXISTS update_sync_policy(id INTEGER PRIMARY KEY CHECK(id=1),enabled INTEGER NOT NULL DEFAULT 0, last_version TEXT NOT NULL DEFAULT '');
            INSERT OR IGNORE INTO update_sync_policy(id) VALUES(1);''')
            cols={r['name'] for r in c.execute('PRAGMA table_info(jobs)')}
            for name,definition in [('scheduled','INTEGER NOT NULL DEFAULT 0'),('attempts','INTEGER NOT NULL DEFAULT 0'),('next_run','INTEGER NOT NULL DEFAULT 0'),('update_version',"TEXT NOT NULL DEFAULT ''")]:
                if name not in cols: c.execute(f'ALTER TABLE jobs ADD COLUMN {name} {definition}')
            c.execute("UPDATE jobs SET state='queued',next_run=0 WHERE state='running' AND update_version<>'' AND attempts<3 AND (SELECT enabled FROM update_sync_policy WHERE id=1)=1")
            c.execute("UPDATE jobs SET state='interrupted',finished=CURRENT_TIMESTAMP WHERE state='running'")
            c.execute("UPDATE jobs SET state='cancelled',finished=CURRENT_TIMESTAMP WHERE kind<>'registry' AND state IN ('queued','retry_wait')")
    def enqueue(self,kind,config):
        if kind!='registry' or not isinstance(config,dict) or config.get('permission') is not True: raise ValueError('Dopušteni su samo ovlašteni zadaci osvježavanja poslovnih podataka.')
        limit=int(config.get('limit',500))
        if not 1<=limit<=1000: raise ValueError('Invalid registry page size.')
        config={'permission':True,'limit':limit}
        raw=json.dumps(config,ensure_ascii=False)
        if len(raw)>30000: raise ValueError('Konfiguracija je prevelika.')
        with self.store.db() as c: return {'id':c.execute('INSERT INTO jobs(kind,config) VALUES (?,?)',(kind,raw)).lastrowid}
    def schedule(self,enabled,hour):
        if type(enabled) is not bool or not 0<=hour<=23: raise ValueError('Neispravno vrijeme.')
        with self.store.db() as c: c.execute('UPDATE schedules SET enabled=?,hour=? WHERE id=1',(enabled,hour))
        return self.summary()
    def update_policy(self,enabled,permission=False):
        if type(enabled) is not bool:raise ValueError("Neispravna postavka.")
        if enabled and (permission is not True or not self.authorized()):
            raise ValueError("Potrebno je ovlaštenje za automatsko preuzimanje novih podataka.")
        with self.dispatch_lock:
            with self.store.db() as c:
                c.execute("UPDATE update_sync_policy SET enabled=? WHERE id=1",(enabled,))
                if not enabled:
                    c.execute("UPDATE jobs SET state='cancelled',finished=CURRENT_TIMESTAMP WHERE update_version<>'' AND state IN ('queued','retry_wait')")
        return self.summary()

    def summary(self):
        with self.store.db() as c: return {'jobs':[dict(r) for r in c.execute('SELECT id,kind,state,created,finished,scheduled,attempts,next_run FROM jobs ORDER BY id DESC LIMIT 100')],'schedule':dict(c.execute('SELECT * FROM schedules WHERE id=1').fetchone()),'update_sync':dict(c.execute('SELECT enabled,last_version FROM update_sync_policy WHERE id=1').fetchone())}
    def cancel(self,i):
        with self.store.db() as c: c.execute("UPDATE jobs SET state='cancelled',finished=CURRENT_TIMESTAMP WHERE id=? AND state IN ('queued','retry_wait')",(int(i),))
        return {'ok':True}
    def direct(self,fn):
        with self.dispatch_lock:
            if self.active is not None: raise ValueError('Red zadataka upravlja aktivnom operacijom.')
            return fn()
    def tick(self,now=None):
        with self.dispatch_lock: return self._tick(now)
    def _tick(self,now=None):
        now=now or datetime.now().astimezone(); day=now.date().isoformat(); epoch=int(now.timestamp())
        with self.store.db() as c:
            c.execute('BEGIN IMMEDIATE'); s=c.execute('SELECT * FROM schedules WHERE id=1').fetchone()
            policy=c.execute("SELECT * FROM update_sync_policy WHERE id=1").fetchone()
            if self.app_version and policy['enabled'] and policy['last_version']!=self.app_version and self.authorized():
                from update_verification import version
                prior=policy['last_version']
                if not prior or version(self.app_version)>version(prior):
                    if not c.execute("SELECT 1 FROM jobs WHERE kind='registry' AND state IN ('queued','running','retry_wait')").fetchone():
                        c.execute("INSERT INTO jobs(kind,config,scheduled,update_version) VALUES ('registry',?,1,?)",(json.dumps({'permission':True,'limit':500}),self.app_version))
                        c.execute("UPDATE update_sync_policy SET last_version=? WHERE id=1",(self.app_version,))
            if s['enabled'] and now.weekday()<5 and now.hour>=s['hour'] and s['last_day']!=day:
                if not c.execute("SELECT 1 FROM jobs WHERE kind='registry' AND state IN ('queued','running','retry_wait')").fetchone(): c.execute("INSERT INTO jobs(kind,config,scheduled) VALUES ('registry',?,1)",(json.dumps({'permission':True,'limit':500}),))
                c.execute('UPDATE schedules SET last_day=? WHERE id=1',(day,))
        state=self.bot.snapshot()['status']
        if self.active is not None:
            if state in ('running','stopping'): return
            with self.store.db() as c:
                row=c.execute('SELECT scheduled,attempts FROM jobs WHERE id=?',(self.active,)).fetchone()
                if state=='failed' and self.bot.snapshot().get('retryable') and row['scheduled'] and row['attempts']<3:
                    c.execute("UPDATE jobs SET state='retry_wait',next_run=? WHERE id=?",(epoch+900*4**(row['attempts']-1),self.active))
                else: c.execute('UPDATE jobs SET state=?,finished=CURRENT_TIMESTAMP WHERE id=?',(state,self.active))
            self.active=None
        if state in ('running','stopping'): return
        with self.store.db() as c:
            c.execute('BEGIN IMMEDIATE'); r=c.execute("SELECT * FROM jobs WHERE kind='registry' AND (state='queued' OR (state='retry_wait' AND next_run<=?)) ORDER BY id LIMIT 1",(epoch,)).fetchone()
            if not r: return
            c.execute("UPDATE jobs SET state='running',attempts=attempts+1,next_run=0 WHERE id=?",(r['id'],))
        try:
            d=json.loads(r['config']); k=r['kind']
            if k!='registry': raise ValueError('Unsupported collection source.')
            if r['update_version']:
                with self.store.db() as c:enabled=c.execute("SELECT enabled FROM update_sync_policy WHERE id=1").fetchone()[0]
                if not enabled or not self.app_version or not self.authorized():
                    raise ValueError('Ovlašteno osvježavanje nije dostupno.')
            start_registry(self.bot,self.registry,self.credentials(),d['limit'],allow_full_refresh=bool(r['update_version']))
            self.active=r['id']
        except Exception:
            with self.store.db() as c: c.execute("UPDATE jobs SET state='failed',finished=CURRENT_TIMESTAMP WHERE id=?",(r['id'],))
    def run(self):
        while not self.stop_event.is_set():
            try: self.tick()
            except Exception as e:
                import sys
                print('Queue: '+type(e).__name__,file=sys.stderr)
            self.stop_event.wait(2)
    def start(self): threading.Thread(target=self.run,daemon=True).start()
    def close(self): self.stop_event.set()
