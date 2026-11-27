"""Compatibility facade and legacy resumable source collection."""
import re
import threading
import time
from urllib.parse import urlencode, urljoin, urlsplit
from urllib.robotparser import RobotFileParser

import requests
from network import public_session
from bs4 import BeautifulSoup
from company_fields import COLS, FIELDS, ENTITY_KINDS, norm, formula_safe
from company_store import Store

__all__ = ['COLS', 'FIELDS', 'ENTITY_KINDS', 'norm', 'formula_safe', 'Store',
           'BASE', 'UA', 'source_url', 'link', 'txt', 'parse_detail',
           'parse_listing', 'Stopped', 'Collector']

BASE = 'https://www.tvrtke.hr/'
UA = 'Crawlvora/7.0 (local directory tool)'

def source_url(s):
    u = urlsplit(urljoin(BASE, s or ''))
    if u.scheme != 'https' or u.netloc.lower() not in ('www.tvrtke.hr','tvrtke.hr'):
        raise ValueError('URL izvan dopuštenog izvora.')
    return u._replace(fragment='').geturl()

def link(s):
    try:
        u = urlsplit(urljoin(BASE, s))
        return u.geturl() if s and u.scheme in ('http','https') and u.hostname and not u.username and not u.password else ''
    except ValueError:
        return ''

def txt(node):
    return node.get_text(' ', strip=True) if node else ''

def parse_detail(html, title):
    s = BeautifulSoup(html, 'html.parser')
    def pick(q): return txt(s.select_one(q))
    def strip_label(q, label):
        return re.sub(r'^\s*'+label+r'\s*:\s*','',pick(q),flags=re.I)
    if not s.select_one('[id^="FirmaPodaci_"]'):
        raise ValueError('Struktura profila nije prepoznata; zapis nije spremljen.')
    logo = s.select_one('#FirmaPodaci_divLogo amp-img, #FirmaPodaci_divLogo img')
    logo = logo.get('src','') if logo else ''
    urls = [link(a.get('href','')) for a in s.select('#FirmaPodaci_divWeb a.linkWWW')]
    urls = [u for u in urls if u]
    return dict(zip(COLS, [title.strip(), link(logo) if 'no-logo.png' not in logo else '', urls[0] if urls else '', urls[1] if len(urls)>1 else '',pick('#FirmaPodaci_divAdresa'),pick('#FirmaPodaci_divMjesto [itemprop="postalCode"]'),pick('#FirmaPodaci_divMjesto [itemprop="addressLocality"]'),pick('#FirmaPodaci_divMjesto [itemprop="addressCountry"]'),pick('a.linkTel [itemprop="telephone"]') or pick('a.linkTel'),pick('#FirmaPodaci_divTelFax [itemprop="telephone"]'),pick('#FirmaPodaci_divKontaktOsoba span'),pick('#FirmaPodaci_divGodinaOsnivanja [itemprop="foundingDate"]'),pick('[itemprop="numberOfEmployees"]'),strip_label('#FirmaPodaci_divBrojRacuna','Broj računa'),strip_label('#FirmaPodaci_divRegistracijskiBroj','MBS'),pick('[itemprop="ratingValue"]'),pick('.divShortDesc.txtCenter.rows4'),pick('#FirmaProizvodi_divOpis')]))

def parse_listing(html):
    s = BeautifulSoup(html, 'html.parser')
    items = {}
    for card in s.select('div.divItemSlide2.roundCorners2.divShadow.divInline.txtLeft'):
        for a in card.select('a[href][title]'):
            title = a.get('title','').strip()
            href = a.get('href','').strip()
            if not title or not href or href.startswith(('#','javascript:','mailto:','tel:')): continue
            try: u = source_url(href)
            except ValueError: continue
            if 'rezultati-pretrage' in u.casefold(): continue
            items.setdefault(u,title)
    nums = [int(t) for a in s.select('.divPager a.pager2, .divPager span') if (t:=txt(a)).isdigit()]
    return list(items.items()), max(nums,default=1)

class Stopped(Exception): pass

