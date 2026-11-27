"""HTTP acceptance of all public PHP routes, using isolated synthetic catalogs."""
import json
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import time
from urllib.parse import urlencode
from urllib.request import urlopen
from urllib.error import HTTPError

ROOT=Path(__file__).resolve().parents[1]
PAGES=('home','pretraga','usluge','cjenik','o-nama','kontakt','privatnost','uvjeti-koristenja','kolacici','impressum','sources','help')

def run():
    php=shutil.which('php')
    if not php: raise RuntimeError('PHP CLI is required')
    with tempfile.TemporaryDirectory() as tmp:
        root=Path(tmp)/'site'
        shutil.copytree(ROOT/'webstranica',root)
        for country,name,number in [('HR','Synthetic <script>alert(1)</script>','000000123'),('GB','Synthetic British Company','AB123456')]:
            folder=root/'storage/data'/country
            shard=country+'-company-000001.json'
            (folder/shard).write_text(json.dumps([{'country':country,'kind':'company','name':name,'registration_number':number,'as_of':'2026-01-01'}]),encoding='utf-8')
            (folder/'manifest.json').write_text(json.dumps({'country':country,'count':1,'published_at':'2026-01-01','shards':[shard]}),encoding='utf-8')
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
        base=f'http://127.0.0.1:{port}'
        with (Path(tmp)/'php.log').open('w+b') as log:
            server=subprocess.Popen([php,'-S',f'127.0.0.1:{port}','-t',str(root)],stdout=log,stderr=log)  # nosec B603 -- fixed executable and arguments
            try:
                for _ in range(100):
                    try:
                        with urlopen(base+'/',timeout=1): break
                    except OSError: time.sleep(.1)
                else: raise RuntimeError('PHP server failed to start')
                def get(**params):
                    with urlopen(base+'/index.php?'+urlencode(params),timeout=10) as response:
                        assert response.status==200
                        assert response.headers['X-Content-Type-Options']=='nosniff'
                        assert "frame-ancestors 'none'" in response.headers['Content-Security-Policy']
                        return response.read().decode('utf-8')
                for page in PAGES:
                    html=get(view=page)
                    assert '<html lang="hr">' in html and '<h1>' in html and 'Crawlvora' in html,page
                hr=get(view='pretraga',country='HR',q='123')
                assert '000000123' in hr and '&lt;script&gt;alert(1)&lt;/script&gt;' in hr
                assert '<script>alert(1)</script>' not in hr
                gb=get(view='pretraga',country='GB',q='AB123456')
                assert 'Synthetic British Company' in gb and '000000123' not in gb
                assert 'Synthetic British Company' not in get(view='pretraga',country='HR',q='AB123456')
                assert '000000123' not in get(view='pretraga',country='HR',kind='nonprofit')
                try:
                    get(view='../../storage')
                except HTTPError as error:
                    assert error.code==404
                else: raise AssertionError('Invalid route accepted')
                folder=root/'storage/data/HR'
                shard='HR-entrepreneur-000001.json'
                record={'country':'HR','kind':'entrepreneur','name':'Synthetic sole trader',
                        'tax_number':'SYNTHETIC-TAX','as_of':'2026-01-01'}
                (folder/shard).write_text(json.dumps([record]),encoding='utf-8')
                (folder/'manifest.json').write_text(json.dumps({'country':'HR','count':1,'shards':[shard]}),encoding='utf-8')
                html=get(view='pretraga',country='HR')
                assert 'Synthetic sole trader' in html and 'SYNTHETIC-TAX' not in html
                assert 'Synthetic sole trader' not in get(view='pretraga',country='HR',q='SYNTHETIC-TAX')
                (folder/shard).write_text(json.dumps([dict(record,country='GB')]),encoding='utf-8')
                try:
                    get(view='pretraga',country='HR')
                except HTTPError as error:
                    assert error.code==503
                    error.close()
                else: raise AssertionError('Mismatched catalog country accepted')
                print(json.dumps({'pages':len(PAGES),'search':'PASS','isolation':'PASS','escaping':'PASS','invalid_route':'PASS','privacy_minimization':'PASS','country_validation':'PASS','scope':'PHP CLI HTTP; Apache access rules not exercised'}))
            finally:
                server.terminate()
                try: server.wait(timeout=10)
                except subprocess.TimeoutExpired: server.kill();server.wait()

if __name__=='__main__':
    run()
