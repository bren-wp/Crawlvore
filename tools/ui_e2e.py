"""Real loopback browser/API integration checks without remote scraping or credentials."""
import json
import os
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from core import Store

def run():
    with tempfile.TemporaryDirectory() as tmp:
        data=Path(tmp)/'data'
        data.mkdir()
        store=Store(data/'companies.sqlite3')
        with store.db() as db:
            for i in range(60):
                store.upsert(db,{'title':f'Demo company {i:03d}','mbs':f'{i+1:09d}','city':'Zagreb' if i%2 else 'Rijeka','phone':'012345' if i%3==0 else '', 'email':'contact@example.invalid' if i==0 else '', 'website':'https://example.invalid' if i%4==0 else ''},provider='csv')
            db.execute("INSERT INTO meta(key,value) VALUES ('ui_language','en')")

        env={k:v for k,v in os.environ.items() if not k.startswith(('SUDREG_','CRAWLVORA_REGISTRY_'))}
        # Do not leave an unread stderr pipe that can block a worker during shutdown.
        worker_log=(Path(tmp)/'worker-stderr.log').open('w+b')
        worker=subprocess.Popen([sys.executable,str(ROOT/'src/tvrtk_scraper.py'),'--worker','--port','0','--data-dir',str(data)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=worker_log,text=True,env=env,cwd=tmp)
        try:
            with ThreadPoolExecutor(max_workers=1) as pool:
                future=pool.submit(worker.stdout.readline)
                try: line=future.result(timeout=90)
                except TimeoutError:
                    worker.kill()
                    raise
            assert line.startswith('CRAWLVORA_READY '),'Worker did not start'
            session=line.strip().split(' ',1)[1]
            errors=[]
            with sync_playwright() as p:
                browser=p.chromium.launch(headless=True,executable_path=os.getenv('CRAWLVORA_TEST_CHROMIUM') or None)
                page=browser.new_page(accept_downloads=True,viewport={'width':1440,'height':900})
                page.on('pageerror',lambda error:errors.append(str(error)))
                page.add_init_script("""document.addEventListener('click',event=>{const button=event.target.closest('button');if(!button)return;const name=button.id||['view','go','profileTab','contactFilter'].map(key=>key in button.dataset?key+':'+button.dataset[key]:'').filter(Boolean).join('|')||'dynamic';const seen=JSON.parse(sessionStorage.getItem('cvQAControls')||'[]');if(!seen.includes(name)){seen.push(name);sessionStorage.setItem('cvQAControls',JSON.stringify(seen));}},true)""")
                page.goto(session,wait_until='domcontentloaded')
                expect(page.locator('html')).to_have_attribute('lang','hr')
                expect(page.locator('#preview-rows .textbtn').first).to_be_visible(timeout=20000)
                page.locator('#top-export').click()
                expect(page.locator('#data')).to_be_visible()
                page.locator('[data-view="overview"]').click()
                page.locator('#overview [data-go="directory"]').click()
                expect(page.locator('#company-rows .textbtn').first).to_be_visible()
                page.locator('[data-view="directory"]').click()
                page.locator('#search').fill('No-match-crawlvora-qa-79cbad')
                expect(page.locator('#result-count')).to_have_text('0 rezultata')
                expect(page.locator('#company-rows')).to_contain_text('Nema rezultata za odabrane kriterije.')
                page.locator('#reset').click()
                expect(page.locator('#company-rows .textbtn').first).to_be_visible()
                page.locator('#next').click()
                expect(page.locator('#prev')).to_be_enabled()
                page.locator('#prev').click()
                for filter_value in ('phone','web','email','missing',''):
                    page.locator('#contact').select_option(filter_value)
                    expect(page.locator('#contact')).to_have_value(filter_value)
                page.locator('#reset').click()
                for selector,extension in [('#filtered-export','.csv'),('#filtered-xlsx','.xlsx')]:
                    with page.expect_download(timeout=60000) as event:
                        page.locator(selector).click()
                    assert event.value.suggested_filename.endswith(extension)
                page.locator('#company-rows .textbtn').first.click()
                expect(page.locator('#detail')).to_be_visible()
                page.locator('[data-profile-tab="history"]').click()
                expect(page.locator('.history-block')).to_be_visible()
                page.locator('[data-profile-tab="details"]').click()
                expect(page.locator('.profile-property').first).to_be_visible()
                expect(page.locator('.profile-group')).to_have_count(3)
                page.locator('#detail').get_by_role('button',name='Sastavi e-poštu').click()
                expect(page.locator('#mail-dialog')).to_be_visible()
                expect(page.locator('#mail-recipient')).to_have_value('contact@example.invalid')
                expect(page.locator('#mail-send')).to_be_disabled()
                page.locator('#mail-template').select_option('security')
                expect(page.locator('#mail-subject')).to_have_value('Sigurnosno upozorenje – provjerite sumnjive poruke')
                expect(page.locator('#mail-body')).not_to_have_value('')
                expect(page.locator('#mail-send')).to_be_disabled()
                page.locator('#mail-close').click()
                expect(page.locator('#mail-dialog')).not_to_be_visible()
                page.locator('#close-detail').click()
                expect(page.locator('#detail')).not_to_be_visible()
                page.locator('[data-view="registry"]').click()
                expect(page.locator('#reg-categories')).to_contain_text('Nema preuzetih kategorija. Pokrenite sinkronizaciju.')
                expect(page.locator('#reg-config')).to_have_text('Pristup nije omogućen')
                expect(page.locator('#reg-start')).to_be_disabled()
                expect(page.locator('#reg-check')).to_be_disabled()
                expect(page.locator('#reg-stop')).to_be_disabled()
                expect(page.locator('#diff-run')).to_be_disabled()
                expect(page.locator('#registry h1')).to_have_text('Crawlvora')
                page.locator('#reg-reload').click()
                expect(page.locator('#reg-categories')).to_contain_text('Nema preuzetih kategorija. Pokrenite sinkronizaciju.')
                assert page.locator('[data-view="collector"],[data-view="studio"]').count()==0
                page.locator('[data-view="jobs"]').click()
                expect(page.locator('#job-rows')).to_contain_text('Nema spremljenih zadataka.')
                page.locator('#jobs-refresh').click()
                expect(page.locator('#job-rows')).to_contain_text('Nema spremljenih zadataka.')
                page.locator('#schedule-enabled').uncheck()
                page.locator('#schedule-hour').fill('4')
                page.locator('#schedule-save').click()
                expect(page.locator('#schedule-state')).to_have_text('Isključeno')
                page.locator('[data-view="data"]').click()
                page.locator('#file').set_input_files({'name':'qa.json','mimeType':'application/json','buffer':json.dumps([{'title':'Crawlvora QA Synthetic Company','city':'Synthetic','phone':'111','oib':'12345678903','mbs':'987654321','entity_kind':'company'},{'title':'Crawlvora QA Synthetic Company','city':'Synthetic','phone':'222','oib':'12345678903','mbs':'987654321'}]).encode()})
                page.locator('#import-btn').click()
                expect(page.locator('#file-name')).to_have_text('Nije odabrana datoteka.')
                page.locator('[data-view="directory"]').click()
                for query in ('Crawlvora QA Synthetic Company','12345678903','987654321'):
                    page.locator('#search').fill(query)
                    expect(page.locator('#result-count')).to_have_text('1 rezultata')
                    expect(page.locator('#company-rows tr')).to_contain_text('Crawlvora QA Synthetic Company')
                page.locator('#search').fill('Crawlvora QA Synthetic Company')
                with page.expect_response(lambda response: '/api/companies?' in response.url and 'entity_kind=nonprofit' in response.url) as filtered_response:
                    page.locator('#entity-kind').select_option('nonprofit')
                assert filtered_response.value.json()['total']==0
                expect(page.locator('#result-count')).to_have_text('0 rezultata')
                page.locator('#entity-kind').select_option('company')
                expect(page.locator('#company-rows .textbtn')).to_have_count(1)
                page.locator('#entity-kind').select_option('')
                page.locator('#company-rows .textbtn').click()
                page.locator('[data-profile-tab="history"]').click()
                expect(page.locator('.alternate-values')).to_contain_text('222')
                expect(page.locator('[data-profile-tab="sources"]')).to_have_count(0)
                assert 'sudreg-data.gov.hr' not in page.locator('#detail').inner_text().lower()
                assert 'Podrijetlo podataka' not in page.locator('#detail').inner_text()

                page.locator('[data-profile-tab="registry"]').click()
                expect(page.locator('.profile-registry')).to_be_visible()
                expect(page.locator('.profile-registry')).to_contain_text('Nema dodatnih poslovnih zapisa.')
                expect(page.locator('.profile-property').first).not_to_be_visible()
                page.locator('#close-detail').click()
                page.locator('[data-view="data"]').click()
                page.locator('#export-clear-all').click()
                expect(page.locator('#export-selected')).to_be_disabled()
                page.locator('input[name="export-field"][value="title"]').check()
                page.locator('input[name="export-field"][value="oib"]').check()
                expect(page.locator('#export-selected')).to_be_enabled()
                page.locator('#export-format').select_option('json')
                with page.expect_download(timeout=60000) as selected_download:
                    page.locator('#export-selected').click()
                with selected_download.value.path().open(encoding='utf-8') as stream:
                    records=json.load(stream)
                assert records and all(set(record)=={'title','oib'} for record in records)
                page.locator('#export-select-all').click()
                assert page.locator('input[name="export-field"]:checked').count()==11
                for selector,ext in [('#all-export','.csv'),('#json-export','.json'),('#xlsx-export','.xlsx')]:
                    with page.expect_download(timeout=60000) as download:
                        page.locator(selector).click()
                    result=download.value
                    assert result.suggested_filename.endswith(ext)
                    assert result.path().stat().st_size>0
                page.locator('[data-view="analytics"]').click()
                expect(page.locator('#analytics-metrics .metric')).to_have_count(4)
                for selector,extension in [('#analytics-export','.csv'),('#analytics-xlsx','.xlsx'),('#analytics-json','.json')]:
                    with page.expect_download(timeout=60000) as event:
                        page.locator(selector).click()
                    assert event.value.suggested_filename.endswith(extension)
                page.locator('[data-view="settings"]').click()
                expect(page.locator('#settings-api')).to_have_text('Pristup nije omogućen')
                page.locator('#registry-client-id').fill('synthetic-id')
                page.locator('#registry-client-secret').fill('synthetic-secret')
                expect(page.locator('#registry-credentials-persist')).to_be_checked()
                # Headless CI may not have an unlocked native vault; test explicit session mode here.
                page.locator('#registry-credentials-persist').uncheck()
                page.locator('#registry-credentials-apply').click()
                expect(page.locator('#registry-credentials-persist')).to_be_checked()
                expect(page.locator('#settings-api')).to_have_text('Pristup omogućen')
                expect(page.locator('#registry-client-secret')).to_have_value('')
                with page.expect_response(lambda response: response.url.endswith('/api/registry/forget') and response.ok) as revocation:
                    page.locator('#registry-credentials-forget').click()
                result=revocation.value.json()
                assert result['configured'] is False and type(result['revocation_verified']) is bool
                expect(page.locator('#settings-api')).to_have_text('Pristup nije omogućen')
                page.locator('#recovery-refresh').click()
                expect(page.locator('#recovery-create')).to_be_enabled()
                page.locator('#recovery-create').click()
                expect(page.locator('#recovery-status')).to_have_text('Kopija je izrađena.',timeout=30000)
                expect(page.locator('#recovery-download')).to_be_enabled()
                with page.expect_download(timeout=60000) as event:
                    page.locator('#recovery-download').click()
                assert event.value.path().stat().st_size>0
                page.once('dialog',lambda dialog:dialog.accept())
                page.locator('#recovery-restore').click()
                expect(page.locator('#recovery-status')).to_have_text('Oporavljeni prostor je izrađen.',timeout=30000)
                page.locator('#recovery-inspect').click()
                expect(page.locator('#recovery-preview')).to_contain_text('Pregled samo za čitanje')
                page.locator('#backup-password').fill('synthetic backup passphrase for testing')
                page.locator('#backup-confirm').fill('synthetic backup passphrase for testing')
                with page.expect_download(timeout=60000) as encrypted:
                    page.locator('#backup-encrypt').click()
                assert encrypted.value.suggested_filename.endswith('.cvbackup')
                with encrypted.value.path().open('rb') as stream:
                    assert stream.read(9)==b'CVBACKUP1'
                expect(page.locator('#backup-password')).to_have_value('')
                expect(page.locator('#backup-confirm')).to_have_value('')
                page.locator('#encrypted-file').set_input_files(str(encrypted.value.path()))
                page.locator('#encrypted-password').fill('synthetic backup passphrase for testing')
                page.once('dialog',lambda dialog:dialog.accept())
                old_count=page.locator('#recovery-space option').count()
                page.locator('#encrypted-restore').click()
                expect(page.locator('#recovery-space option')).to_have_count(old_count+1,timeout=60000)
                expect(page.locator('#recovery-status')).to_have_text('Oporavljeni prostor je izrađen.',timeout=60000)
                expect(page.locator('#encrypted-password')).to_have_value('')
                page.locator('#integrity-check').click()
                expect(page.locator('#integrity-results')).to_contain_text('Originalna baza: Provjereno',timeout=60000)
                page.once('dialog',lambda dialog:dialog.accept())
                page.locator('#workspace-activate').click()
                expect(page.locator('#workspace-selected')).to_contain_text('recovery-')
                expect(page.locator('#workspace-active')).to_contain_text('Originalna baza')
                page.once('dialog',lambda dialog:dialog.accept())
                page.locator('#workspace-primary').click()
                expect(page.locator('#workspace-selected')).to_contain_text('Originalna baza')
                page.locator('.protected-panel summary').click()
                page.locator('#protected-password').fill('synthetic catalog passphrase for browser test')
                page.locator('#protected-confirm').fill('synthetic catalog passphrase for browser test')
                page.once('dialog',lambda dialog:dialog.accept())
                page.locator('#protected-unlock').click()
                expect(page.locator('#protected-lock')).to_be_enabled(timeout=60000)
                page.locator('#protected-create').click()
                expect(page.locator('#protected-download')).to_be_enabled(timeout=60000)
                with page.expect_response(lambda response: response.url.endswith('/api/recovery/protected-verify') and response.ok,timeout=60000):
                    page.locator('#protected-verify').click()
                with page.expect_download(timeout=60000) as protected_download:
                    page.locator('#protected-download').click()
                with protected_download.value.path().open('rb') as stream:
                    assert stream.read(9)==b'CVBACKUP1'
                with page.expect_download(timeout=60000) as manifest:
                    page.locator('#protected-manifest').click()
                payload=json.loads(manifest.value.path().read_text())
                assert payload['manifest']['archive']==protected_download.value.suggested_filename
                assert len(payload['signature'])==64
                page.locator('#protected-restore-test').click()
                expect(page.locator('#recovery-status')).to_contain_text('Test oporavka uspješan',timeout=60000)
                old_count=page.locator('#recovery-space option').count()
                page.once('dialog',lambda dialog:dialog.accept())
                page.locator('#protected-restore').click()
                expect(page.locator('#recovery-space option')).to_have_count(old_count+1,timeout=60000)
                page.locator('#protected-lock').click()
                expect(page.locator('#protected-status')).to_have_text('Katalog je zaključan.')
                expect(page.locator('#protected-download')).to_be_disabled()
                page.reload()
                expect(page.locator('html')).to_have_attribute('data-theme','dark')
                expect(page.locator('html')).to_have_attribute('lang','hr')
                expect(page.locator('#theme,#language,#settings-light,#settings-en')).to_have_count(0)
                controls=page.evaluate("JSON.parse(sessionStorage.getItem('cvQAControls')||'[]')")
                print('CLICK_COVERAGE '+json.dumps({'distinct_control_keys':len(controls),'keys':sorted(controls)}),flush=True)
                assert not errors,errors
                browser.close()
            worker.stdin.close()
            assert worker.wait(timeout=25)==0
            print('PASS: real local browser, authenticated API, search/empty results, details, registry state, tasks, import/export, fixed Croatian dark interface.')
        finally:
            if worker.poll() is None: worker.kill(); worker.wait()
            for stream in (worker.stdin,worker.stdout,worker.stderr):
                if stream and not stream.closed: stream.close()
            worker_log.close()

if __name__=='__main__':
    run()
