"""Lossless RGB comparison. No resizing, masking or perceptual threshold."""
import argparse
import json
from pathlib import Path
from PIL import Image,ImageChops

VIEWS=("overview","directory","registry","jobs","data","analytics","settings")

def compare(reference,candidate,diff_dir):
    diff_dir.mkdir(parents=True,exist_ok=True)
    results=[]
    for view in VIEWS:
        with Image.open(reference/(view+"-dark.png")) as a, Image.open(candidate/(view+".png")) as b:
            if a.size!=b.size:
                raise ValueError(f"{view}: unequal dimensions {a.size} vs {b.size}")
            delta=ImageChops.difference(a.convert("RGB"),b.convert("RGB"))
            combined=ImageChops.lighter(ImageChops.lighter(*delta.split()[:2]),delta.split()[2])
            hist=combined.histogram()
            total=a.width*a.height
            changed=total-hist[0]
            delta.save(diff_dir/(view+"-diff.png"))
            results.append({"view":view,"size":list(a.size),"changed_pixels":changed,"total_pixels":total,
                            "changed_percent":round(100*changed/total,6),"exact":changed==0})
    return results

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("reference",type=Path);p.add_argument("candidate",type=Path);p.add_argument("output",type=Path)
    p.add_argument("--report-only",action="store_true")
    args=p.parse_args()
    results=compare(args.reference,args.candidate,args.output)
    report={"exact":all(r["exact"] for r in results),"views":results}
    (args.output/"report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report,indent=2))
    if not report["exact"] and not args.report_only:raise SystemExit(1)
