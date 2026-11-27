"""Public Croatian registry synchronization and SQLite snapshot repository."""
import csv
import hashlib
import io
import json
import re
import threading
from contextlib import nullcontext
from core import Stopped, formula_safe
from registry_access import credentials, configured, RegistryAccess
from registry_client import BASE, TOKEN_URL, SPEC_URL, Client, TransientRegistryError

__all__ = ['credentials', 'configured', 'RegistryAccess', 'BASE', 'TOKEN_URL',
           'SPEC_URL', 'Client', 'TransientRegistryError', 'NAME', 'catalog',
           'rows_of', 'normalized_id', 'Registry', 'start_registry']

NAME=re.compile(r'^[a-z][a-z0-9_]*$')

def catalog(spec):
    def resolve(p):
        if '$ref' in p:
            ref=p['$ref'];
            if not ref.startswith('#/'): raise ValueError('Nepodržana vanjska referenca OpenAPI-ja.')
            p=spec
            for k in ref[2:].split('/'): p=p[k.replace('~1','/').replace('~0','~')]
        return p
    out={}
    for path, item in spec['paths'].items():
        name=path.rstrip('/').split('/')[-1]
        if not NAME.fullmatch(name) or name in ('snapshots','counts','detalji_subjekta','open_api') or 'get' not in item: continue
        # Do not use legacy, restricted or parameterized paths.
        if path not in ('/'+name,'/api/javni/'+name,'/javni/'+name): continue
        params={}
        for raw in item.get('parameters',[])+item['get'].get('parameters',[]):
            p=resolve(raw)
            if p.get('in')=='query': params[p['name']]=p
        if 'snapshot_id' not in params: continue
        if any(p.get('required') and k not in ('snapshot_id','limit','offset','only_active','expand_relations','omit_nulls') for k,p in params.items()): continue
        out[name]=set(params)
    if 'subjekti' not in out: raise ValueError('OpenAPI ne sadrži očekivanu javnu metodu subjekti.')
    return dict(sorted(out.items(),key=lambda kv:(kv[0]!='subjekti',kv[0])))

def rows_of(payload):
    if isinstance(payload,list): rows=payload
    elif isinstance(payload,dict):
        candidates=[v for v in payload.values() if isinstance(v,list)]
        if len(candidates)!=1: raise ValueError('Nepoznata struktura JSON odgovora.')
        rows=candidates[0]
    else: raise ValueError('Nepoznata struktura JSON odgovora.')
    if any(not isinstance(x,dict) for x in rows): raise ValueError('Neispravan redak API-ja.')
    return rows

def normalized_id(v,width):
    s=str(v if v is not None else '')
    return s.zfill(width) if s.isascii() and s.isdigit() and len(s)<=width else ''

