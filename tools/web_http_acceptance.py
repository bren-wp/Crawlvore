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
PAGES=('home','pretraga','usluge','cjenik','o-nama','kontakt','privatnost','uvjeti-koristenja','kolacici','impressum','sources','help','features','downloads')

def run():
    php=shutil.which('php')
    if not php: raise RuntimeError('PHP CLI is required')
    with tempfile.TemporaryDirectory() as tmp:
        root=Path(tmp)/'site'
        shutil.copytree(ROOT/'webstranica',root)
        (root/'site-config.json').write_text(json.dumps({'base_url':'https://example.invalid/catalog/'}),encoding='utf-8')
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
                    params.setdefault('lang','hr')
                    with urlopen(base+'/index.php?'+urlencode(params),timeout=10) as response:
                        assert response.status==200
                        assert response.headers['X-Content-Type-Options']=='nosniff'
                        assert "frame-ancestors 'none'" in response.headers['Content-Security-Policy']
                        return response.read().decode('utf-8')
                for page in PAGES:
                    html=get(view=page)
                    assert '<html lang="hr">' in html and '<h1>' in html and 'Crawlvora' in html,page
                for page in PAGES:
                    english=get(view=page,lang='en')
                    assert '<html lang="en">' in english and '<h1>' in english and 'Crawlvora' in english,page
                    assert 'Main navigation' in english,page
                    assert 'hreflang="hr"' in english and 'hreflang="en"' in english,page
                    assert 'https://example.invalid/catalog/index.php?view=' in english,page
                assert 'name="robots" content="noindex,follow"' in get(view='pretraga',kind='company')
                assert 'rel="canonical"' not in get(view='pretraga',q='123')
                hr=get(view='pretraga',country='HR',q='123')
                assert '000000123' in hr and '&lt;script&gt;alert(1)&lt;/script&gt;' in hr
                assert '<script>alert(1)</script>' not in hr
                gb=get(view='pretraga',country='GB',q='AB123456')
                assert 'Synthetic British Company' in gb and '000000123' not in gb
                profile=get(view='profile',country='GB',kind='company',id='AB123456',lang='en')
                assert 'Synthetic British Company' in profile and 'Company profile' in profile
                assert 'name="robots" content="noindex,follow"' in profile
                assert '000000123' not in profile
                for invalid in ('AB123','../secret'):
                    try: get(view='profile',country='GB',kind='company',id=invalid)
                    except HTTPError as error:
                        assert error.code==404
                        error.close()
                    else: raise AssertionError('Invalid profile accepted')
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
                def rejects_catalog():
                    try:
                        get(view='pretraga',country='HR')
                    except HTTPError as error:
                        assert error.code==503
                        error.close()
                    else: raise AssertionError('Malformed catalog accepted')
                (folder/shard).write_text(json.dumps([dict(record,as_of='invalid')]),encoding='utf-8')
                rejects_catalog()
                (folder/'manifest.json').write_text(json.dumps({'country':'HR','count':1,'shards':['GB-company-000001.json']}),encoding='utf-8')
                rejects_catalog()
                (folder/'manifest.json').write_text(json.dumps({'country':'HR','count':1,'shards':[shard]}),encoding='utf-8')
                outside=Path(tmp)/'outside.json'
                outside.write_text(json.dumps([record]),encoding='utf-8')
                (folder/shard).unlink()
                try:
                    (folder/shard).symlink_to(outside)
                except (OSError,NotImplementedError):
                    pass  # Windows without symlink privileges; Linux CI exercises this.
                else:
                    rejects_catalog()
                    (folder/shard).unlink()
                print(json.dumps({'pages':len(PAGES)*2,'search':'PASS','isolation':'PASS','escaping':'PASS','invalid_route':'PASS','privacy_minimization':'PASS','country_validation':'PASS','scope':'PHP CLI HTTP; Apache access rules not exercised'}))
            finally:
                server.terminate()
                try: server.wait(timeout=10)
                except subprocess.TimeoutExpired: server.kill();server.wait()

if __name__=='__main__':
    run()
