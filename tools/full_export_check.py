"""Full synthetic directory exports in isolated processes with peak RSS evidence."""
import argparse
import csv
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from core import Store
from bulk_io import export_file,json_records


def peak_rss_bytes():
    if os.name=='nt':
        import ctypes
        from ctypes import wintypes
        class MemoryCounters(ctypes.Structure):
            _fields_=[('cb',wintypes.DWORD),('PageFaultCount',wintypes.DWORD)]+[
                (name,ctypes.c_size_t) for name in (
                    'PeakWorkingSetSize','WorkingSetSize','QuotaPeakPagedPoolUsage',
                    'QuotaPagedPoolUsage','QuotaPeakNonPagedPoolUsage','QuotaNonPagedPoolUsage',
                    'PagefileUsage','PeakPagefileUsage')]
        counters=MemoryCounters()
        counters.cb=ctypes.sizeof(counters)
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.GetCurrentProcess.restype=wintypes.HANDLE
        psapi=ctypes.WinDLL('psapi',use_last_error=True)
        query=psapi.GetProcessMemoryInfo
        query.argtypes=(wintypes.HANDLE,ctypes.POINTER(MemoryCounters),wintypes.DWORD)
        query.restype=wintypes.BOOL
        if not query(kernel.GetCurrentProcess(),ctypes.byref(counters),counters.cb):
            raise ctypes.WinError(ctypes.get_last_error())
        return int(counters.PeakWorkingSetSize)
    import resource
    value=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(value if sys.platform=='darwin' else value*1024)


def child(database,output,kind,count):
    store=Store(database)
    before=peak_rss_bytes()
    start=time.perf_counter()
    export_file(store,output,kind)
    elapsed=time.perf_counter()-start
    peak=peak_rss_bytes()
    if kind=='json':
        with output.open(encoding='utf-8') as stream:
            for index,record in enumerate(json_records(stream),1):
                assert record['title']==f'Synthetic full export {index-1:07}'
                assert record['sources'] and record['sources'][0]['provider']=='registry'
            assert index==count
    elif kind=='csv':
        with output.open(encoding='utf-8-sig',newline='') as stream:
            reader=csv.reader(stream)
            header=next(reader)
            assert 'Sources' in header
            for index,record in enumerate(reader,1):
                assert record[0]==f'Synthetic full export {index-1:07}'
                assert record[-1]=='registry'
            assert index==count
    else:
        from openpyxl import load_workbook
        workbook=load_workbook(output,read_only=True,data_only=False)
        index=0
        try:
            for sheet in workbook:
                rows=sheet.iter_rows()
                header=next(rows)
                assert header[-1].value=='Sources'
                for row in rows:
                    assert row[0].value==f'Synthetic full export {index:07}'
                    assert row[-1].value=='registry'
                    assert all(cell.data_type!='f' for cell in row)
                    index+=1
            assert index==count
        finally:
            workbook.close()
    return {'format':kind,'records':count,'bytes':output.stat().st_size,
            'elapsed_seconds':round(elapsed,3),'baseline_peak_rss_bytes':before,
            'export_peak_rss_bytes':peak,'validation_peak_rss_bytes':peak_rss_bytes()}


def run(count,formats=('json','csv','xlsx')):
    with tempfile.TemporaryDirectory() as tmp:
        root=Path(tmp); database=root/'synthetic.sqlite3';store=Store(database)
        start=time.perf_counter()
        with store.db() as db:
            db.execute('BEGIN IMMEDIATE')
            for i in range(count):
                store.upsert(db,{'title':f'Synthetic full export {i:07}',
                                 'city':f'City {i%100:03}','mbs':str(i+1)},provider='registry')
        seed_seconds=round(time.perf_counter()-start,3)
        results=[]
        for kind in formats:
            output=root/('full.'+kind)
            raw=subprocess.check_output([sys.executable,str(Path(__file__).resolve()),
                '--child',str(database),str(output),kind,str(count)],text=True)
            result=json.loads(raw)
            assert result['records']==count
            results.append(result)
            output.unlink()
        with store.db() as db:
            assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
            assert not db.execute('PRAGMA foreign_key_check').fetchall()
        return {'records':count,'seed_seconds':seed_seconds,'exports':results,'integrity':'ok'}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--records',type=int,default=100000)
    parser.add_argument('--formats',nargs='+',choices=('json','csv','xlsx'),default=['json','csv','xlsx'])
    parser.add_argument('--child',nargs=4,help=argparse.SUPPRESS)
    args=parser.parse_args()
    if args.child:
        database,output,kind,count=args.child
        if kind not in ('json','csv','xlsx'):parser.error('Invalid format')
        print(json.dumps(child(Path(database),Path(output),kind,int(count))))
    else:
        if not 100<=args.records<=1000000:parser.error('records must be 100 to 1000000')
        print(json.dumps(run(args.records,args.formats),indent=2))