class Registry:
    def __init__(self,store):
        self.store=store
        with store.db() as c:
            c.executescript('''CREATE TABLE IF NOT EXISTS registry_runs(snapshot TEXT PRIMARY KEY, manifest TEXT NOT NULL, complete INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS registry_pages(snapshot TEXT NOT NULL, category TEXT NOT NULL, offset INTEGER NOT NULL, n INTEGER NOT NULL, digest TEXT NOT NULL, PRIMARY KEY(snapshot,category,offset));
            CREATE INDEX IF NOT EXISTS registry_page_digest ON registry_pages(snapshot,category,digest);
            CREATE TABLE IF NOT EXISTS registry_rows(snapshot TEXT NOT NULL, category TEXT NOT NULL, ordinal INTEGER NOT NULL, mbs TEXT NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(snapshot,category,ordinal));
            CREATE INDEX IF NOT EXISTS registry_mbs ON registry_rows(snapshot,mbs,category);
            CREATE TABLE IF NOT EXISTS registry_progress(snapshot TEXT NOT NULL, category TEXT NOT NULL, next_offset INTEGER NOT NULL, done INTEGER NOT NULL, total INTEGER, PRIMARY KEY(snapshot,category));''')
    def summary(self):
        with self.store.db() as c:
            runs=[dict(r) for r in c.execute('SELECT snapshot,complete FROM registry_runs ORDER BY CAST(snapshot AS INTEGER) DESC')]; categories=[dict(r) for r in c.execute('SELECT snapshot,category,next_offset AS rows,done,total FROM registry_progress ORDER BY CAST(snapshot AS INTEGER) DESC,category')]
        return {'runs':runs,'categories':categories}
    def browse(self,snapshot,category,page=1,limit=50,q=''):
        with self.store.db() as c:
            query=q.strip()[:200]
            if query:
                args=(snapshot,category,query,normalized_id(query,9))
                total=c.execute('SELECT count(*) FROM registry_rows WHERE snapshot=? AND category=? AND (instr(lower(payload),lower(?))>0 OR mbs=?)',args).fetchone()[0]
                cursor=c.execute('SELECT payload FROM registry_rows WHERE snapshot=? AND category=? AND (instr(lower(payload),lower(?))>0 OR mbs=?) ORDER BY ordinal LIMIT ? OFFSET ?',(*args,limit,(page-1)*limit))
            else:
                total=c.execute('SELECT count(*) FROM registry_rows WHERE snapshot=? AND category=?',(snapshot,category)).fetchone()[0]
                cursor=c.execute('SELECT payload FROM registry_rows WHERE snapshot=? AND category=? ORDER BY ordinal LIMIT ? OFFSET ?',(snapshot,category,limit,(page-1)*limit))
            rows=[json.loads(r[0]) for r in cursor]
        return {'total':total,'rows':rows}
    def export_rows(self,snapshot,category):
        if not str(snapshot).isdigit() or not NAME.fullmatch(category): raise ValueError('Neispravna kategorija.')
        with self.store.db() as c:
            for r in c.execute('SELECT payload FROM registry_rows WHERE snapshot=? AND category=? ORDER BY ordinal',(snapshot,category)):
                yield (r[0]+'\n').encode('utf-8')
    def export_csv(self,snapshot,category):
        # Preserve the union of fields across pages, including fields absent from the first record.
        with self.store.db() as c:
            c.execute('BEGIN')
            sql='SELECT payload FROM registry_rows WHERE snapshot=? AND category=? ORDER BY ordinal'
            keys=list(dict.fromkeys(k for r in c.execute(sql,(snapshot,category)) for k in json.loads(r[0])))
            f=io.StringIO(newline=''); w=csv.writer(f)
            def line(values):
                f.seek(0); f.truncate(0); w.writerow(values); return f.getvalue().encode('utf-8')
            yield b'\xef\xbb\xbf'+line([formula_safe(k) for k in keys])
            for r in c.execute(sql,(snapshot,category)):
                d=json.loads(r[0]); values=[]
                for k in keys:
                    v=d.get(k)
                    if k.lower() in ('mbs','oib') and v is not None: v=normalized_id(v,9 if k.lower()=='mbs' else 11) or v
                    if isinstance(v,(list,dict)): v=json.dumps(v,ensure_ascii=False)
                    values.append(formula_safe(str(v) if v is not None else ''))
                yield line(values)
    def _repair_category(self,bot,client,snap,name,params):
        """Repair only missing rows covered by immutable saved page receipts."""
        with self.store.db() as c:
            progress=c.execute('SELECT next_offset,done,total FROM registry_progress WHERE snapshot=? AND category=?',(snap,name)).fetchone()
            actual,first,last=c.execute('SELECT count(*),min(ordinal),max(ordinal) FROM registry_rows WHERE snapshot=? AND category=?',(snap,name)).fetchone()
            pages=c.execute('SELECT offset,n,digest FROM registry_pages WHERE snapshot=? AND category=? ORDER BY offset',(snap,name)).fetchall()
        if progress is None:
            if actual or pages: raise ValueError('Uncheckpointed registry rows; existing data retained.')
            return False
        offset,done,total=progress
        if type(offset) is not int or type(total) is not int or not 0<=offset<=total or done not in (0,1) or bool(done)!=(offset==total):
            raise ValueError('Invalid registry checkpoint; existing data retained.')
        end=0
        paged={'offset','limit'}<=params
        for start,count,digest in pages:
            if type(start) is not int or type(count) is not int or start!=end or not 0<=count<=offset-end or (paged and count>1000) or (count==0 and offset!=0) or not isinstance(digest,str) or not re.fullmatch(r'[a-f0-9]{64}',digest):
                raise ValueError('Invalid registry page receipts; existing data retained.')
            end+=count
        if not pages or end!=offset or actual>offset or (actual and (first<0 or last>=offset)):
            raise ValueError('Inconsistent registry checkpoint; existing data retained.')
        with bot.lock: bot.state['reused']=bot.state.get('reused',0)+actual
        if actual==offset:
            return False
        # A missing row is recoverable only from its original snapshot and page.
        # Mark incomplete before repair; a failure must never leave a complete claim.
        with self.store.db() as c:
            c.execute('UPDATE registry_runs SET complete=0 WHERE snapshot=?',(snap,))
        repaired=0
        for start,count,digest in pages:
            bot.wait(0)
            with self.store.db() as c:
                found=c.execute('SELECT count(*) FROM registry_rows WHERE snapshot=? AND category=? AND ordinal>=? AND ordinal<?',(snap,name,start,start+count)).fetchone()[0]
            if found==count: continue
            q=self._page_query(snap,params,start,count)
            h,p=client.get(name,q); rows=self._page_rows(h,p,params)
            if str(h.get('X-Snapshot-Id',''))!=snap or len(rows)!=count or (paged and int(h.get('X-Total-Count',-1))!=total):
                raise ValueError('Repair snapshot or page count mismatch; existing data retained.')
            if 'X-Rows-Returned' in h and int(h['X-Rows-Returned'])!=count:
                raise ValueError('Repair response count mismatch.')
            if self._page_digest(rows)!=digest:
                raise ValueError('Repair page checksum mismatch; existing data retained.')
            with self.store.db() as c:
                c.execute('BEGIN IMMEDIATE')
                saved=dict((r[0],(r[1],json.loads(r[2]))) for r in c.execute('SELECT ordinal,mbs,payload FROM registry_rows WHERE snapshot=? AND category=? AND ordinal>=? AND ordinal<?',(snap,name,start,start+count)))
                missing=[]
                for i,row in enumerate(rows,start):
                    mbs=normalized_id(row.get('mbs'),9)
                    if i in saved:
                        if saved[i]!=(mbs,row): raise ValueError('Existing registry row conflicts with repair; retained.')
                    else:
                        missing.append((snap,name,i,mbs,json.dumps(row,ensure_ascii=False)))
                c.executemany('INSERT INTO registry_rows VALUES (?,?,?,?,?)',missing)
                repaired+=len(missing)
            with bot.lock: bot.state['processed']+=count
        with bot.lock: bot.state['repaired']=bot.state.get('repaired',0)+repaired
        bot.log(f'Repaired {repaired} missing registry rows in {name}.')
        return bool(repaired)

    @staticmethod
    def _page_query(snap,params,offset,limit):
        q={'snapshot_id':snap}
        if {'offset','limit'}<=params:q.update(offset=offset,limit=limit)
        if 'only_active' in params:q['only_active']='false'
        if 'expand_relations' in params:q['expand_relations']='true'
        if 'omit_nulls' in params:q['omit_nulls']='false'
        if 'no_data_error' in params:q['no_data_error']='0'
        return q

    @staticmethod
    def _page_rows(headers,payload,params):
        # The public API explicitly permits an empty object for no_data_error=0.
        # Require a confirming zero-row header; never mistake an error object for data.
        if payload=={} and 'no_data_error' in params and str(headers.get('X-Rows-Returned',''))=='0':
            return []
        return rows_of(payload)

    @staticmethod
    def _page_digest(rows):
        return hashlib.sha256(json.dumps(rows,sort_keys=True,ensure_ascii=False).encode()).hexdigest()

    def sync(self,bot,client,limit=500,*,pinned_snapshot=None,allow_full_refresh=True):
        spec=client.spec(); cats=catalog(spec)
        _,payload=client.get('snapshots'); snaps=rows_of(payload)
        latest=next((x for x in snaps if str(x.get('staleness'))=='1'),None)
        if latest is None: raise ValueError('Nema označene najnovije snimke.')
        snap=str(latest.get('snapshot_id',latest.get('id','')))
        if not snap.isdigit(): raise ValueError('Nedostaje identifikator snimke.')
        manifest=json.dumps({k:sorted(v|({'scope:all'} if 'only_active' in v else set())) for k,v in cats.items()},sort_keys=True)
        # Prefer an unfinished snapshot still advertised by the server; never mix snapshots.
        available={str(x.get('snapshot_id',x.get('id',''))) for x in snaps}
        with self.store.db() as c:
            pending=c.execute('SELECT snapshot FROM registry_runs WHERE complete=0 AND manifest=? ORDER BY CAST(snapshot AS INTEGER) DESC',(manifest,)).fetchall()
        if pinned_snapshot is not None:
            if pinned_snapshot not in available: raise ValueError('Saved distribution snapshot is no longer available. Existing data retained.')
            snap=pinned_snapshot
        else:
            snap=next((r[0] for r in pending if r[0] in available),snap)
        with self.store.db() as c:
            old=c.execute('SELECT * FROM registry_runs WHERE snapshot=?',(snap,)).fetchone()
            prior=c.execute('SELECT snapshot FROM registry_runs ORDER BY CAST(snapshot AS INTEGER) DESC LIMIT 1').fetchone()
            if old is None and prior is not None and not allow_full_refresh:
                bot.update(update_available=snap,local_snapshot=prior[0])
                bot.log('A different registry snapshot is available. Full refresh requires explicit confirmation.')
                return False
            if old and old['manifest']!=manifest: raise ValueError('Specifikacija se promijenila tijekom snimke; potreban je novi snapshot.')
            was_complete=bool(old and old['complete'])
            projected_current=bool(c.execute('SELECT 1 FROM meta WHERE key=? AND value=?',('registry_projection:'+snap,'2')).fetchone())
            c.execute('INSERT OR IGNORE INTO registry_runs(snapshot,manifest) VALUES (?,?)',(snap,manifest))
        bot.update(last=len(cats),phase='download',snapshot_id=snap); bot.log(f'Snimka {snap} · {len(cats)} skupnih kategorija')
        repaired=False
        for index,(name,params) in enumerate(cats.items(),1):
            bot.update(page=index); bot.log(f'{name} · {index}/{len(cats)}')
            try:
                repaired=self._repair_category(bot,client,snap,name,params) or repaired
            except ValueError:
                with self.store.db() as c:c.execute('UPDATE registry_runs SET complete=0 WHERE snapshot=?',(snap,))
                raise
            with self.store.db() as c: old=c.execute('SELECT * FROM registry_progress WHERE snapshot=? AND category=?',(snap,name)).fetchone()
            if was_complete and (not old or not old['done']):
                with self.store.db() as c:c.execute('UPDATE registry_runs SET complete=0 WHERE snapshot=?',(snap,))
                was_complete=False
            if old and old['done']: continue
            offset=old['next_offset'] if old else 0; total=old['total'] if old else None; paged={'offset','limit'}<=params
            while True:
                bot.wait(0); q=self._page_query(snap,params,offset,limit)
                h,p=client.get(name,q); rows=self._page_rows(h,p,params)
                if str(h.get('X-Snapshot-Id',''))!=snap: raise ValueError('Snapshot zaglavlje ne odgovara traženoj snimci.')
                if 'X-Rows-Returned' in h and int(h['X-Rows-Returned'])!=len(rows): raise ValueError('Broj redaka ne odgovara zaglavlju.')
                if paged:
                    if 'X-Total-Count' not in h: raise ValueError('Nedostaje X-Total-Count; sinkronizacija zaustavljena.')
                    count=int(h['X-Total-Count'])
                    if total is not None and count!=total: raise ValueError('Ukupan broj redaka se promijenio.')
                    total=count
                    if offset+len(rows)>total or len(rows)>limit or (not rows and offset<total): raise ValueError('Nekonzistentna paginacija.')
                else: total=len(rows)
                digest=self._page_digest(rows); nxt=offset+len(rows); done=nxt==total
                with self.store.db() as c:
                    if rows and c.execute('SELECT 1 FROM registry_pages WHERE snapshot=? AND category=? AND digest=?',(snap,name,digest)).fetchone(): raise ValueError('API ponavlja istu stranicu.')
                    c.executemany('INSERT INTO registry_rows VALUES (?,?,?,?,?)',[(snap,name,offset+i,normalized_id(row.get('mbs'),9),json.dumps(row,ensure_ascii=False)) for i,row in enumerate(rows)])
                    c.execute('INSERT INTO registry_pages VALUES (?,?,?,?,?)',(snap,name,offset,len(rows),digest))
                    c.execute('INSERT INTO registry_progress VALUES (?,?,?,?,?) ON CONFLICT(snapshot,category) DO UPDATE SET next_offset=excluded.next_offset,done=excluded.done,total=excluded.total',(snap,name,nxt,int(done),total))
                with bot.lock: bot.state['processed']+=len(rows)
                offset=nxt
                if done: break
        if was_complete and not repaired and projected_current:
            bot.log('Snimka registra već je preuzeta i obrađena.')
            bot.update(phase='complete')
            return True
        # The directory projection and completed marker commit atomically.
        # Existing readers retain their previous consistent SQLite snapshot.
        with self.store.db() as c:
            self.merge(snap,bot,connection=c)
            bot.update(phase='finalizing')
            missing=c.execute("SELECT count(*) FROM registry_rows r WHERE r.snapshot=? AND r.category='subjekti' AND r.mbs<>'' AND NOT EXISTS (SELECT 1 FROM companies c WHERE c.mbs=r.mbs)",(snap,)).fetchone()[0]
            if missing: raise ValueError('Poslovni imenik nije potpun: '+str(missing))
            c.execute('UPDATE registry_runs SET complete=1 WHERE snapshot=?',(snap,))
        bot.update(phase='complete')
        return True
    def merge(self,snap,bot,connection=None):
        # Keep original payloads; project documented v3 fields into the directory.
        def value(record,*keys):
            for key in keys:
                v=record.get(key)
                if isinstance(v,(str,int)) and not isinstance(v,bool) and str(v).strip():
                    return str(v).strip()
                if isinstance(v,dict):
                    nested=value(v,'naziv','ime')
                    if nested: return nested
            return ''
        def related(c,mbs,category):
            if category not in available:
                return
            for rr in c.execute("SELECT payload FROM registry_rows INDEXED BY registry_mbs WHERE snapshot=? AND mbs=? AND category=? ORDER BY ordinal",(snap,mbs,category)):
                yield json.loads(rr[0])
        with (self.store.db() if connection is None else nullcontext(connection)) as c:
            # Avoid millions of empty index probes in partial/offline snapshots.
            available={name for name in ('tvrtke','nazivi','skracene_tvrtke','sjedista','email_adrese','pretezite_djelatnosti') if c.execute('SELECT 1 FROM registry_rows WHERE snapshot=? AND category=? LIMIT 1',(snap,name)).fetchone()}
            # The official codebook is small (6,400 rows in snapshot 1370).
            # Keep its revision alongside each code; never mix different NKD revisions.
            nkd={}
            for rr in c.execute("SELECT payload FROM registry_rows WHERE snapshot=? AND category='nacionalna_klasifikacija_djelatnosti' ORDER BY ordinal",(snap,)):
                reference=json.loads(rr[0])
                key=value(reference,'id')
                label=' · '.join(filter(None,[value(reference,'verzija'),value(reference,'sifra'),value(reference,'puni_naziv')]))
                if key and label:
                    if len(nkd)>=50000 and key not in nkd: raise ValueError('Prevelik NKD šifrarnik.')
                    if key in nkd and nkd[key]!=label: raise ValueError('Proturječan NKD šifrarnik.')
                    nkd[key]=label
            total=c.execute("SELECT count(*) FROM registry_rows WHERE snapshot=? AND category='subjekti'",(snap,)).fetchone()[0]
            bot.update(phase='projection',projected=0,projection_total=total,snapshot_id=snap)
            for projected,r in enumerate(c.execute("SELECT payload FROM registry_rows WHERE snapshot=? AND category='subjekti' ORDER BY ordinal",(snap,)),1):
                bot.wait(0)
                if projected%512==0: bot.update(projected=projected-1)
                d=json.loads(r[0]); mbs=normalized_id(d.get('mbs'),9); oib=normalized_id(d.get('oib'),11)
                if not mbs:
                    bot.inc('skipped')
                    continue
                title=value(d,'tvrtka_naziv','naziv','tvrtka','skracena_tvrtka')
                if not title:
                    for category in ('tvrtke','nazivi','skracene_tvrtke'):
                        title=next((name for x in related(c,mbs,category)
                                    if (name:=value(x,'ime','naziv','tvrtka','tvrtka_naziv'))),'')
                        if title: break
                if not title:
                    title=value(d,'tvrtka_kod_brisanja')
                if not title:
                    # Some official subjects have no published name. Preserve the subject
                    # with its real identifier; never invent a legal company name.
                    known=c.execute('SELECT title FROM companies WHERE mbs=? LIMIT 1',(mbs,)).fetchone()
                    title=known[0] if known and known[0] else 'MBS '+mbs
                row={'title':title,'mbs':mbs,'oib':oib}
                founded=value(d,'datum_osnivanja')
                if re.match(r'^\d{4}(?:-|$)',founded): row['year']=founded[:4]
                for a in related(c,mbs,'sjedista'):
                    if str(a.get('status',1))!='1': continue
                    number=value(a,'kucni_broj')
                    suffix=value(a,'kucni_podbroj')
                    row.update(city=value(a,'naziv_naselja','naselje_naziv','naselje','grad','naselje_van_sifrarnika'),
                               country=value(a,'drzava_naziv','drzava'),
                               address=' '.join(filter(None,[value(a,'ulica','ulica_naziv','adresa'),number+suffix])),
                               postal=normalized_id(a.get('postanski_broj'),5))
                    if not row['country'] and 'drzava_id' in a and a['drzava_id'] is None:
                        row['country']='Hrvatska'
                    break
                # Keep all public e-mail rows in the raw snapshot; directory uses the first.
                email=next((address for e in related(c,mbs,'email_adrese')
                            if str(e.get('status',1))=='1' and (address:=value(e,'adresa'))),'')
                if email: row['email']=email
                # Assign a category only when the authoritative relation is unambiguous.
                if nkd:
                    industries={nkd[key] for relation in related(c,mbs,'pretezite_djelatnosti')
                                if (key:=value(relation,'nacionalna_klasifikacija_djelatnosti_id')) in nkd}
                    if len(industries)==1: row['industry']=next(iter(industries))
                if self.store.upsert(c,row,provider='registry',origin=BASE+'/subjekti'): bot.inc('added')
            c.execute("INSERT INTO meta(key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",('registry_projection:'+snap,'2'))
            bot.update(projected=total)

