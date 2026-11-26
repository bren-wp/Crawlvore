"""Country-isolated import of the seven-part Companies House monthly snapshot."""
import argparse
import csv
import hashlib
import io
import json
import re
import sqlite3
import zipfile
from contextlib import closing
from pathlib import Path

PART = re.compile(r'BasicCompanyData-(\d{4}-\d{2}-\d{2})-part([1-7])_7(?:\(\d+\))?\.zip')
SOURCE = 'https://download.companieshouse.gov.uk/en_output.html'


def build(archives, destination):
    parts = {}; dates = set()
    for archive in map(Path, archives):
        match = PART.fullmatch(archive.name)
        if not match or int(match[2]) in parts: raise ValueError('Invalid or duplicate archive')
        dates.add(match[1]); parts[int(match[2])] = archive
    if set(parts) != set(range(1, 8)) or len(dates) != 1: raise ValueError('Require seven parts of one snapshot')
    snapshot = dates.pop(); destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    pending = destination/'united-kingdom.sqlite3.incomplete'; final = destination/'united-kingdom.sqlite3'
    counts=[]; headers=None
    with closing(sqlite3.connect(pending)) as db:
        db.execute('PRAGMA synchronous=NORMAL')
        db.execute('CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL)')
        for part, archive in sorted(parts.items()):
            with zipfile.ZipFile(archive) as z:
                expected=f'BasicCompanyData-{snapshot}-part{part}_7.csv'
                if z.namelist()!=[expected]: raise ValueError('Unexpected archive content')
                with io.TextIOWrapper(z.open(expected),encoding='utf-8-sig',newline='') as stream:
                    reader=csv.reader(stream); current=[field.strip() for field in next(reader)]
                    if headers is None:
                        headers=current
                        if len(headers)!=55 or len(set(headers))!=55 or headers[:2]!=['CompanyName','CompanyNumber']: raise ValueError('Unexpected schema')
                        columns=['name','registration_number']+[f'c{i:02d}' for i in range(2,55)]
                        db.execute('CREATE TABLE companies ('+','.join(col+' TEXT NOT NULL' for col in columns)+')')  # nosec B608 -- generated identifiers
                        statement='INSERT INTO companies VALUES ('+','.join('?' for _ in columns)+')'  # nosec B608 -- placeholders only
                    elif current!=headers: raise ValueError('Schema mismatch')
                    count=0; batch=[]
                    for row in reader:
                        if len(row)!=55 or not row[0].strip() or not re.fullmatch(r'[A-Z0-9]{8}',row[1]): raise ValueError(f'Invalid record in part {part}, row {count+1}')
                        batch.append(row); count+=1
                        if len(batch)>=5000: db.executemany(statement,batch); batch.clear()
                    if batch: db.executemany(statement,batch)
                    db.commit()
                with archive.open('rb') as raw: digest=hashlib.file_digest(raw,'sha256').hexdigest()
                counts.append({'part':part,'rows':count,'sha256':digest}); print(json.dumps(counts[-1]),flush=True)
        db.execute('CREATE UNIQUE INDEX company_number ON companies(registration_number)')
        db.execute('CREATE INDEX company_name ON companies(name COLLATE NOCASE)')
        total=sum(item['rows'] for item in counts)
        if db.execute('SELECT count(*) FROM companies').fetchone()[0]!=total: raise ValueError('Row count mismatch')
        manifest={'country':'GB','source':SOURCE,'snapshot':snapshot,'scope':'live-register monthly snapshot','rows':total,'columns':headers,'parts':counts,'complete':True}
        db.executemany('INSERT INTO metadata VALUES (?,?)',[(k,json.dumps(v,ensure_ascii=False)) for k,v in manifest.items()]); db.commit()
        if db.execute('PRAGMA integrity_check').fetchall()!=[('ok',)]: raise ValueError('SQLite integrity failed')
    pending.rename(final)
    with final.open('rb') as raw: manifest['database_sha256']=hashlib.file_digest(raw,'sha256').hexdigest()
    (destination/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print(json.dumps({'complete':True,'rows':total,'database_sha256':manifest['database_sha256']}),flush=True)
    return manifest


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination',type=Path); parser.add_argument('archives',nargs=7,type=Path)
    args=parser.parse_args(); build(args.archives,args.destination)
