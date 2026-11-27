"""Bounded, evidence-ranked extraction suggestions for unfamiliar HTML layouts."""
import re
import unicodedata
from collections import Counter
from bs4 import BeautifulSoup
from soupsieve import escape, SelectorSyntaxError
from sources import parse_html, FIELDS

ALIASES={
 'title': ('naziv','tvrtka','company name','business name','name','subjekt','ime tvrtke','naziv tvrtke','company title','organization name'),
 'oib': ('oib','tax id','vat id','porezni broj'), 'mbs': ('mbs','registration number','maticni broj subjekta'),
 'city': ('grad','city','mjesto','naselje','address locality','locality'),
 'address': ('adresa','address','street','street address','sjediste'),
 'postal': ('postal code','postanski broj','zip','postal'), 'country': ('country','drzava','address country'),
 'phone': ('telefon','phone','tel','telephone','contact phone'), 'email': ('email','e mail','mail'),
 'website': ('web','website','web stranica','url','homepage'), 'industry': ('djelatnost','industry','activity','nkd'),
 'description': ('description','opis'), 'year': ('founding year','godina osnivanja'), 'employees': ('employees','zaposleni','broj zaposlenih')}
SEMANTIC={'title':['[itemprop="name"]','h2','h3','h4','h1'], 'city':['[itemprop="addressLocality"]'], 'address':['[itemprop="streetAddress"]'], 'phone':['a[href^="tel:"]::attr(href)','[itemprop="telephone"]'], 'email':['a[href^="mailto:"]::attr(href)','[itemprop="email"]'], 'website':['[itemprop="url"]::attr(href)'], 'industry':['[itemprop="industry"]'], 'postal':['[itemprop="postalCode"]'], 'country':['[itemprop="addressCountry"]'], 'description':['[itemprop="description"]']}
BLOCKS=('article','li','tr','div','section','aside','dd')

def normalize(text):
    text=re.sub(r'([a-z])([A-Z])',r'\1 \2',str(text)); text=unicodedata.normalize('NFKD',text.casefold()); return ' '.join(re.findall(r'[a-z0-9]+',''.join(c for c in text if not unicodedata.combining(c))))

def field_for(text):
    name=normalize(text)
    for key,aliases in ALIASES.items():
        if name in aliases: return key
    # Match semantic suffixes, not arbitrary substrings such as "mailing-address".
    for key,aliases in ALIASES.items():
        if any(name.endswith(' '+a) for a in aliases if len(a)>3): return key
    return None

def classes(el):
    return [c for c in el.get('class',[]) if re.fullmatch(r'[\w-]{1,80}',c) and not re.fullmatch(r'.*\d{3,}.*',c)]

def component(el):
    return el.name+''.join('.'+escape(c) for c in classes(el)[:2])

def value(node,q):
    sel,sep,attr=q.partition('::attr('); el=node.select_one(sel) if sel and sel!=':scope' else node
    if el is None: return ''
    raw=el.get(attr.rstrip(')'),'') if sep else el.get_text(' ',strip=True)
    return str(raw).strip()

def relative(el,root):
    path=[]
    while el is not root and el.parent is not None:
        idx=1+sum(x.name==el.name for x in el.previous_siblings if getattr(x,'name',None)); path.append(f'{el.name}:nth-of-type({idx})'); el=el.parent
    return ':scope > '+' > '.join(reversed(path)) if path else ':scope'

def field_candidates(nodes):
    first=nodes[0]; proposals={k:[] for k in ALIASES}
    def add(k,q,weight):
        if k in proposals and len(q)<=500 and (q,weight) not in proposals[k]: proposals[k].append((q,weight))
    for k,choices in SEMANTIC.items():
        for i,q in enumerate(choices): add(k,q,85-i*3)
    for el in [first,*first.find_all(True,limit=100)]:
        for attr in el.attrs:
            if attr.startswith('data-'):
                field=field_for(attr[5:]); q=relative(el,first) if el is not first else ''
                if field: add(field,q+f'::attr({attr})',105)
        if el is first: continue
        for cls in classes(el):
            field=field_for(cls)
            if field:
                q='.'+escape(cls)
                if field=='website' and el.name=='a' and el.get('href'): q+='::attr(href)'
                add(field,q,90); add(field,relative(el,first),65)
        # Common label/value pattern: <dt>OIB</dt><dd>...</dd> or label + sibling.
        if el.name in ('dt','label','strong','b','span','th'):
            k=field_for(el.get_text(' ',strip=True).rstrip(':')); sibling=el.find_next_sibling()
            if k and sibling and sibling.get_text(' ',strip=True): add(k,relative(sibling,first),96)
    if first.name=='tr':
        table=first.find_parent('table'); header=table.select_one('thead tr') if table else None
        if header is None and table: header=next((r for r in table.select('tr') if r.find('th')),None)
        if header:
            for idx,cell in enumerate(header.find_all(['th','td'],recursive=False),1):
                k=field_for(cell.get_text(' ',strip=True));
                if k: add(k,f'td:nth-child({idx})',120)
    if first.name=='a': add('title',':scope',45)
    if first.name=='tr': add('title','td:first-child',35)
    selected={}; strengths={}
    for k,qs in proposals.items():
        best=None
        for q,w in qs:
            vals=[value(n,q) for n in nodes]; coverage=sum(bool(v) for v in vals)/len(nodes)
            if coverage<0.5: continue
            if k=='title' and len(nodes)>1 and len(set(v.casefold() for v in vals if v))<2: continue
            if k=='title' and any(len(v)>250 for v in vals): continue
            score=w+20*coverage
            if best is None or score>best[0]: best=(score,q,coverage)
        if best: selected[k]=best[1]; strengths[k]=round(best[2],2)
    return selected,strengths

