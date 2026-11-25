"""Streaming registry exports preserving raw fields and identifier formatting."""
import json, re
from xml.sax.saxutils import XMLGenerator
from registry import NAME, normalized_id

def export(registry,snapshot,category,kind,path):
    if not snapshot.isdigit() or not NAME.fullmatch(category): raise ValueError('Neispravna kategorija.')
    with registry.store.db() as c:
        c.execute('BEGIN')
        sql='SELECT payload FROM registry_rows WHERE snapshot=? AND category=? ORDER BY ordinal'; args=(snapshot,category)
        if kind=='sql':
            with open(path,'w',encoding='utf-8') as f:
                f.write('BEGIN;\nCREATE TABLE IF NOT EXISTS registry_export(snapshot TEXT, category TEXT, ordinal INTEGER, payload TEXT, PRIMARY KEY(snapshot,category,ordinal));\n')
                def literal(v): return "'"+v.replace("'","''")+"'"
                for i,r in enumerate(c.execute(sql,args)): f.write(f'INSERT OR REPLACE INTO registry_export VALUES ({literal(snapshot)},{literal(category)},{i},{literal(r[0])});\n')
                f.write('COMMIT;\n')
        elif kind=='xml':
            with open(path,'wb') as f:
                x=XMLGenerator(f,encoding='utf-8'); x.startDocument(); x.startElement('registry',{'snapshot':snapshot,'category':category})
                for r in c.execute(sql,args):
                    x.startElement('record',{})
                    for k,v in json.loads(r[0]).items():
                        # JSON text preserves exact value types, including null and nested values.
                        safe_key=re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\ud800-\udfff\ufffe\uffff]','',k)
                        attrs={'name':safe_key,'encoding':'json'}
                        if safe_key!=k: attrs['originalName']=json.dumps(k,ensure_ascii=True)
                        x.startElement('field',attrs); x.characters(json.dumps(v,ensure_ascii=True)); x.endElement('field')
                    x.endElement('record')
                x.endElement('registry'); x.endDocument()
        elif kind=='xlsx':
            from openpyxl import Workbook
            from openpyxl.cell import WriteOnlyCell
            from openpyxl.styles import Font, PatternFill
            from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
            from openpyxl.utils import get_column_letter
            keys=list(dict.fromkeys(k for r in c.execute(sql,args) for k in json.loads(r[0]))) or ['payload']
            if len(keys)>16384: raise ValueError('Previše stupaca za Excel.')
            wb=Workbook(write_only=True)
            def sheet(index):
                ws=wb.create_sheet(f'Registry {index}'); ws.freeze_panes='A2'
                for j,k in enumerate(keys,1): ws.column_dimensions[get_column_letter(j)].width=min(48,max(17,len(k)+5))
                def header(k):
                    cell=WriteOnlyCell(ws,value=k); cell.data_type='s'; cell.font=Font(bold=True,color='FFFFFF'); cell.fill=PatternFill('solid',fgColor='123C39'); return cell
                ws.append([header(k) for k in keys]); return ws
            ws=sheet(1); n=1; idx=1
            for r in c.execute(sql,args):
                if n==1048576: ws.auto_filter.ref=f'A1:{get_column_letter(len(keys))}{n}'; idx+=1; ws=sheet(idx); n=1
                d=json.loads(r[0]); cells=[]
                for k in keys:
                    v=d.get(k); v=normalized_id(v,9 if k.lower()=='mbs' else 11) or v if k.lower() in ('mbs','oib') and v is not None else v
                    text=json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict)) else str(v) if v is not None else ''
                    cell=WriteOnlyCell(ws,value=ILLEGAL_CHARACTERS_RE.sub('',text)[:32767]); cell.data_type='s'; cells.append(cell)
                ws.append(cells); n+=1
            ws.auto_filter.ref=f'A1:{get_column_letter(len(keys))}{n}'; wb.save(path)
        else: raise ValueError('Nepodržan format.')
