"""Check real worker layouts in both languages and themes with synthetic long contact values."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor

from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from core import Store


def capture(output):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        workspace = Path(tmp) / "data"
        workspace.mkdir()
        store = Store(workspace / "companies.sqlite3")
        with store.db() as conn:
            for index, name in enumerate(("Atlas Demo", "Birch Demo", "Cedar Demo",
                                          "Delta Demo", "Elm Demo", "Fjord Demo")):
                store.upsert(conn, {"title": name, "city": ("Zagreb", "Rijeka", "Split")[index % 3],
                                    "website": "https://example.invalid", "entity_kind": "company", "phone": "+385 51 123 456 789 012", "address": "Long demonstration address " * 4})
            conn.execute("INSERT INTO meta(key,value) VALUES ('seeded','1')")
        env = {k: v for k, v in os.environ.items()
               if not k.startswith(("SUDREG_", "CRAWLVORA_"))}
        with (Path(tmp) / "worker.log").open("w+b") as log:
            worker = subprocess.Popen(
                [sys.executable, str(ROOT / "tvrtk_scraper.py"), "--worker",
                 "--port", "0", "--data-dir", str(workspace)],
                cwd=tmp, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=log, text=True)
            try:
                with ThreadPoolExecutor(max_workers=1) as pool:
                    future = pool.submit(worker.stdout.readline)
                    try:
                        line = future.result(timeout=90)
                    except TimeoutError:
                        worker.kill()
                        raise
                if not line.startswith("CRAWLVORA_READY "):
                    raise RuntimeError("Worker startup failed")
                with sync_playwright() as pw:
                    browser = pw.chromium.launch(headless=True,
                        executable_path=os.getenv("CRAWLVORA_TEST_CHROMIUM") or None)
                    page = browser.new_page(viewport={"width": 1440, "height": 900})
                    page.goto(line.strip().split(" ", 1)[1], wait_until="domcontentloaded")
                    expect(page.locator("html")).to_have_attribute("lang", "en")
                    expect(page.locator("#preview-rows .textbtn").first).to_be_visible(timeout=20000)
                    expect(page.locator("#preview-rows")).to_contain_text("Demo")
                    findings=[]
                    cases=0
                    errors=[]
                    page.on("pageerror",lambda error:errors.append(str(error)))
                    for lang in ("en","hr"):
                        page.evaluate("(lang)=>post('/api/preferences/language',{language:lang})",lang)
                        page.reload()
                        expect(page.locator("html")).to_have_attribute("lang",lang)
                        for theme in ("dark","light"):
                            page.evaluate("(theme)=>document.documentElement.dataset.theme=theme",theme)
                            for width,height in ((360,300),(390,844),(768,480),(1024,600),(1120,720),(1440,900)):
                                page.set_viewport_size({"width":width,"height":height})
                                for view in ("overview","directory","registry","jobs","data","analytics","settings","national"):
                                    page.evaluate("(view)=>go(view)",view)
                                    expect(page.locator("#"+view)).to_be_visible()
                                    if view in ("overview","directory"):
                                        page.locator(("#preview-rows" if view=="overview" else "#company-rows")+" .textbtn").first.wait_for()
                                    cases+=1
                                    info=page.evaluate("""(view)=>{
                                      const section=document.getElementById(view);
                                      const clipped=[...section.querySelectorAll('td,button,.metric strong,.reg-metric strong')].filter(e=>{
                                        const cs=getComputedStyle(e);
                                        return e.getClientRects().length && e.scrollWidth>e.clientWidth+2 && cs.overflowX==='visible';
                                      }).map(e=>({tag:e.tagName,text:e.textContent.slice(0,40),overflow:e.scrollWidth-e.clientWidth}));
                                      return {pageOverflow:document.documentElement.scrollWidth>innerWidth,clipped};
                                    }""",view)
                                    if info["pageOverflow"] or info["clipped"]:
                                        findings.append({"lang":lang,"theme":theme,"width":width,"view":view,**info})
                                page.evaluate("go('directory')")
                                page.locator("#company-rows .textbtn").first.click()
                                expect(page.locator("#detail")).to_be_visible()
                                box=page.locator("#detail").bounding_box()
                                assert box["width"]<=width+1 and box["height"]<=height+1
                                page.locator("#close-detail").click()
                    import json
                    (output/"layout-report.json").write_text(json.dumps({"screen_cases":cases,"dialog_cases":24,"findings":findings,"page_errors":errors},indent=2),encoding="utf-8")
                    print("Screen cases",cases,"dialog cases",24,"layout findings",len(findings),"page errors",len(errors),flush=True)
                    print(json.dumps(findings[:12]),flush=True)
                    browser.close()
                    if findings or errors:
                        raise AssertionError("Layout regression or browser error; see layout-report.json")
                worker.stdin.close()
                if worker.wait(timeout=25) != 0:
                    raise RuntimeError("Worker exit failed")
            finally:
                if worker.poll() is None:
                    worker.kill()
                    worker.wait()
                for stream in (worker.stdin, worker.stdout):
                    if stream and not stream.closed:
                        stream.close()
    print("Layout audit complete")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output")
    capture(parser.parse_args().output)

