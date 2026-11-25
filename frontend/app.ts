'use strict';
// Typed contracts for the local HTTP API. Business and registry values remain source data.
interface CompanyRow { id:number; title:string; address?:string; postal?:string; city?:string; country?:string; phone?:string; website?:string; providers?:string }
interface CompanyPage { total:number; rows:CompanyRow[] }
interface CompanyDetails extends CompanyRow { [field:string]: unknown; sources?:{provider:string;url:string;updated:string}[] }
interface CompanyHistory { changed_at:string;provider:string;changes:Record<string,{before:unknown;after:unknown}> }
interface DashboardStats { total:number; cities:number; phones:number; websites:number; top_cities:{city:string;n:number}[] }
interface BotStatus { status:string; kind?:string; page:number;last:number;processed:number;added:number;skipped:number;errors:number;logs:string[] }
interface SourceInfo { label:string;provider:string;n:number }
interface RegistryRun { snapshot:string;complete:number|boolean }
interface RegistryCategory { snapshot:string;category:string;rows:number;total:number|null;done:number|boolean }
interface RegistrySummary { configured:boolean;runs:RegistryRun[];categories:RegistryCategory[] }
interface RegistryPage { total:number;rows:Record<string,unknown>[] }
interface RegistryDiff { before:string;after:string;categories:{category:string;comparable:boolean;added:number;removed:number;affected_subjects:number}[] }
interface ScraperConfig { [key:string]: any; mapping?:Record<string,string>;provider?:string;resume?:boolean }
interface SavedProject { id:number|string;name:string;config:ScraperConfig }
interface StudioResult { html:string; selector:string; mapping:Record<string,string>;suggestions:{selector:string;count:number;fields?:number}[];elements:{sample:string;selector:string}[];preview:Record<string,unknown>[];confidence?:string }
interface JobSummary { schedule:{enabled:boolean|number;hour:number}; jobs:{id:number;kind:string;state:string;created:string;finished?:string;attempts?:number;next_run?:number}[] }
interface InterfaceElements {
  "analytics-metrics": HTMLElementTagNameMap["div"];
  "analytics-cities": HTMLElementTagNameMap["div"];
  "analytics-coverage": HTMLElementTagNameMap["div"];
  "analytics-history": HTMLElementTagNameMap["div"];
  "analytics-export": HTMLElementTagNameMap["button"];
  "analytics-xlsx": HTMLElementTagNameMap["button"];
  "analytics-json": HTMLElementTagNameMap["button"];
  "settings-count": HTMLElementTagNameMap["div"];
  "settings-api": HTMLElementTagNameMap["div"];
  "settings-dark": HTMLElementTagNameMap["button"];
  "settings-light": HTMLElementTagNameMap["button"];
  "settings-en": HTMLElementTagNameMap["button"];
  "settings-hr": HTMLElementTagNameMap["button"];
  "studio-code": HTMLElementTagNameMap["pre"];
  "language": HTMLElementTagNameMap["button"];
  "language-label": HTMLElementTagNameMap["span"];
  "theme": HTMLElementTagNameMap["button"];
  "crumb": HTMLElementTagNameMap["strong"];
  "top-export": HTMLElementTagNameMap["button"];
  "overview": HTMLElementTagNameMap["section"];
  "metrics": HTMLElementTagNameMap["div"];
  "city-chart": HTMLElementTagNameMap["div"];
  "coverage": HTMLElementTagNameMap["div"];
  "source-summary": HTMLElementTagNameMap["div"];
  "preview-rows": HTMLElementTagNameMap["tbody"];
  "directory": HTMLElementTagNameMap["section"];
  "filtered-export": HTMLElementTagNameMap["button"];
  "filtered-xlsx": HTMLElementTagNameMap["button"];
  "search": HTMLElementTagNameMap["input"];
  "city": HTMLElementTagNameMap["select"];
  "contact": HTMLElementTagNameMap["select"];
  "source-filter": HTMLElementTagNameMap["select"];
  "sort": HTMLElementTagNameMap["select"];
  "result-count": HTMLElementTagNameMap["span"];
  "reset": HTMLElementTagNameMap["button"];
  "company-rows": HTMLElementTagNameMap["tbody"];
  "page-label": HTMLElementTagNameMap["span"];
  "prev": HTMLElementTagNameMap["button"];
  "next": HTMLElementTagNameMap["button"];
  "collector": HTMLElementTagNameMap["section"];
  "run-status": HTMLElementTagNameMap["span"];
  "project-select": HTMLElementTagNameMap["select"];
  "project-name": HTMLElementTagNameMap["input"];
  "project-save": HTMLElementTagNameMap["button"];
  "project-delete": HTMLElementTagNameMap["button"];
  "collect-form": HTMLElementTagNameMap["form"];
  "provider": HTMLElementTagNameMap["select"];
  "source-help": HTMLElementTagNameMap["div"];
  "native-settings": HTMLElementTagNameMap["div"];
  "term": HTMLElementTagNameMap["input"];
  "start": HTMLElementTagNameMap["input"];
  "end": HTMLElementTagNameMap["input"];
  "resume": HTMLElementTagNameMap["input"];
  "external-settings": HTMLElementTagNameMap["div"];
  "engine-label": HTMLElementTagNameMap["label"];
  "engine": HTMLElementTagNameMap["select"];
  "endpoint": HTMLElementTagNameMap["input"];
  "selector-label": HTMLElementTagNameMap["label"];
  "selector": HTMLElementTagNameMap["input"];
  "token-label": HTMLElementTagNameMap["label"];
  "api-token": HTMLElementTagNameMap["input"];
  "pages": HTMLElementTagNameMap["input"];
  "pagination-mode": HTMLElementTagNameMap["select"];
  "page-start": HTMLElementTagNameMap["input"];
  "offset-step": HTMLElementTagNameMap["input"];
  "next-wrap": HTMLElementTagNameMap["label"];
  "next-selector": HTMLElementTagNameMap["input"];
  "cursor-wrap": HTMLElementTagNameMap["div"];
  "cursor-path": HTMLElementTagNameMap["input"];
  "cursor-param": HTMLElementTagNameMap["input"];
  "mapping-grid": HTMLElementTagNameMap["div"];
  "delay": HTMLElementTagNameMap["input"];
  "permission": HTMLElementTagNameMap["input"];
  "start-btn": HTMLElementTagNameMap["button"];
  "queue-add": HTMLElementTagNameMap["button"];
  "stop-btn": HTMLElementTagNameMap["button"];
  "progress-label": HTMLElementTagNameMap["span"];
  "progress-percent": HTMLElementTagNameMap["strong"];
  "progress-bar": HTMLElementTagNameMap["div"];
  "run-metrics": HTMLElementTagNameMap["div"];
  "logs": HTMLElementTagNameMap["pre"];
  "studio": HTMLElementTagNameMap["section"];
  "studio-apply": HTMLElementTagNameMap["button"];
  "studio-engine": HTMLElementTagNameMap["select"];
  "studio-url": HTMLElementTagNameMap["input"];
  "studio-permission": HTMLElementTagNameMap["input"];
  "studio-html": HTMLElementTagNameMap["textarea"];
  "studio-file": HTMLElementTagNameMap["input"];
  "studio-scan": HTMLElementTagNameMap["button"];
  "studio-candidates": HTMLElementTagNameMap["div"];
  "studio-selector": HTMLElementTagNameMap["input"];
  "studio-select": HTMLElementTagNameMap["button"];
  "studio-field": HTMLElementTagNameMap["select"];
  "studio-elements": HTMLElementTagNameMap["div"];
  "studio-mapping": HTMLElementTagNameMap["div"];
  "studio-preview": HTMLElementTagNameMap["button"];
  "studio-count": HTMLElementTagNameMap["span"];
  "studio-head": HTMLElementTagNameMap["thead"];
  "studio-body": HTMLElementTagNameMap["tbody"];
  "data": HTMLElementTagNameMap["section"];
  "file": HTMLElementTagNameMap["input"];
  "file-name": HTMLElementTagNameMap["p"];
  "import-btn": HTMLElementTagNameMap["button"];
  "all-export": HTMLElementTagNameMap["button"];
  "json-export": HTMLElementTagNameMap["button"];
  "xlsx-export": HTMLElementTagNameMap["button"];
  "registry": HTMLElementTagNameMap["section"];
  "reg-config": HTMLElementTagNameMap["span"];
  "reg-metrics": HTMLElementTagNameMap["div"];
  "reg-limit": HTMLElementTagNameMap["input"];
  "reg-permission": HTMLElementTagNameMap["input"];
  "reg-start": HTMLElementTagNameMap["button"];
  "reg-stop": HTMLElementTagNameMap["button"];
  "reg-check": HTMLElementTagNameMap["button"];
  "reg-status": HTMLElementTagNameMap["p"];
  "reg-progress-label": HTMLElementTagNameMap["span"];
  "reg-percent": HTMLElementTagNameMap["strong"];
  "reg-progress-bar": HTMLElementTagNameMap["div"];
  "reg-logs": HTMLElementTagNameMap["pre"];
  "reg-snapshot": HTMLElementTagNameMap["select"];
  "reg-reload": HTMLElementTagNameMap["button"];
  "reg-categories": HTMLElementTagNameMap["tbody"];
  "diff-before": HTMLElementTagNameMap["select"];
  "diff-after": HTMLElementTagNameMap["select"];
  "diff-run": HTMLElementTagNameMap["button"];
  "diff-status": HTMLElementTagNameMap["p"];
  "diff-rows": HTMLElementTagNameMap["tbody"];
  "reg-table-title": HTMLElementTagNameMap["h2"];
  "reg-export": HTMLElementTagNameMap["button"];
  "reg-export-csv": HTMLElementTagNameMap["button"];
  "reg-export-xlsx": HTMLElementTagNameMap["button"];
  "reg-export-xml": HTMLElementTagNameMap["button"];
  "reg-export-sql": HTMLElementTagNameMap["button"];
  "reg-prev": HTMLElementTagNameMap["button"];
  "reg-page": HTMLElementTagNameMap["span"];
  "reg-next": HTMLElementTagNameMap["button"];
  "reg-search": HTMLElementTagNameMap["input"];
  "reg-row-count": HTMLElementTagNameMap["span"];
  "reg-head": HTMLElementTagNameMap["thead"];
  "reg-body": HTMLElementTagNameMap["tbody"];
  "jobs": HTMLElementTagNameMap["section"];
  "jobs-refresh": HTMLElementTagNameMap["button"];
  "schedule-state": HTMLElementTagNameMap["span"];
  "schedule-enabled": HTMLElementTagNameMap["input"];
  "schedule-hour": HTMLElementTagNameMap["input"];
  "schedule-permission": HTMLElementTagNameMap["input"];
  "schedule-save": HTMLElementTagNameMap["button"];
  "jobs-registry": HTMLElementTagNameMap["button"];
  "job-metrics": HTMLElementTagNameMap["div"];
  "job-rows": HTMLElementTagNameMap["tbody"];
  "detail": HTMLElementTagNameMap["dialog"];
  "detail-title": HTMLElementTagNameMap["h2"];
  "detail-sub": HTMLElementTagNameMap["p"];
  "close-detail": HTMLElementTagNameMap["button"];
  "detail-body": HTMLElementTagNameMap["div"];
  "toast": HTMLElementTagNameMap["div"];
}

