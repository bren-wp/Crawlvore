import sys, tempfile, time, json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from core import Store
from registry import Registry
from snapshot_diff import compare
with tempfile.TemporaryDirectory() as td:
    store=Store(Path(td)/'stress.db'); reg=Registry(store)
    n=50000; t=time.monotonic()
    with store.db() as c:
        c.executemany('INSERT INTO registry_runs VALUES (?,?,1)', [(s,json.dumps({'subjekti':[]}),) for s in ('1','2')])
        for s in ('1','2'):
            c.executemany('INSERT INTO registry_rows VALUES (?,?,?,?,?)',((s,'subjekti',i,str(i).zfill(9),json.dumps({'mbs':i,'naziv':f'Entity {i}' if s=='1' or i%100 else f'Changed {i}'})) for i in range(n)))
    insert=time.monotonic()-t; t=time.monotonic()
    for _ in range(3):
        d=compare(reg,'1','2')['categories'][0]; assert d['added']==d['removed']==d['affected_subjects']==500,d
    diff=(time.monotonic()-t)/3
    with store.db() as c: assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    print(json.dumps({'synthetic_rows':2*n,'insert_seconds':round(insert,3),'mean_diff_seconds':round(diff,3),'repetitions':3,'integrity':'ok'}))
