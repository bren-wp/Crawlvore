"""Persistent, identity-checked UK download staging. Never truncate a saved partial."""
import json
import os
import re
import tempfile
from pathlib import Path

MAX_ARCHIVE=2*1024**3

def strong_etag(value):
    return value if isinstance(value,str) and re.fullmatch(r'"[^"\r\n]{1,250}"',value) else None

def save_meta(path,record):
    fd,name=tempfile.mkstemp(dir=path.parent,prefix='meta-')
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as output:
            json.dump(record,output);output.flush();os.fsync(output.fileno())
        os.replace(name,path)
    finally:
        Path(name).unlink(missing_ok=True)

def candidates(root,name):
    for folder in sorted(root.glob('transfer-*'),key=lambda p:p.name,reverse=True):
        if folder.is_symlink() or not folder.is_dir():continue
        path=folder/name;meta=folder/'transfer.json'
        if path.is_symlink() or meta.is_symlink() or not path.is_file() or not meta.is_file():continue
        try:
            if meta.stat().st_size>4096:continue
            record=json.loads(meta.read_text(encoding='utf-8'))
            size=path.stat().st_size;total=record['total']
            if record['name']!=name or type(total) is not int or not 0<size<=total<=MAX_ARCHIVE:continue
        except (OSError,ValueError,KeyError,TypeError):continue
        yield path,record,size

def transfer(session,url,root,name,check,progress):
    root.mkdir(parents=True,exist_ok=True)
    partial=None
    for path,record,size in candidates(root,name):
        if record.get('complete') is True and size==record['total']:return path
        if strong_etag(record.get('etag')) and size<record['total']:
            if partial is None or size>partial[2]:partial=(path,record,size)
    headers={'Accept-Encoding':'identity'}
    if partial:
        headers.update(Range=f'bytes={partial[2]}-',**{'If-Range':partial[1]['etag']})
    check()
    with session.get(url,timeout=(15,20),allow_redirects=False,stream=True,headers=headers) as response:
        encoding=response.headers.get('Content-Encoding','identity').lower()
        if encoding not in ('','identity'):raise ValueError('Unexpected encoded download.')
        etag=strong_etag(response.headers.get('ETag'))
        length=response.headers.get('Content-Length')
        if length is None or not length.isascii() or not length.isdigit() or len(length)>10:
            raise ValueError('Missing or invalid download length.')
        expected=int(length)
        if response.status_code==206 and partial:
            path,record,offset=partial
            total=record['total']
            if etag!=record['etag'] or response.headers.get('Content-Range')!=f'bytes {offset}-{total-1}/{total}' or expected!=total-offset:
                raise ValueError('Remote snapshot identity changed. Saved partial retained.')
            mode='ab'
        elif response.status_code==200:
            total=expected;offset=0;mode='xb'
            if not 0<total<=MAX_ARCHIVE:raise ValueError('Invalid download size.')
            # Range unsupported or identity changed: retain the previous file.
            folder=Path(tempfile.mkdtemp(prefix='transfer-',dir=root))
            path=folder/name
            record={'name':name,'total':total,'etag':etag,'complete':False}
            save_meta(folder/'transfer.json',record)
        else:raise ValueError('UK snapshot unavailable. Saved data retained.')
        count=offset;durable=offset
        with path.open(mode) as output:
            try:
                for chunk in response.iter_content(1024*1024):
                    check()
                    if count+len(chunk)>total:raise ValueError('Download exceeds declared size.')
                    output.write(chunk);count+=len(chunk)
                    if count-durable>=16*1024**2:
                        output.flush();os.fsync(output.fileno());durable=count
                    progress(phase='download',bytes=count,total=total)
            finally:
                output.flush();os.fsync(output.fileno())
        if count!=total:raise ValueError('Incomplete download. Saved bytes retained.')
        record['complete']=True
        save_meta(path.parent/'transfer.json',record)
        return path