function $<K extends keyof InterfaceElements>(id:K):InterfaceElements[K];
function $(id:string):HTMLElement & Partial<HTMLInputElement & HTMLSelectElement & HTMLDialogElement>;
function $(id:string):HTMLElement {
  const element=document.getElementById(id);
  if(!element)throw Error('Missing interface element: '+id);
  return element;
}
const token=document.querySelector<HTMLMetaElement>('meta[name="local-token"]')?.content || document.querySelector<HTMLMetaElement>('meta[name="csrf-token"]')?.content || '';
const nf=new Intl.NumberFormat(UI_LANGUAGE==='hr'?'hr-HR':'en-US'); const n=(v:unknown)=>nf.format(Number(v??0)); let page=1, total=0, serial=0, timer:ReturnType<typeof setTimeout>, current='overview';
const make=<K extends keyof HTMLElementTagNameMap>(tag:K,text?:unknown,cls?:string):HTMLElementTagNameMap[K]=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=String(text);if(cls)e.className=cls;return e};
async function api<T=unknown>(path:string,opts:RequestInit={}):Promise<T>{const r=await fetch(path,opts);const d=await r.json();if(!r.ok)throw Error(translate(String(d.error||'Operacija nije uspjela.')));return d as T;}
function toast(msg:string){$('toast').textContent=msg;$('toast').hidden=false;clearTimeout(timer);timer=setTimeout(()=>$('toast').hidden=true,5500);}
const fail=(e:unknown)=>toast(e instanceof Error?e.message:translate('Pogreška pri povezivanju.'));
function post<T=unknown>(path:string,data:unknown){return api<T>(path,{method:'POST',headers:{'Content-Type':'application/json','X-Local-Token':token},body:JSON.stringify(data)});}
function filters(){return new URLSearchParams({q:$('search').value,city:$('city').value,contact:$('contact').value,provider:$('source-filter').value});}
function download(filtered=false){location.href='/api/export'+(filtered?'?'+filters():'');}
function go(view:string){current=view;document.querySelectorAll<HTMLElement>('.view').forEach(e=>e.hidden=e.id!==view);document.querySelectorAll<HTMLElement>('[data-view]').forEach(e=>e.classList.toggle('active',e.dataset.view===view));$('crumb').textContent={overview:translate('Pregled'),directory:translate('Poslovni imenik'),collector:translate('Web bot'),studio:'Scraper Studio',registry:translate('Sudski registar'),data:translate('Uvoz i izvoz'),jobs:translate('Zadaci i raspored'),analytics:translate('Analitika i izvještaji'),settings:translate('Postavke')}[view];if(view==='analytics')refreshAnalytics().catch(fail);if(view==='settings')refreshSettings().catch(fail);if(view==='jobs')refreshJobs(true).catch(fail);if(view==='overview')overview().catch(fail);if(view==='directory')directory().catch(fail);if(view==='registry')registryRefresh().catch(fail);if(view==='collector'){refreshBotStatus().catch(fail);loadProjects().catch(fail);}window.scrollTo(0,0);}
function safeLink(value:unknown){if(typeof value!=='string')return null;try{const u=new URL(value);const host=u.hostname.toLowerCase().replace(/\.$/,'');return ['http:','https:'].includes(u.protocol)&&!u.username&&!u.password&&host.includes('.')&&!/^[\d.]+$/.test(host)&&!/(^|\.)(localhost|local|internal|test|invalid|onion)$/.test(host)?u.href:null;}catch{return null;}}
function rows(target:string,items:CompanyRow[]){const body=$(target);body.replaceChildren();for(const r of items){const tr=make('tr');const title=make('td');title.append(make('strong',r.title),make('small',[r.address,r.postal].filter(Boolean).join(' · '),'muted'));tr.append(title,make('td',r.city||'—'),make('td',r.phone||'—'));const web=make('td');const url=safeLink(r.website);if(url){const a=make('a',translate('Otvori ↗'));a.href=url;a.target='_blank';a.rel='noopener noreferrer';web.append(a)}else web.textContent='—';const action=make('td'),btn=make('button',translate('Detalji →'),'textbtn');btn.addEventListener('click',()=>detail(r.id).catch(fail));action.append(btn);const source=make('td');source.append(make('span',(r.providers||'').split(',').filter(Boolean).map(x=>providerNames[x]||x).join(' · ')||'—','source-chip'));tr.append(web,source,action);body.append(tr)}if(!items.length){const tr=make('tr'),td=make('td',translate('Nema rezultata za odabrane kriterije.'),'muted');td.colSpan=6;tr.append(td);body.append(tr)}}
async function overview(){const [s,p]=await Promise.all([api<DashboardStats>('/api/stats'),api<CompanyPage>('/api/companies?limit=5&sort=new')]);$('metrics').replaceChildren();for(const [label,value,sym] of [[translate('Tvrtke u bazi'),s.total,'▤'],[translate('Gradovi'),s.cities,'⌖'],[translate('S telefonom'),s.phones,'☎'],[translate('S web stranicom'),s.websites,'↗']]){const c=make('article',undefined,'metric panel');c.append(make('div',sym,'metric-icon'),make('p',label),make('strong',n(value)));$('metrics').append(c)}$('city-chart').replaceChildren();for(const c of s.top_cities){const item=make('div',undefined,'chart-item'),head=make('div',undefined,'chart-label'),bar=make('div',undefined,'track'),fill=make('div');head.append(make('span',c.city),make('strong',n(c.n)));fill.style.width=100*c.n/(s.top_cities[0].n||1)+'%';bar.append(fill);item.append(head,bar);$('city-chart').append(item)}$('coverage').replaceChildren();for(const [label,count] of [[translate('Telefonski broj'),s.phones],[translate('Web stranica'),s.websites]]){const pct=s.total?Math.round(Number(count)/s.total*100):0;const item=make('div',undefined,'coverage-item'),head=make('div',undefined,'chart-label'),bar=make('div',undefined,'track'),fill=make('div');head.append(make('span',label),make('strong',pct+'%'));fill.style.width=pct+'%';bar.append(fill);item.append(head,bar,make('small',n(count)+translate(' od ')+n(s.total),'muted'));$('coverage').append(item)}rows('preview-rows',p.rows);}
async function cities(){const v=$('city').value;const cs=await api<string[]>('/api/cities');$('city').replaceChildren(new Option(translate('Svi gradovi'),''));for(const c of cs)$('city').add(new Option(c,c));$('city').value=v;}
async function directory(){const seq=++serial,p=filters();p.set('page',String(page));p.set('sort',$('sort').value);const d=await api<CompanyPage>('/api/companies?'+p);if(seq!==serial)return;total=d.total;const pages=Math.max(1,Math.ceil(total/25));if(page>pages){page=pages;return directory()}rows('company-rows',d.rows);$('result-count').textContent=n(total)+translate(' rezultata');$('page-label').textContent=translate('Stranica ')+n(page)+translate(' od ')+n(pages);$('prev').disabled=page<=1;$('next').disabled=page>=pages;}
const detailFields:Record<string,string>={oib:'OIB',email:translate('Poslovni e-mail'),industry:translate('Djelatnost'),address:translate('Adresa'),postal:translate('Poštanski broj'),city:translate('Grad'),country:translate('Država'),phone:translate('Telefon'),fax:translate('Telefon / faks'),website:translate('Web stranica'),social:translate('Društvene mreže'),logo:'Logo URL',person:translate('Kontakt osoba'),year:translate('Godina osnivanja'),employees:translate('Broj zaposlenih'),account:translate('Broj računa'),mbs:'MBS',rating:translate('Ocjena'),description:translate('Opis'),products:translate('Proizvodi i usluge'),source:translate('Izvor')};
async function detail(id:number|string){const r=await api<CompanyDetails>('/api/company/'+id);$('detail-title').textContent=r.title;$('detail-sub').textContent=[r.city,r.country].filter(Boolean).join(' · ');const body=$('detail-body');body.replaceChildren();for(const [key,label] of Object.entries(detailFields)){const el=make('div',undefined,'detail-field profile-property');el.append(make('small',label,'muted'));const u=['website','social','logo','source'].includes(key)&&safeLink(r[key]);if(u){const a=make('a',u);a.href=u;a.target='_blank';a.rel='noopener noreferrer';el.append(a)}else el.append(make('div',r[key]||'—'));body.append(el)}const src=make('div',undefined,'detail-field profile-sources');src.append(make('h3',translate('Poveznice izvora')));if(!(r.sources||[]).length)src.append(make('p',translate('Nema povezanih izvora.'),'muted'));for(const x of r.sources||[]){src.append(make('div',(providerNames[x.provider]||x.provider)+' · '+x.updated));const u=safeLink(x.url);if(u){const a=make('a',u);a.href=u;a.target='_blank';a.rel='noopener noreferrer';src.append(a)}}body.append(src);const hist=make('div',undefined,'detail-field history-block');hist.append(make('h3',translate('Povijest promjena')));body.append(hist);setProfileTab('details');$('detail').showModal();try{const changes=await api<CompanyHistory[]>('/api/history/'+id);if(!changes.length)hist.append(make('p',translate('Nema zabilježenih promjena od ove verzije.'),'muted'));for(const r of changes){const group=make('div',undefined,'history-event');group.append(make('strong',r.changed_at+' UTC · '+(providerNames[r.provider]||r.provider)));for(const [k,v] of Object.entries(r.changes))group.append(make('p',(detailFields[k]||k)+': '+(v.before||'—')+' → '+(v.after||'—')));hist.append(group)}}catch(e){hist.append(make('p',translate('Povijest nije dostupna.'),'muted'))}}
let lastStatus='idle';async function refreshBotStatus(){const s=await api<BotStatus>('/api/status'),active=['running','stopping'].includes(s.status);$('run-status').textContent=({idle:translate('Spremno'),running:translate('Aktivno'),stopping:translate('Zaustavljanje'),stopped:translate('Zaustavljeno'),failed:translate('Pogreška'),completed:translate('Završeno'),completed_with_errors:translate('Završeno s pogreškama')})[s.status]||s.status;$('start-btn').disabled=active;$('stop-btn').disabled=s.status!=='running';const pct=s.status==='completed'?100:0; $('progress-label').textContent=s.page?translate('Stranica ')+n(s.page)+' / '+n(s.last):translate('Nema aktivne operacije');$('progress-percent').textContent=active?translate('U tijeku'):pct? '100%':'—';$('progress-bar').style.width=(active?Math.min(99,Math.max(0,(s.page-1)/Math.max(s.last,1)*100)):pct)+'%';$('run-metrics').replaceChildren();for(const [k,v] of [[translate('Obrađeno'),s.processed],[translate('Dodano'),s.added],[translate('Preskočeno'),s.skipped],[translate('Pogreške'),s.errors]]){const c=make('div');c.append(make('small',k,'muted'),make('strong',n(v)));$('run-metrics').append(c)}$('logs').textContent=s.logs.join('\n')||translate('Nema aktivnosti.');if(lastStatus!==s.status&&!active){if(current==='overview')overview().catch(fail);if(current==='directory')directory().catch(fail);cities().catch(fail);providers().catch(fail)}lastStatus=s.status;}
document.querySelectorAll<HTMLElement>('[data-view]').forEach(e=>e.addEventListener('click',()=>go(e.dataset.view)));document.querySelectorAll<HTMLElement>('[data-go]').forEach(e=>e.addEventListener('click',()=>go(e.dataset.go)));$('all-export').onclick=()=>download();$('filtered-export').onclick=()=>download(true);$('close-detail').onclick=()=>$('detail').close();$('prev').onclick=()=>{page--;directory().catch(fail)};$('next').onclick=()=>{page++;directory().catch(fail)};let debounce;$('search').oninput=()=>{clearTimeout(debounce);debounce=setTimeout(()=>{page=1;directory().catch(fail)},250)};for(const id of ['city','contact','sort','source-filter'])$(id).onchange=()=>{page=1;directory().catch(fail)};$('reset').onclick=()=>{for(const id of ['search','city','contact','source-filter'])$(id).value='';$('sort').value='title';page=1;directory().catch(fail)};
$('collect-form').onsubmit=async e=>{e.preventDefault();$('start-btn').disabled=true;try{if($('provider').value==='registry'){go('registry');return;}if($('provider').value==='tvrtke') await post('/api/start',{term:$('term').value,start:+$('start').value,end:$('end').value?+$('end').value:null,delay:+$('delay').value,resume:$('resume').checked,permission:$('permission').checked});else {const mapping:Record<string,string>={};document.querySelectorAll<HTMLInputElement>('[data-map]').forEach(e=>{if(e.value.trim())mapping[e.dataset.map]=e.value.trim()});await post('/api/start-external',{provider:$('provider').value,url:$('endpoint').value,selector:$('selector').value,token:$('api-token').value,engine:$('provider').value==='html'?$('engine').value:'http',pages:+$('pages').value,delay:+$('delay').value,mapping,permission:$('permission').checked,...paginationConfig()});$('api-token').value='';}await refreshBotStatus();toast(translate('Web bot je pokrenut.'))}catch(err){$('start-btn').disabled=false;fail(err)}};$('stop-btn').onclick=()=>post('/api/stop',{}).then(refreshBotStatus).catch(fail);$('file').onchange=()=>{const f=$('file').files[0];$('file-name').textContent=f?f.name:translate('Nije odabrana datoteka.');$('import-btn').disabled=!f};$('import-btn').onclick=async()=>{const f=$('file').files[0];if(!f)return;$('import-btn').disabled=true;try{const r=await api<{read:number;added:number}>(f.name.toLowerCase().endsWith('.json')?'/api/import-json':'/api/import',{method:'POST',headers:{'X-Local-Token':token},body:f});toast(translate('Učitano ')+n(r.read)+translate(' · novih ')+n(r.added));await cities();await providers();$('file').value='';$('file-name').textContent=translate('Nije odabrana datoteka.');}catch(e){fail(e);$('import-btn').disabled=false}};
const providerNames:Record<string,string>={tvrtke:'Tvrtke.hr',companywall:'CompanyWall.hr',registry:translate('Sudski registar'),company:'Company.hr',html:translate('Prilagođeni web'),json:translate('Prilagođeni API'),csv:translate('CSV / postojeći podaci')};
const hints:Record<string,string>={tvrtke:translate('Pretraživanje poslovnog imenika prema nazivu.'),companywall:translate('Unesite ugovorenu Web API adresu i mapiranje iz dokumentacije CompanyWalla.'),registry:translate('Unesite adresu javnog REST API-ja iz službene dokumentacije Sudskog registra.'),company:translate('Unesite službeni API endpoint i odgovarajuće mapiranje.'),html:translate('Unesite dopuštenu javnu HTTPS stranicu, CSS selektor kartice tvrtke i selektore polja.'),json:translate('Unesite autorizirani JSON API endpoint i mapirajte polja.')};
const maps:Record<string,string>={title:translate('Naziv tvrtke'),oib:'OIB',mbs:'MBS',industry:translate('Djelatnost'),address:translate('Adresa'),postal:translate('Poštanski broj'),city:translate('Grad'),country:translate('Država'),phone:translate('Telefon'),email:translate('Poslovni e-mail'),website:translate('Web stranica'),year:translate('Godina osnivanja'),employees:translate('Broj zaposlenih'),rating:translate('Ocjena'),description:translate('Opis')};
for(const [k,v] of Object.entries(maps)){const label=make('label',v),inp=make('input');inp.dataset.map=k;inp.placeholder=k;inp.autocomplete='off';label.append(inp);$('mapping-grid').append(label)}
function sourceChange(){const p=$('provider').value;$('native-settings').hidden=p!=='tvrtke';$('external-settings').hidden=p==='tvrtke';$('source-help').textContent=hints[p];$('token-label').hidden=p==='html';$('engine-label').hidden=p!=='html';$('engine').value='http';$('selector-label').firstChild.textContent=p==='html'?translate('CSS selektor kartice tvrtke'):translate('Putanja JSON liste (prazno = korijenska lista)');$('selector').placeholder=p==='html'?'.company-card':'data.items';$('endpoint').required=p!=='tvrtke'&&p!=='registry';if(p==='registry'){$('external-settings').hidden=true;go('registry');}$('api-token').value='';for(const e of document.querySelectorAll<HTMLInputElement>('[data-map]')){e.value='';e.placeholder=p==='html'?'.'+e.dataset.map:e.dataset.map;} }
$('provider').onchange=sourceChange;sourceChange();
async function providers(){const list=await api<SourceInfo[]>('/api/providers'),select=$('source-filter'),old=select.value;select.replaceChildren(new Option(translate('Svi izvori'),''));$('source-summary').replaceChildren();for(const p of list){select.append(new Option(p.label,p.provider));const r=make('div',undefined,'source-row');r.append(make('span',p.label),make('strong',n(p.n)));$('source-summary').append(r)}select.value=old;}
$('json-export').onclick=()=>location.href='/api/export-json';
try{document.documentElement.dataset.theme=localStorage.getItem('crawlvora-theme')||'dark'}catch{}$('theme').onclick=()=>{const t=document.documentElement.dataset.theme==='light'?'dark':'light';document.documentElement.dataset.theme=t;try{localStorage.setItem('crawlvora-theme',t)}catch{}};cities().catch(fail);providers().catch(fail);go('overview');refreshBotStatus().catch(fail);let polling=false;setInterval(async()=>{if(polling)return;polling=true;try{await refreshBotStatus()}catch{}finally{polling=false}},1500);

