"""Opt-in rendering of permitted same-origin HTTPS pages with Playwright."""
import time
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser
from core import UA
from sources import validated_url
from network import public_session

class Renderer:
    def __init__(self,base,wait,delay=3):
        self.base=validated_url(base,'html'); self.wait=wait; self.delay=delay; self.last=0; self.session=public_session(); self.session.trust_env=False; self.session.headers['User-Agent']=UA
        self.rp=RobotFileParser(); origin=f'https://{self.base.netloc}'
        try:
            body,_,_=self.fetch(origin+'/robots.txt',256000,check=False); self.rp.parse(body.decode('utf-8',errors='replace').splitlines()); self.delay=max(delay,self.rp.crawl_delay(UA) or 0,self.rp.crawl_delay('*') or 0)
        except Exception:
            self.session.close(); raise
    def fetch(self,url,cap,check=True):
        u=validated_url(url,'html')
        if u.netloc!=self.base.netloc or (check and not self.rp.can_fetch(UA,url)): raise PermissionError('Nedopuštena adresa ili robots.txt.')
        self.wait(self.delay-(time.monotonic()-self.last)); self.last=time.monotonic()
        with self.session.get(url,timeout=(8,15),allow_redirects=False,stream=True) as r:
            if r.status_code!=200: raise PermissionError(f'Izvor HTTP {r.status_code}.')
            data=bytearray()
            for chunk in r.iter_content(65536):
                self.wait(0); data.extend(chunk)
                if len(data)>cap: raise ValueError('Odgovor je prevelik.')
            return bytes(data),r.headers.get('Content-Type','application/octet-stream'),r.status_code
    def render(self,url):
        from playwright.sync_api import sync_playwright
        error=[]; count=0
        with sync_playwright() as p:
            # Force browser traffic through intercepted requests; fail closed for other connections.
            browser=p.chromium.launch(headless=True,proxy={'server':'http://127.0.0.1:1','bypass':''},args=['--proxy-bypass-list=<-loopback>','--disable-background-networking','--disable-quic'])
            try:
                context=browser.new_context(service_workers='block',accept_downloads=False,user_agent=UA)
                def route(r):
                    nonlocal count
                    req=r.request
                    if req.method!='GET' or req.resource_type not in ('document','script','xhr','fetch') or urlsplit(req.url).netloc!=self.base.netloc or count>=40: r.abort(); return
                    count+=1
                    try:
                        data,ctype,status=self.fetch(req.url,2_000_000); r.fulfill(status=status,body=data,content_type=ctype)
                    except Exception as e: error.append(e); r.abort()
                context.route('**/*',route)
                if hasattr(context,'route_web_socket'): context.route_web_socket('**/*',lambda ws: ws.close())
                page=context.new_page(); page.goto(url,wait_until='domcontentloaded',timeout=180000); page.wait_for_timeout(1500); self.wait(0)
                if error: raise error[0]
                html=page.content()
                if len(html)>2_000_000: raise ValueError('HTML je prevelik.')
                return html.encode()
            finally: browser.close()
    def close(self): self.session.close()
