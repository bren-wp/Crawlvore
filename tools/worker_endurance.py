"""Measure isolated real worker CPU, RSS and concurrent API stability."""
import argparse
import concurrent.futures
import http.cookiejar
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
import psutil

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from core import Store

def run(seconds, records):
    with tempfile.TemporaryDirectory() as tmp:
        workspace=Path(tmp)/"data"
        workspace.mkdir()
        store=Store(workspace/"companies.sqlite3")
        with store.db() as db:
            db.execute("BEGIN IMMEDIATE")
            for i in range(records):
                store.upsert(db,{"title":f"Synthetic company {i:07}","city":f"City {i%100:03}","mbs":str(i+1)},provider="registry")
        env={k:v for k,v in os.environ.items() if not k.startswith(("SUDREG_","CRAWLVORA_"))}
        with tempfile.TemporaryFile(mode="w+b") as log:
            worker=subprocess.Popen([sys.executable,str(ROOT/"src/tvrtk_scraper.py"),"--worker","--port","0","--data-dir",str(workspace)],
                                    stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=log,text=True,env=env)
            try:
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    f=pool.submit(worker.stdout.readline)
                    try:line=f.result(timeout=90)
                    except TimeoutError:worker.kill();raise
                if not line.startswith("CRAWLVORA_READY "):raise RuntimeError("Worker startup failed")
                url=line.strip().split(" ",1)[1]
                base=url.split("/session/",1)[0]
                process=psutil.Process(worker.pid)
                stop=threading.Event()
                observations=[]
                def reader(index):
                    # Separate cookie jar/opener per thread.
                    client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
                    with client.open(url,timeout=10) as r:r.read()
                    latencies=[]
                    while not stop.is_set():
                        t=time.monotonic()
                        path="/api/stats" if index==0 else "/api/companies?city=City%20001&limit=25"
                        with client.open(base+path,timeout=10) as r:body=json.load(r)
                        if index==0 and body["total"]!=records:raise RuntimeError("Stats mismatch")
                        if index and (body["total"]!=records//100 or len(body["rows"])!=25):raise RuntimeError("Directory mismatch")
                        latencies.append(time.monotonic()-t)
                        stop.wait(.15)
                    return latencies
                start=time.monotonic()
                initial_cpu=process.cpu_times()
                with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
                    futures=[pool.submit(reader,i) for i in range(4)]
                    try:
                        while time.monotonic()-start<seconds:
                            for future in futures:
                                if future.done():future.result();raise RuntimeError("Unexpected reader exit")
                            if worker.poll() is not None:raise RuntimeError("Worker exited during endurance")
                            mem=process.memory_info().rss
                            observations.append(mem)
                            time.sleep(min(1,max(0,seconds-(time.monotonic()-start))))
                    finally:stop.set()
                    latencies=[ms*1000 for f in futures for ms in f.result(timeout=15)]
                elapsed=time.monotonic()-start
                last_cpu=process.cpu_times()
                cpu=last_cpu.user+last_cpu.system-initial_cpu.user-initial_cpu.system
                worker.stdin.close()
                if worker.wait(timeout=20)!=0:raise RuntimeError("Worker failed to shut down")
                with store.db() as db:
                    integrity=db.execute("PRAGMA integrity_check").fetchone()[0]
                    foreign_keys=len(db.execute("PRAGMA foreign_key_check").fetchall())
                if integrity!="ok" or foreign_keys:raise RuntimeError("Integrity verification failed")
                values=sorted(latencies)
                return {"scope":"real authenticated worker, synthetic data; excludes native UI",
                        "seconds":round(elapsed,2),"records":records,"requests":len(values),
                        "p50_ms":round(statistics.median(values),2),"p95_ms":round(values[max(0,(95*len(values)+99)//100-1)],2),
                        "peak_rss_bytes":max(observations),"first_rss_bytes":observations[0],"last_rss_bytes":observations[-1],
                        "cpu_seconds":round(cpu,3),"mean_cpu_percent_of_one_core":round(100*cpu/elapsed,2),
                        "integrity":integrity,"foreign_key_violations":foreign_keys}
            finally:
                if worker.poll() is None:worker.kill();worker.wait()
                for stream in (worker.stdin,worker.stdout):
                    if stream and not stream.closed:stream.close()

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--seconds",type=int,default=600)
    p.add_argument("--records",type=int,default=25000)
    args=p.parse_args()
    if not 10<=args.seconds<=14400 or not 2500<=args.records<=100000 or args.records%100:
        p.error("seconds: 10–14400; records: 2500–100000, divisible by 100")
    print(json.dumps(run(args.seconds,args.records),indent=2))
