"""Lossless RGB comparison. No resizing, masking or perceptual threshold."""
import argparse
import json
from collections import Counter
from pathlib import Path
from PIL import Image,ImageChops

VIEWS=("overview","directory","registry","jobs","data","analytics","settings")

def region_diagnostics(delta):
    """Report where and how much pixels differ; never change the exact gate."""
    width,height=delta.size
    combined=ImageChops.lighter(ImageChops.lighter(*delta.split()[:2]),delta.split()[2])
    grid=[]
    for row in range(min(4,height)):
        for col in range(min(4,width)):
            x0,x1=col*width//min(4,width),(col+1)*width//min(4,width)
            y0,y1=row*height//min(4,height),(row+1)*height//min(4,height)
            hist=combined.crop((x0,y0,x1,y1)).histogram()
            total=(x1-x0)*(y1-y0)
            grid.append({"bounds":[x0,y0,x1,y1],"changed_pixels":total-hist[0],
                         "total_pixels":total,"mean_max_channel_error":round(sum(i*n for i,n in enumerate(hist))/total,6)})
    hist=combined.histogram()
    return {"max_channel_error_histogram":{"0":hist[0],"1_to_2":sum(hist[1:3]),
              "3_to_8":sum(hist[3:9]),"9_to_32":sum(hist[9:33]),"33_to_255":sum(hist[33:])},
            "regions":grid}


def dark_color_diagnostics(reference,candidate):
    """Diagnose signed one/two-level dark palette errors without ignoring them."""
    pairs=Counter()
    signed=Counter()
    for expected,actual in zip(reference.get_flattened_data(),candidate.get_flattened_data()):
        if max(expected)>64 or max(actual)>64 or expected==actual:
            continue
        residual=tuple(a-b for a,b in zip(actual,expected))
        if max(map(abs,residual))<=2:
            signed[residual]+=1
            pairs[(expected,actual)]+=1
    return {"pixels":sum(signed.values()),
            "signed_candidate_minus_reference":[{"rgb":list(rgb),"pixels":count}
                                                for rgb,count in signed.most_common()],
            "dominant_color_pairs":[{"reference":list(ref),"candidate":list(actual),"pixels":count}
                                    for (ref,actual),count in pairs.most_common(16)]}


def compare(reference,candidate,diff_dir):
    diff_dir.mkdir(parents=True,exist_ok=True)
    results=[]
    for view in VIEWS:
        with Image.open(reference/(view+"-dark.png")) as a, Image.open(candidate/(view+".png")) as b:
            if a.size!=b.size:
                raise ValueError(f"{view}: unequal dimensions {a.size} vs {b.size}")
            reference_rgb,candidate_rgb=a.convert("RGB"),b.convert("RGB")
            delta=ImageChops.difference(reference_rgb,candidate_rgb)
            combined=ImageChops.lighter(ImageChops.lighter(*delta.split()[:2]),delta.split()[2])
            hist=combined.histogram()
            total=a.width*a.height
            changed=total-hist[0]
            delta.save(diff_dir/(view+"-diff.png"))
            results.append({"view":view,"size":list(a.size),"changed_pixels":changed,"total_pixels":total,
                            "changed_percent":round(100*changed/total,6),"exact":changed==0,"diagnostics":{**region_diagnostics(delta),"dark_colors":dark_color_diagnostics(reference_rgb,candidate_rgb)}})
    return results

def meets_threshold(results, maximum=0):
    if not 0<=maximum<=100:raise ValueError("Invalid changed-pixel threshold")
    return len(results)==len(VIEWS) and all(100*r["changed_pixels"]<=maximum*r["total_pixels"] for r in results)

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("reference",type=Path);p.add_argument("candidate",type=Path);p.add_argument("output",type=Path)
    p.add_argument("--report-only",action="store_true")
    p.add_argument("--max-changed-percent",type=float,default=0)
    args=p.parse_args()
    results=compare(args.reference,args.candidate,args.output)
    report={"exact":meets_threshold(results),"threshold_percent":args.max_changed_percent,"threshold_passed":meets_threshold(results,args.max_changed_percent),"views":results}
    (args.output/"report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report,indent=2))
    if not report["threshold_passed"] and not args.report_only:raise SystemExit(1)
