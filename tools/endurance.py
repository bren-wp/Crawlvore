"""Concurrent local database endurance; default four hours, short smoke via --seconds."""
import argparse, concurrent.futures, json, sys, tempfile, threading, time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from core import Store
from data_safety import verified_backup,restore_workspace

def run(seconds):
    with tempfile.TemporaryDirectory() as td:
        store=Store(Path(td)/'endurance.sqlite3')
        # Never use the historical directory CSV or the user's real catalog for load tests.
        with store.db() as db:
            db.execute('BEGIN IMMEDIATE')
            for i in range(25000):
                store.upsert(db,{'title':f'Synthetic company {i:07}','city':f'City {i%100:03}',
                                 'mbs':str(i+1)},provider='registry')
        initial=store.stats()['total']; start=time.monotonic(); end=start+seconds; stop=threading.Event(); counts={}; latencies={}
        def worker(name,action):
            count=0; total=0.; maximum=0.
            try:
                while time.monotonic()<end and not stop.is_set():
                    t=time.monotonic(); action(count); elapsed=time.monotonic()-t; count+=1; total+=elapsed; maximum=max(maximum,elapsed)
            except BaseException:
                stop.set(); raise
            finally:
                counts[name]=count; latencies[name]={'mean_ms':round(total/max(count,1)*1000,3),'max_ms':round(maximum*1000,3)}
        def write(i):
            with store.db() as c: store.upsert(c,{'title':f'Endurance fixture {i%100}','city':'Synthetic','phone':str(i%100)},provider='html')
        def read(i):
            r=store.query(city='City 001',limit=25); assert r['total']==250 and len(r['rows'])==25
        def stats(i): assert store.stats()['total']>=initial
        def export(i): assert len(store.export(q='Endurance fixture'))>20
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            futures=[pool.submit(worker,n,a) for n,a in [('write',write),('search',read),('stats',stats),('export',export)]]
            for f in futures: f.result()
        assert all(counts.get(name,0)>0 for name in ('write','search','stats','export'))
        assert time.monotonic()-start>=seconds
        with store.db() as c: integrity=c.execute('PRAGMA integrity_check').fetchone()[0]; fk=list(c.execute('PRAGMA foreign_key_check'))
        assert integrity=='ok' and not fk
        assert initial<=store.stats()['total']<=initial+100
        backup=verified_backup(Path(store.path))
        restored=Store(restore_workspace(backup,Path(td)/'recovered'))
        assert restored.stats()==store.stats()
        return {'recovery_verified':True,'requested_seconds':seconds,'elapsed_seconds':round(time.monotonic()-start,3),'operations':counts,'latencies':latencies,'initial_records':initial,'final_records':store.stats()['total'],'integrity':integrity,'foreign_key_violations':len(fk)}
if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('--seconds',type=int,default=14400); args=ap.parse_args(); assert args.seconds>0; print(json.dumps(run(args.seconds),indent=2))
