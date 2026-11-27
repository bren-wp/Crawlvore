"""Versioned authenticated, streaming backup encryption using PyCA cryptography.

Never publish unauthenticated plaintext. The caller supplies a private directory
for temporary files. The destination must not exist.
"""
import os
import tempfile
from pathlib import Path
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

MAGIC=b'CVBACKUP1'
CHUNK=1024*1024

def key_for(password,salt):
    if not isinstance(password,str) or not 16<=len(password)<=1024:
        raise ValueError('Use a backup passphrase of at least 16 characters.')
    return Scrypt(salt=salt,length=32,n=2**17,r=8,p=1).derive(password.encode('utf-8'))

def transform(source,destination,password,decrypt=False):
    source,destination=Path(source),Path(destination)
    if destination.exists() or destination.is_symlink(): raise FileExistsError('Destination exists.')
    fd,name=tempfile.mkstemp(prefix='.cvbackup-',dir=destination.parent)
    pending=Path(name)
    try:
        with os.fdopen(fd,'wb') as out,source.open('rb') as inp:
            if decrypt:
                header=inp.read(len(MAGIC)+28)
                if len(header)!=len(MAGIC)+28 or not header.startswith(MAGIC):
                    raise ValueError('Invalid encrypted backup.')
                size=os.fstat(inp.fileno()).st_size-len(header)-16
                if size<=0: raise ValueError('Invalid encrypted backup length.')
                inp.seek(-16,os.SEEK_END)
                tag=inp.read(16); inp.seek(len(header))
                ctx=Cipher(algorithms.AES(key_for(password,header[len(MAGIC):len(MAGIC)+16])),modes.GCM(header[-12:],tag)).decryptor()
                ctx.authenticate_additional_data(header)
                remaining=size
                while remaining:
                    chunk=inp.read(min(CHUNK,remaining))
                    if not chunk: raise ValueError('Truncated backup.')
                    out.write(ctx.update(chunk)); remaining-=len(chunk)
                out.write(ctx.finalize())
            else:
                salt,nonce=os.urandom(16),os.urandom(12)
                header=MAGIC+salt+nonce
                ctx=Cipher(algorithms.AES(key_for(password,salt)),modes.GCM(nonce)).encryptor()
                ctx.authenticate_additional_data(header); out.write(header)
                while chunk:=inp.read(CHUNK): out.write(ctx.update(chunk))
                out.write(ctx.finalize()); out.write(ctx.tag)
            out.flush(); os.fsync(out.fileno())
        # No overwrite: publish only a complete authenticated result.
        os.link(pending,destination)
        if os.name!='nt':
            directory=os.open(destination.parent,os.O_RDONLY)
            try: os.fsync(directory)
            finally: os.close(directory)
    finally:
        if pending.exists(): pending.unlink()
    return destination

def encrypt_backup(source,destination,password):
    return transform(source,destination,password)

def decrypt_backup(source,destination,password):
    return transform(source,destination,password,decrypt=True)
