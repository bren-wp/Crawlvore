"""Capture the running Croatian UI against a disposable synthetic workspace."""
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
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
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
                                    "website": "https://example.invalid", "entity_kind": "company", "email": "kontakt@example.invalid" if index == 0 else ""})
            conn.execute("INSERT INTO meta(key,value) VALUES ('seeded','1')")
            conn.execute("INSERT INTO meta(key,value) VALUES ('ui_language','en')")
        env = {k: v for k, v in os.environ.items()
               if not k.startswith(("SUDREG_", "CRAWLVORA_"))}
        with (Path(tmp) / "worker.log").open("w+b") as log:
            worker = subprocess.Popen(
                [sys.executable, str(ROOT / "src" / "tvrtk_scraper.py"), "--worker",
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
                    expect(page.locator("html")).to_have_attribute("lang", "hr")
                    expect(page.locator("#preview-rows .textbtn").first).to_be_visible(timeout=20000)
                    expect(page.locator("#preview-rows")).to_contain_text("Demo")
                    def shot(name):
                        page.screenshot(path=str(output / (name + ".jpg")), type="jpeg", quality=78)
                    for view in ("overview", "directory", "registry", "jobs", "data", "analytics", "settings"):
                        page.locator('[data-view="' + view + '"]').click()
                        expect(page.locator("#" + view)).to_be_visible()
                        page.wait_for_timeout(350)
                        shot(view + "-dark")
                    page.locator('[data-view="directory"]').click()
                    page.locator("#company-rows .textbtn").first.click()
                    expect(page.locator("#detail")).to_be_visible()
                    shot("profile-dark")
                    page.locator('#detail').get_by_role('button',name='Sastavi e-poštu').click()
                    expect(page.locator('#mail-dialog')).to_be_visible()
                    page.locator('#mail-template').select_option('security')
                    expect(page.locator('#mail-subject')).to_have_value('Sigurnosno upozorenje – provjerite sumnjive poruke')
                    shot("mail-dark")
                    page.locator('#mail-close').click()
                    page.locator("#close-detail").click()
                    browser.close()
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
    print("Captured", len(list(output.glob("*.jpg"))), "real worker-backed browser views")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output")
    capture(parser.parse_args().output)