// Persistent project library and interactive extraction studio.
function paginationConfig(){return {mode:$('pagination-mode').value,page_start:+$('page-start').value,offset_step:+$('offset-step').value,next_selector:$('next-selector').value,cursor_path:$('cursor-path').value,cursor_param:$('cursor-param').value};}
function paginationChange(){const m=$('pagination-mode').value;$('next-wrap').hidden=m!=='next';$('cursor-wrap').hidden=m!=='cursor';}
$('pagination-mode').onchange=paginationChange;paginationChange();
function config(){const mapping:Record<string,string>={};document.querySelectorAll<HTMLInputElement>('[data-map]').forEach(e=>{if(e.value.trim())mapping[e.dataset.map]=e.value.trim()});return {provider:$('provider').value,engine:$('provider').value==='html'?$('engine').value:'http',term:$('term').value,start:+$('start').value,end:$('end').value?+$('end').value:null,resume:$('resume').checked,url:$('endpoint').value,selector:$('selector').value,pages:+$('pages').value,delay:+$('delay').value,mapping,...paginationConfig()};}
let projects:SavedProject[]=[];
async function loadProjects(selected=$('project-select').value){projects=await api<SavedProject[]>('/api/projects');$('project-select').replaceChildren(new Option(translate('Novi projekt'),''));for(const p of projects)$('project-select').append(new Option(p.name,String(p.id)));$('project-select').value=selected;}
function setConfig(c:ScraperConfig){$('provider').value=c.provider||'tvrtke';sourceChange();for(const [id,key] of Object.entries({engine:'engine',term:'term',start:'start',end:'end',endpoint:'url',selector:'selector',pages:'pages',delay:'delay','pagination-mode':'mode','page-start':'page_start','offset-step':'offset_step','next-selector':'next_selector','cursor-path':'cursor_path','cursor-param':'cursor_param'})){if(c[key]!==undefined)$(id).value=c[key]??'';}$('resume').checked=c.resume!==false;$('permission').checked=false;for(const e of document.querySelectorAll<HTMLInputElement>('[data-map]'))e.value=c.mapping?.[e.dataset.map]||'';paginationChange();}
$('project-select').onchange=()=>{const p=projects.find(p=>String(p.id)===$('project-select').value);$('project-name').value=p?.name||'';if(p)setConfig(p.config);};
$('project-save').onclick=async()=>{try{const r=await post<{id:number}>('/api/projects/save',{id:$('project-select').value||null,name:$('project-name').value,config:config()});await loadProjects(String(r.id));toast(translate('Projekt je spremljen. API token nije pohranjen.'))}catch(e){fail(e)}};
$('project-delete').onclick=async()=>{if(!$('project-select').value||!confirm(translate('Izbrisati odabrani projekt? Prikupljeni podaci ostaju u bazi.')))return;try{await post('/api/projects/delete',{id:$('project-select').value});await loadProjects('');$('project-name').value='';toast(translate('Projekt je izbrisan.'))}catch(e){fail(e)}};
$('xlsx-export').onclick=()=>location.href='/api/export-xlsx';$('filtered-xlsx').onclick=()=>location.href='/api/export-xlsx?'+filters();
let studioHTML='', studioMap:Record<string,string>={}, studioResult:StudioResult|null=null;
for(const [key,label] of Object.entries(maps)){$('studio-field').append(new Option(label,key));const l=make('label',label),i=make('input');i.dataset.studioMap=key;i.placeholder=translate('CSS selektor');i.oninput=()=>{studioMap[key]=i.value;};l.append(i);$('studio-mapping').append(l)}
function syncStudio(){for(const el of document.querySelectorAll<HTMLInputElement>('[data-studio-map]'))el.value=studioMap[el.dataset.studioMap]||'';}
function drawStudio(r:StudioResult){studioResult=r;$('studio-code').textContent=r.html.slice(0,16000);$('studio-selector').value=r.selector;$('studio-candidates').replaceChildren();for(const c of r.suggestions){const b=make('button',`${c.selector} · ${c.count} · ${c.fields||0} ${translate("polja")}`,'btn secondary small');b.type='button';b.onclick=()=>{$('studio-selector').value=c.selector;scanStudio('select')};$('studio-candidates').append(b)}$('studio-elements').replaceChildren();for(const el of r.elements){const b=make('button',undefined,'element-choice');b.type='button';b.append(make('strong',el.sample),make('small',el.selector));b.onclick=()=>{studioMap[$('studio-field').value]=el.selector;syncStudio();scanStudio('preview')};$('studio-elements').append(b)}const cols=Object.keys(studioMap).filter(k=>studioMap[k]);const head=make('tr');for(const k of cols)head.append(make('th',maps[k]||k));$('studio-head').replaceChildren(head);$('studio-body').replaceChildren();for(const row of r.preview){const tr=make('tr');for(const k of cols)tr.append(make('td',row[k]||'—'));$('studio-body').append(tr)}$('studio-count').textContent=`${r.preview.length} ${translate("zapisa")} · ${Object.keys(r.mapping).length} ${translate("polja")}${r.confidence==='low'?translate(' · provjerite mapiranje'):''}`;$('studio-apply').disabled=!r.preview.length;}
async function scanStudio(mode:'scan'|'select'|'preview'){const controls=['studio-scan','studio-select','studio-preview'];controls.forEach(id=>$(id).disabled=true);try{const data:{html:string;url:string;engine:string;permission:boolean;selector:string;mapping?:Record<string,string>}={html:mode==='scan'?$('studio-html').value:studioHTML,url:$('studio-url').value,engine:$('studio-engine').value,permission:$('studio-permission').checked,selector:mode==='scan'?'':$('studio-selector').value};if(mode==='preview')data.mapping=studioMap;const r=await post<StudioResult>('/api/inspect',data);studioHTML=r.html;if(mode!=='preview'){studioMap=r.mapping;syncStudio();}drawStudio(r);toast(r.preview.length?translate('Uzorak je analiziran.'):translate('Nema rezultata; odaberite drugi selektor.'))}catch(e){fail(e)}finally{controls.forEach(id=>$(id).disabled=false)}}
$('studio-file').onchange=async()=>{const f=$('studio-file').files[0];if(!f)return;if(f.size>2000000)return toast(translate('HTML datoteka je prevelika.'));$('studio-html').value=await f.text();};$('studio-scan').onclick=()=>scanStudio('scan');$('studio-select').onclick=()=>scanStudio('select');$('studio-preview').onclick=()=>scanStudio('preview');$('studio-apply').onclick=()=>{if(!studioResult)return;setConfig({provider:'html',engine:$('studio-engine').value,url:$('studio-url').value,selector:$('studio-selector').value,mapping:studioMap,pages:1,delay:3,mode:'page'});$('project-select').value='';$('project-name').value='';go('collector');toast(translate('Pravila su prenesena. Provjerite adresu i dopuštenje pa pokrenite bota.'));};