class Collector:
    def __init__(self,store):
        self.store=store; self.lock=threading.Lock(); self.stop_event=threading.Event(); self.state={'status':'idle','page':0,'last':0,'processed':0,'added':0,'skipped':0,'errors':0,'logs':[]}; self.last_request=0
    def snapshot(self):
        with self.lock: return dict(self.state,logs=list(self.state['logs']))
    def update(self,**kw):
        with self.lock: self.state.update(kw)
    def log(self,s):
        with self.lock: self.state['logs']=(self.state['logs']+[time.strftime('%H:%M:%S')+'  '+s])[-100:]
    def inc(self,k):
        with self.lock: self.state[k]+=1
    def start(self,term,start,end,delay,resume=True):
        with self.lock:
            if self.state['status'] in ('running','stopping'): raise ValueError('Prikupljanje je već aktivno.')
            self.stop_event.clear(); self.state={'status':'running','kind':'tvrtke','page':start,'last':end or start,'processed':0,'added':0,'skipped':0,'errors':0,'logs':[]}
        threading.Thread(target=self.run,args=(term,start,end,delay,resume),daemon=True).start()
    def stop(self):
        with self.lock:
            if self.state['status']=='running': self.state['status']='stopping'; self.stop_event.set()
    def wait(self,n):
        if self.stop_event.wait(max(0,n)): raise Stopped()
    def fetch(self,session,url,delay,robots=None):
        url=source_url(url)
        for attempt in range(3):
            self.wait(delay-(time.monotonic()-self.last_request))
            if robots and not robots.can_fetch(UA,url): raise PermissionError('robots.txt ne dopušta pristup ovoj adresi.')
            self.last_request=time.monotonic()
            try:
                with session.get(url,timeout=(8,20),allow_redirects=False,stream=True) as r:
                    if r.status_code in (401,403,429): raise PermissionError(f'Izvor je odbio ili ograničio pristup (HTTP {r.status_code}); prikupljanje zaustavljeno.')
                    if 300<=r.status_code<400: raise ValueError('Izvor je vratio preusmjerenje; provjerite adresu izvora.')
                    r.raise_for_status()
                    chunks=[]; size=0
                    for b in r.iter_content(65536):
                        self.wait(0); size+=len(b)
                        if size>8*1024*1024: raise ValueError('Odgovor izvora je prevelik.')
                        chunks.append(b)
                    return b''.join(chunks).decode(r.encoding or 'utf-8',errors='replace')
            except requests.RequestException as e:
                if attempt==2 or (getattr(e,'response',None) is not None and e.response.status_code<500): raise
                self.wait(2**(attempt+1))
        raise RuntimeError('Neuspjelo preuzimanje.')
    def run(self,term,start,end,delay,resume):
        job=norm(term)
        try:
            with public_session() as session:
                session.headers.update({'User-Agent':UA,'Accept':'text/html,application/xhtml+xml,text/plain','Accept-Language':'hr,en;q=0.8'})
                # Fail closed if the source policy cannot be retrieved.
                rp=RobotFileParser(); rp.set_url(urljoin(BASE,'robots.txt')); rp.parse(self.fetch(session,rp.url,delay).splitlines())
                delay=max(delay,rp.crawl_delay(UA) or 0,rp.crawl_delay('*') or 0)
                page=start; last=end or start; seen_pages=set()
                while page<=last:
                    self.update(page=page,last=last); self.log(f'Stranica {page}')
                    url=urljoin(BASE,'Rezultati-pretrage,PID-4.aspx')+'?'+urlencode({'M':'','Z':'0','D':'0','P':'','F':term,'stranica':page})
                    items,found=parse_listing(self.fetch(session,url,delay,rp))
                    if not items: raise ValueError('Nema prepoznatih rezultata; provjerite upit i strukturu izvora.')
                    signature=tuple(u for u,_ in items)
                    if signature in seen_pages: raise ValueError('Izvor ponavlja istu stranicu; prikupljanje zaustavljeno.')
                    seen_pages.add(signature); last=max(last,found) if end is None else min(end,max(page,found)); self.update(last=last)
                    for u,title in items:
                        self.wait(0)
                        if resume and self.store.done(job,u): self.inc('skipped'); continue
                        try:
                            row=parse_detail(self.fetch(session,u,delay,rp),title)
                            if self.store.save(job,u,row): self.inc('added')
                            self.inc('processed')
                        except (requests.RequestException,ValueError) as e:
                            self.inc('errors'); self.log(f'Preskočeno: {title[:80]} — {type(e).__name__}: {e}')
                    page+=1
            self.update(status='completed_with_errors' if self.snapshot()['errors'] else 'completed'); self.log('Prikupljanje završeno.')
        except Stopped: self.update(status='stopped'); self.log('Zaustavljeno. Spremljeni zapisi su sačuvani.')
        except Exception as e: self.log(str(e)); self.update(status='failed')
