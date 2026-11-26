"""Stage actual HR and GB snapshots for a private, local native preview build."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parent))
from prepare_registry_preview import prepare as prepare_hr
from prepare_national_bundle import prepare as prepare_gb

def stage(hr,gb,root):
    root=Path(root).resolve()
    if not (root/'tvrtk_scraper.py').is_file(): raise ValueError('Expected source checkout.')
    if (root/'registry-bundle').exists() or (root/'national-data').exists(): raise ValueError('Refusing to overwrite existing staging.')
    hr_report=prepare_hr(hr,root/'registry-bundle')
    print(json.dumps({'HR':hr_report}),flush=True)
    gb_report=prepare_gb(gb,root/'national-data/GB')
    print(json.dumps({'GB':gb_report}),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('hr')
    parser.add_argument('gb')
    parser.add_argument('root')
    parser.add_argument('--private-local-preview',action='store_true',required=True)
    args=parser.parse_args()
    stage(args.hr,args.gb,args.root)