let regSelection:RegistryCategory|null=null, regPage=1, regTotal=0;
let regRefreshBusy=false, regRowsSerial=0, regSearchTimer;
async function registryRefresh(){
 if(regRefreshBusy)return; regRefreshBusy=true;
 try{
 const [r,s]=await Promise.all([api<RegistrySummary>('/api/registry'),api<BotStatus>('/api/status')]);
 const active=['running','stopping'].includes(s.status), ours=['registry','registry-check'].includes(s.kind);
 $('reg-config').textContent=r.configured?translate('API konfiguriran'):translate('API nije konfiguriran');
 $('reg-config').dataset.state=r.configured?'ready':'warning';
 $('reg-start').disabled=!r.configured||active; $('reg-check').disabled=!r.configured||active; $('reg-stop').disabled=!ours||s.status!=='running';
 $('reg-status').textContent=active&&!ours?translate('Aktivan je drugi web bot'):ours?(({running:translate('Aktivno'),stopping:translate('Zaustavljanje'),completed:translate('Završeno'),failed:translate('Pogreška'),stopped:translate('Zaustavljeno')})[s.status]||s.status):translate('Spremno');
 $('reg-logs').textContent=ours?s.logs.slice(-12).join('\n')||translate('Čekanje na API…'):translate('Nema aktivnosti registra.');
 const progress=ours&&s.kind==='registry'&&s.last?Math.min(100,s.status==='completed'?100:Math.max(0,(s.page-1)/s.last*100)):0;
 $('reg-progress-label').textContent=ours&&s.kind==='registry'&&s.last?translate('Kategorija ')+n(s.page)+' / '+n(s.last):translate('Nema aktivne sinkronizacije');
 $('reg-percent').textContent=progress?Math.floor(progress)+'%':'—'; $('reg-progress-bar').style.width=progress+'%';
 updateDiffOptions(r.runs); const selected=$('reg-snapshot').value; const options=[make('option',translate('Sve snimke'))]; options[0].value='';
 for(const run of r.runs){const o=make('option',run.snapshot+' · '+(run.complete?translate('završena'):translate('nedovršena')));o.value=run.snapshot;options.push(o)}
 $('reg-snapshot').replaceChildren(...options); $('reg-snapshot').value=r.runs.some(x=>x.snapshot===selected)?selected:'';
 const cats=r.categories.filter(c=>!selected||c.snapshot===selected);
 $('reg-metrics').replaceChildren();
 for(const [label,value,sub] of [[translate('Snimke'),r.runs.length,translate('Lokalno pohranjene')],[translate('Dovršene snimke'),r.runs.filter(x=>x.complete).length,translate('Konzistentna preuzimanja')],[translate('Kategorije'),cats.filter(c=>c.done).length,translate('Dovršene u odabiru')],[translate('Izvorni redci'),cats.reduce((a,c)=>a+c.rows,0),translate('Preuzeto po kategorijama')]]){const el=make('article',undefined,'reg-metric panel');el.append(make('span',label,'muted'),make('strong',n(value)),make('small',sub,'muted'));$('reg-metrics').append(el)}
 $('reg-categories').replaceChildren();
 for(const c of cats){const tr=make('tr');for(const v of [c.snapshot,c.category,n(c.rows)+(c.total==null?'':' / '+n(c.total))])tr.append(make('td',v));const state=make('td');state.append(make('span',c.done?translate('Preuzeto'):translate('Nedovršeno'),c.done?'registry-pill done':'registry-pill'));tr.append(state);const td=make('td'),b=make('button',translate('Otvori'),'btn secondary small');b.onclick=()=>{regSelection=c;regPage=1;$('reg-search').value='';$('reg-search').disabled=false;registryRows().catch(fail)};td.append(b);tr.append(td);$('reg-categories').append(tr)}
 if(!cats.length){const tr=make('tr'),td=make('td',translate('Nema preuzetih kategorija. Pokrenite sinkronizaciju.'),'empty-state');td.colSpan=5;tr.append(td);$('reg-categories').append(tr)}
 }finally{regRefreshBusy=false}
}
async function registryRows(){if(!regSelection)return;const serial=++regRowsSerial;const p=new URLSearchParams({snapshot:regSelection.snapshot,category:regSelection.category,page:String(regPage),q:$('reg-search').value});const r=await api<RegistryPage>('/api/registry/rows?'+p);if(serial!==regRowsSerial)return;regTotal=r.total;const keys=[...new Set(r.rows.flatMap(Object.keys))];const tr=make('tr');for(const k of keys)tr.append(make('th',k));$('reg-head').replaceChildren(tr);$('reg-body').replaceChildren();for(const row of r.rows){const tr=make('tr');for(const k of keys){const v=row[k];let display=v==null?'—':typeof v==='object'?JSON.stringify(v):String(v);if(v!=null&&['oib','mbs'].includes(k.toLowerCase())&&/^\d+$/.test(display))display=display.padStart(k.toLowerCase()==='oib'?11:9,'0');tr.append(make('td',display))}$('reg-body').append(tr)}$('reg-table-title').textContent=regSelection.category+' · '+regSelection.snapshot;$('reg-export').disabled=false;$('reg-export-csv').disabled=false;for(const format of ['xlsx','xml','sql'])$('reg-export-'+format).disabled=false;$('reg-row-count').textContent=n(regTotal)+translate(' rezultata · izvoz cijele kategorije');$('reg-page').textContent=regPage+' / '+Math.max(1,Math.ceil(regTotal/50));$('reg-prev').disabled=regPage<=1;$('reg-next').disabled=regPage*50>=regTotal}
$('reg-snapshot').onchange=()=>registryRefresh().catch(fail);
$('reg-search').oninput=()=>{clearTimeout(regSearchTimer);regSearchTimer=setTimeout(()=>{regPage=1;registryRows().catch(fail)},250)};
$('reg-check').onclick=()=>post('/api/registry/check',{permission:$('reg-permission').checked}).then(registryRefresh).catch(fail);
$('reg-export-csv').onclick=()=>{if(regSelection)location.href='/api/registry/export-csv?'+new URLSearchParams({snapshot:regSelection.snapshot,category:regSelection.category})};
$('reg-start').onclick=()=>post('/api/registry/start',{limit:+$('reg-limit').value,permission:$('reg-permission').checked}).then(registryRefresh).catch(fail);$('reg-stop').onclick=()=>post('/api/stop',{}).then(registryRefresh).catch(fail);$('reg-reload').onclick=()=>registryRefresh().catch(fail);$('reg-prev').onclick=()=>{if(regPage>1){regPage--;registryRows().catch(fail)}};$('reg-next').onclick=()=>{if(regPage*50<regTotal){regPage++;registryRows().catch(fail)}};setInterval(()=>{if(current==='registry')registryRefresh().catch(()=>{})},2500);