def inspect_html(html,selector='',mapping=None):
    if not isinstance(html,str) or len(html.encode('utf-8'))>2_000_000: raise ValueError('HTML uzorak mora biti manji od 2 MB.')
    if not isinstance(selector,str) or len(selector)>500: raise ValueError('CSS selektor je predug.')
    if mapping is not None and (not isinstance(mapping,dict) or any(k not in FIELDS or not isinstance(v,str) or len(v)>500 for k,v in mapping.items())): raise ValueError('Neispravno mapiranje.')
    soup=BeautifulSoup(html,'html.parser')
    for n in soup.select('script,style,template,noscript,iframe,object,svg'): n.decompose()
    counts=Counter()
    for n in soup.find_all(BLOCKS,limit=20000):
        if n.find_parent(["nav","footer"]) or n.find_parent(attrs={"role":"navigation"}) or n.has_attr("hidden") or n.find_parent(attrs={"hidden":True}): continue
        if not n.find(['h1','h2','h3','h4','a','td','dt','span']) and not n.get('data-name'): continue
        if n.name=='tr' and not n.find('td'): continue
        if not 1<=len(n.get_text(' ',strip=True))<=4000 and not n.get('data-name'): continue
        if n.name=='tr': counts['tr:has(td)']+=1
        else:
            counts[component(n)]+=1
            for c in classes(n)[:3]:
                q=n.name+'.'+escape(c)
                if q!=component(n): counts[q]+=1
            if classes(n) and component(n)!=n.name: counts[n.name]+=1
    ranked=[]; seen=set()
    try:
        for sel,count in counts.most_common(60):
            if count<2: continue
            nodes=soup.select(sel,limit=12)
            if len(nodes)<2 or any(n.select_one(sel) for n in nodes): continue
            signature=tuple(id(n) for n in nodes)
            if signature in seen: continue
            guessed,coverage=field_candidates(nodes)
            if 'title' not in guessed: continue
            seen.add(signature)
            score=12*len(guessed)+sum(coverage.values())*5+min(count,20)*.3+4*(nodes[0].name in ('article','tr'))+3*('.' in sel)
            if guessed['title']=='td:first-child': score-=3
            if len(guessed)==1: score-=15
            ranked.append((score,sel,count,guessed,coverage))
        ranked.sort(key=lambda x:x[0],reverse=True)
        suggestions=[{'selector':s,'count':n,'fields':len(g),'confidence':'high' if len(g)>=3 else 'medium' if len(g)>=2 else 'low'} for _,s,n,g,_ in ranked[:8]]
        selector=selector or (suggestions[0]['selector'] if suggestions else '')
        nodes=soup.select(selector,limit=10) if selector else []
        guessed,coverage=field_candidates(nodes) if nodes else ({},{})
        effective=guessed if mapping is None else mapping
        options=[]; used=set()
        if nodes:
            for el in nodes[0].find_all(True,limit=100):
                q=component(el); v=el.get_text(' ',strip=True)
                for key,sample in [(q,v),(q+'::attr(href)',el.get('href',''))]:
                    if sample and key not in used: used.add(key); options.append({'selector':key,'sample':str(sample)[:160]})
        preview=list(parse_html(html,selector,effective,limit=10)) if selector and effective.get('title') else []
    except SelectorSyntaxError as e: raise ValueError('Neispravan CSS selektor.') from e
    return {'selector':selector,'suggestions':suggestions,'mapping':guessed,'elements':options[:60],'preview':preview,'coverage':coverage,'confidence':'high' if len(guessed)>=3 else 'medium' if len(guessed)>=2 else 'low','warnings':[] if len(guessed)>=3 else ['Provjerite mapiranje: malo prepoznatih poslovnih polja.']}
