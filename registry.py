"""Public Croatian court registry v3: schema-driven, checkpointed snapshot mirror."""
import json, os, re, time, threading, hashlib, sys, csv, io
from pathlib import Path
from urllib.parse import urlsplit
import requests
from network import public_session
from core import Stopped, UA, formula_safe

BASE='https://sudreg-data.gov.hr/api/javni'
TOKEN_URL='https://sudreg-data.gov.hr/api/oauth/token'
SPEC_URL=BASE+'/dokumentacija/open_api'
NAME=re.compile(r'^[a-z][a-z0-9_]*$')

def credentials(root, data_dir):
    for p in (Path(data_dir)/'sudreg.private.json', Path(root)/'sudreg.private.json', Path(sys.executable).parent/'sudreg.private.json' if getattr(sys,'frozen',False) else Path(root)/'sudreg.private.json', Path.cwd()/'sudreg.private.json'):
        if p.is_file():
            try:
                d=json.loads(p.read_text(encoding='utf-8-sig'))
                if not isinstance(d,dict): raise ValueError()
            except (OSError,ValueError): raise ValueError('Privatna konfiguracija nije valjana.') from None
            break
    else: d={}
    return tuple(v.strip() if isinstance(v,str) else '' for v in (os.getenv('SUDREG_CLIENT_ID',d.get('client_id','')),os.getenv('SUDREG_CLIENT_SECRET',d.get('client_secret',''))))

def configured(root,data_dir):
    try: return all(credentials(root,data_dir))
    except ValueError: return False

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

class TransientRegistryError(ValueError):
    """Retryable network or server failure; never used for access denials."""

class Client:
    def __init__(self,bot,creds,delay=3):
        self.bot=bot; self.creds=creds; self.delay=delay; self.session=public_session(); self.session.trust_env=False; self.token=''; self.expiry=0
        self.session.headers.update({'User-Agent':UA,'Accept':'application/json','Content-Type':'application/json'})
    def close(self): self.session.close()
    def request(self,method,url,**kw):
        if urlsplit(url).netloc!='sudreg-data.gov.hr' or not url.startswith('https://'): raise ValueError('Nedopušten API host.')
        for attempt in range(3):
            self.bot.wait(self.delay-(time.monotonic()-self.bot.last_request)); self.bot.last_request=time.monotonic()
            try:
                with self.session.request(method,url,timeout=(10,60),allow_redirects=False,stream=True,**kw) as r:
                    if r.status_code in (429,403): raise PermissionError(f'Sudski registar: HTTP {r.status_code}. Prikupljanje zaustavljeno.')
                    if r.status_code>=500:
                        if attempt<2: self.bot.wait(2**(attempt+1)); continue
                        raise TransientRegistryError('Privremena pogreška poslužitelja.')
                    chunks=[]; size=0
                    for chunk in r.iter_content(65536):
                        self.bot.wait(0); size+=len(chunk)
                        if size>10*1024*1024: raise ValueError('Odgovor veći od 10 MB; smanjite veličinu stranice.')
                        chunks.append(chunk)
                    try: body=json.loads(b''.join(chunks))
                    except (ValueError,UnicodeError): raise ValueError(f'Sudski registar: neispravan JSON (HTTP {r.status_code}).') from None
                    return r.status_code, r.headers, body
            except requests.RequestException:
                if attempt==2: raise TransientRegistryError('Mrežna pogreška Sudskog registra.') from None
                self.bot.wait(2**(attempt+1))
    def auth(self):
        code,_,body=self.request('POST',TOKEN_URL,auth=self.creds,data={'grant_type':'client_credentials'},headers={'Content-Type':'application/x-www-form-urlencoded'})
        if code!=200 or not isinstance(body,dict) or not isinstance(body.get('access_token'),str) or not body['access_token']: raise ValueError(f'OAuth2 autentikacija nije uspjela (HTTP {code}). Provjerite pristupne podatke.')
        self.token=body['access_token']; self.expiry=time.monotonic()+max(1,int(body.get('expires_in',300))-30)
    def get(self,name,params=None):
        for attempt in range(2):
            if time.monotonic()>=self.expiry: self.auth()
            code,h,b=self.request('GET',BASE+'/'+name,params=params or {},headers={'Authorization':'Bearer '+self.token})
            if code==401 and attempt==0: self.expiry=0; continue
            if code==200: return h,b
            if code==400 and isinstance(b,dict) and str(b.get('error_code'))=='505': return h,[]
            raise ValueError(f'Sudski registar: {name} · HTTP {code}.')
        raise ValueError('Autentikacija nije uspjela.')
    def spec(self):
        code,_,body=self.request('GET',SPEC_URL,headers={'Accept':'application/openapi+json, application/json'})
        if code!=200 or not isinstance(body,dict) or 'paths' not in body: raise ValueError('OpenAPI specifikacija nije dostupna.')
        return body