$('reg-export').onclick=()=>{if(regSelection)location.href='/api/registry/export?'+new URLSearchParams({snapshot:regSelection.snapshot,category:regSelection.category})};

for(const format of ['xlsx','xml','sql'])$('reg-export-'+format).onclick=()=>{if(regSelection)location.href='/api/registry/export-'+format+'?'+new URLSearchParams({snapshot:regSelection.snapshot,category:regSelection.category})};
const jobLabels:Record<string,string>={retry_wait:translate('Čeka ponavljanje'),queued:translate('Na čekanju'),running:translate('Aktivno'),completed:translate('Završeno'),completed_with_errors:translate('S pogreškama'),failed:translate('Pogreška'),stopped:translate('Zaustavljeno'),interrupted:translate('Prekinuto'),cancelled:translate('Otkazano')};
async function refreshJobs(init=false){const r=await api<JobSummary>('/api/jobs');if(init){$('schedule-enabled').checked=!!r.schedule.enabled;$('schedule-hour').value=String(r.schedule.hour);}$('schedule-state').textContent=r.schedule.enabled?translate('Aktivno'):translate('Isključeno');const m=$('job-metrics');m.replaceChildren();for(const state of ['queued','retry_wait','running','completed','failed']){const el=make('div');el.append(make('small',jobLabels[state],'muted'),make('strong',n(r.jobs.filter(x=>x.state===state).length)));m.append(el)}const b=$('job-rows');b.replaceChildren();for(const j of r.jobs){const tr=make('tr');for(const v of [j.id,providerNames[j.kind]||j.kind,jobLabels[j.state]||j.state,j.created,j.finished||'—',String(j.attempts||0)+(j.next_run?' · '+new Date(j.next_run*1000).toLocaleString(UI_LANGUAGE==='hr'?'hr-HR':'en-US'):'')])tr.append(make('td',String(v)));const td=make('td');if(['queued','retry_wait'].includes(j.state)){const cancel=make('button',translate('Otkaži'),'btn secondary small');cancel.onclick=()=>post('/api/jobs/cancel',{id:j.id}).then(()=>refreshJobs()).catch(fail);td.append(cancel)}tr.append(td);b.append(tr)}if(!r.jobs.length){const tr=make('tr');const td=make('td',translate('Nema spremljenih zadataka.'),'empty-state');td.colSpan=7;tr.append(td);b.append(tr)}}
$('jobs-refresh').onclick=()=>refreshJobs(true).catch(fail);
$('schedule-save').onclick=()=>post('/api/jobs/schedule',{enabled:$('schedule-enabled').checked,hour:+$('schedule-hour').value,permission:$('schedule-permission').checked}).then(()=>{toast(translate('Raspored je spremljen.'));return refreshJobs(true)}).catch(fail);
$('jobs-registry').onclick=()=>post('/api/jobs/add',{kind:'registry',config:{permission:$('schedule-permission').checked,limit:500}}).then(()=>refreshJobs()).catch(fail);
$('queue-add').onclick=()=>{const c=config();if($('api-token').value)return toast(translate('Red zadataka ne pohranjuje API tokene.'));post('/api/jobs/add',{kind:c.provider,config:{...c,permission:$('permission').checked}}).then(()=>{toast(translate('Zadatak je spremljen.'));go('jobs')}).catch(fail)};
setInterval(()=>{if(current==='jobs')refreshJobs().catch(()=>{})},3000);

