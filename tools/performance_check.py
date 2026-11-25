"""Repeatable benchmark on synthetic company records, without production data."""
import argparse,json,statistics,sys,tempfile,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from core import Store
from data_safety import verified_backup,restore_workspace

def measure(fn,repeats=20):
    values=[]
    for _ in range(repeats):
        t=time.perf_counter()
        fn()
        values.append((time.perf_counter()-t)*1000)
    ordered=sorted(values)
    return {'samples':len(values),'p50_ms':round(statistics.median(values),3),'p95_ms':round(ordered[max(0,(95*len(values)+99)//100-1)],3),'max_ms':round(max(values),3)}

def run(count):
    with tempfile.TemporaryDirectory() as tmp:
        root=Path(tmp); path=root/'companies.sqlite3'; store=Store(path)
        t=time.perf_counter()
        with store.db() as c:
            c.execute('BEGIN IMMEDIATE')
            for i in range(count):
                store.upsert(c,{'title':f'Synthetic company {i:07}','city':f'City {i%100:03}','phone':str(i),'mbs':str(i+1)},provider='registry')
        seed_seconds=time.perf_counter()-t
        assert store.stats()['total']==count
        city='City 001'
        result={'records':count,'seed_seconds':round(seed_seconds,3),
                'filtered_page':measure(lambda:store.query(city=city)),
                'substring_search':measure(lambda:store.query(q='company 000')),
                'indexed_mbs':measure(lambda:store.query(q='mbs:'+str(count))),
                'stats':measure(store.stats),
                'filtered_json':measure(lambda:store.export_json(city=city),5)}
        t=time.perf_counter(); backup=verified_backup(path); result['backup_ms']=round((time.perf_counter()-t)*1000,3)
        t=time.perf_counter(); restored=Store(restore_workspace(backup,root/'restored')); result['restore_ms']=round((time.perf_counter()-t)*1000,3)
        assert restored.stats()==store.stats()
        with restored.db() as c:
            assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
            assert not c.execute('PRAGMA foreign_key_check').fetchall()
            result['query_plan']=[r[3] for r in c.execute("EXPLAIN QUERY PLAN SELECT id,title FROM companies WHERE city=? ORDER BY title COLLATE NOCASE,id LIMIT 25",(city,))]
        result['integrity']='ok'
        return result

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--records',type=int,default=100000); args=p.parse_args()
    if not 100<=args.records<=1000000: p.error('records must be between 100 and 1000000')
    print(json.dumps(run(args.records),indent=2))
