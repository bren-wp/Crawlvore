"""Local company directory storage and polite, resumable source collection."""
import csv
import json
import io
import re
import sqlite3
import threading
import time
import unicodedata
from contextlib import contextmanager
from urllib.parse import urlencode, urljoin, urlsplit
from urllib.robotparser import RobotFileParser

import requests
from network import public_session
from bs4 import BeautifulSoup

FIELDS = ['Title','Logo URL','Website URL','Social URL','Street Address','Postal Code','City','Country','Phone Number','Phone/Fax','Responsible Person','Year of Establishment','Number of Employees','Account Number','Mbs Number','Rating Value','Description','Product/Company Description']
COLS = ['title','logo','website','social','address','postal','city','country','phone','fax','person','year','employees','account','mbs','rating','description','products']
BASE = 'https://www.tvrtke.hr/'
UA = 'Crawlvora/7.0 (local directory tool)'

def norm(s):
    return ' '.join(unicodedata.normalize('NFC', str(s or '')).casefold().split())

def source_url(s):
    u = urlsplit(urljoin(BASE, s or ''))
    if u.scheme != 'https' or u.netloc.lower() not in ('www.tvrtke.hr','tvrtke.hr'):
        raise ValueError('URL izvan dopuštenog izvora.')
    return u._replace(fragment='').geturl()

def link(s):
    try:
        u = urlsplit(urljoin(BASE, s))
        return u.geturl() if s and u.scheme in ('http','https') and u.hostname and not u.username and not u.password else ''
    except ValueError:
        return ''

def txt(node):
    return node.get_text(' ', strip=True) if node else ''

def parse_detail(html, title):
    s = BeautifulSoup(html, 'html.parser')
    def pick(q): return txt(s.select_one(q))
    def strip_label(q, label):
        return re.sub(r'^\s*'+label+r'\s*:\s*','',pick(q),flags=re.I)
    if not s.select_one('[id^="FirmaPodaci_"]'):
        raise ValueError('Struktura profila nije prepoznata; zapis nije spremljen.')
    logo = s.select_one('#FirmaPodaci_divLogo amp-img, #FirmaPodaci_divLogo img')
    logo = logo.get('src','') if logo else ''
    urls = [link(a.get('href','')) for a in s.select('#FirmaPodaci_divWeb a.linkWWW')]
    urls = [u for u in urls if u]
    return dict(zip(COLS, [title.strip(), link(logo) if 'no-logo.png' not in logo else '', urls[0] if urls else '', urls[1] if len(urls)>1 else '',pick('#FirmaPodaci_divAdresa'),pick('#FirmaPodaci_divMjesto [itemprop="postalCode"]'),pick('#FirmaPodaci_divMjesto [itemprop="addressLocality"]'),pick('#FirmaPodaci_divMjesto [itemprop="addressCountry"]'),pick('a.linkTel [itemprop="telephone"]') or pick('a.linkTel'),pick('#FirmaPodaci_divTelFax [itemprop="telephone"]'),pick('#FirmaPodaci_divKontaktOsoba span'),pick('#FirmaPodaci_divGodinaOsnivanja [itemprop="foundingDate"]'),pick('[itemprop="numberOfEmployees"]'),strip_label('#FirmaPodaci_divBrojRacuna','Broj računa'),strip_label('#FirmaPodaci_divRegistracijskiBroj','MBS'),pick('[itemprop="ratingValue"]'),pick('.divShortDesc.txtCenter.rows4'),pick('#FirmaProizvodi_divOpis')]))

def parse_listing(html):
    s = BeautifulSoup(html, 'html.parser')
    items = {}
    for card in s.select('div.divItemSlide2.roundCorners2.divShadow.divInline.txtLeft'):
        for a in card.select('a[href][title]'):
            title = a.get('title','').strip()
            href = a.get('href','').strip()
            if not title or not href or href.startswith(('#','javascript:','mailto:','tel:')): continue
            try: u = source_url(href)
            except ValueError: continue
            if 'rezultati-pretrage' in u.casefold(): continue
            items.setdefault(u,title)
    nums = [int(t) for a in s.select('.divPager a.pager2, .divPager span') if (t:=txt(a)).isdigit()]
    return list(items.items()), max(nums,default=1)

