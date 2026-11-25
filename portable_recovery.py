"""Authenticated portable recovery manifest; no machine-bound key required."""
import hashlib
import hmac
import json
import re
import tempfile
from pathlib import Path
from encrypted_backup import key_for, decrypt_backup
from data_safety import restore_workspace
from backup_replica import file_digest

def signature(key,body):
    raw=json.dumps(body,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()
    return hmac.new(key,b'Crawlvora portable recovery v1\x00'+raw,hashlib.sha256).hexdigest()

def manifest_bytes(key,salt,entry,count,head):
    body={'version':1,'salt':salt.hex(),'archive':entry['archive'],'bytes':entry['bytes'],
          'sha256':entry['sha256'],'sequence':entry['seq'],'catalog_count':count,'catalog_head':head}
    return json.dumps({'manifest':body,'signature':signature(key,body)},sort_keys=True,indent=2).encode()+b'\n'

def verify_manifest(raw,password,expected_head=None):
    if len(raw)>16384: raise ValueError('Recovery manifest too large.')
    document=json.loads(raw)
    if not isinstance(document,dict) or set(document)!={'manifest','signature'}: raise ValueError('Invalid manifest.')
    body=document['manifest']
    fields={'version','salt','archive','bytes','sha256','sequence','catalog_count','catalog_head'}
    if not isinstance(body,dict) or set(body)!=fields or body['version']!=1: raise ValueError('Invalid manifest.')
    if not isinstance(body['archive'],str) or not re.fullmatch(r'protected-[a-f0-9]{32}\.cvbackup',body['archive']): raise ValueError('Invalid archive name.')
    for field,length in (('salt',32),('sha256',64),('catalog_head',64)):
        if not isinstance(body[field],str) or not re.fullmatch('[a-f0-9]{'+str(length)+'}',body[field]): raise ValueError('Invalid manifest field.')
    if any(type(body[k]) is not int for k in ('bytes','sequence','catalog_count')) or not 53<body['bytes'] or not 1<=body['sequence']<=body['catalog_count']: raise ValueError('Invalid manifest values.')
    if not isinstance(document['signature'],str) or not hmac.compare_digest(document['signature'],signature(key_for(password,bytes.fromhex(body['salt'])),body)): raise ValueError('Recovery manifest authentication failed.')
    if expected_head is not None and not hmac.compare_digest(body['catalog_head'],expected_head): raise ValueError('Manifest does not match independent trusted checkpoint.')
    return body

def recover(manifest,archive,destination,password,expected_head=None):
    manifest,archive,destination=Path(manifest),Path(archive),Path(destination)
    if destination.exists() or destination.is_symlink(): raise FileExistsError('Destination already exists.')
    with manifest.open('rb') as stream: body=verify_manifest(stream.read(16385),password,expected_head)
    if archive.is_symlink() or not archive.is_file() or archive.name!=body['archive'] or archive.stat().st_size!=body['bytes'] or not hmac.compare_digest(file_digest(archive),body['sha256']):
        raise ValueError('Archive does not match authenticated manifest.')
    with tempfile.TemporaryDirectory(dir=destination.parent) as tmp:
        decoded=decrypt_backup(archive,Path(tmp)/'authenticated.sqlite3',password)
        return restore_workspace(decoded,destination)
