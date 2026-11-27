"""Measure packaged native smoke wall time and host-process CPU, not interactive responsiveness."""
import argparse
import json
import os
from pathlib import Path
import statistics
import subprocess
import time


def cpu_seconds(process):
    if os.name=="nt":
        import ctypes
        from ctypes import wintypes
        kernel=ctypes.WinDLL("kernel32",use_last_error=True)
        query=kernel.GetProcessTimes
        query.argtypes=[wintypes.HANDLE]+[ctypes.POINTER(wintypes.FILETIME)]*4
        query.restype=wintypes.BOOL
        values=[wintypes.FILETIME() for _ in range(4)]
        if not query(int(process._handle),*(ctypes.byref(v) for v in values)):
            raise ctypes.WinError(ctypes.get_last_error())
        return sum((v.dwHighDateTime<<32)+v.dwLowDateTime for v in values[2:])/10_000_000
    import resource
    usage=resource.getrusage(resource.RUSAGE_CHILDREN)
    return usage.ru_utime+usage.ru_stime


def run(executable,samples):
    runs=[]
    env={k:v for k,v in os.environ.items() if not k.startswith(("CRAWLVORA_","SUDREG_"))}
    for _ in range(samples):
        baseline=cpu_seconds(None) if os.name!="nt" else 0
        start=time.perf_counter()
        proc=subprocess.Popen([str(executable.resolve()),"--native-smoke"],env=env)
        try:
            code=proc.wait(timeout=240)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            raise
        elapsed=time.perf_counter()-start
        if code!=0: raise RuntimeError(f"Native smoke failed: {code}")
        runs.append({"wall_ms":round(elapsed*1000,3),
                     "cpu_ms":round((cpu_seconds(proc)-baseline)*1000,3)})
    return {"scope":"native smoke launch through UI readiness and shutdown; no idle or live registry workload",
            "cpu_scope":"host process only" if os.name=="nt" else "waited child process resource usage",
            "runs":runs,"median_wall_ms":statistics.median(r["wall_ms"] for r in runs),
            "median_cpu_ms":statistics.median(r["cpu_ms"] for r in runs)}


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("executable",type=Path)
    p.add_argument("--samples",type=int,default=3)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    if not 1<=a.samples<=10: p.error("samples must be 1 to 10")
    report=run(a.executable,a.samples)
    a.output.write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report))
