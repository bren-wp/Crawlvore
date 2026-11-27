"""Registry credential resolution and per-workspace secure authorization."""
import json
import os
import sys
import threading
import time
from pathlib import Path
from native_vault import NativeVault, VaultUnavailable

def credentials(root, data_dir):
    # Treat each credential source as an indivisible pair. An explicitly supplied
    # environment configuration must never silently borrow a secret from a file.
    keys=('SUDREG_CLIENT_ID','SUDREG_CLIENT_SECRET')
    if any(k in os.environ for k in keys):
        return tuple(os.environ.get(k,'').strip() for k in keys)
    paths=[Path(data_dir)/'sudreg.private.json', Path(root)/'sudreg.private.json']
    if getattr(sys,'frozen',False):
        paths.append(Path(sys.executable).parent/'sudreg.private.json')
    for p in dict.fromkeys(paths):
        if not p.is_file():
            continue
        try:
            d=json.loads(p.read_text(encoding='utf-8-sig'))
            if not isinstance(d,dict):
                raise ValueError()
        except (OSError,ValueError):
            raise ValueError('Privatna konfiguracija nije valjana.') from None
        return tuple(v.strip() if isinstance(v,str) else '' for v in (d.get('client_id',''),d.get('client_secret','')))
    return ('','')

def configured(root,data_dir):
    try: return all(credentials(root,data_dir))
    except ValueError: return False


class RegistryAccess:
    """Per-workspace authorization, isolated from the backup vault."""
    def __init__(self,root,data_dir,vault=None):
        self.root=root
        self.data_dir=data_dir
        self.vault=vault if vault is not None else NativeVault(data_dir,purpose='registry')
        self.lock=threading.RLock()
        self.session=None
        self.saved=None
        self.loaded=False
        self.retry_after=0.0

    def _load(self):
        if not self.loaded and time.monotonic()>=self.retry_after:
            try:
                record=self.vault.load()
                if record is not None and record.get('authorized') is True:
                    self.saved=self._pair(record)
            except (VaultUnavailable,ValueError,OSError):
                # No plaintext fallback is created when the OS vault is unavailable.
                self.saved=None
                self.retry_after=time.monotonic()+30.0
                return
            self.loaded=True

    @staticmethod
    def _pair(data):
        if not isinstance(data,dict):
            raise ValueError('Invalid credentials.')
        pair=tuple(data.get(k) for k in ('client_id','client_secret'))
        if not all(isinstance(v,str) and 0<len(v.strip())<=512 and not any(ord(ch)<32 for ch in v) for v in pair):
            raise ValueError('Enter valid Client ID and Client Secret.')
        return tuple(v.strip() for v in pair)

    def current(self):
        with self.lock:
            if self.session is not None:
                return self.session
            if any(k in os.environ for k in ('SUDREG_CLIENT_ID','SUDREG_CLIENT_SECRET')):
                return credentials(self.root,self.data_dir),False
            self._load()
            if self.saved is not None:
                return self.saved,True
            return credentials(self.root,self.data_dir),False

    def credentials(self):
        return self.current()[0]

    def status(self):
        try:
            pair,authorized=self.current()
            return {'configured':all(pair),'authorized':authorized and all(pair)}
        except ValueError:
            return {'configured':False,'authorized':False}

    def apply(self,data):
        pair=self._pair(data)
        persist=data.get('persist',False)
        if type(persist) is not bool:
            raise ValueError('Invalid secure storage preference.')
        with self.lock:
            if persist:
                if data.get('permission') is not True:
                    raise ValueError('Potvrdite korištenje javnog API-ja.')
                try:
                    self.vault.save({'client_id':pair[0],'client_secret':pair[1],'authorized':True})
                except (VaultUnavailable,OSError):
                    raise ValueError('Sigurna pohrana pristupnih podataka nije dostupna.') from None
                self.saved=pair
                self.loaded=True
            self.session=(pair,persist)
            return self.status()

    def provision_from_environment(self):
        """Explicit, per-user managed deployment enrollment; never embed a shared secret."""
        if os.environ.pop('CRAWLVORA_REGISTRY_PROVISION','')!='1':
            return False
        # Consume the deployment pair before launching any vault subprocess.
        data={'client_id':os.environ.pop('SUDREG_CLIENT_ID',''),
              'client_secret':os.environ.pop('SUDREG_CLIENT_SECRET',''),
              'persist':True,'permission':True}
        self.apply(data)
        return True

    def provision_from_package(self):
        # Only a frozen private Windows worker can carry an embedded DPAPI capsule.
        if sys.platform!='win32' or not getattr(sys,'frozen',False) or os.environ.get('CRAWLVORA_NATIVE_SMOKE')=='1':
            return False
        capsule=Path(self.root)/'registry-private.dpapi'
        if not capsule.is_file(): return False
        with self.lock:
            try:
                # Any existing record (including a revocation tombstone) wins.
                if self.vault.load() is not None: return False
                if capsule.is_symlink() or not 0<capsule.stat().st_size<=65536:
                    raise ValueError('Invalid private registry package.')
                protector=NativeVault(Path.home()/'.crawlvora-private-package-v1',purpose='registry')
                data=json.loads(protector.crypt(capsule.read_bytes(),decrypt=True))
                if not isinstance(data,dict) or data.get('version')!=1:
                    raise ValueError('Invalid private registry package.')
                self.apply(dict(data,persist=True,permission=True))
                return True
            except (VaultUnavailable,OSError,ValueError,TypeError):
                raise ValueError('Private registry package cannot be authorized on this Windows profile.') from None

    def forget(self):
        with self.lock:
            try:
                self.vault.save({'authorized':False})
            except (VaultUnavailable,OSError):
                # Disable access for the current process even when persistent
                # revocation cannot be confirmed. Never claim the OS record was erased.
                self.saved=None
                self.loaded=False
                self.session=(('', ''),False)
                return dict(self.status(),revocation_verified=False)
            self.saved=None
            self.loaded=True
            self.session=(('', ''),False)
            return dict(self.status(),revocation_verified=True)
