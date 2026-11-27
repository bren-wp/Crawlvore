"""Record and verify the source and snapshot identities of accepted Windows pairs."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re

EDITIONS={'HR':('HR',),'Online':()}

def sha(value,length):
    if not isinstance(value,str) or not re.fullmatch('[a-f0-9]{'+str(length)+'}',value):
        raise ValueError('Invalid identity digest')
    return value

def names(edition):
    suffix='-'+edition
    return ('Portable'+suffix+'.exe','Setup'+suffix+'.exe')

def file_info(path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size==0:
        raise ValueError('Missing accepted asset: '+path.name)
    with path.open('rb') as stream:
        return {'size':path.stat().st_size,'sha256':hashlib.file_digest(stream,'sha256').hexdigest()}

def record(root,edition,source,hr):
    root=Path(root);source=sha(source,40)
    expected=EDITIONS[edition];data={}
    for country,value in (('HR',hr),):
        if country in expected:data[country]=sha(value,64)
        elif value:raise ValueError('Unexpected snapshot in '+edition)
    receipt={'edition':edition,'source_commit':source,'snapshots':data,
             'assets':{name:file_info(root/name) for name in names(edition)}}
    with (root/('acceptance-'+edition+'.json')).open('x',encoding='utf-8') as out:
        json.dump(receipt,out,sort_keys=True,indent=2);out.flush();os.fsync(out.fileno())
    return receipt

def verify(root,source,manifest):
    root=Path(root);source=sha(source,40)
    snapshots={country:sha(manifest[country]['database_sha256'],64) for country in ('HR',)}
    for edition,countries in EDITIONS.items():
        path=root/('acceptance-'+edition+'.json')
        if path.is_symlink() or not path.is_file() or path.stat().st_size>16384:
            raise ValueError('Missing or invalid edition acceptance: '+edition)
        actual=json.loads(path.read_text(encoding='utf-8'))
        expected={'edition':edition,'source_commit':source,
                  'snapshots':{country:snapshots[country] for country in countries},
                  'assets':{name:file_info(root/name) for name in names(edition)}}
        if actual!=expected:raise ValueError('Edition acceptance mismatch: '+edition)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('directory',type=Path);p.add_argument('--source',required=True)
    p.add_argument('--edition',choices=EDITIONS);p.add_argument('--hr',default='')
    p.add_argument('--manifest',type=Path)
    a=p.parse_args()
    if a.edition and not a.manifest:record(a.directory,a.edition,a.source,a.hr)
    elif a.manifest and not a.edition:verify(a.directory,a.source,json.loads(a.manifest.read_text(encoding='utf-8')))
    else:p.error('Specify edition or manifest')
    print('Edition acceptance evidence verified')
