"""Verify the exact 14-file release matrix before promotion, including remote asset digests."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import zipfile

FILES=('Portable.exe','Setup.exe','Portable-HR.exe','Setup-HR.exe','Portable-GB.exe','Setup-GB.exe','Portable-Online.exe','Setup-Online.exe','Crawlvora-Linux-amd64.deb','Crawlvora-Linux-x86_64.tar.gz','Crawlvora-source.zip','REGISTRY-MANIFEST.json','Crawlvora-WordPress.zip')
ALL_FILES=set(FILES)|{'SHA256SUMS.txt'}
MAX_SIZE=2*1024**3

def digest(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def validate_snapshots(hr,gb):
    # Older completed HR manifests omit the complete flag. Partial manifests
    # always carry explicit progress; never accept those for distribution.
    if not isinstance(hr,dict) or not isinstance(gb,dict):
        raise ValueError('Invalid registry snapshot manifest')
    categories=hr.get('categories')
    if (hr.get('complete',True) is not True
            or 'progress' in hr or 'completed_categories' in hr
            or hr.get('scope')!='all-status'
            or not isinstance(categories,dict) or len(categories)<36
            or any(not isinstance(key,str) or not key or type(count) is not int or count<0
                   for key,count in categories.items())
            or type(hr.get('category_count')) is not int
            or hr['category_count']!=len(categories)
            or type(hr.get('subjects')) is not int or hr['subjects']<1
            or categories.get('subjekti')!=hr['subjects']
            or type(hr.get('rows')) is not int or hr['rows']!=sum(categories.values())):
        raise ValueError('Incomplete or inconsistent HR snapshot')
    if (gb.get('complete') is not True or gb.get('country')!='GB'
            or type(gb.get('rows')) is not int or gb['rows']<1):
        raise ValueError('Incomplete GB snapshot')
    for data in (hr,gb):
        identity=data.get('database_sha256')
        if not isinstance(identity,str) or not re.fullmatch(r'[0-9a-f]{64}',identity):
            raise ValueError('Missing database identity')

def validate_zip(path, *, wordpress=False):
    """Reject ambiguous, traversing and nonregular members before promotion."""
    plugin="crawlvora-business-directory/"
    required={plugin+name for name in (
        "crawlvora-business-directory.php","includes/class-catalog.php",
        "assets/directory.css","readme.txt","uninstall.php")}
    prefix=plugin if wordpress else "Crawlvora/"
    names=set()
    files=set()
    with zipfile.ZipFile(path) as archive:
        for info in archive.infolist():
            name=info.filename
            parts=name.rstrip("/").split("/")
            key=name.rstrip("/").casefold()
            mode=(info.external_attr>>16)&0o170000
            if (not name.startswith(prefix) or not all(parts)
                    or any(part in (".","..") for part in parts)
                    or "\\" in name or ":" in name or key in names
                    or mode not in ((0,0o040000) if info.is_dir() else (0,0o100000))):
                raise ValueError("Unsafe ZIP member: "+name)
            names.add(key)
            if not info.is_dir(): files.add(name)
        if not files or archive.testzip() is not None:
            raise ValueError("Invalid ZIP: "+str(path))
        if wordpress and files!=required:
            raise ValueError("Unexpected WordPress package content")
        if not wordpress and not {"Crawlvora/VERSION","Crawlvora/package.json"}<=files:
            raise ValueError("Incomplete source archive")


def validate(root):
    root=Path(root)
    result={}
    for name in FILES:
        path=root/name
        if path.is_symlink() or not path.is_file() or not 0<path.stat().st_size<MAX_SIZE:
            raise ValueError('Missing or invalid asset: '+name)
        with path.open('rb') as stream:
            prefix=stream.read(8)
        if name.endswith('.exe') and prefix[:2]!=b'MZ':raise ValueError('Invalid Windows executable: '+name)
        if name.endswith('.deb') and prefix!=b'!<arch>\n':raise ValueError('Invalid DEB')
        if name.endswith('.tar.gz') and prefix[:2]!=b'\x1f\x8b':raise ValueError('Invalid TAR.GZ')
        if name.endswith('.zip'):
            validate_zip(path,wordpress=name=='Crawlvora-WordPress.zip')
        result[name]={'size':path.stat().st_size,'digest':'sha256:'+digest(path)}
    manifest=json.loads((root/'REGISTRY-MANIFEST.json').read_text(encoding='utf-8'))
    if manifest.get('windows_editions')!={'Full':['HR','GB'],'HR':['HR'],'GB':['GB'],'Online':[]}:
        raise ValueError('Incorrect edition matrix')
    hr,gb=manifest['HR'],manifest['GB']
    validate_snapshots(hr,gb)
    sums=root/'SHA256SUMS.txt'
    if sums.is_symlink() or not sums.is_file():raise ValueError('Missing checksums')
    expected={name:info['digest'][7:] for name,info in result.items()}
    lines=sums.read_text(encoding='ascii').splitlines()
    if len(lines)!=len(expected):raise ValueError('Incorrect checksum count')
    actual={}
    for line in lines:
        match=re.fullmatch(r'([a-f0-9]{64}) [ *](.+)',line)
        if not match or match[2] in actual:raise ValueError('Invalid checksum list')
        actual[match[2]]=match[1]
    if actual!=expected:raise ValueError('Checksum mismatch')
    result[sums.name]={'size':sums.stat().st_size,'digest':'sha256:'+digest(sums)}
    return result

def verify_remote(local,release):
    if release.get('draft') is not True:raise ValueError('Release must still be a draft')
    assets=release.get('assets',[])
    if len(assets)!=len(ALL_FILES) or {a['name'] for a in assets}!=ALL_FILES:raise ValueError('Remote asset matrix mismatch')
    for asset in assets:
        expected=local[asset['name']]
        if asset.get('state')!='uploaded' or asset.get('size')!=expected['size'] or asset.get('digest')!=expected['digest']:
            raise ValueError('Remote verification failed: '+asset['name'])

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('directory',type=Path);p.add_argument('--remote',type=Path)
    args=p.parse_args();local=validate(args.directory)
    if args.remote:verify_remote(local,json.loads(args.remote.read_text(encoding='utf-8')))
    print('Release matrix accepted:',len(local))
