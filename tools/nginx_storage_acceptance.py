"""Disposable Nginx reverse-proxy integration; no real user catalog or hosting."""
import json
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import time
from urllib.request import urlopen
from urllib.error import HTTPError

ROOT=Path(__file__).resolve().parents[1]


def port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1",0))
        return sock.getsockname()[1]


def run():
    with tempfile.TemporaryDirectory() as tmp:
        root=Path(tmp); site=root/"site"
        shutil.copytree(ROOT/"webstranica",site)
        folder=site/"storage/data/HR"
        shard="HR-company-000001.json"
        (folder/shard).write_text(json.dumps([{"country":"HR","kind":"company","name":"Synthetic Nginx company","registration_number":"000000123","as_of":"2026-01-01"}]))
        (folder/"manifest.json").write_text(json.dumps({"country":"HR","count":1,"shards":[shard]}))
        backend,frontend=port(),port()
        config=root/"nginx.conf"
        config.write_text(f"""pid {root}/nginx.pid;
error_log {root}/error.log;
events {{ worker_connections 128; }}
http {{
    access_log off;
    client_body_temp_path {root}/body;
    proxy_temp_path {root}/proxy;
    fastcgi_temp_path {root}/fastcgi;
    uwsgi_temp_path {root}/uwsgi;
    scgi_temp_path {root}/scgi;
    server {{
        listen 127.0.0.1:{frontend};
        root {site};
        location ^~ /storage/ {{ deny all; }}
        location = /storage {{ deny all; }}
        location = / {{ proxy_pass http://127.0.0.1:{backend}/index.php; }}
        location = /index.php {{ proxy_pass http://127.0.0.1:{backend}; }}
        location ^~ /assets/ {{ try_files $uri =404; }}
        location / {{ return 404; }}
    }}
}}
""",encoding="utf-8")
        with (root/"php.log").open("wb") as log:
            php=subprocess.Popen(["php","-S",f"127.0.0.1:{backend}","-t",str(site)],stdout=log,stderr=log)
            nginx=None
            try:
                subprocess.run(["nginx","-t","-p",str(root),"-c",str(config)],check=True)
                nginx=subprocess.Popen(["nginx","-p",str(root),"-c",str(config),"-g","daemon off;"])
                base=f"http://127.0.0.1:{frontend}"
                for _ in range(100):
                    try:
                        with urlopen(base+"/",timeout=1):break
                    except OSError:time.sleep(.1)
                else:raise RuntimeError("Nginx failed to start")
                with urlopen(base+"/index.php?view=pretraga&country=HR&q=123",timeout=10) as response:
                    assert b"Synthetic Nginx company" in response.read()
                for path in ("/storage","/storage/","/storage/data/HR/manifest.json",
                             "/storage/data/HR/"+shard,"/storage%2fdata/HR/"+shard):
                    try:
                        with urlopen(base+path,timeout=10):pass
                    except HTTPError as error:
                        assert error.code==403,path
                        assert b"Synthetic Nginx company" not in error.read()
                        error.close()
                    else:raise AssertionError("Private storage accessible: "+path)
                print("NGINX_STORAGE_ACCEPTANCE_PASS (Nginx + PHP CLI upstream)")
            finally:
                for process in (nginx,php):
                    if process is not None:
                        process.terminate()
                        try:process.wait(timeout=10)
                        except subprocess.TimeoutExpired:process.kill();process.wait()


if __name__=="__main__":
    run()