def start_registry(bot,registry,creds,limit=500,check=False,*,pinned_snapshot=None,allow_full_refresh=True):
    if not all(creds): raise ValueError('Nedostaje privatna konfiguracija poslovnih podataka.')
    if not 1<=limit<=1000: raise ValueError('Veličina stranice mora biti 1–1000.')
    with bot.lock:
        if bot.state['status'] in ('running','stopping'): raise ValueError('Prikupljanje je već aktivno.')
        bot.stop_event.clear(); bot.state={'status':'running','kind':'registry-check' if check else 'registry','page':0,'last':0,'processed':0,'added':0,'skipped':0,'errors':0,'logs':[]}
    def run():
        client=Client(bot,creds)
        try:
            if check:
                client.auth(); bot.log('OAuth2 autentikacija uspješna.')
                cats=catalog(client.spec()); _,data=client.get('snapshots'); snaps=rows_of(data)
                if not snaps: raise ValueError('API nije vratio dostupne snimke.')
                bot.log(f'API dostupan · {len(cats)} kategorija · {len(snaps)} snimki.')
            else: registry.sync(bot,client,limit,pinned_snapshot=pinned_snapshot); bot.log('Sinkronizacija završena.')
            bot.update(status='completed')
        except Stopped: bot.update(status='stopped'); bot.log('Zaustavljeno. Spremljene stranice ostaju dostupne.')
        except Exception as e: bot.inc('errors'); bot.update(status='failed',retryable=isinstance(e,TransientRegistryError)); bot.log(str(e) if isinstance(e,(ValueError,PermissionError)) else 'Pogreška: '+type(e).__name__)
        finally: client.close()
    threading.Thread(target=run,daemon=True).start()
