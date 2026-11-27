"""Configurable, permission-aware connectors for public HTML and authorized JSON APIs."""
import json
import socket
from urllib.parse import urlsplit, urljoin, parse_qsl, urlencode, urlunsplit
from urllib.robotparser import RobotFileParser
import requests
from network import public_session, public_ip
from bs4 import BeautifulSoup
from core import COLS, UA, Stopped, norm

PROVIDERS = {'companywall': ('companywall.hr',), 'registry': ('sudreg-data.gov.hr',), 'company': ('company.hr',)}
NAMES = {'tvrtke':'Tvrtke.hr','companywall':'CompanyWall.hr','registry':'Sudski registar','company':'Company.hr','html':'Prilagođeni web','json':'Prilagođeni API','csv':'CSV / postojeći podaci'}
EXTRA = ['oib','email','industry']
FIELDS = COLS + EXTRA

def validated_url(url, provider='json'):
    u=urlsplit(url)
    if u.scheme!='https' or not u.hostname or u.username or u.password or u.port not in (None,443) or u.fragment:
        raise ValueError('Unesite javni HTTPS URL bez korisničkih podataka, fragmenta ili posebnog porta.')
    host=u.hostname.lower().rstrip('.')
    if provider in PROVIDERS and not any(host==h or host.endswith('.'+h) for h in PROVIDERS[provider]):
        raise ValueError('URL ne pripada odabranom izvoru.')
    if provider=='html' and any(host==h or host.endswith('.'+h) for domains in PROVIDERS.values() for h in domains):
        raise ValueError('Za taj portal koristite autorizirani API konektor.')
    try: addresses=socket.getaddrinfo(host,443,type=socket.SOCK_STREAM)
    except OSError: raise ValueError('Domena nije dostupna.') from None
    if not addresses or any(not public_ip(a[4][0]) for a in addresses):
        raise ValueError('Privatne, lokalne i rezervirane mreže nisu dopuštene.')
    return u

def path_get(obj,path):
    if not path: return obj
    for p in path.split('.'):
        if isinstance(obj,dict): obj=obj.get(p)
        elif isinstance(obj,list) and p.isdigit() and int(p)<len(obj): obj=obj[int(p)]
        else: return None
    return obj

def clean(value):
    return str(value).strip()[:16000] if isinstance(value,(str,int,float)) and not isinstance(value,bool) else ''

def parse_json(payload, records, mapping):
    data=path_get(payload,records)
    if not isinstance(data,list): raise ValueError('Putanja zapisa ne vodi do JSON liste.')
    for item in data:
        if not isinstance(item,dict): continue
        row={k:clean(path_get(item,v)) for k,v in mapping.items() if k in FIELDS and v}
        if row.get('title'): yield row

def parse_html(html,selector,mapping,limit=None):
    soup=BeautifulSoup(html,'html.parser')
    for node in soup.select(selector,limit=limit):
        row={}
        for k,v in mapping.items():
            if k not in FIELDS or not v: continue
            q,sep,attr=v.partition('::attr(')
            el=node.select_one(q) if q and q != ":scope" else node
            if el:
                value=el.get(attr.rstrip(')'),'') if sep else el.get_text(' ',strip=True)
                if isinstance(value,str) and k in ('phone','email'): value=value.removeprefix('tel:').removeprefix('mailto:')
                row[k]=clean(value)
        if row.get('title'): yield row

