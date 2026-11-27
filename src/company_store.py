"""SQLite company repository; existing schema and transactions are preserved."""
import csv
import io
import json
import re
import sqlite3
from contextlib import contextmanager
from company_fields import COLS, FIELDS, ENTITY_KINDS, norm, formula_safe
from duplicate_review import archived_target

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
            for col in ('oib','email','industry','entity_kind'):
                if col not in existing: c.execute(f"ALTER TABLE companies ADD COLUMN {col} TEXT NOT NULL DEFAULT ''")
            c.execute("CREATE INDEX IF NOT EXISTS idx_entity_kind ON companies(entity_kind)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_industry_title ON companies(industry,title COLLATE NOCASE,id)")
            c.execute("DROP INDEX IF EXISTS idx_industry")
            c.execute("CREATE INDEX IF NOT EXISTS idx_email_present_title ON companies(title COLLATE NOCASE,id) WHERE email<>''")
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
        entity_kind=str(row.get('entity_kind') or '')
        if entity_kind and entity_kind not in ENTITY_KINDS: raise ValueError('Invalid entity classification.')
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
        if not old and provider!='registry':
            old=archived_target(c,identity,source,vals,entity_kind)
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
        if entity_kind and entity_kind!='unknown':
            current=c.execute('SELECT entity_kind FROM companies WHERE id=?',(i,)).fetchone()[0]
            if current not in ('','unknown',entity_kind): raise ValueError('Conflicting entity classification; existing data preserved.')
            c.execute('UPDATE companies SET entity_kind=? WHERE id=?',(entity_kind,i))
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
            count+=1; added+=self.upsert(c,dict(zip(COLS,(row[k] for k in FIELDS)),oib=row.get('OIB',''),email=row.get('Email',''),industry=row.get('Industry',''),entity_kind=row.get('Entity Type','')))
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
    def where(self,q='',city='',contact='',provider='',entity_kind='',industry=''):
        # SQL fragments below are fixed literals; user input is only bound as parameters.
        clauses=[]; args=[]
        # Recognize plain identifiers automatically; retain explicit legacy prefixes.
        # Exact indexed matches avoid false positives in phones, addresses and descriptions.
        text=norm(q)
        candidate=text[4:].strip() if text.startswith(('oib:','mbs:')) else text
        digits=re.sub(r'[ -]','',candidate)
        numeric=bool(re.fullmatch(r'[0-9]+',digits))
        if numeric and len(digits)==11 and not text.startswith('mbs:'):
            clauses.append('oib=?'); args.append(digits)
        elif numeric and 1<=len(digits)<=9 and not text.startswith('oib:'):
            mbs=digits.zfill(9)
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
        if entity_kind:
            if entity_kind not in ENTITY_KINDS: raise ValueError('Invalid entity classification.')
            if entity_kind=='unknown': clauses.append("entity_kind IN ('','unknown')")
            else: clauses.append('entity_kind=?'); args.append(entity_kind)
        if industry: clauses.append('industry=?'); args.append(industry)
        if city: clauses.append('city=?'); args.append(city)
        if provider: clauses.append('EXISTS (SELECT 1 FROM origins WHERE company_id=companies.id AND provider=?)'); args.append(provider)
        if contact=='phone': clauses.append("phone<>''")
        elif contact=='web': clauses.append("website<>''")
        elif contact=='email': clauses.append("email<>''")
        elif contact=='missing': clauses.append("phone='' AND website=''")
        return (' WHERE '+' AND '.join(clauses) if clauses else ''),args
    def query(self,q='',city='',contact='',page=1,limit=25,sort='title',provider='',entity_kind='',industry=''):
        where,args=self.where(q,city,contact,provider,entity_kind,industry)
        order={'title':'title COLLATE NOCASE ASC,id','title_desc':'title COLLATE NOCASE DESC,id','city':'city COLLATE NOCASE,title COLLATE NOCASE,id','new':'id DESC'}.get(sort,'id')
        with self.db() as c:
            c.execute('BEGIN')
            if provider and not (q or city or contact or entity_kind or industry):
                # Drive the provider-only count from the narrower provenance index.
                # DISTINCT preserves one result per company with multiple source URLs.
                total=c.execute('SELECT count(DISTINCT company_id) FROM origins WHERE provider=? AND EXISTS (SELECT 1 FROM companies WHERE id=origins.company_id)',(provider,)).fetchone()[0]
            else:
                total=c.execute('SELECT count(*) FROM companies'+where,args).fetchone()[0]  # nosec B608 -- Store.where returns only fixed clauses; all data is bound, sort is allowlisted.
            rows=c.execute('SELECT id,title,city,address,postal,phone,website,description,oib,email,industry,entity_kind,(SELECT group_concat(DISTINCT provider) FROM origins WHERE company_id=companies.id) providers FROM companies'+where+' ORDER BY '+order+' LIMIT ? OFFSET ?',(*args,limit,(page-1)*limit))  # nosec B608 -- Store.where returns only fixed clauses; all data is bound, sort is allowlisted.
            return {'total':total,'rows':[dict(r) for r in rows]}
    def cities(self):
        with self.db() as c: return [r[0] for r in c.execute("SELECT DISTINCT city FROM companies WHERE city<>'' ORDER BY city COLLATE NOCASE")]
    def industries(self):
        with self.db() as c:
            return [r[0] for r in c.execute("SELECT DISTINCT industry FROM companies WHERE industry<>'' ORDER BY industry COLLATE NOCASE LIMIT 10000")]
    def detail(self,i):
        with self.db() as c:
            c.execute('BEGIN')
            r=c.execute('SELECT * FROM companies WHERE id=?',(i,)).fetchone()
            if not r: return None
            sources=[dict(x) for x in c.execute('SELECT provider,url,updated FROM origins WHERE company_id=? ORDER BY provider,url',(i,))]
            alternatives=[dict(x) for x in c.execute('SELECT field,value,provider,observed_at FROM alternate_values WHERE company_id=? ORDER BY field,provider,value',(i,))]
            return dict({k:r[k] for k in ['id','source',*COLS,'oib','email','industry','entity_kind']},sources=sources,alternate_values=alternatives)
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
