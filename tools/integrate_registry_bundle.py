"""Import a verified registry bundle without replacing the user's database."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from core import Store
from data_safety import verified_backup, workspace_lock
from registry import Registry
from registry_integration import integrate_snapshot
from workspace_integrity import inspect_database


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('workspace',type=Path)
    parser.add_argument('bundle',type=Path)
    parser.add_argument('manifest',type=Path)
    args=parser.parse_args()
    workspace=args.workspace.resolve()
    database=workspace/'companies.sqlite3'
    if not database.is_file() or database.is_symlink():
        raise ValueError('Existing workspace database required.')
    with workspace_lock(workspace):
        if inspect_database(database)!='ok':
            raise ValueError('Existing workspace failed integrity check.')
        if verified_backup(database) is None:
            raise ValueError('Verified pre-import backup required.')
        store=Store(database)
        report=integrate_snapshot(store,Registry(store),args.bundle,args.manifest)
        print(json.dumps(report))


if __name__=='__main__':
    try:
        main()
    except Exception as error:
        print('Registry integration not accepted: '+type(error).__name__,file=sys.stderr)
        raise SystemExit(1) from None
