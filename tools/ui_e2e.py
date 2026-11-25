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

def run():
    with tempfile.TemporaryDirectory() as tmp:
        data=Path(tmp)/'data'
        env={k:v for k,v in os.environ.items() if k not in ('SUDREG_CLIENT_ID','SUDREG_CLIENT_SECRET')}
        worker=subprocess.Popen([sys.executable,str(ROOT/'tvrtk_scraper.py'),'--worker','--port','0','--data-dir',str(data)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=env,cwd=tmp)
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
                page.goto(session,wait_until='domcontentloaded')
                expect(page.locator('html')).to_have_attribute('lang','en')
                expect(page.locator('#preview-rows .textbtn').first).to_be_visible(timeout=20000)
                page.locator('[data-view="directory"]').click()
                expect(page.locator('#company-rows .textbtn').first).to_be_visible()
                page.locator('#search').fill('No-match-crawlvora-qa-79cbad')
                expect(page.locator('#result-count')).to_have_text('0 results')
                expect(page.locator('#company-rows')).to_contain_text('No records match')
                page.locator('#reset').click()
                expect(page.locator('#company-rows .textbtn').first).to_be_visible()
                page.locator('#company-rows .textbtn').first.click()
                expect(page.locator('#detail')).to_be_visible()
                page.locator('#close-detail').click()
                expect(page.locator('#detail')).not_to_be_visible()
                page.locator('[data-view="registry"]').click()
                expect(page.locator('#reg-categories')).to_contain_text('No downloaded categories')
                expect(page.locator('#reg-config')).to_have_text('API not configured')
                expect(page.locator('#reg-start')).to_be_disabled()
                assert page.locator('[data-view="collector"],[data-view="studio"]').count()==0
                page.locator('[data-view="jobs"]').click()
                expect(page.locator('#job-rows')).to_contain_text('No saved tasks')
                page.locator('#schedule-enabled').uncheck()
                page.locator('#schedule-hour').fill('4')
                page.locator('#schedule-save').click()
                expect(page.locator('#schedule-state')).to_have_text('Disabled')
                page.locator('[data-view="data"]').click()
                page.locator('#file').set_input_files({'name':'qa.json','mimeType':'application/json','buffer':json.dumps([{'title':'Crawlvora QA Synthetic Company','city':'Synthetic'}]).encode()})
                page.locator('#import-btn').click()
                expect(page.locator('#file-name')).to_have_text('No file selected.')
                for selector,ext in [('#all-export','.csv'),('#json-export','.json'),('#xlsx-export','.xlsx')]:
                    with page.expect_download(timeout=60000) as download:
                        page.locator(selector).click()
                    result=download.value
                    assert result.suggested_filename.endswith(ext)
                    assert result.path().stat().st_size>0
                page.locator('[data-view="analytics"]').click()
                expect(page.locator('#analytics-metrics .metric')).to_have_count(4)
                page.locator('[data-view="settings"]').click()
                expect(page.locator('#settings-api')).to_have_text('API not configured')
                page.locator('#settings-light').click()
                expect(page.locator('html')).to_have_attribute('data-theme','light')
                page.locator('#settings-dark').click()
                expect(page.locator('html')).to_have_attribute('data-theme','dark')
                page.locator('#theme').click()
                expect(page.locator('html')).to_have_attribute('data-theme','light')
                page.locator('#language').click()
                expect(page.locator('html')).to_have_attribute('lang','hr')
                expect(page.locator('#overview h1')).to_have_text('Pregled imenika')
                page.reload()
                expect(page.locator('html')).to_have_attribute('lang','hr')
                assert not errors,errors
                browser.close()
            worker.stdin.close()
            assert worker.wait(timeout=25)==0
            print('PASS: real local browser, authenticated API, search/empty results, details, registry state, tasks, import/export, themes and language persistence.')
        finally:
            if worker.poll() is None: worker.kill(); worker.wait()
            for stream in (worker.stdin,worker.stdout,worker.stderr):
                if stream and not stream.closed: stream.close()

if __name__=='__main__':
    run()