def formula_safe(v):
    return "'"+v if v.lstrip().startswith(('=','+','-','@','\t','\r','\n')) or v.startswith(('\t','\r','\n')) else v

class Store:
    def __init__(self,path):
        self.path = str(path)
        with self.db() as c:
            c.execute('PRAGMA journal_mode=WAL')
            c.execute('CREATE TABLE IF NOT EXISTS companies (id INTEGER PRIMARY KEY, identity TEXT UNIQUE NOT NULL, source TEXT UNIQUE, '+','.join(k+" TEXT NOT NULL DEFAULT ''" for k in COLS)+', search_text TEXT NOT NULL DEFAULT \'\')')
            c.execute('CREATE INDEX IF NOT EXISTS idx_city ON companies(city)')
            c.execute('CREATE INDEX IF NOT EXISTS idx_title ON companies(title COLLATE NOCASE)')
            c.execute('CREATE INDEX IF NOT EXISTS idx_city_title ON companies(city,title COLLATE NOCASE,id)')
            c.execute('CREATE TABLE IF NOT EXISTS completed (job TEXT, url TEXT, PRIMARY KEY(job,url))')
            c.execute('CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)')
            existing={r[1] for r in c.execute('PRAGMA table_info(companies)')}
            for col in ('oib','email','industry'):
                if col not in existing: c.execute(f"ALTER TABLE companies ADD COLUMN {col} TEXT NOT NULL DEFAULT ''")
            c.execute("CREATE INDEX IF NOT EXISTS idx_oib ON companies(oib)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_mbs ON companies(mbs)")
            c.execute("CREATE TABLE IF NOT EXISTS origins (company_id INTEGER NOT NULL, provider TEXT NOT NULL, url TEXT NOT NULL DEFAULT '', updated TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY(company_id,provider,url), FOREIGN KEY(company_id) REFERENCES companies(id))")
            c.execute('CREATE TABLE IF NOT EXISTS company_history(id INTEGER PRIMARY KEY,company_id INTEGER NOT NULL,provider TEXT NOT NULL,changed_at TEXT DEFAULT CURRENT_TIMESTAMP,changes TEXT NOT NULL)')
            c.execute('CREATE INDEX IF NOT EXISTS history_company ON company_history(company_id,id DESC)')
            c.execute('CREATE INDEX IF NOT EXISTS history_changed_at ON company_history(changed_at)')
            c.execute('CREATE TABLE IF NOT EXISTS alternate_values(company_id INTEGER NOT NULL, field TEXT NOT NULL, value TEXT NOT NULL, provider TEXT NOT NULL, observed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY(company_id,field,value,provider), FOREIGN KEY(company_id) REFERENCES companies(id))')
            c.execute('CREATE INDEX IF NOT EXISTS origin_provider ON origins(provider,company_id)')
            # The derived index and its maintenance triggers commit together.
            c.execute('SAVEPOINT search_index')
            try:
                c.execute("CREATE VIRTUAL TABLE IF NOT EXISTS company_fts USING fts5(search_text, content='companies', content_rowid='id', tokenize='unicode61')")
                c.execute("""CREATE TRIGGER IF NOT EXISTS company_fts_insert AFTER INSERT ON companies BEGIN
                    INSERT INTO company_fts(rowid,search_text) VALUES(new.id,new.search_text); END""")
                c.execute("""CREATE TRIGGER IF NOT EXISTS company_fts_delete AFTER DELETE ON companies BEGIN
                    INSERT INTO company_fts(company_fts,rowid,search_text) VALUES('delete',old.id,old.search_text); END""")
                c.execute("""CREATE TRIGGER IF NOT EXISTS company_fts_update AFTER UPDATE OF search_text ON companies WHEN old.search_text<>new.search_text BEGIN
                    INSERT INTO company_fts(company_fts,rowid,search_text) VALUES('delete',old.id,old.search_text);
                    INSERT INTO company_fts(rowid,search_text) VALUES(new.id,new.search_text); END""")
                if not c.execute("SELECT 1 FROM meta WHERE key='fts_v1'").fetchone():
                    c.execute("INSERT INTO company_fts(company_fts) VALUES('rebuild')")
                    c.execute("INSERT INTO meta VALUES('fts_v1','1')")
                self.fts_available=True
            except sqlite3.OperationalError as error:
                c.execute('ROLLBACK TO search_index')
                if 'no such module: fts5' not in str(error).lower(): raise
                # An existing FTS database must not be opened for writes by an incompatible runtime.
                if c.execute("SELECT 1 FROM meta WHERE key='fts_v1'").fetchone(): raise
                self.fts_available=False
            finally:
                c.execute('RELEASE search_index')
            if not c.execute("SELECT 1 FROM meta WHERE key='origins_v2'").fetchone():
                c.execute("INSERT OR IGNORE INTO origins(company_id,provider,url) SELECT id,CASE WHEN source IS NULL THEN 'csv' ELSE 'tvrtke' END,coalesce(source,'') FROM companies")
                c.execute("INSERT INTO meta VALUES ('origins_v2','1')")
    @contextmanager
    def db(self):
        c=sqlite3.connect(self.path,timeout=20)
        c.row_factory=sqlite3.Row
        c.execute("PRAGMA foreign_keys=ON")
        c.execute("PRAGMA synchronous=FULL")
        try:
            with c: yield c
        finally: c.close()
    def upsert(self,c,row,source=None,provider=None,origin=None):
        cols=COLS+['oib','email','industry']
        vals={k:str(row.get(k) or '').strip() for k in cols}
        if not vals['title']: return False
        # An OIB must be a valid 11-digit identifier with the ISO 7064 checksum.
        oib=re.sub(r'\s','',vals['oib'])
        if re.fullmatch(r'[0-9]{11}',oib):
            a=10
            for digit in oib[:10]: a=((a+int(digit))%10 or 10)*2%11
            vals['oib']=oib if (11-a)%10==int(oib[-1]) else ''
        else: vals['oib']=''
        raw_mbs=vals['mbs']
        if re.fullmatch(r'[0-9]{1,9}',raw_mbs): vals['mbs']=raw_mbs.zfill(9)
        identity=norm(vals['title'])+'\x1f'+norm(vals['city'])
        old=c.execute('SELECT * FROM companies WHERE source=?',(source,)).fetchone() if source else None
        if not old and re.fullmatch(r'[0-9]{9}',vals['mbs']):
            matches=c.execute('SELECT * FROM companies WHERE mbs IN (?,?,?,?,?,?,?,?,?) LIMIT 2',tuple(vals['mbs'][i:] if not vals['mbs'][:i].strip('0') else vals['mbs'] for i in range(9))).fetchall()
            if len(matches)==1 and (not vals['oib'] or not matches[0]['oib'] or vals['oib']==matches[0]['oib']):
                old=matches[0]
            elif len(matches)>1:
                raise ValueError('Ambiguous MBS; existing records preserved.')
            elif matches:
                raise ValueError('Conflicting OIB and MBS; existing records preserved.')
        if not old and vals['oib']:
            matches=c.execute('SELECT * FROM companies WHERE oib=? LIMIT 2',(vals['oib'],)).fetchall()
            if len(matches)==1 and not (provider=='registry' and vals['mbs'] and matches[0]['mbs'] and vals['mbs']!=matches[0]['mbs'].zfill(9)): old=matches[0]
        if old and vals['oib'] and old['oib'] and vals['oib']!=old['oib']: raise ValueError('Sukob OIB identifikatora; zapis nije spojen.')
        if not old and provider=='registry' and vals['mbs']:
            if vals['city'] and vals['address']:
                candidate=c.execute('SELECT * FROM companies WHERE identity=?',(identity,)).fetchone()
                if candidate and norm(candidate['address'])==norm(vals['address']) and (not candidate['oib'] or candidate['oib']==vals['oib']) and (not candidate['mbs'] or candidate['mbs'].zfill(9)==vals['mbs']):
                    old=candidate
        if not old and provider=='registry' and vals['mbs']:
            old=c.execute("SELECT * FROM companies WHERE mbs=? AND EXISTS (SELECT 1 FROM origins WHERE company_id=companies.id AND provider='registry')",(vals['mbs'],)).fetchone()
            identity='registry\x1f'+vals['mbs']
        if not old and (provider!='registry' or not vals['mbs']):
            old=c.execute('SELECT * FROM companies WHERE identity=?',(identity,)).fetchone()
            if old and vals['oib'] and old['oib'] and vals['oib']!=old['oib']:
                identity+='\x1f'+vals['oib']; old=c.execute('SELECT * FROM companies WHERE identity=?',(identity,)).fetchone()
        if old and vals['oib'] and old['oib'] and vals['oib']!=old['oib']: raise ValueError('Sukob OIB identifikatora; zapis nije spojen.')
        if old and provider=='registry' and vals['mbs'] and old['mbs'] and vals['mbs']!=old['mbs'].zfill(9): raise ValueError('Sukob MBS identifikatora; zapis nije spojen.')
        if old and vals['mbs'] and old['mbs'] and vals['mbs'].zfill(9)!=old['mbs'].zfill(9):
            raise ValueError('Conflicting MBS; existing records preserved.')
        if old:
            # Preserve differing incoming values even when the directory prefers an existing contact.
            for key,value in vals.items():
                if value and old[key] and value!=old[key]:
                    c.execute('INSERT OR IGNORE INTO alternate_values(company_id,field,value,provider) VALUES (?,?,?,?)',(old['id'],key,value,provider or ('tvrtke' if source else 'csv')))
            official={'title','mbs','oib','city','country','address'}
            vals={k:(vals[k] or old[k]) if provider=='registry' and k in official else (old[k] or vals[k]) for k in cols}
            changes={k:{'before':old[k],'after':v} for k,v in vals.items() if old[k]!=v}
            if changes: c.execute('INSERT INTO company_history(company_id,provider,changes) VALUES (?,?,?)',(old['id'],provider or ('tvrtke' if source else 'csv'),json.dumps(changes,ensure_ascii=False)))
            if changes or (source and not old['source']): c.execute('UPDATE companies SET title=?,logo=?,website=?,social=?,address=?,postal=?,city=?,country=?,phone=?,fax=?,person=?,year=?,employees=?,account=?,mbs=?,rating=?,description=?,products=?,oib=?,email=?,industry=?,source=?,search_text=? WHERE id=?',(*vals.values(),old['source'] or source,norm(' '.join(vals.values())),old['id']))
            i=old['id']
        else:
            i=c.execute('INSERT INTO companies(identity,source,title,logo,website,social,address,postal,city,country,phone,fax,person,year,employees,account,mbs,rating,description,products,oib,email,industry,search_text) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(identity,source,*vals.values(),norm(' '.join(vals.values())))).lastrowid
        c.execute("INSERT INTO origins(company_id,provider,url) VALUES (?,?,?) ON CONFLICT(company_id,provider,url) DO UPDATE SET updated=CURRENT_TIMESTAMP",(i,provider or ('tvrtke' if source else 'csv'),origin or source or ''))
        return not bool(old)
    def history(self,i):
        with self.db() as c: return [dict(r,changes=json.loads(r['changes'])) for r in c.execute('SELECT id,provider,changed_at,changes FROM company_history WHERE company_id=? ORDER BY id DESC LIMIT 100',(i,))]
    def providers(self):
        with self.db() as c: return [dict(r) for r in c.execute('SELECT provider,count(DISTINCT company_id) n FROM origins GROUP BY provider ORDER BY provider')]
    def import_json(self,raw):
        data=__import__('json').loads(raw)
        if not isinstance(data,list) or any(not isinstance(r,dict) or not isinstance(r.get('title'),str) or not r['title'].strip() for r in data): raise ValueError('JSON mora biti lista objekata s poljem title.')
        with self.db() as c:
            c.execute('BEGIN IMMEDIATE')
            added=sum(self.upsert(c,{k:v for k,v in r.items() if isinstance(v,(str,int,float))},provider='csv') for r in data)
        return {'read':len(data),'added':added}
    def export_json(self,**filters):
        where,args=self.where(**filters)
        with self.db() as c:
            c.execute('BEGIN')
            rows=[dict(r) for r in c.execute('SELECT id,title,logo,website,social,address,postal,city,country,phone,fax,person,year,employees,account,mbs,rating,description,products,oib,email,industry FROM companies'+where+' ORDER BY id',args)]  # nosec B608 -- Store.where returns only fixed clauses; all data is bound, sort is allowlisted.
            # Limit metadata reads to the selected IDs; fixed-size batches avoid SQLite variable limits.
            by_id={r['id']:r for r in rows}
            for r in rows:
                r['sources']=[]
                r['alternate_values']=[]
            ids=list(by_id)
            for start in range(0,len(ids),500):
                batch=ids[start:start+500]
                placeholders=','.join('?' for _ in batch)
                for r in c.execute('SELECT company_id,provider,url,updated FROM origins WHERE company_id IN ('+placeholders+') ORDER BY company_id,provider,url',batch):  # nosec B608 -- placeholders only, bound integer IDs.
                    by_id[r['company_id']]['sources'].append({k:r[k] for k in ('provider','url','updated')})
                for r in c.execute('SELECT company_id,field,value,provider,observed_at FROM alternate_values WHERE company_id IN ('+placeholders+') ORDER BY company_id,field,provider,value',batch):  # nosec B608 -- placeholders only, bound integer IDs.
                    by_id[r['company_id']]['alternate_values'].append({k:r[k] for k in ('field','value','provider','observed_at')})
        return __import__('json').dumps(rows,ensure_ascii=False,indent=2).encode()
    def import_csv(self,stream):
        with self.db() as c:
            c.execute('BEGIN IMMEDIATE')
            return self._import_csv(c,stream)
    def _import_csv(self,c,stream):
        reader=csv.DictReader(stream)
        if not reader.fieldnames or not set(FIELDS).issubset(reader.fieldnames): raise ValueError('CSV ne sadrži očekivanih 18 stupaca.')
        count=added=0
        for row in reader:
            if None in row or any(row.get(k) is None for k in FIELDS): raise ValueError(f'Neispravan CSV redak {reader.line_num}.')
            count+=1; added+=self.upsert(c,dict(zip(COLS,(row[k] for k in FIELDS)),oib=row.get('OIB',''),email=row.get('Email',''),industry=row.get('Industry','')))
        return {'read':count,'added':added}
    def seed(self,path):
        with self.db() as c:
            c.execute('BEGIN IMMEDIATE')
            if c.execute("SELECT 1 FROM meta WHERE key='seeded'").fetchone(): return
            with open(path,encoding='utf-8-sig',newline='') as f: self._import_csv(c,f)
            c.execute("INSERT INTO meta VALUES ('seeded','1')")
    def analytics(self):
        # Local observations, not inferred business growth or fabricated register events.
        with self.db() as c:
            days=[dict(r) for r in c.execute("SELECT substr(changed_at,1,10) AS day, count(*) AS n FROM company_history WHERE changed_at >= datetime('now','-30 days') GROUP BY day ORDER BY day")]
        return {'days':days}
    def stats(self):
        with self.db() as c:
            c.execute('BEGIN')
            r=c.execute("SELECT count(*) total,count(DISTINCT NULLIF(city,'')) cities,count(NULLIF(phone,'')) phones,count(NULLIF(website,'')) websites FROM companies").fetchone()
            cities=[dict(x) for x in c.execute("SELECT city,count(*) n FROM companies WHERE city<>'' GROUP BY city ORDER BY n DESC,city LIMIT 6")]
            return dict(r,top_cities=cities)
    def where(self,q='',city='',contact='',provider=''):
        # SQL fragments below are fixed literals; user input is only bound as parameters.
        clauses=[]; args=[]
        # Explicit identifier prefixes use existing indexes; ordinary text semantics stay unchanged.
        text=norm(q)
        if text.startswith('oib:') and re.fullmatch(r'[0-9]{11}',text[4:].strip()):
            clauses.append('oib=?'); args.append(text[4:].strip())
        elif text.startswith('mbs:') and re.fullmatch(r'[0-9]{1,9}',text[4:].strip()):
            mbs=text[4:].strip().zfill(9)
            clauses.append('mbs IN (?,?,?,?,?,?,?,?,?)')
            args.extend(mbs[i:] if not mbs[:i].strip('0') else mbs for i in range(9))
        elif text.startswith('fts:'):
            phrase=text[4:].strip()
            if not phrase or len(phrase)>200 or '\x00' in phrase: raise ValueError('Invalid full-text query.')
            if self.fts_available:
                clauses.append('id IN (SELECT rowid FROM company_fts WHERE company_fts MATCH ?)')
                args.append('"'+phrase.replace('"','""')+'"')
            else:
                clauses.append('instr(search_text,?)>0'); args.append(phrase)
        elif q: clauses.append('instr(search_text,?)>0'); args.append(text)
        if city: clauses.append('city=?'); args.append(city)
        if provider: clauses.append('EXISTS (SELECT 1 FROM origins WHERE company_id=companies.id AND provider=?)'); args.append(provider)
        if contact=='phone': clauses.append("phone<>''")
        elif contact=='web': clauses.append("website<>''")
        elif contact=='missing': clauses.append("phone='' AND website=''")
        return (' WHERE '+' AND '.join(clauses) if clauses else ''),args
    def query(self,q='',city='',contact='',page=1,limit=25,sort='title',provider=''):
        where,args=self.where(q,city,contact,provider)
        order={'title':'title COLLATE NOCASE ASC,id','title_desc':'title COLLATE NOCASE DESC,id','city':'city COLLATE NOCASE,title COLLATE NOCASE,id','new':'id DESC'}.get(sort,'id')
        with self.db() as c:
            c.execute('BEGIN')
            total=c.execute('SELECT count(*) FROM companies'+where,args).fetchone()[0]  # nosec B608 -- Store.where returns only fixed clauses; all data is bound, sort is allowlisted.
            rows=c.execute('SELECT id,title,city,address,postal,phone,website,description,oib,email,industry,(SELECT group_concat(DISTINCT provider) FROM origins WHERE company_id=companies.id) providers FROM companies'+where+' ORDER BY '+order+' LIMIT ? OFFSET ?',(*args,limit,(page-1)*limit))  # nosec B608 -- Store.where returns only fixed clauses; all data is bound, sort is allowlisted.
            return {'total':total,'rows':[dict(r) for r in rows]}
    def cities(self):
        with self.db() as c: return [r[0] for r in c.execute("SELECT DISTINCT city FROM companies WHERE city<>'' ORDER BY city COLLATE NOCASE")]
    def detail(self,i):
        with self.db() as c:
            c.execute('BEGIN')
            r=c.execute('SELECT * FROM companies WHERE id=?',(i,)).fetchone()
            if not r: return None
            sources=[dict(x) for x in c.execute('SELECT provider,url,updated FROM origins WHERE company_id=? ORDER BY provider,url',(i,))]
            alternatives=[dict(x) for x in c.execute('SELECT field,value,provider,observed_at FROM alternate_values WHERE company_id=? ORDER BY field,provider,value',(i,))]
            return dict({k:r[k] for k in ['id','source',*COLS,'oib','email','industry']},sources=sources,alternate_values=alternatives)
    def export(self,**filters):
        where,args=self.where(**filters); out=io.StringIO(newline=''); w=csv.writer(out); w.writerow(FIELDS+['OIB','Email','Industry','Sources'])
        with self.db() as c:
            for r in c.execute('SELECT '+','.join(COLS+['oib','email','industry'])+",coalesce((SELECT group_concat(DISTINCT provider) FROM origins WHERE company_id=companies.id),'') FROM companies"+where+' ORDER BY id',args): w.writerow([formula_safe(v) for v in r])  # nosec B608 -- Store.where returns only fixed clauses; all data is bound, sort is allowlisted.
        return out.getvalue().encode('utf-8-sig')
    def done(self,job,url):
        with self.db() as c: return bool(c.execute('SELECT 1 FROM completed WHERE job=? AND url=?',(job,url)).fetchone())
    def save(self,job,url,row):
        with self.db() as c:
            added=self.upsert(c,row,url); c.execute('INSERT OR IGNORE INTO completed VALUES (?,?)',(job,url)); return added

class Stopped(Exception): pass

class Collector:
    def __init__(self,store):
        self.store=store; self.lock=threading.Lock(); self.stop_event=threading.Event(); self.state={'status':'idle','page':0,'last':0,'processed':0,'added':0,'skipped':0,'errors':0,'logs':[]}; self.last_request=0
    def snapshot(self):
        with self.lock: return dict(self.state,logs=list(self.state['logs']))
    def update(self,**kw):
        with self.lock: self.state.update(kw)
    def log(self,s):
        with self.lock: self.state['logs']=(self.state['logs']+[time.strftime('%H:%M:%S')+'  '+s])[-100:]
    def inc(self,k):
        with self.lock: self.state[k]+=1
    def start(self,term,start,end,delay,resume=True):
        with self.lock:
            if self.state['status'] in ('running','stopping'): raise ValueError('Prikupljanje je već aktivno.')
            self.stop_event.clear(); self.state={'status':'running','kind':'tvrtke','page':start,'last':end or start,'processed':0,'added':0,'skipped':0,'errors':0,'logs':[]}
        threading.Thread(target=self.run,args=(term,start,end,delay,resume),daemon=True).start()
    def stop(self):
        with self.lock:
            if self.state['status']=='running': self.state['status']='stopping'; self.stop_event.set()
    def wait(self,n):
        if self.stop_event.wait(max(0,n)): raise Stopped()
    def fetch(self,session,url,delay,robots=None):
        url=source_url(url)
        for attempt in range(3):
            self.wait(delay-(time.monotonic()-self.last_request))
            if robots and not robots.can_fetch(UA,url): raise PermissionError('robots.txt ne dopušta pristup ovoj adresi.')
            self.last_request=time.monotonic()
            try:
                with session.get(url,timeout=(8,20),allow_redirects=False,stream=True) as r:
                    if r.status_code in (401,403,429): raise PermissionError(f'Izvor je odbio ili ograničio pristup (HTTP {r.status_code}); prikupljanje zaustavljeno.')
                    if 300<=r.status_code<400: raise ValueError('Izvor je vratio preusmjerenje; provjerite adresu izvora.')
                    r.raise_for_status()
                    chunks=[]; size=0
                    for b in r.iter_content(65536):
                        self.wait(0); size+=len(b)
                        if size>8*1024*1024: raise ValueError('Odgovor izvora je prevelik.')
                        chunks.append(b)
                    return b''.join(chunks).decode(r.encoding or 'utf-8',errors='replace')
            except requests.RequestException as e:
                if attempt==2 or (getattr(e,'response',None) is not None and e.response.status_code<500): raise
                self.wait(2**(attempt+1))
        raise RuntimeError('Neuspjelo preuzimanje.')
    def run(self,term,start,end,delay,resume):
        job=norm(term)
        try:
            with public_session() as session:
                session.headers.update({'User-Agent':UA,'Accept':'text/html,application/xhtml+xml,text/plain','Accept-Language':'hr,en;q=0.8'})
                # Fail closed if the source policy cannot be retrieved.
                rp=RobotFileParser(); rp.set_url(urljoin(BASE,'robots.txt')); rp.parse(self.fetch(session,rp.url,delay).splitlines())
                delay=max(delay,rp.crawl_delay(UA) or 0,rp.crawl_delay('*') or 0)
                page=start; last=end or start; seen_pages=set()
                while page<=last:
                    self.update(page=page,last=last); self.log(f'Stranica {page}')
                    url=urljoin(BASE,'Rezultati-pretrage,PID-4.aspx')+'?'+urlencode({'M':'','Z':'0','D':'0','P':'','F':term,'stranica':page})
                    items,found=parse_listing(self.fetch(session,url,delay,rp))
                    if not items: raise ValueError('Nema prepoznatih rezultata; provjerite upit i strukturu izvora.')
                    signature=tuple(u for u,_ in items)
                    if signature in seen_pages: raise ValueError('Izvor ponavlja istu stranicu; prikupljanje zaustavljeno.')
                    seen_pages.add(signature); last=max(last,found) if end is None else min(end,max(page,found)); self.update(last=last)
                    for u,title in items:
                        self.wait(0)
                        if resume and self.store.done(job,u): self.inc('skipped'); continue
                        try:
                            row=parse_detail(self.fetch(session,u,delay,rp),title)
                            if self.store.save(job,u,row): self.inc('added')
                            self.inc('processed')
                        except (requests.RequestException,ValueError) as e:
                            self.inc('errors'); self.log(f'Preskočeno: {title[:80]} — {type(e).__name__}: {e}')
                    page+=1
            self.update(status='completed_with_errors' if self.snapshot()['errors'] else 'completed'); self.log('Prikupljanje završeno.')
        except Stopped: self.update(status='stopped'); self.log('Zaustavljeno. Spremljeni zapisi su sačuvani.')
        except Exception as e: self.log(str(e)); self.update(status='failed')
