"""Download the official Serbian APR JSON to an isolated staging directory."""
import argparse
import hashlib
import json
from pathlib import Path
import requests

SOURCE='https://openapi.apr.gov.rs/api/opendata/companies'
MAX_BYTES=512*1024*1024


def download(destination):
    root=Path(destination)
    root.mkdir(parents=True,exist_ok=False)
    pending=root/'companies.json.incomplete'
    digest=hashlib.sha256()
    size=0
    with requests.get(SOURCE,headers={'Accept':'application/json','User-Agent':'Crawlvora APR importer'},stream=True,timeout=(15,90),allow_redirects=False) as response:
        response.raise_for_status()
        if response.status_code!=200 or 'json' not in response.headers.get('Content-Type','').lower():
            raise ValueError('Unexpected APR response')
        with pending.open('xb') as stream:
            for chunk in response.iter_content(1024*1024):
                size+=len(chunk)
                if size>MAX_BYTES: raise ValueError('APR response exceeded configured safety limit')
                digest.update(chunk); stream.write(chunk)
    with pending.open(encoding='utf-8-sig') as stream:
        data=json.load(stream)
    if not isinstance(data,(list,dict)) or not data: raise ValueError('Unexpected APR JSON')
    pending.rename(root/'companies.json')
    result={'country':'RS','source':SOURCE,'bytes':size,'sha256':digest.hexdigest(),'schema_verified':False,'imported':False}
    (root/'download-manifest.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination',type=Path)
    print(json.dumps(download(parser.parse_args().destination)))
