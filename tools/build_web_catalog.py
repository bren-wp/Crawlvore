"""Create reviewed organization-only JSON shards for the separate website."""
import argparse
import json
import re
from datetime import date, datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
KINDS={'company','entrepreneur','institution','nonprofit','unknown'}
SOURCES=json.loads((ROOT/'webstranica/sources.json').read_text(encoding='utf-8'))


def publish_record(raw):
    country=raw.get('country')
    kind=raw.get('kind')
    if country not in SOURCES or SOURCES[country]['status']=='lookup_only' or kind not in KINDS:
        raise ValueError('Unsupported source or classification.')
    if raw.get('publication_reviewed') is not True:
        raise ValueError('Record requires publication review.')
    name=raw.get('name')
    if not isinstance(name,str) or not name.strip() or len(name)>500:
        raise ValueError('Invalid organization name.')
    as_of=date.fromisoformat(raw['as_of']).isoformat()
    record={'country':country,'kind':kind,'name':name.strip(),'as_of':as_of}
    for key in ('registration_number','tax_number','city'):
        value=raw.get(key)
        if value is None or value=='': continue
        if not isinstance(value,str) or len(value)>100: raise ValueError('Invalid published field.')
        if key=='tax_number' and kind in ('entrepreneur','unknown'): continue
        if key=='registration_number' and not re.fullmatch(r'[A-Za-z0-9 .-]{1,100}',value): raise ValueError('Invalid registration number.')
        if key=='tax_number' and not re.fullmatch(r'[A-Za-z0-9 .-]{1,100}',value): raise ValueError('Invalid tax number.')
        record[key]=value
    return record


def build(source,destination,country=None):
    destination=Path(destination)
    destination.mkdir(mode=0o700)
    buckets={}
    counters={}
    shards=[]
    count=0
    selected=country
    def flush(key):
        bucket=buckets[key]
        if not bucket: return
        counters[key]=counters.get(key,0)+1
        if counters[key]>999999: raise ValueError('Shard count exceeded.')
        name=f'{key}-{counters[key]:06d}.json'
        (destination/name).write_text(json.dumps(bucket,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
        shards.append(name)
        bucket.clear()
    with Path(source).open(encoding='utf-8') as stream:
        for line in stream:
            if not line.strip(): continue
            record=publish_record(json.loads(line))
            if selected is None: selected=record['country']
            if record['country']!=selected: raise ValueError('Mixed-country catalog rejected')
            key=record['country']+'-'+record['kind']
            bucket=buckets.setdefault(key,[])
            bucket.append(record)
            count+=1
            if len(bucket)>=500: flush(key)
    for key in buckets: flush(key)
    manifest={'version':1,'country':selected,'count':count,'published_at':datetime.now(timezone.utc).date().isoformat(),'shards':sorted(shards)}
    (destination/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    return manifest


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input_jsonl',type=Path)
    parser.add_argument('new_data_directory',type=Path)
    parser.add_argument('--country',choices=sorted(SOURCES),required=True)
    parser.add_argument('--publication-reviewed',action='store_true',required=True)
    args=parser.parse_args()
    print(json.dumps(build(args.input_jsonl,args.new_data_directory,args.country)))