def start_external(bot, data):
    provider=data.get('provider','json'); url=str(data.get('url','')).strip(); selector=str(data.get('selector','')).strip(); mapping=data.get('mapping'); token=str(data.get('token','')); delay=float(data.get('delay',3)); pages=int(data.get('pages',1))
    if provider not in ('companywall','registry','company','html','json') or not data.get('permission'): raise ValueError('Potvrdite da imate dopuštenje za odabrani izvor.')
    if not isinstance(mapping,dict) or not mapping.get('title') or any(k not in FIELDS or not isinstance(v,str) or len(v)>500 for k,v in mapping.items()): raise ValueError('Mapiranje mora sadržavati polje title (naziv).')
    if provider=='html' and (not selector or token): raise ValueError('HTML zahtijeva CSS selektor i ne koristi API token.')
    engine=data.get('engine','http')
    if engine not in ('http','playwright') or (engine=='playwright' and provider!='html'): raise ValueError('Neispravan renderer.')
    mode=data.get('mode','page'); next_selector=str(data.get('next_selector','')); cursor_path=str(data.get('cursor_path','')); cursor_param=str(data.get('cursor_param','cursor')); page_start=int(data.get('page_start',1)); offset_step=int(data.get('offset_step',20))
    if not 3<=delay<=60 or not 1<=pages<=100 or mode not in ('page','offset','next','cursor') or not 0<=page_start<=100000 or not 1<=offset_step<=10000: raise ValueError('Neispravne postavke paginacije.')
    if pages>1 and ((mode=='page' and '{page}' not in url) or (mode=='offset' and '{offset}' not in url) or (mode=='next' and (provider!='html' or not next_selector)) or (mode=='cursor' and (provider=='html' or not cursor_path or not cursor_param))): raise ValueError('Dopunite postavke odabranog načina paginacije.')
    if any(c in token for c in '\r\n') or len(token)>4096: raise ValueError('Neispravan API token.')
    validated_url(url.replace('{page}',str(page_start)).replace('{offset}',str(page_start)),provider)
    with bot.lock:
        if bot.state['status'] in ('running','stopping'): raise ValueError('Prikupljanje je već aktivno.')
        bot.stop_event.clear(); bot.state={'status':'running','kind':'external','page':1,'last':pages,'processed':0,'added':0,'skipped':0,'errors':0,'logs':[]}
    import threading
    threading.Thread(target=run_external,args=(bot,provider,url,selector,mapping,token,delay,pages,mode,next_selector,cursor_path,cursor_param,page_start,offset_step,engine),daemon=True).start()