function updateDiffOptions(runs:RegistryRun[]){const ids=runs.filter(x=>x.complete).map(x=>String(x.snapshot));for(const [id,idx] of ([['diff-before',1],['diff-after',0]] as const)){const el=$(id),old=el.value;el.replaceChildren(...ids.map(v=>new Option(v,v)));el.value=ids.includes(old)?old:(ids[idx]||'');} $('diff-run').disabled=ids.length<2;}
$('diff-run').onclick=async()=>{const b=$('diff-run');b.disabled=true;try{const p=new URLSearchParams({before:$('diff-before').value,after:$('diff-after').value});const r=await api<RegistryDiff>('/api/registry/diff?'+p);$('diff-rows').replaceChildren();for(const c of r.categories){const tr=make('tr');for(const v of [c.category,c.comparable?n(c.added):translate('Nije usporedivo'),c.comparable?n(c.removed):'—',c.comparable?n(c.affected_subjects):'—'])tr.append(make('td',v));$('diff-rows').append(tr)}$('diff-status').textContent=translate('Snimke ')+r.before+' → '+r.after+translate(' · izmjena retka prikazuje se kao uklanjanje i dodavanje.');}catch(e){fail(e)}finally{b.disabled=false}};


function renderChart(target:string, entries:{label:string;n:number}[]) {
    const el=$(target); el.replaceChildren();
    const max=Math.max(1,...entries.map(x=>Number(x.n)));
    for(const item of entries) {
        const row=make('div',undefined,'chart-item'), label=make('div',undefined,'chart-label'), bar=make('div',undefined,'track'), fill=make('div');
        label.append(make('span',item.label),make('strong',n(item.n)));
        fill.style.width=Math.max(0,Math.min(100,100*Number(item.n)/max))+'%';
        bar.append(fill); row.append(label,bar); el.append(row);
    }
    if(!entries.length)el.append(make('p',translate('Nema evidentiranih promjena.'),'muted'));
}
async function refreshAnalytics(){
    const [s,h]=await Promise.all([api<DashboardStats>('/api/stats'),api<{days:{day:string;n:number}[]}>('/api/analytics')]);
    const metrics=$('analytics-metrics');metrics.replaceChildren();
    for(const [label,value] of [[translate('Tvrtke u bazi'),s.total],[translate('Gradovi'),s.cities],[translate('S telefonom'),s.phones],[translate('S web stranicom'),s.websites]]){
        const card=make('article',undefined,'metric panel');card.append(make('p',label),make('strong',n(value)));metrics.append(card);
    }
    renderChart('analytics-cities',s.top_cities.map(x=>({label:x.city,n:x.n})));
    const coverage=$('analytics-coverage');coverage.replaceChildren();
    for(const [label,count] of [[translate('Telefonski broj'),s.phones],[translate('Web stranica'),s.websites]]){
        const percent=s.total?Math.round(Number(count)*100/s.total):0;
        const row=make('div',undefined,'coverage-item'),head=make('div',undefined,'chart-label'),bar=make('div',undefined,'track'),fill=make('div');
        head.append(make('span',label),make('strong',percent+'%'));fill.style.width=percent+'%';bar.append(fill);row.append(head,bar,make('small',n(count)+' / '+n(s.total),'muted'));coverage.append(row);
    }
    renderChart('analytics-history',h.days.map(x=>({label:x.day,n:x.n})));
    await providers();
}
function syncSettings(){
    const dark=document.documentElement.dataset.theme!=='light';
    $('settings-dark').setAttribute('aria-pressed',String(dark));$('settings-light').setAttribute('aria-pressed',String(!dark));
    $('settings-en').setAttribute('aria-pressed',String(UI_LANGUAGE==='en'));$('settings-hr').setAttribute('aria-pressed',String(UI_LANGUAGE==='hr'));
}
async function refreshSettings(){
    syncSettings();
    const [s,r]=await Promise.all([api<DashboardStats>('/api/stats'),api<RegistrySummary>('/api/registry')]);
    $('settings-count').textContent=n(s.total);
    $('settings-api').textContent=translate(r.configured?'API konfiguriran':'API nije konfiguriran');
}
function syncQuickFilters(){
    document.querySelectorAll<HTMLButtonElement>('[data-contact-filter]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.contactFilter===$('contact').value)));
}
document.querySelectorAll<HTMLButtonElement>('[data-contact-filter]').forEach(b=>b.addEventListener('click',()=>{$('contact').value=b.dataset.contactFilter||'';$('contact').dispatchEvent(new Event('change'));syncQuickFilters()}));
$('contact').addEventListener('change',syncQuickFilters);$('reset').addEventListener('click',syncQuickFilters);syncQuickFilters();
$('analytics-export').onclick=()=>download();$('analytics-xlsx').onclick=()=>location.href='/api/export-xlsx';$('analytics-json').onclick=()=>location.href='/api/export-json';
$('settings-dark').onclick=()=>{if(document.documentElement.dataset.theme==='light')$('theme').click();syncSettings()};
$('settings-light').onclick=()=>{if(document.documentElement.dataset.theme!=='light')$('theme').click();syncSettings()};
$('settings-en').onclick=()=>{if(UI_LANGUAGE!=='en')$('language').click()};
$('settings-hr').onclick=()=>{if(UI_LANGUAGE!=='hr')$('language').click()};
$('theme').addEventListener('click',syncSettings);syncSettings();

function setProfileTab(tab:string){
  const dialog=$('detail');dialog.dataset.profileTab=tab;
  dialog.querySelectorAll<HTMLButtonElement>('[data-profile-tab]').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.profileTab===tab)));
  dialog.scrollTop=0;
}
$('detail').querySelectorAll<HTMLButtonElement>('[data-profile-tab]').forEach(button=>button.addEventListener('click',()=>setProfileTab(button.dataset.profileTab||'details')));