class Registry:
    def __init__(self,store):
        self.store=store
        with store.db() as c:
            c.executescript('''CREATE TABLE IF NOT EXISTS registry_runs(snapshot TEXT PRIMARY KEY, manifest TEXT NOT NULL, complete INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS registry_pages(snapshot TEXT NOT NULL, category TEXT NOT NULL, offset INTEGER NOT NULL, n INTEGER NOT NULL, digest TEXT NOT NULL, PRIMARY KEY(snapshot,category,offset));
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
    def sync(self,bot,client,limit=500):
        spec=client.spec(); cats=catalog(spec)
        _,payload=client.get('snapshots'); snaps=rows_of(payload)
        latest=next((x for x in snaps if str(x.get('staleness'))=='1'),None)
        if latest is None: raise ValueError('Nema označene najnovije snimke.')
        snap=str(latest.get('snapshot_id',latest.get('id','')))
        if not snap.isdigit(): raise ValueError('Nedostaje identifikator snimke.')
        manifest=json.dumps({k:sorted(v) for k,v in cats.items()},sort_keys=True)
        # Prefer an unfinished snapshot still advertised by the server; never mix snapshots.
        available={str(x.get('snapshot_id',x.get('id',''))) for x in snaps}
        with self.store.db() as c:
            pending=c.execute('SELECT snapshot FROM registry_runs WHERE complete=0 AND manifest=? ORDER BY CAST(snapshot AS INTEGER) DESC',(manifest,)).fetchall()
        snap=next((r[0] for r in pending if r[0] in available),snap)
        with self.store.db() as c:
            old=c.execute('SELECT * FROM registry_runs WHERE snapshot=?',(snap,)).fetchone()
            if old and old['manifest']!=manifest: raise ValueError('Specifikacija se promijenila tijekom snimke; potreban je novi snapshot.')
            if old and old['complete']: bot.log('Najnovija snimka već je preuzeta.'); return
            c.execute('INSERT OR IGNORE INTO registry_runs(snapshot,manifest) VALUES (?,?)',(snap,manifest))
        bot.update(last=len(cats)); bot.log(f'Snimka {snap} · {len(cats)} skupnih kategorija')
        for index,(name,params) in enumerate(cats.items(),1):
            bot.update(page=index); bot.log(f'{name} · {index}/{len(cats)}')
            with self.store.db() as c: old=c.execute('SELECT * FROM registry_progress WHERE snapshot=? AND category=?',(snap,name)).fetchone()
            if old and old['done']: continue
            offset=old['next_offset'] if old else 0; total=old['total'] if old else None; paged={'offset','limit'}<=params
            while True:
                bot.wait(0); q={'snapshot_id':snap}
                if paged: q.update(offset=offset,limit=limit)
                if 'expand_relations' in params: q['expand_relations']='true'
                if 'omit_nulls' in params: q['omit_nulls']='false'
                h,p=client.get(name,q); rows=rows_of(p)
                if str(h.get('X-Snapshot-Id',''))!=snap: raise ValueError('Snapshot zaglavlje ne odgovara traženoj snimci.')
                if 'X-Rows-Returned' in h and int(h['X-Rows-Returned'])!=len(rows): raise ValueError('Broj redaka ne odgovara zaglavlju.')
                if paged:
                    if 'X-Total-Count' not in h: raise ValueError('Nedostaje X-Total-Count; sinkronizacija zaustavljena.')
                    count=int(h['X-Total-Count'])
                    if total is not None and count!=total: raise ValueError('Ukupan broj redaka se promijenio.')
                    total=count
                    if offset+len(rows)>total or len(rows)>limit or (not rows and offset<total): raise ValueError('Nekonzistentna paginacija.')
                else: total=len(rows)
                digest=hashlib.sha256(json.dumps(rows,sort_keys=True,ensure_ascii=False).encode()).hexdigest(); nxt=offset+len(rows); done=nxt==total
                with self.store.db() as c:
                    if rows and c.execute('SELECT 1 FROM registry_pages WHERE snapshot=? AND category=? AND digest=?',(snap,name,digest)).fetchone(): raise ValueError('API ponavlja istu stranicu.')
                    c.executemany('INSERT INTO registry_rows VALUES (?,?,?,?,?)',[(snap,name,offset+i,normalized_id(row.get('mbs'),9),json.dumps(row,ensure_ascii=False)) for i,row in enumerate(rows)])
                    c.execute('INSERT INTO registry_pages VALUES (?,?,?,?,?)',(snap,name,offset,len(rows),digest))
                    c.execute('INSERT INTO registry_progress VALUES (?,?,?,?,?) ON CONFLICT(snapshot,category) DO UPDATE SET next_offset=excluded.next_offset,done=excluded.done,total=excluded.total',(snap,name,nxt,int(done),total))
                with bot.lock: bot.state['processed']+=len(rows)
                offset=nxt
                if done: break
        self.merge(snap,bot)
        with self.store.db() as c: c.execute('UPDATE registry_runs SET complete=1 WHERE snapshot=?',(snap,))
    def merge(self,snap,bot):
        # Keep original registry records intact. Add only named business entities to directory.
        with self.store.db() as c:
            for r in c.execute("SELECT payload FROM registry_rows WHERE snapshot=? AND category='subjekti' ORDER BY ordinal",(snap,)):
                bot.wait(0); d=json.loads(r[0]); mbs=normalized_id(d.get('mbs'),9); oib=normalized_id(d.get('oib'),11)
                title=next((d[k] for k in ('tvrtka_naziv','naziv','tvrtka','skracena_tvrtka') if isinstance(d.get(k),str) and d[k].strip()),'')
                if not title and mbs:
                    for rr in c.execute("SELECT payload FROM registry_rows WHERE snapshot=? AND mbs=? AND category IN ('tvrtke','nazivi','skracene_tvrtke')",(snap,mbs)):
                        x=json.loads(rr[0]); title=next((x[k] for k in ('naziv','tvrtka','tvrtka_naziv') if isinstance(x.get(k),str) and x[k].strip()),'')
                        if title: break
                if not title or not mbs: continue
                row={'title':title,'mbs':mbs,'oib':oib}
                for rr in c.execute("SELECT payload FROM registry_rows WHERE snapshot=? AND mbs=? AND category='sjedista'",(snap,mbs)):
                    a=json.loads(rr[0]); status=a.get('status',1)
                    if str(status)!='1': continue
                    def val(*keys):
                        for k in keys:
                            v=a.get(k)
                            if isinstance(v,(str,int)) and str(v).strip(): return str(v)
                            if isinstance(v,dict) and isinstance(v.get('naziv'),str): return v['naziv']
                        return ''
                    row.update(city=val('naselje_naziv','naselje','grad'),country=val('drzava_naziv','drzava'),address=' '.join(filter(None,[val('ulica','ulica_naziv','adresa'),val('kucni_broj')]))); break
                # Use public registry MBS for stable identity; avoid merging distinct legal entities by name.
                if self.store.upsert(c,row,provider='registry',origin=BASE+'/subjekti'): bot.inc('added')

def start_registry(bot,registry,creds,limit=500,check=False):
    if not all(creds): raise ValueError('Nedostaje privatna konfiguracija Sudskog registra.')
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
            else: registry.sync(bot,client,limit); bot.log('Sinkronizacija završena.')
            bot.update(status='completed')
        except Stopped: bot.update(status='stopped'); bot.log('Zaustavljeno. Spremljene stranice ostaju dostupne.')
        except Exception as e: bot.inc('errors'); bot.update(status='failed',retryable=isinstance(e,TransientRegistryError)); bot.log(str(e) if isinstance(e,(ValueError,PermissionError)) else 'Pogreška: '+type(e).__name__)
        finally: client.close()
    threading.Thread(target=run,daemon=True).start()
