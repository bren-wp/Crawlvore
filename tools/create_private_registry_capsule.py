"""Create a user-bound Windows DPAPI capsule for private native builds only."""
import getpass
import json
import os
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from native_vault import NativeVault
from registry import RegistryAccess
from live_registry_check import check


def main():
    if sys.platform!='win32' or os.environ.get('GITHUB_ACTIONS') or os.environ.get('CI'):
        raise SystemExit('Private capsule creation requires the target Windows desktop user, not CI.')
    if len(sys.argv)!=2:
        raise SystemExit('Expected private capsule destination.')
    keys=('SUDREG_CLIENT_ID','SUDREG_CLIENT_SECRET')
    if any(k in os.environ for k in keys):
        pair=tuple(os.environ.pop(k,'') for k in keys)
    else:
        pair=(getpass.getpass('Authorized Client ID: '),getpass.getpass('Authorized Client Secret: '))
    client_id,client_secret=RegistryAccess._pair(dict(zip(('client_id','client_secret'),pair)))
    # A private build must verify the actual pair before sealing it.
    try:
        check((client_id,client_secret))
    except Exception as error:
        raise SystemExit('Private registry authorization check failed: '+type(error).__name__) from None
    raw=json.dumps({'version':1,'client_id':client_id,'client_secret':client_secret},separators=(',',':')).encode()
    vault=NativeVault(Path.home()/'.crawlvora-private-package-v1',purpose='registry')
    sealed=vault.crypt(raw)
    if vault.crypt(sealed,decrypt=True)!=raw:
        raise SystemExit('Private capsule verification failed.')
    path=Path(sys.argv[1])
    with path.open('xb') as stream:
        stream.write(sealed)
    print('Private DPAPI capsule verified; no credential values printed.')


if __name__=='__main__':
    main()
