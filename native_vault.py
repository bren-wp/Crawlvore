"""OS-protected catalog credentials and external checkpoint, never a plaintext key file."""
import ctypes
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

class VaultUnavailable(RuntimeError):
    pass

class NativeVault:
    def __init__(self,workspace,purpose='backup'):
        if purpose not in ('backup','registry'):
            raise ValueError('Unsupported vault purpose.')
        identity=os.fsencode(os.path.normcase(str(Path(workspace).resolve())))
        # Preserve existing backup vault identifiers exactly.
        if purpose=='registry':
            identity=b'Crawlvora registry credentials\x00'+identity
        self.identity=hashlib.sha256(identity).hexdigest()
        self.purpose=purpose
        self.backend='dpapi' if sys.platform=='win32' else 'secret-service' if sys.platform.startswith('linux') else 'unsupported'

    def windows_path(self):
        base=os.environ.get('LOCALAPPDATA')
        if not base: raise VaultUnavailable('Windows profile unavailable.')
        return Path(base)/'CrawlvoraSecureVault'/ (self.identity+'.dpapi')

    def crypt(self,data,decrypt=False):
        from ctypes import wintypes
        class Blob(ctypes.Structure):
            _fields_=[('cbData',wintypes.DWORD),('pbData',ctypes.POINTER(ctypes.c_ubyte))]
        def blob(value):
            buf=(ctypes.c_ubyte*len(value)).from_buffer_copy(value)
            return Blob(len(value),buf),buf
        inp,buf=blob(data)
        entropy,entropy_buf=blob(('Crawlvora:'+self.identity).encode())
        out=Blob()
        dll=ctypes.WinDLL('crypt32',use_last_error=True)
        fn=dll.CryptUnprotectData if decrypt else dll.CryptProtectData
        fn.argtypes=[ctypes.POINTER(Blob),ctypes.c_void_p,ctypes.POINTER(Blob),ctypes.c_void_p,ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(Blob)]
        fn.restype=wintypes.BOOL
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.LocalFree.argtypes=[ctypes.c_void_p]
        kernel.LocalFree.restype=ctypes.c_void_p
        try:
            if not fn(ctypes.byref(inp),None,ctypes.byref(entropy),None,None,1,ctypes.byref(out)):
                raise VaultUnavailable('Windows DPAPI operation failed.')
            return ctypes.string_at(out.pbData,out.cbData)
        finally:
            if out.pbData:
                ctypes.memset(out.pbData,0,out.cbData)
                kernel.LocalFree(out.pbData)
            ctypes.memset(buf,0,len(buf))
            ctypes.memset(entropy_buf,0,len(entropy_buf))

    def secret_tool(self,action,value=None):
        executable=shutil.which('secret-tool')
        if not executable or not os.environ.get('DBUS_SESSION_BUS_ADDRESS'):
            raise VaultUnavailable('Linux Secret Service is unavailable.')
        args=[executable,action]
        if action=='store': args+=['--label='+('Crawlvora registry access' if self.purpose=='registry' else 'Crawlvora protected backup catalog')]
        args+=['application','Crawlvora','workspace',self.identity]
        try:
            result=subprocess.run(args,input=value,capture_output=True,timeout=20,check=False)  # nosec B603 -- fixed executable/arguments; secret only via stdin.
        except (OSError,subprocess.TimeoutExpired) as error:
            raise VaultUnavailable('Linux Secret Service request failed.') from error
        if result.returncode:
            if action=='lookup' and result.returncode==1 and not result.stderr.strip(): return None
            raise VaultUnavailable('Linux Secret Service request failed.')
        return result.stdout.rstrip(b'\n')

    def load(self):
        if self.backend=='dpapi':
            path=self.windows_path()
            if path.parent.is_symlink() or path.is_symlink(): raise VaultUnavailable('Invalid vault path.')
            if not path.exists(): return None
            if path.stat().st_size>65536: raise VaultUnavailable('Invalid vault record size.')
            raw=self.crypt(path.read_bytes(),True)
        elif self.backend=='secret-service':
            raw=self.secret_tool('lookup')
            if raw is None: return None
        else: raise VaultUnavailable('Unsupported secure vault.')
        try:
            value=json.loads(raw)
            if not isinstance(value,dict) or value.get('identity')!=self.identity or value.get('version')!=1: raise ValueError()
            return value
        except (ValueError,TypeError) as error:
            raise VaultUnavailable('Invalid protected vault record.') from error

    def save(self,value):
        raw=json.dumps(dict(value,identity=self.identity,version=1),separators=(',',':')).encode()
        if self.backend=='dpapi':
            path=self.windows_path()
            if path.parent.is_symlink() or path.is_symlink(): raise VaultUnavailable('Invalid vault path.')
            path.parent.mkdir(parents=True,exist_ok=True)
            protected=self.crypt(raw)
            fd,name=tempfile.mkstemp(prefix='vault-',dir=path.parent)
            try:
                with os.fdopen(fd,'wb') as stream:
                    stream.write(protected); stream.flush(); os.fsync(stream.fileno())
                os.replace(name,path)
            finally:
                if os.path.exists(name): os.unlink(name)
        elif self.backend=='secret-service':
            self.secret_tool('store',raw)
        else: raise VaultUnavailable('Unsupported secure vault.')
        if self.load()!=json.loads(raw): raise VaultUnavailable('Secure vault read-back failed.')
