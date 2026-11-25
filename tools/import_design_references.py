"""Import only the explicitly approved generated design archive. Never rebase references on app captures."""
import argparse
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile

ROOT=Path(__file__).resolve().parents[1]
LOCK=json.loads((ROOT/'branding/reference-lock.json').read_text(encoding='utf-8'))

def digest(data):
    return hashlib.sha256(data).hexdigest()

def verify():
    for name,expected in LOCK['files'].items():
        file=ROOT/name
        if not file.is_file() or digest(file.read_bytes())!=expected:
            raise ValueError('Missing or changed design reference: '+name)
    print('Verified all ten approved design reference PNGs.')

def import_archive(archive):
    if digest(archive.read_bytes())!=LOCK['archive_sha256']:
        raise ValueError('Archive SHA-256 mismatch')
    with ZipFile(archive) as z:
        paths=set(LOCK['files'])|{'branding/references/manifest.json'}
        if set(z.namelist())!=paths or len(z.namelist())!=len(paths):
            raise ValueError('Unexpected ZIP entries')
        content={name:z.read(name) for name in paths}
        for name,expected in LOCK['files'].items():
            if digest(content[name])!=expected:
                raise ValueError('Reference SHA-256 mismatch: '+name)
        for name,data in content.items():
            target=ROOT/name
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(data)
    verify()

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--verify',action='store_true')
    parser.add_argument('archive',nargs='?',type=Path)
    args=parser.parse_args()
    if args.verify: verify()
    elif args.archive: import_archive(args.archive)
    else: parser.error('Provide the approved reference ZIP or --verify')
