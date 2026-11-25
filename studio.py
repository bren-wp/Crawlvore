"""Project storage, HTML inspection and spreadsheet export for Crawlvora."""
import io, json, re
from urllib.parse import urlsplit

class Projects:
    def __init__(self,store):
        self.store=store
        with store.db() as c:
            c.execute('CREATE TABLE IF NOT EXISTS projects (id INTEGER PRIMARY KEY, name TEXT NOT NULL, config TEXT NOT NULL, updated TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)')
    def list(self):
        with self.store.db() as c: return [dict(r,config=json.loads(r['config'])) for r in c.execute('SELECT * FROM projects ORDER BY updated DESC,id DESC')]
    def save(self,data):
        name=str(data.get('name','')).strip(); config=data.get('config')
        if not name or len(name)>120 or not isinstance(config,dict): raise ValueError('Unesite naziv i konfiguraciju projekta.')
        keys=('provider','term','start','end','resume','url','selector','mapping','pages','delay','mode','next_selector','cursor_path','cursor_param','page_start','offset_step','engine')
        cfg={k:config[k] for k in keys if k in config}
        if cfg.get('url'):
            u=urlsplit(cfg['url']);
            if u.username or u.password or re.search(r'(?:^|&)(?:token|api[_-]?key|secret|password|access_token|authorization)=',u.query,re.I): raise ValueError('Pristupne podatke unesite u polje API token, ne u URL.')
        raw=json.dumps(cfg,ensure_ascii=False)
        if len(raw)>30000: raise ValueError('Konfiguracija je prevelika.')
        with self.store.db() as c:
            if data.get('id'):
                i=int(data['id']); cur=c.execute('UPDATE projects SET name=?,config=?,updated=CURRENT_TIMESTAMP WHERE id=?',(name,raw,i));
                if not cur.rowcount: raise ValueError('Projekt nije pronađen.')
            else: i=c.execute('INSERT INTO projects(name,config) VALUES (?,?)',(name,raw)).lastrowid
        return {'id':i}
    def delete(self,i):
        with self.store.db() as c: c.execute('DELETE FROM projects WHERE id=?',(int(i),))
        return {'ok':True}

from detection import inspect_html  # public Studio entry point

def excel(store,**filters):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.utils import get_column_letter
    from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
    # Explicit strings keep OIB, postal codes and hostile formula prefixes as text.
    wb=Workbook(); ws=wb.active; ws.title='Poslovni imenik'
    cols=['title','oib','mbs','industry','city','address','postal','country','phone','email','website','year','employees','rating','description','products','fax','person','account','logo','social']
    headers=['Naziv tvrtke','OIB','MBS','Djelatnost','Grad','Adresa','Poštanski broj','Država','Telefon','E-mail','Web','Godina osnivanja','Zaposleni','Ocjena','Opis','Proizvodi','Fax','Kontakt osoba','Račun','Logo','Društvene mreže','Izvori']
    ws.append(headers); where,args=store.where(**filters)
    with store.db() as c:
        rows=c.execute('SELECT '+','.join(cols)+",coalesce((SELECT group_concat(DISTINCT provider) FROM origins WHERE company_id=companies.id),'') FROM companies"+where+' ORDER BY id',args)
        for i,row in enumerate(rows,2):
            if i>1048576: raise ValueError('Previše redaka za jedan Excel list.')
            for j,v in enumerate(row,1):
                cell=ws.cell(i,j,ILLEGAL_CHARACTERS_RE.sub('',str(v or ''))[:32767]); cell.data_type='s'; cell.number_format='@'
    for cell in ws[1]: cell.fill=PatternFill('solid',fgColor='123C39'); cell.font=Font(bold=True,color='FFFFFF'); cell.alignment=Alignment(vertical='center')
    ws.row_dimensions[1].height=28; ws.freeze_panes='B2'; ws.auto_filter.ref=ws.dimensions
    for i,width in enumerate([42,16,16,30,24,36,16,18,24,32,42,20,16,14,55,45,24,28,28,30,30,24],1): ws.column_dimensions[get_column_letter(i)].width=width
    out=io.BytesIO(); wb.save(out); return out.getvalue()
