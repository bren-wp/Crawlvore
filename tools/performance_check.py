"""Repeatable benchmark on synthetic company records, without production data."""
import argparse,json,platform,sqlite3,statistics,sys,tempfile,time,tracemalloc
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from core import Store
from bulk_io import export_file,json_records
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
                if i%500==0:
                    company_id=c.execute('SELECT id FROM companies WHERE mbs=?',(str(i+1).zfill(9),)).fetchone()[0]
                    c.execute("INSERT INTO origins(company_id,provider,url) VALUES(?, 'csv', '')",(company_id,))
        seed_seconds=time.perf_counter()-t
        assert store.stats()['total']==count
        assert store.fts_available, 'FTS5 is required for the indexed benchmark'
        assert store.query(q='fts:company 0000001')['total']==store.query(q='company 0000001')['total']==1
        city='City 001'
        result={'records':count,'python':platform.python_version(),'sqlite':sqlite3.sqlite_version,'platform':platform.system(),'seed_seconds':round(seed_seconds,3),
                'filtered_page':measure(lambda:store.query(city=city)),
                'substring_search':measure(lambda:store.query(q='company 000')),
                'indexed_mbs':measure(lambda:store.query(q='mbs:'+str(count))),
                'fts_available':store.fts_available,
                'indexed_phrase':measure(lambda:store.query(q='fts:company 0000001')),
                'same_phrase_scan':measure(lambda:store.query(q='company 0000001')),
                'stats':measure(store.stats),
                'filtered_json':measure(lambda:store.export_json(city=city),5)}
        # Same database, same connection and same results; only the SQL count strategy differs.
        with store.db() as c:
            old='SELECT count(*) FROM companies WHERE EXISTS (SELECT 1 FROM origins WHERE company_id=companies.id AND provider=?)'
            new='SELECT count(DISTINCT company_id) FROM origins WHERE provider=? AND EXISTS (SELECT 1 FROM companies WHERE id=origins.company_id)'
            expected=(count+499)//500
            assert c.execute(old,('csv',)).fetchone()[0]==c.execute(new,('csv',)).fetchone()[0]==expected
            result['rare_provider_count']={'matches':expected,
                'previous':measure(lambda:c.execute(old,('csv',)).fetchone()),
                'optimized':measure(lambda:c.execute(new,('csv',)).fetchone()),
                'plan':[r[3] for r in c.execute('EXPLAIN QUERY PLAN '+new,('csv',))]}
        assert store.query(provider='csv')['total']==expected
        assert store.query(provider='registry',city=city)['total']==(count+98)//100
        result['rare_provider_page']=measure(lambda:store.query(provider='csv'))
        # Exercise the actual disk-backed production export rather than only the legacy in-memory API.
        output=root/'filtered.json'
        tracemalloc.start()
        try:
            t=time.perf_counter()
            export_file(store,output,'json',city=city)
            elapsed=time.perf_counter()-t
            _,peak=tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        with output.open(encoding='utf-8') as stream:
            exported=sum(1 for _ in json_records(stream))
        assert exported==(count+98)//100
        result['streamed_json']={'records':exported,'bytes':output.stat().st_size,
                                 'elapsed_ms':round(elapsed*1000,3),'peak_python_allocated_bytes':peak}
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
