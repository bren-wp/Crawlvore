"""Build a standalone, registry-only distribution mirror. No credentials in output."""
import argparse
from contextlib import closing
import getpass
import json
import os
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from core import Collector, Store
from data_safety import workspace_lock
from native_vault import NativeVault, VaultUnavailable
from registry import Registry, RegistryAccess, start_registry
from registry_bundle import verify_bundle


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('workspace',type=Path)
    parser.add_argument('--authorized-workspace',type=Path)
    parser.add_argument('--limit',type=int,default=1000)
    args=parser.parse_args()
    root=args.workspace.resolve()
    root.mkdir(parents=True,exist_ok=True)
    with workspace_lock(root):
        collect(args,root)


def collect(args,root):
    path=root/'registry-seed.sqlite3'
    if (root/'registry-seed.json').exists():
        report=verify_bundle(path)
        saved=json.loads((root/'registry-seed.json').read_text(encoding='utf-8'))
        if saved!=report:
            raise ValueError('Registry manifest does not match the verified database.')
        print(json.dumps(report,ensure_ascii=False))
        return
    keys=('SUDREG_CLIENT_ID','SUDREG_CLIENT_SECRET')
    if any(k in os.environ for k in keys):
        pair=tuple(os.environ.pop(k,'') for k in keys)
    elif args.authorized_workspace is not None:
        record=NativeVault(args.authorized_workspace.resolve(),purpose='registry').load()
        if not record or record.get('authorized') is not True:
            raise ValueError('Authorized local vault record required.')
        pair=RegistryAccess._pair(record)
    elif sys.stdin.isatty():
        pair=(getpass.getpass('Authorized Client ID: '),getpass.getpass('Authorized Client Secret: '))
    else:
        raise ValueError('Authorized registry credentials required.')
    pair=RegistryAccess._pair(dict(zip(('client_id','client_secret'),pair)))
    store=Store(path)
    bot=Collector(store)
    registry=Registry(store)
    with store.db() as db:
        snapshots=[row[0] for row in db.execute('SELECT snapshot FROM registry_runs')]
    if len(snapshots)>1:raise ValueError('Mixed distribution snapshots; originals retained.')
    start_registry(bot,registry,pair,args.limit,pinned_snapshot=snapshots[0] if snapshots else None)
    try:
        while True:
            status=bot.snapshot()
            if status['status'] not in ('running','stopping'):
                if status['status']!='completed':
                    raise ValueError('Registry collection incomplete; checkpoint retained.')
                break
            print(json.dumps({k:status[k] for k in ('page','last','processed','status')}),flush=True)
            time.sleep(30)
    except KeyboardInterrupt:
        bot.stop()
        while bot.snapshot()['status'] in ('running','stopping'):
            time.sleep(1)
        raise SystemExit(130) from None
    with closing(sqlite3.connect(path)) as db:
        if db.execute('PRAGMA wal_checkpoint(TRUNCATE)').fetchone()[0]:
            raise ValueError('Registry checkpoint busy.')
        db.execute('PRAGMA journal_mode=DELETE')
    report=verify_bundle(path)
    (root/'registry-seed.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False),flush=True)


if __name__=='__main__':
    try:
        main()
    except (OSError,ValueError,sqlite3.Error,VaultUnavailable) as error:
        print('Registry bundle not accepted: '+type(error).__name__,file=sys.stderr)
        raise SystemExit(1) from None
