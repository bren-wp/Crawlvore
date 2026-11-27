"""Responsive browser checks against the actual bilingual PHP site."""
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import time
from urllib.request import urlopen
from urllib.parse import urlencode
from playwright.sync_api import sync_playwright
from web_http_acceptance import PAGES,ROOT


def run():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1",0));port=sock.getsockname()[1]
    base=f"http://127.0.0.1:{port}/index.php"
    with tempfile.TemporaryFile() as log:
        proc=subprocess.Popen(["php","-S",f"127.0.0.1:{port}","-t",str(ROOT/"webstranica")],stdout=log,stderr=log)
        try:
            for _ in range(100):
                try:
                    with urlopen(base,timeout=1):break
                except OSError:time.sleep(.1)
            else:raise RuntimeError("PHP failed to start")
            with sync_playwright() as pw:
                options={"headless":True}
                if os.environ.get("CRAWLVORA_TEST_CHROMIUM"):options["executable_path"]=os.environ["CRAWLVORA_TEST_CHROMIUM"]
                browser=pw.chromium.launch(**options)
                page=browser.new_page()
                cases=0
                for language in ("en","hr"):
                    for width,height in ((360,800),(390,844),(768,1024),(1024,768),(1440,900)):
                        page.set_viewport_size({"width":width,"height":height})
                        for route in PAGES:
                            response=page.goto(base+"?"+urlencode({"view":route,"lang":language}))
                            assert response.status==200,(route,language)
                            assert page.locator("html").get_attribute("lang")==language
                            assert page.locator("h1").count()==1
                            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth+1"),(route,language,width)
                            cases+=1
                browser.close()
            print(f"WEB_LAYOUT_ACCEPTANCE_PASS: {cases} page/language/viewport cases")
        finally:
            proc.terminate()
            try:proc.wait(timeout=10)
            except subprocess.TimeoutExpired:proc.kill();proc.wait()


if __name__=="__main__":
    run()
