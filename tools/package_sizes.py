"""Measure release packages and reject unexpectedly large builds."""
import argparse
import json
from pathlib import Path

# Decimal MB: ceilings, not promised final sizes. Revisit only with measured evidence.
LIMITS = {"HR": 750_000_000, "Online": 45_000_000}
BASELINE = {"setup": 23123355, "portable": 27018398, "deb": 27753888, "tar": 34855984}

def report(root, edition, platform):
    root=Path(root)
    names=({"setup":f"Setup-{edition}.exe","portable":f"Portable-{edition}.exe"} if platform=="Windows"
           else {"deb":"Crawlvora-Linux-amd64.deb","tar":"Crawlvora-Linux-x86_64.tar.gz"})
    result=[]
    for kind,name in names.items():
        path=root/name
        if not path.is_file() or path.is_symlink(): raise ValueError("Missing package: "+name)
        size=path.stat().st_size
        if not 0<size<=LIMITS[edition]:
            raise ValueError(f"{name}: {size} bytes exceeds {edition} size budget {LIMITS[edition]}")
        row={"name":name,"bytes":size,"limit_bytes":LIMITS[edition]}
        if edition=="Online":
            row.update(baseline_bytes=BASELINE[kind],change_percent=round(100*(size/BASELINE[kind]-1),2))
        result.append(row)
    return {"edition":edition,"platform":platform,"packages":result}

def release_report(root, mode):
    root=Path(root)
    result=[]
    for edition,suffix in (("HR","HR-Full"),("Online","HR-Online")):
        if edition=="HR" and mode=="online":continue
        for kind,name in {
            "setup":f"Setup-{suffix}.exe","portable":f"Portable-{suffix}.exe",
            "deb":f"Crawlvora-Linux-{suffix}-amd64.deb",
            "tar":f"Crawlvora-Linux-{suffix}-x86_64.tar.gz"}.items():
            path=root/name
            if not path.is_file() or path.is_symlink():raise ValueError("Missing package: "+name)
            size=path.stat().st_size
            if not 0<size<=LIMITS[edition]:raise ValueError("Package exceeds size budget: "+name)
            row={"edition":edition,"name":name,"bytes":size,"limit_bytes":LIMITS[edition]}
            if edition=="Online":row.update(baseline_bytes=BASELINE[kind],change_percent=round(100*(size/BASELINE[kind]-1),2))
            result.append(row)
    return {"packages":result}

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("directory",type=Path)
    p.add_argument("--edition",choices=LIMITS)
    p.add_argument("--platform",choices=("Windows","Linux"))
    p.add_argument("--release",choices=("full","online"))
    a=p.parse_args()
    if a.release and not (a.edition or a.platform):data=release_report(a.directory,a.release)
    elif not a.release and a.edition and a.platform:data=report(a.directory,a.edition,a.platform)
    else:p.error("Specify release mode or both edition and platform")
    output=json.dumps(data,indent=2)
    print(output)
    (a.directory/"PACKAGE-SIZES.json").write_text(output+"\n",encoding="utf-8")
