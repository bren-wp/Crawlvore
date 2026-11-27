"""Report against the new approved design reference set, never historical UI screenshots."""
import argparse
import hashlib
import json
from pathlib import Path
from PIL import Image, ImageChops

def compare(reference,actual):
    lock=json.loads((reference.parent/'reference-lock.json').read_text(encoding='utf-8'))
    results=[]
    for entry in sorted(lock['files']):
        path=reference/Path(entry).name
        if path.stem in ('collector','studio'): continue  # retired by registry-only product scope
        capture=actual/('en-'+path.stem+'-dark-1440-fixture.png')
        row={'screen':path.stem,'identical':False}
        if not path.is_file() or not capture.is_file():
            row.update(missing_reference=not path.is_file(),missing_capture=not capture.is_file())
        elif hashlib.sha256(path.read_bytes()).hexdigest()!=lock['files'][entry]:
            row.update(reference_hash_mismatch=True)
        else:
            with Image.open(path) as aa,Image.open(capture) as bb:
                a,b=aa.convert('RGB'),bb.convert('RGB')
                if a.size!=b.size:
                    row.update(reference_size=a.size,actual_size=b.size,reason='Native chrome, fixture data or canvas dimensions differ; exact pixel comparison is not yet valid.')
                else:
                    difference=ImageChops.difference(a,b)
                    count=sum(pixel!=(0,0,0) for pixel in difference.getdata())
                    row.update(size=a.size,changed_pixels=count,changed_percent=round(100*count/(a.width*a.height),5),identical=count==0)
        results.append(row)
    return results

if __name__=='__main__':
    root=Path(__file__).resolve().parents[1]
    parser=argparse.ArgumentParser()
    parser.add_argument('--reference',type=Path,default=root/'branding/references')
    parser.add_argument('--actual',type=Path,default=root/'branding')
    parser.add_argument('--strict',action='store_true')
    args=parser.parse_args()
    rows=compare(args.reference,args.actual)
    print(json.dumps(rows,indent=2))
    raise SystemExit(1 if args.strict and (not rows or not all(row['identical'] for row in rows)) else 0)
