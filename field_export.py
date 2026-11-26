"""Bounded-memory export of explicitly selected business directory fields."""
import csv
import json

from core import formula_safe

FIELDS={'title':'Company','email':'Email','phone':'Phone','oib':'OIB','mbs':'MBS',
        'website':'Website','city':'City','address':'Address','postal':'Postal code',
        'country':'Country','industry':'Industry'}


def selected_fields(value):
    fields=value.split(',')
    if not fields or len(fields)>len(FIELDS) or len(set(fields))!=len(fields) or any(f not in FIELDS for f in fields):
        raise ValueError('Invalid export fields.')
    return fields


def export_selected(store, path, fields, kind, omit_empty=True, distinct=False, **filters):
    fields=selected_fields(','.join(fields))
    where,args=store.where(**filters)
    if kind not in ('csv','json','xlsx'):
        raise ValueError('Invalid export format.')
    if omit_empty:
        predicate='('+' OR '.join(f"coalesce({f},'')<>''" for f in fields)+')'
        where+=(' AND ' if where else ' WHERE ')+predicate
    sql='SELECT '+('DISTINCT ' if distinct else '')+','.join(fields)+' FROM companies'+where
    sql+=' ORDER BY '+(','.join(fields) if distinct else 'id')
    with store.db() as db:
        db.execute('BEGIN')
        rows=db.execute(sql,args)  # nosec B608 -- fields allowlisted, fixed filter clauses, bound values.
        if kind=='csv':
            with open(path,'w',encoding='utf-8-sig',newline='') as out:
                writer=csv.writer(out)
                writer.writerow(fields)
                for row in rows:
                    writer.writerow([formula_safe(str(v or '')) for v in row])
        elif kind=='json':
            with open(path,'w',encoding='utf-8') as out:
                out.write('[')
                for index,row in enumerate(rows):
                    if index: out.write(',')
                    json.dump(dict(zip(fields,row)),out,ensure_ascii=False)
                out.write(']')
        else:
            from openpyxl import Workbook
            from openpyxl.cell import WriteOnlyCell
            from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
            workbook=Workbook(write_only=True)
            sheet=workbook.create_sheet('Business data 1')
            sheet.append(fields)
            for index,row in enumerate(rows):
                if index and index%1048575==0:
                    sheet=workbook.create_sheet('Business data '+str(index//1048575+1))
                    sheet.append(fields)
                cells=[]
                for value in row:
                    cell=WriteOnlyCell(sheet,value=ILLEGAL_CHARACTERS_RE.sub('',str(value or ''))[:32767])
                    cell.data_type='s'
                    cells.append(cell)
                sheet.append(cells)
            workbook.save(path)
