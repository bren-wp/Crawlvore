"""Disk-backed bulk directory I/O; bounded memory and transactional imports."""
import csv
import json
from pathlib import Path
from core import COLS, FIELDS, formula_safe

MAX_IMPORT=2*1024**3
CHUNK=1024*1024
MAX_RECORD=8*CHUNK
COLUMNS=COLS+['oib','email','industry','entity_kind']

def receive(stream,path,size):
    if not 0<size<=MAX_IMPORT: raise ValueError('Invalid import size (maximum 2 GiB).')
    with Path(path).open('xb') as out:
        remaining=size
        while remaining:
            data=stream.read(min(CHUNK,remaining))
            if not data: raise ValueError('Incomplete request body.')
            out.write(data); remaining-=len(data)

def json_records(stream):
    decoder=json.JSONDecoder()
    buf=''; eof=False
    def more():
        nonlocal buf,eof
        data=stream.read(CHUNK)
        if not data: eof=True
        buf+=data
    def trim():
        nonlocal buf
        while True:
            buf=buf.lstrip()
            if buf or eof: return
            more()
    trim()
    if not buf.startswith('['): raise ValueError('Expected JSON array.')
    buf=buf[1:]; trim()
    if buf.startswith(']'):
        buf=buf[1:]
    else:
        while True:
            trim()
            if not buf.startswith('{'): raise ValueError('Expected JSON object.')
            while True:
                try:
                    obj,end=decoder.raw_decode(buf)
                    break
                except json.JSONDecodeError:
                    if eof or len(buf)>MAX_RECORD: raise ValueError('Invalid or oversized JSON record.') from None
                    more()
            if end>MAX_RECORD: raise ValueError('JSON record exceeds size limit.')
            if not isinstance(obj,dict) or not isinstance(obj.get('title'),str) or not obj['title'].strip():
                raise ValueError('JSON records require title.')
            yield obj
            buf=buf[end:]; trim()
            if buf.startswith(']'):
                buf=buf[1:]; break
            if not buf.startswith(','): raise ValueError('Invalid JSON array separator.')
            buf=buf[1:]
    trim()
    if buf: raise ValueError('Unexpected data after JSON array.')

def import_file(store,path,kind):
    with Path(path).open(encoding='utf-8-sig',newline='') as stream:
        if kind=='csv': return store.import_csv(stream)
        if kind!='json': raise ValueError('Invalid import format.')
        count=added=0
        with store.db() as db:
            db.execute('BEGIN IMMEDIATE')
            for record in json_records(stream):
                added+=store.upsert(db,{k:v for k,v in record.items() if isinstance(v,(str,int,float))},provider='csv')
                count+=1
        return {'read':count,'added':added}

def export_file(store,path,kind,**filters):
    where,args=store.where(**filters)
    with store.db() as db:
        db.execute('BEGIN')
        rows=db.execute("SELECT id,"+','.join(COLUMNS)+",coalesce((SELECT group_concat(DISTINCT provider) FROM origins WHERE company_id=companies.id),'') AS providers FROM companies"+where+' ORDER BY id',args)  # nosec B608 -- fixed columns, allowlisted filters, bound values
        if kind=='csv':
            with Path(path).open('w',encoding='utf-8-sig',newline='') as out:
                writer=csv.writer(out); writer.writerow(FIELDS+['OIB','Email','Industry','Entity Type','Sources'])
                for row in rows: writer.writerow([formula_safe(row[k]) for k in COLUMNS+['providers']])
        elif kind=='json':
            with Path(path).open('w',encoding='utf-8') as out:
                out.write('['); first=True
                while batch:=rows.fetchmany(500):
                    records={row['id']:{k:row[k] for k in ['id']+COLUMNS}|{'sources':[],'alternate_values':[]} for row in batch}
                    ids=list(records); marks=','.join('?' for _ in ids)
                    for row in db.execute('SELECT company_id,provider,url,updated FROM origins WHERE company_id IN ('+marks+') ORDER BY company_id,provider,url',ids):  # nosec B608 -- placeholders only
                        records[row['company_id']]['sources'].append({k:row[k] for k in ('provider','url','updated')})
                    for row in db.execute('SELECT company_id,field,value,provider,observed_at FROM alternate_values WHERE company_id IN ('+marks+') ORDER BY company_id,field,provider,value',ids):  # nosec B608 -- placeholders only
                        records[row['company_id']]['alternate_values'].append({k:row[k] for k in ('field','value','provider','observed_at')})
                    for record in records.values():
                        if not first: out.write(',')
                        first=False; json.dump(record,out,ensure_ascii=False)
                out.write(']')
        elif kind=='xlsx':
            from openpyxl import Workbook
            from openpyxl.cell import WriteOnlyCell
            from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
            wb=Workbook(write_only=True)
            for i,row in enumerate(rows):
                if i%1048575==0:
                    sheet=wb.create_sheet('Directory '+str(i//1048575+1))
                    sheet.append(FIELDS+['OIB','Email','Industry','Entity Type','Sources'])
                cells=[]
                for k in COLUMNS+['providers']:
                    cell=WriteOnlyCell(sheet,value=ILLEGAL_CHARACTERS_RE.sub('',str(row[k] or ''))[:32767]);cell.data_type='s';cells.append(cell)
                sheet.append(cells)
            if not wb.worksheets: wb.create_sheet('Directory 1').append(FIELDS+['OIB','Email','Industry','Entity Type','Sources'])
            wb.save(path)
        else: raise ValueError('Invalid export format.')

def company_registry(store,company_id,snapshot='',offset=0):
    if not 0<=offset<=10000000: raise ValueError('Invalid offset.')
    with store.db() as db:
        record=db.execute('SELECT mbs FROM companies WHERE id=?',(company_id,)).fetchone()
        if record is None: return None
        snapshots=[dict(row) for row in db.execute('SELECT snapshot,complete FROM registry_runs ORDER BY CAST(snapshot AS INTEGER) DESC')]
        if snapshot and snapshot not in {row['snapshot'] for row in snapshots}: raise ValueError('Unknown snapshot.')
        snapshot=snapshot or (snapshots[0]['snapshot'] if snapshots else '')
        if not record['mbs'] or not snapshot: return {'snapshot':snapshot,'snapshots':snapshots,'rows':[],'next':False}
        mbs=str(record['mbs']).zfill(9)
        rows=db.execute('SELECT category,ordinal,payload FROM registry_rows INDEXED BY registry_mbs WHERE snapshot=? AND mbs=? ORDER BY category,ordinal LIMIT 26 OFFSET ?',(snapshot,mbs,offset)).fetchall()
        return {'snapshot':snapshot,'snapshots':snapshots,'rows':[{'category':row['category'],'ordinal':row['ordinal'],'data':json.loads(row['payload'])} for row in rows[:25]],'next':len(rows)>25}
