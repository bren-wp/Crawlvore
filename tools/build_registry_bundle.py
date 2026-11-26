"""Build a standalone, registry-only distribution mirror. No credentials in output."""
import argparse
import getpass
import json
import os
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from core import Collector, Store
from registry import Registry, RegistryAccess, start_registry
from registry_bundle import verify_bundle


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('workspace',type=Path)
    parser.add_argument('--limit',type=int,default=1000)
    args=parser.parse_args()
    root=args.workspace.resolve()
    root.mkdir(parents=True,exist_ok=True)
    path=root/'registry-seed.sqlite3'
    if (root/'registry-seed.json').exists():
        print(json.dumps(verify_bundle(path),ensure_ascii=False))
        return
    keys=('SUDREG_CLIENT_ID','SUDREG_CLIENT_SECRET')
    if any(k in os.environ for k in keys):
        pair=tuple(os.environ.pop(k,'') for k in keys)
    elif sys.stdin.isatty():
        pair=(getpass.getpass('Authorized Client ID: '),getpass.getpass('Authorized Client Secret: '))
    else:
        raise ValueError('Authorized registry credentials required.')
    pair=RegistryAccess._pair(dict(zip(('client_id','client_secret'),pair)))
    store=Store(path)
    bot=Collector(store)
    registry=Registry(store)
    start_registry(bot,registry,pair,args.limit)
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
    with sqlite3.connect(path) as db:
        if db.execute('PRAGMA wal_checkpoint(TRUNCATE)').fetchone()[0]:
            raise ValueError('Registry checkpoint busy.')
        db.execute('PRAGMA journal_mode=DELETE')
    report=verify_bundle(path)
    (root/'registry-seed.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False),flush=True)


if __name__=='__main__':
    try:
        main()
    except (OSError,ValueError,sqlite3.Error) as error:
        print('Registry bundle not accepted: '+type(error).__name__,file=sys.stderr)
        raise SystemExit(1) from None
