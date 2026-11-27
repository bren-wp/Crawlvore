"""Recover an encrypted backup into a new workspace; never overwrite an existing one."""
import argparse
import getpass
import sys
import tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from encrypted_backup import decrypt_backup
from data_safety import restore_workspace

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('archive',type=Path)
    p.add_argument('new_workspace',type=Path)
    a=p.parse_args()
    if a.new_workspace.exists() or a.new_workspace.is_symlink():
        p.error('Destination already exists.')
    try:
        with tempfile.TemporaryDirectory(dir=a.new_workspace.parent) as tmp:
            decoded=decrypt_backup(a.archive,Path(tmp)/'verified.sqlite3',getpass.getpass('Backup passphrase: '))
            restore_workspace(decoded,a.new_workspace)
    except Exception as error:
        p.exit(1,'Recovery failed; no existing workspace was replaced. '+type(error).__name__+'\n')
    print('Verified recovered workspace:',a.new_workspace)
