"""Native transport for large user-selected import/export files."""
import http.client
import json
import os
import tempfile
from pathlib import Path
from urllib.parse import urlencode

MAX_IMPORT=2*1024**3
MAX_EXPORT=8*1024**3
IMPORT_ROUTES={"/api/import","/api/import-json"}
EXPORT_ROUTES={"/api/export","/api/export-json","/api/export-xlsx","/api/export-fields",
               "/api/registry/export","/api/registry/export-csv","/api/registry/export-xlsx",
               "/api/registry/export-xml","/api/registry/export-sql","/api/recovery/download"}

def headers(client):
    return {"Cookie":f"crawlvora_session_{client.port}={client._token}","X-Local-Token":client._token}

def upload(client,route,path):
    if route not in IMPORT_ROUTES:raise ValueError("Nedopušten uvoz.")
    path=Path(path)
    if path.is_symlink() or not path.is_file():raise ValueError("Odaberite datoteku.")
    conn=http.client.HTTPConnection("127.0.0.1",client.port,timeout=900)
    try:
        with path.open("rb") as stream:
            size=os.fstat(stream.fileno()).st_size
            if not 0<size<=MAX_IMPORT:raise ValueError("Datoteka je prevelika ili prazna.")
            def chunks():
                remaining=size
                while remaining:
                    data=stream.read(min(1024**2,remaining))
                    if not data:raise ValueError("Datoteka je promijenjena tijekom uvoza.")
                    remaining-=len(data)
                    yield data
            conn.request("POST",route,body=chunks(),headers=dict(headers(client),**{"Content-Type":"application/octet-stream","Content-Length":str(size)}))
            with conn.getresponse() as response:
                raw=response.read(65537)
                if len(raw)>65536 or "application/json" not in response.getheader("Content-Type",""):raise ValueError("Neispravan odgovor.")
                result=json.loads(raw)
                if response.status!=200:raise ValueError("Uvoz nije uspio.")
                return result
    finally:conn.close()

def download(client,route,params,path):
    if route not in EXPORT_ROUTES:raise ValueError("Nedopušten izvoz.")
    path=Path(path).absolute()
    if path.exists() or path.is_symlink() or not path.parent.is_dir():raise ValueError("Odaberite novu datoteku.")
    conn=http.client.HTTPConnection("127.0.0.1",client.port,timeout=900)
    pending=None
    try:
        conn.request("GET",route+("?"+urlencode(params) if params else ""),headers=headers(client))
        with conn.getresponse() as response:
            if response.status!=200:raise ValueError("Izvoz nije uspio.")
            size=response.getheader("Content-Length")
            if size is not None and (not size.isdigit() or int(size)>MAX_EXPORT):raise ValueError("Izvoz je prevelik.")
            fd,name=tempfile.mkstemp(prefix=".tvrtke-export-",dir=path.parent)
            pending=Path(name)
            with os.fdopen(fd,"wb") as stream:
                total=0
                while chunk:=response.read(1024**2):
                    total+=len(chunk)
                    if total>MAX_EXPORT:raise ValueError("Izvoz je prevelik.")
                    stream.write(chunk)
                if size is not None and total!=int(size):raise ValueError("Izvoz nije potpun.")
                stream.flush();os.fsync(stream.fileno())
            os.link(pending,path)
            return {"bytes":total}
    finally:
        conn.close()
        if pending is not None:pending.unlink(missing_ok=True)