def run_external(bot,provider,url,selector,mapping,token,delay,pages,mode="page",next_selector="",cursor_path="",cursor_param="cursor",page_start=1,offset_step=20,engine="http"):
    renderer=None
    try:
        with public_session() as s:
            s.trust_env=False
            s.headers.update({'User-Agent':UA,'Accept':'text/html' if provider=='html' else 'application/json'})
            if token: s.headers['Authorization']='Bearer '+token
            def get(target):
                validated_url(target,provider); bot.wait(delay-(__import__('time').monotonic()-bot.last_request)); bot.last_request=__import__('time').monotonic()
                with s.get(target,timeout=(8,20),allow_redirects=False,stream=True) as r:
                    if r.status_code in (401,403,429): raise PermissionError(f'Pristup odbijen ili ograničen (HTTP {r.status_code}).')
                    if r.status_code!=200: raise ValueError(f'Izvor je vratio HTTP {r.status_code}.')
                    chunks=[]; size=0
                    for chunk in r.iter_content(65536):
                        bot.wait(0); size+=len(chunk)
                        if size>8*1024*1024: raise ValueError('Odgovor prelazi 8 MB.')
                        chunks.append(chunk)
                    return b''.join(chunks)
            base=url.replace('{page}',str(page_start)).replace('{offset}',str(page_start)); host=urlsplit(base).netloc.lower(); target=base; visited=set()
            rp=None
            if provider=='html' and engine=='playwright':
                from dynamic import Renderer
                renderer=Renderer(base,bot.wait,delay)
            elif provider=='html':
                u=urlsplit(base); rp=RobotFileParser(); rp.parse(get(f'https://{u.netloc}/robots.txt').decode('utf-8').splitlines()); delay=max(delay,rp.crawl_delay(UA) or 0,rp.crawl_delay('*') or 0)
            seen=set()
            for p in range(1,pages+1):
                if mode=='page': target=url.replace('{page}',str(page_start+p-1))
                elif mode=='offset': target=url.replace('{offset}',str(page_start+(p-1)*offset_step))
                if urlsplit(target).netloc.lower()!=host or target in visited: raise ValueError('Paginacija vodi izvan izvora ili ponavlja adresu.')
                visited.add(target); bot.update(page=p); bot.log(f'{NAMES[provider]} · stranica {p}')
                if rp and not rp.can_fetch(UA,target): raise PermissionError('robots.txt ne dopušta pristup.')
                body=renderer.render(target) if renderer else get(target)
                payload=json.loads(body) if provider!='html' else None
                rows=list(parse_html(body,selector,mapping) if provider=='html' else parse_json(payload,selector,mapping))
                if not rows:
                    if p==1: raise ValueError('Nema zapisa s nazivom. Provjerite mapiranje i selektor.')
                    bot.log('Nema dodatnih rezultata.'); break
                signature=tuple((norm(r['title']),r.get('oib',''),r.get('city','')) for r in rows)
                if signature in seen: raise ValueError('Izvor ponavlja rezultate; provjerite paginaciju.')
                seen.add(signature)
                # Store origin only, never query strings that might contain credentials.
                origin=urlsplit(target); origin=f'{origin.scheme}://{origin.netloc}{origin.path}'
                with bot.store.db() as c:
                    for row in rows:
                        bot.wait(0)
                        if bot.store.upsert(c,row,provider=provider,origin=origin): bot.inc('added')
                        bot.inc('processed')
                if mode=='next' and p<pages:
                    node=BeautifulSoup(body,'html.parser').select_one(next_selector)
                    href=node.get('href') if node else None
                    if not href: break
                    target=urljoin(target,href)
                elif mode=='cursor' and p<pages:
                    cursor=path_get(payload,cursor_path)
                    if cursor is None or cursor=='': break
                    if not isinstance(cursor,(str,int)) or isinstance(cursor,bool): raise ValueError('Neispravan API kursor.')
                    u=urlsplit(base); q=[(k,v) for k,v in parse_qsl(u.query,keep_blank_values=True) if k!=cursor_param]; q.append((cursor_param,str(cursor))); target=urlunsplit((u.scheme,u.netloc,u.path,urlencode(q),''))
            bot.update(status='completed'); bot.log('Prikupljanje završeno.')
    except Stopped: bot.update(status='stopped'); bot.log('Zaustavljeno; prethodno spremljene stranice su sačuvane.')
    except Exception as e:
        # Avoid leaking endpoint credentials or tokens into activity logs.
        bot.log(str(e) if isinstance(e,(PermissionError,ValueError)) and not isinstance(e,json.JSONDecodeError) and not isinstance(e,requests.RequestException) else f'Pogreška izvora: {type(e).__name__}')
        bot.inc('errors'); bot.update(status='failed')
    finally:
        if renderer: renderer.close()

def fetch_preview(url,engine="http"):
    """Only permitted public HTTPS HTML; no scripts, redirects or cookies rendered."""
    import time
    if engine=='playwright':
        from dynamic import Renderer
        r=Renderer(url,lambda n: time.sleep(max(0,n)))
        try: return r.render(url).decode('utf-8')
        finally: r.close()
    if engine!='http': raise ValueError('Nepodržan renderer.')
    u=validated_url(url,'html')
    with public_session() as s:
        s.trust_env=False; s.headers.update({'User-Agent':UA,'Accept':'text/html,text/plain'})
        def get(target,limit):
            validated_url(target,'html')
            with s.get(target,timeout=(8,15),allow_redirects=False,stream=True) as r:
                if r.status_code!=200: raise ValueError(f'Izvor je vratio HTTP {r.status_code}.')
                result=bytearray()
                for chunk in r.iter_content(32768):
                    result.extend(chunk)
                    if len(result)>limit: raise ValueError('Odgovor prelazi dopuštenu veličinu.')
                return bytes(result)
        rp=RobotFileParser(); rp.parse(get(f'https://{u.netloc}/robots.txt',256000).decode('utf-8',errors='replace').splitlines())
        if not rp.can_fetch(UA,url): raise ValueError('robots.txt ne dopušta pristup.')
        delay=max(3,rp.crawl_delay(UA) or 0,rp.crawl_delay('*') or 0)
        if delay>60: raise ValueError('Izvor zahtijeva dulji razmak; pregledajte lokalni HTML uzorak.')
        time.sleep(delay)
        return get(url,2_000_000).decode('utf-8',errors='replace')
