"""Compare captured screenshots to a fixed reference directory, no automatic rebasing."""
import argparse, json
from pathlib import Path
from PIL import Image, ImageChops

def compare(reference,actual):
    results=[]
    for path in sorted(reference.glob('*fixture.png')):
        other=actual/path.name
        if not other.is_file(): results.append({'file':path.name,'identical':False,'missing':True}); continue
        with Image.open(path) as aa, Image.open(other) as bb:
            a,b=aa.convert('RGB'),bb.convert('RGB')
            if a.size!=b.size: results.append({'file':path.name,'reference':a.size,'actual':b.size,'identical':False}); continue
            d=ImageChops.difference(a,b); count=sum(p!=(0,0,0) for p in d.getdata()); results.append({'file':path.name,'size':a.size,'changed_pixels':count,'changed_percent':round(100*count/(a.width*a.height),5),'identical':count==0})
    if not results: raise ValueError('Reference directory contains no fixture screenshots')
    return results
if __name__=='__main__':
    root=Path(__file__).resolve().parents[1]; p=argparse.ArgumentParser(); p.add_argument('--reference',type=Path,default=root/'verification/v7-reference'); p.add_argument('--actual',type=Path,default=root/'branding'); p.add_argument('--strict',action='store_true'); args=p.parse_args(); rows=compare(args.reference,args.actual); print(json.dumps(rows,indent=2)); raise SystemExit(1 if args.strict and not all(x['identical'] for x in rows) else 0)
