"""Bounded production smoke: no bulk mirror, no records or credentials in logs."""
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from registry import Client, catalog, rows_of, credentials

class Pace:
    last_request=0
    def wait(self,seconds):
        if seconds>0:
            time.sleep(seconds)

def check():
    root=Path(__file__).resolve().parents[1]
    creds=credentials(root,Path(os.environ.get('CRAWLVORA_DATA_DIR',str(root/'data'))))
    if not all(creds):
        raise SystemExit('Production registry check blocked: configure private SUDREG_CLIENT_ID and SUDREG_CLIENT_SECRET.')
    client=Client(Pace(),creds,delay=3)
    try:
        client.auth()
        categories=catalog(client.spec())
        _, payload=client.get('snapshots')
        snapshot=next((r for r in rows_of(payload) if str(r.get('staleness'))=='1'),None)
        assert snapshot is not None,'No latest snapshot'
        identifier=str(snapshot.get('snapshot_id',snapshot.get('id','')))
        assert identifier.isdigit(),'Invalid snapshot identifier'
        assert {'limit','offset'}<=categories['subjekti'],'Bulk endpoint pagination is unavailable'
        headers,body=client.get('subjekti',{'snapshot_id':identifier,'limit':1,'offset':0})
        rows=rows_of(body)
        assert str(headers.get('X-Snapshot-Id',''))==identifier,'Snapshot mismatch'
        count=int(headers['X-Total-Count'])
        assert count>0 and len(rows)==1,'Expected one sample row'
        assert rows[0].get('mbs') is not None,'Missing company identifier'
        print(json.dumps({'oauth2':True,'public_openapi':True,'bulk_categories':len(categories),'snapshot_consistent':True,'sample_rows':len(rows),'total_rows':count}))
    finally:
        client.close()

if __name__=='__main__':
    try:
        check()
    except Exception as error:
        # Never log token responses, raw records, request headers or credential values.
        print('Production registry check failed: '+type(error).__name__,file=sys.stderr)
        raise SystemExit(1) from None
