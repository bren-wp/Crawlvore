'use strict';
const $=id=>{const element=document.getElementById(id);if(!element)throw Error('Missing interface element: '+id);return element;}, token=document.querySelector('meta[name="local-token"]')?.content || document.querySelector('meta[name="csrf-token"]')?.content || '';
const nf=new Intl.NumberFormat(UI_LANGUAGE==='hr'?'hr-HR':'en-US'); const n=v=>nf.format(Number(v??0)); let page=1, total=0, serial=0, timer, current='overview';
const make=(tag,text,cls)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=String(text);if(cls)e.className=cls;return e};
async function api(path,opts={}){const r=await fetch(path,opts);const d=await r.json();if(!r.ok)throw Error(translate(String(d.error||'Operacija nije uspjela.')));return d;}
function toast(msg){$('toast').textContent=msg;$('toast').hidden=false;clearTimeout(timer);timer=setTimeout(()=>$('toast').hidden=true,5500);}
const fail=e=>toast(e instanceof Error?e.message:translate('Pogreška pri povezivanju.'));
function post(path,data){return api(path,{method:'POST',headers:{'Content-Type':'application/json','X-Local-Token':token},body:JSON.stringify(data)});}
function filters(){return new URLSearchParams({q:$('search').value,city:$('city').value,contact:$('contact').value,provider:$('source-filter').value,entity_kind:$('entity-kind').value});}
function download(filtered=false){location.href='/api/export'+(filtered?'?'+filters():'');}
function go(view){current=view;document.querySelectorAll('.view').forEach(e=>e.hidden=e.id!==view);document.querySelectorAll('[data-view]').forEach(e=>e.classList.toggle('active',e.dataset.view===view));$('crumb').textContent={overview:translate('Pregled'),directory:translate('Poslovni imenik'),national:translate('Crawlvora UK'),registry:translate('Crawlvora Sync'),data:translate('Uvoz i izvoz'),jobs:translate('Zadaci i raspored'),analytics:translate('Analitika i izvještaji'),settings:translate('Postavke')}[view];if(view==='analytics')refreshAnalytics().catch(fail);if(view==='settings')refreshSettings().catch(fail);if(view==='jobs')refreshJobs(true).catch(fail);if(view==='overview')overview().catch(fail);if(view==='directory')directory().catch(fail);if(view==='national')nationalSearch(1).catch(fail);if(view==='registry')registryRefresh().catch(fail);window.scrollTo(0,0);}
function safeLink(value){if(typeof value!=='string')return null;try{const u=new URL(value);const host=u.hostname.toLowerCase().replace(/\.$/,'');return ['http:','https:'].includes(u.protocol)&&!u.username&&!u.password&&host.includes('.')&&!/^[\d.]+$/.test(host)&&!/(^|\.)(localhost|local|internal|test|invalid|onion)$/.test(host)?u.href:null;}catch{return null;}}
function rows(target,items){const body=$(target);body.replaceChildren();for(const r of items){const tr=make('tr');const title=make('td');title.append(make('strong',r.title),make('small',[r.address,r.postal].filter(Boolean).join(' · '),'muted'));tr.append(title,make('td',r.city||'—'),make('td',r.phone||'—'));const web=make('td');const url=safeLink(r.website);if(url){const a=make('a',translate('Otvori ↗'));a.href=url;a.target='_blank';a.rel='noopener noreferrer';web.append(a)}else web.textContent='—';const action=make('td'),btn=make('button',translate('Detalji →'),'textbtn');btn.addEventListener('click',()=>detail(r.id).catch(fail));action.append(btn);const source=make('td');source.append(make('span',(r.providers||'').split(',').filter(Boolean).map(x=>providerNames[x]||x).join(' · ')||'—','source-chip'));tr.append(web,source,action);body.append(tr)}if(!items.length){const tr=make('tr'),td=make('td',translate('Nema rezultata za odabrane kriterije.'),'muted');td.colSpan=6;tr.append(td);body.append(tr)}}
let dashboardReady=false;
async function overview(){const [s,p]=await Promise.all([api('/api/stats'),api('/api/companies?limit=5&sort=new')]);$('metrics').replaceChildren();for(const [label,value,sym] of [[translate('Tvrtke u bazi'),s.total,'▤'],[translate('Gradovi'),s.cities,'⌖'],[translate('S telefonom'),s.phones,'☎'],[translate('S web stranicom'),s.websites,'↗']]){const c=make('article',undefined,'metric panel');c.append(make('div',sym,'metric-icon'),make('p',label),make('strong',n(value)));$('metrics').append(c)}$('city-chart').replaceChildren();for(const c of s.top_cities){const item=make('div',undefined,'chart-item'),head=make('div',undefined,'chart-label'),bar=make('div',undefined,'track'),fill=make('div');head.append(make('span',c.city),make('strong',n(c.n)));fill.style.width=100*c.n/(s.top_cities[0].n||1)+'%';bar.append(fill);item.append(head,bar);$('city-chart').append(item)}$('coverage').replaceChildren();for(const [label,count] of [[translate('Telefonski broj'),s.phones],[translate('Web stranica'),s.websites]]){const pct=s.total?Math.round(count/s.total*100):0;const item=make('div',undefined,'coverage-item'),head=make('div',undefined,'chart-label'),bar=make('div',undefined,'track'),fill=make('div');head.append(make('span',label),make('strong',pct+'%'));fill.style.width=pct+'%';bar.append(fill);item.append(head,bar,make('small',n(count)+translate(' od ')+n(s.total),'muted'));$('coverage').append(item)}rows('preview-rows',p.rows);if(!dashboardReady){await post('/api/ui-ready',{});dashboardReady=true;}}
async function cities(){const v=$('city').value;const cs=await api('/api/cities');$('city').replaceChildren(new Option(translate('Svi gradovi'),''));for(const c of cs)$('city').add(new Option(c,c));$('city').value=v;}
async function directory(){const seq=++serial,p=filters();p.set('page',String(page));p.set('sort',$('sort').value);const d=await api('/api/companies?'+p);if(seq!==serial)return;total=d.total;const pages=Math.max(1,Math.ceil(total/25));if(page>pages){page=pages;return directory()}rows('company-rows',d.rows);$('result-count').textContent=n(total)+translate(' rezultata');$('page-label').textContent=translate('Stranica ')+n(page)+translate(' od ')+n(pages);$('prev').disabled=page<=1;$('next').disabled=page>=pages;}
const detailFields={entity_kind:translate('Vrsta subjekta'),oib:'OIB',email:translate('Poslovni e-mail'),industry:translate('Djelatnost'),address:translate('Adresa'),postal:translate('Poštanski broj'),city:translate('Grad'),country:translate('Država'),phone:translate('Telefon'),fax:translate('Telefon / faks'),website:translate('Web stranica'),social:translate('Društvene mreže'),person:translate('Kontakt osoba'),year:translate('Godina osnivanja'),employees:translate('Broj zaposlenih'),account:translate('Broj računa'),mbs:'MBS',rating:translate('Ocjena'),description:translate('Opis'),products:translate('Proizvodi i usluge')};
async function detail(id){const r=await api('/api/company/'+id);$('detail-title').textContent=r.title;$('detail-sub').textContent=[r.city,r.country].filter(Boolean).join(' · ');const body=$('detail-body');body.replaceChildren();for(const [key,label] of Object.entries(detailFields)){const el=make('div',undefined,'detail-field profile-property');el.append(make('small',label,'muted'));const u=['website','social','logo','source'].includes(key)&&safeLink(r[key]);if(u){const a=make('a',u);a.href=u;a.target='_blank';a.rel='noopener noreferrer';el.append(a)}else el.append(make('div',r[key]||'—'));body.append(el)}const src=make('div',undefined,'detail-field profile-sources');src.append(make('h3',translate('Podrijetlo podataka')));if(!(r.sources||[]).length)src.append(make('p',translate('Nema povezanih izvora.'),'muted'));for(const x of r.sources||[]){src.append(make('div',(providerNames[x.provider]||x.provider)+' · '+x.updated));const u=safeLink(x.url);if(u){const a=make('a',u);a.href=u;a.target='_blank';a.rel='noopener noreferrer';src.append(a)}}const alt=make('div',undefined,'alternate-values');alt.append(make('h3',translate('Sačuvane alternativne vrijednosti')));if(!(r.alternate_values||[]).length)alt.append(make('p',translate('Nema alternativnih vrijednosti.'),'muted'));for(const v of r.alternate_values||[]){const item=make('div',undefined,'history-event');item.append(make('strong',detailFields[v.field]||v.field),make('p',v.value),make('small',(providerNames[v.provider]||v.provider)+' · '+v.observed_at+' UTC','muted'));alt.append(item)}src.append(alt);body.append(src);const hist=make('div',undefined,'detail-field history-block');hist.append(make('h3',translate('Povijest promjena')));body.append(hist);addRegistryProfile(id,body);setProfileTab('details');$('detail').showModal();try{const changes=await api('/api/history/'+id);if(!changes.length)hist.append(make('p',translate('Nema zabilježenih promjena od ove verzije.'),'muted'));for(const r of changes){const group=make('div',undefined,'history-event');group.append(make('strong',r.changed_at+' UTC · '+(providerNames[r.provider]||r.provider)));for(const [k,v] of Object.entries(r.changes))group.append(make('p',(detailFields[k]||k)+': '+(v.before||'—')+' → '+(v.after||'—')));hist.append(group)}}catch(e){hist.append(make('p',translate('Povijest nije dostupna.'),'muted'))}}
document.querySelectorAll('[data-view]').forEach(e=>e.addEventListener('click',()=>go(e.dataset.view)));document.querySelectorAll('[data-go]').forEach(e=>e.addEventListener('click',()=>go(e.dataset.go)));$('all-export').onclick=()=>download();$('filtered-export').onclick=()=>download(true);$('close-detail').onclick=()=>$('detail').close();$('prev').onclick=()=>{page--;directory().catch(fail)};$('next').onclick=()=>{page++;directory().catch(fail)};let debounce;$('search').oninput=()=>{clearTimeout(debounce);debounce=setTimeout(()=>{page=1;directory().catch(fail)},250)};for(const id of ['city','contact','sort','source-filter','entity-kind'])$(id).onchange=()=>{page=1;directory().catch(fail)};$('reset').onclick=()=>{for(const id of ['search','city','contact','source-filter','entity-kind'])$(id).value='';$('sort').value='title';page=1;directory().catch(fail)};
const providerNames={tvrtke:'Tvrtke.hr',companywall:'CompanyWall.hr',registry:translate('Crawlvora Sync'),company:'Company.hr',html:translate('Prilagođeni web'),json:translate('Prilagođeni API'),csv:translate('CSV / postojeći podaci')};
async function providers(){const list=await api('/api/providers'),select=$('source-filter'),old=select.value;select.replaceChildren(new Option(translate('Svi izvori'),''));$('source-summary').replaceChildren();for(const p of list){const label=providerNames[p.provider]||p.label;select.append(new Option(label,p.provider));const r=make('div',undefined,'source-row');r.append(make('span',label),make('strong',n(p.n)));$('source-summary').append(r)}select.value=old;}
$('json-export').onclick=()=>location.href='/api/export-json';
const exportFields=[...document.querySelectorAll('input[name="export-field"]')];
function syncExportFields(){$('export-selected').disabled=!exportFields.some(field=>field.checked);}
for(const field of exportFields)field.addEventListener('change',syncExportFields);
$('export-select-all').onclick=()=>{for(const field of exportFields)field.checked=true;syncExportFields();};
$('export-clear-all').onclick=()=>{for(const field of exportFields)field.checked=false;syncExportFields();};
$('export-selected').onclick=()=>{const selected=exportFields.filter(field=>field.checked).map(field=>field.value);if(!selected.length)return;const p=$('export-filtered').checked?filters():new URLSearchParams();p.set('fields',selected.join(','));p.set('format',$('export-format').value);p.set('distinct',$('export-distinct').checked?'1':'0');p.set('omit_empty','1');location.href='/api/export-fields?'+p;};
syncExportFields();
let themeWrite=Promise.resolve();
$('theme').onclick=()=>{const t=document.documentElement.dataset.theme==='light'?'dark':'light';document.documentElement.dataset.theme=t;themeWrite=themeWrite.then(async()=>{await post('/api/preferences/theme',{theme:t})}).catch(fail);};cities().catch(fail);providers().catch(fail);go('overview');

$('xlsx-export').onclick=()=>location.href='/api/export-xlsx';$('filtered-xlsx').onclick=()=>location.href='/api/export-xlsx?'+filters();
let regSelection=null, regPage=1, regTotal=0;
let previousRegistryAuthorization=false;
let regRefreshBusy=false, regRowsSerial=0, regSearchTimer;
async function registryRefresh(){
 if(regRefreshBusy)return; regRefreshBusy=true;
 try{
 const [r,s]=await Promise.all([api('/api/registry'),api('/api/status')]);
 const active=['running','stopping'].includes(s.status), ours=['registry','registry-check'].includes(s.kind);
 $('reg-config').textContent=r.configured?translate('Pristup omogućen'):translate('Pristup nije omogućen');
 $('reg-config').dataset.state=r.configured?'ready':'warning';
 if(!!r.authorized!==previousRegistryAuthorization){$('reg-permission').checked=!!r.authorized;previousRegistryAuthorization=!!r.authorized;} $('reg-permission').disabled=!!r.authorized;
 $('reg-start').disabled=!r.configured||active; $('reg-check').disabled=!r.configured||active; $('reg-stop').disabled=!ours||s.status!=='running';
 $('reg-status').textContent=active&&!ours?translate('Druga operacija je u tijeku'):ours?(({running:translate('Aktivno'),stopping:translate('Zaustavljanje'),completed:translate('Završeno'),failed:translate('Pogreška'),stopped:translate('Zaustavljeno')})[s.status]||s.status):translate('Spremno');
 $('reg-logs').textContent=ours?translate('Priprema osvježavanja…'):translate('Nema aktivnog osvježavanja.');
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
async function registryRows(){if(!regSelection)return;const serial=++regRowsSerial;const p=new URLSearchParams({snapshot:regSelection.snapshot,category:regSelection.category,page:String(regPage),q:$('reg-search').value});const r=await api('/api/registry/rows?'+p);if(serial!==regRowsSerial)return;regTotal=r.total;const keys=[...new Set(r.rows.flatMap(Object.keys))];const tr=make('tr');for(const k of keys)tr.append(make('th',k));$('reg-head').replaceChildren(tr);$('reg-body').replaceChildren();for(const row of r.rows){const tr=make('tr');for(const k of keys){const v=row[k];let display=v==null?'—':typeof v==='object'?JSON.stringify(v):String(v);if(v!=null&&['oib','mbs'].includes(k.toLowerCase())&&/^\d+$/.test(display))display=display.padStart(k.toLowerCase()==='oib'?11:9,'0');tr.append(make('td',display))}$('reg-body').append(tr)}$('reg-table-title').textContent=regSelection.category+' · '+regSelection.snapshot;$('reg-export').disabled=false;$('reg-export-csv').disabled=false;for(const format of ['xlsx','xml','sql'])$('reg-export-'+format).disabled=false;$('reg-row-count').textContent=n(regTotal)+translate(' rezultata · izvoz cijele kategorije');$('reg-page').textContent=regPage+' / '+Math.max(1,Math.ceil(regTotal/50));$('reg-prev').disabled=regPage<=1;$('reg-next').disabled=regPage*50>=regTotal}
$('reg-snapshot').onchange=()=>registryRefresh().catch(fail);
$('reg-search').oninput=()=>{clearTimeout(regSearchTimer);regSearchTimer=setTimeout(()=>{regPage=1;registryRows().catch(fail)},250)};
$('reg-check').onclick=()=>post('/api/registry/check',{permission:$('reg-permission').checked}).then(registryRefresh).catch(fail);
$('reg-export-csv').onclick=()=>{if(regSelection)location.href='/api/registry/export-csv?'+new URLSearchParams({snapshot:regSelection.snapshot,category:regSelection.category})};
$('reg-start').onclick=()=>post('/api/registry/start',{limit:+$('reg-limit').value,permission:$('reg-permission').checked}).then(registryRefresh).catch(fail);$('reg-stop').onclick=()=>post('/api/stop',{}).then(registryRefresh).catch(fail);$('reg-reload').onclick=()=>registryRefresh().catch(fail);$('reg-prev').onclick=()=>{if(regPage>1){regPage--;registryRows().catch(fail)}};$('reg-next').onclick=()=>{if(regPage*50<regTotal){regPage++;registryRows().catch(fail)}};setInterval(()=>{if(current==='registry'&&!document.hidden)registryRefresh().catch(()=>{})},2500);

$('reg-export').onclick=()=>{if(regSelection)location.href='/api/registry/export?'+new URLSearchParams({snapshot:regSelection.snapshot,category:regSelection.category})};

for(const format of ['xlsx','xml','sql'])$('reg-export-'+format).onclick=()=>{if(regSelection)location.href='/api/registry/export-'+format+'?'+new URLSearchParams({snapshot:regSelection.snapshot,category:regSelection.category})};
const jobLabels={retry_wait:translate('Čeka ponavljanje'),queued:translate('Na čekanju'),running:translate('Aktivno'),completed:translate('Završeno'),completed_with_errors:translate('S pogreškama'),failed:translate('Pogreška'),stopped:translate('Zaustavljeno'),interrupted:translate('Prekinuto'),cancelled:translate('Otkazano')};
let jobsRefreshSequence=0, jobsRendered='';
async function refreshJobs(init=false){const request=++jobsRefreshSequence;const r=await api('/api/jobs');if(request!==jobsRefreshSequence)return;if(init){$('schedule-enabled').checked=!!r.schedule.enabled;$('schedule-hour').value=String(r.schedule.hour);}$('schedule-state').textContent=r.schedule.enabled?translate('Aktivno'):translate('Isključeno');const signature=JSON.stringify(r.jobs);if(signature===jobsRendered)return;jobsRendered=signature;const m=$('job-metrics');m.replaceChildren();for(const state of ['queued','retry_wait','running','completed','failed']){const el=make('div');el.append(make('small',jobLabels[state],'muted'),make('strong',n(r.jobs.filter(x=>x.state===state).length)));m.append(el)}const b=$('job-rows');b.replaceChildren();for(const j of r.jobs){const tr=make('tr');for(const v of [j.id,providerNames[j.kind]||j.kind,jobLabels[j.state]||j.state,j.created,j.finished||'—',String(j.attempts||0)+(j.next_run?' · '+new Date(j.next_run*1000).toLocaleString(UI_LANGUAGE==='hr'?'hr-HR':'en-US'):'')])tr.append(make('td',String(v)));const td=make('td');if(['queued','retry_wait'].includes(j.state)){const cancel=make('button',translate('Otkaži'),'btn secondary small');cancel.onclick=()=>post('/api/jobs/cancel',{id:j.id}).then(()=>refreshJobs()).catch(fail);td.append(cancel)}tr.append(td);b.append(tr)}if(!r.jobs.length){const tr=make('tr');const td=make('td',translate('Nema spremljenih zadataka.'),'empty-state');td.colSpan=7;tr.append(td);b.append(tr)}}
$('jobs-refresh').onclick=()=>refreshJobs(true).catch(fail);
$('schedule-save').onclick=()=>post('/api/jobs/schedule',{enabled:$('schedule-enabled').checked,hour:+$('schedule-hour').value,permission:$('schedule-permission').checked}).then(()=>{toast(translate('Raspored je spremljen.'));return refreshJobs(true)}).catch(fail);
$('jobs-registry').onclick=()=>post('/api/jobs/add',{kind:'registry',config:{permission:$('schedule-permission').checked,limit:500}}).then(()=>refreshJobs()).catch(fail);
setInterval(()=>{if(current==='jobs'&&!document.hidden)refreshJobs().catch(()=>{})},3000);
document.addEventListener('visibilitychange',()=>{if(!document.hidden){if(current==='registry')registryRefresh().catch(()=>{});if(current==='jobs')refreshJobs().catch(()=>{});}});

function updateDiffOptions(runs){const ids=runs.filter(x=>x.complete).map(x=>String(x.snapshot));for(const [id,idx] of [['diff-before',1],['diff-after',0]]){const el=$(id),old=el.value;el.replaceChildren(...ids.map(v=>new Option(v,v)));el.value=ids.includes(old)?old:(ids[idx]||'');} $('diff-run').disabled=ids.length<2;}
$('diff-run').onclick=async()=>{const b=$('diff-run');b.disabled=true;try{const p=new URLSearchParams({before:$('diff-before').value,after:$('diff-after').value});const r=await api('/api/registry/diff?'+p);$('diff-rows').replaceChildren();for(const c of r.categories){const tr=make('tr');for(const v of [c.category,c.comparable?n(c.added):translate('Nije usporedivo'),c.comparable?n(c.removed):'—',c.comparable?n(c.affected_subjects):'—'])tr.append(make('td',v));$('diff-rows').append(tr)}$('diff-status').textContent=translate('Snimke ')+r.before+' → '+r.after+translate(' · izmjena retka prikazuje se kao uklanjanje i dodavanje.');}catch(e){fail(e)}finally{b.disabled=false}};


function renderChart(target, entries) {
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
    const [s,h]=await Promise.all([api('/api/stats'),api('/api/analytics')]);
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
    const [s,r]=await Promise.all([api('/api/stats'),api('/api/registry')]);
    $('settings-count').textContent=n(s.total);
    $('settings-api').textContent=translate(r.configured?'Pristup omogućen':'Pristup nije omogućen');
    await refreshRecovery();
}
function syncQuickFilters(){
    document.querySelectorAll('[data-contact-filter]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.contactFilter===$('contact').value)));
}
document.querySelectorAll('[data-contact-filter]').forEach(b=>b.addEventListener('click',()=>{$('contact').value=b.dataset.contactFilter||'';$('contact').dispatchEvent(new Event('change'));syncQuickFilters()}));
$('contact').addEventListener('change',syncQuickFilters);$('reset').addEventListener('click',syncQuickFilters);syncQuickFilters();
$('analytics-export').onclick=()=>download();$('analytics-xlsx').onclick=()=>location.href='/api/export-xlsx';$('analytics-json').onclick=()=>location.href='/api/export-json';
$('settings-dark').onclick=()=>{if(document.documentElement.dataset.theme==='light')$('theme').click();syncSettings()};
$('settings-light').onclick=()=>{if(document.documentElement.dataset.theme!=='light')$('theme').click();syncSettings()};
$('settings-en').onclick=()=>{if(UI_LANGUAGE!=='en')$('language').click()};
$('settings-hr').onclick=()=>{if(UI_LANGUAGE!=='hr')$('language').click()};
$('theme').addEventListener('click',syncSettings);syncSettings();

function setProfileTab(tab){
  const dialog=$('detail');dialog.dataset.profileTab=tab;
  dialog.querySelectorAll('[data-profile-tab]').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.profileTab===tab)));
  dialog.scrollTop=0;
}
$('detail').querySelectorAll('[data-profile-tab]').forEach(button=>button.addEventListener('click',()=>setProfileTab(button.dataset.profileTab||'details')));

$('registry-credentials-apply').onclick=async()=>{const secret=$('registry-client-secret');try{await post('/api/registry/credentials',{client_id:$('registry-client-id').value,client_secret:secret.value,persist:$('registry-credentials-persist').checked,permission:$('registry-credentials-persist').checked});$('registry-client-id').value='';$('registry-credentials-persist').checked=false;await refreshSettings();toast(translate('Pristupni podaci su primijenjeni.'));}catch(e){fail(e)}finally{secret.value=''}};
$('registry-credentials-forget').onclick=async()=>{try{const result=await post('/api/registry/forget',{});$('registry-credentials-persist').checked=false;$('reg-permission').checked=false;previousRegistryAuthorization=false;await refreshSettings();toast(translate(result.revocation_verified?'Spremljeni pristup je uklonjen.':'Pristup je isključen za ovu sesiju. Trajno uklanjanje nije potvrđeno.'));}catch(e){fail(e)}};

$('file').onchange=()=>{const f=$('file').files[0];$('file-name').textContent=f?f.name:translate('Nije odabrana datoteka.');$('import-btn').disabled=!f||f.size>2*1024**3;if(f&&f.size>2*1024**3)toast(translate('Datoteka je prevelika (2 GiB).'));};$('import-btn').onclick=async()=>{const f=$('file').files[0];if(!f||f.size>2*1024**3)return;$('import-btn').disabled=true;$('file').disabled=true;try{const r=await api(f.name.toLowerCase().endsWith('.json')?'/api/import-json':'/api/import',{method:'POST',headers:{'X-Local-Token':token},body:f});toast(translate('Učitano ')+n(r.read)+translate(' · novih ')+n(r.added));await cities();await providers();$('file').value='';$('file-name').textContent=translate('Nije odabrana datoteka.');}catch(e){fail(e);$('import-btn').disabled=false}finally{$('file').disabled=false}};

let recoveryList=[];
let recoveryBusy=false;
function syncRecovery(){
    const backup=$('recovery-backup').value, item=recoveryList.find(x=>x.id===backup);
    $('recovery-size').textContent=item?translate('Veličina kopije')+': '+n(item.bytes)+' B':'';
    $('recovery-download').disabled=recoveryBusy||!backup;
    $('backup-encrypt').disabled=recoveryBusy||!backup;
    $('recovery-restore').disabled=recoveryBusy||!backup;
    $('recovery-inspect').disabled=recoveryBusy||!$('recovery-space').value;
    $('recovery-create').disabled=recoveryBusy;
    $('recovery-refresh').disabled=recoveryBusy;
    $('workspace-activate').disabled=recoveryBusy||!$('recovery-space').value;
    $('workspace-primary').disabled=recoveryBusy;
    $('encrypted-restore').disabled=recoveryBusy;
    $('integrity-check').disabled=recoveryBusy;
    syncProtected();
}
async function refreshRecovery(){
    const r=await api('/api/recovery');
    recoveryList=r.backups||[];
    const label=id=>id==='primary'?translate('Originalna baza'):id;
    $('workspace-active').textContent=translate('Aktivni radni prostor')+': '+label(r.active||'primary');
    $('workspace-selected').textContent=translate('Odabir za sljedeće pokretanje')+': '+label(r.selected||'primary');
    for(const [id,items,caption] of [['recovery-backup',recoveryList,'Odaberi kopiju'],['recovery-space',r.recovered||[],'Odaberi prostor']]){
        const select=$(id),prev=select.value;
        select.replaceChildren(new Option(translate(caption),''));
        for(const item of items)select.add(new Option(item.id,item.id));
        if(items.some(x=>x.id===prev))select.value=prev;
    }
    syncRecovery();
    await refreshIntegrity();
    await refreshProtected();
}
async function recoveryAction(action){
    if(recoveryBusy)return;
    recoveryBusy=true;syncRecovery();
    try{await action()}catch(e){fail(e)}finally{recoveryBusy=false;syncRecovery()}
}
$('recovery-backup').onchange=syncRecovery;
$('recovery-space').onchange=()=>{$('recovery-preview').replaceChildren();syncRecovery()};
$('recovery-refresh').onclick=()=>recoveryAction(refreshRecovery);
$('recovery-create').onclick=()=>recoveryAction(async()=>{
    const r=await post('/api/recovery/create',{});
    await refreshRecovery();$('recovery-backup').value=r.id;
    $('recovery-status').textContent=translate('Kopija je izrađena.');
});
$('recovery-download').onclick=()=>{location.href='/api/recovery/download?'+new URLSearchParams({id:$('recovery-backup').value})};
$('recovery-restore').onclick=()=>{
    const id=$('recovery-backup').value;
    if(!id||!confirm(translate('Vratiti kopiju u zaseban radni prostor? Aktivna baza neće se mijenjati.')))return;
    void recoveryAction(async()=>{
        const r=await post('/api/recovery/restore',{id,confirmed:true});
        await refreshRecovery();$('recovery-space').value=r.id;
        $('recovery-status').textContent=translate('Oporavljeni prostor je izrađen.');
        $('recovery-preview').replaceChildren();
    });
};
$('recovery-inspect').onclick=()=>recoveryAction(async()=>{
    const id=$('recovery-space').value;
    const r=await api('/api/recovery/inspect?'+new URLSearchParams({id}));
    if($('recovery-space').value!==id)return;
    const preview=$('recovery-preview');preview.replaceChildren(make('strong',translate('Pregled samo za čitanje')+' · '+n(r.total)));
    for(const row of r.rows)preview.append(make('p',row.title+' · '+row.city,'muted'));
});

function selectWorkspace(id){
    if(!id||!confirm(translate('Promijeniti radni prostor pri sljedećem pokretanju? Sve baze ostaju sačuvane.')))return;
    void recoveryAction(async()=>{await post('/api/recovery/select',{id,confirmed:true});await refreshRecovery();$('recovery-status').textContent=translate('Odabir je spremljen. Zatvorite i ponovno pokrenite aplikaciju.');});
}
$('workspace-activate').onclick=()=>selectWorkspace($('recovery-space').value);
$('workspace-primary').onclick=()=>selectWorkspace('primary');

$('backup-encrypt').onclick=()=>recoveryAction(async()=>{
    const password=$('backup-password').value, id=$('recovery-backup').value;
    if(password.length<16||password!==$('backup-confirm').value)throw Error(translate('Lozinke se moraju podudarati i imati najmanje 16 znakova.'));
    $('backup-password').value='';$('backup-confirm').value='';
    const r=await post('/api/recovery/encrypt',{id,password});
    const a=document.createElement('a');a.href='/api/recovery/encrypted-download?'+new URLSearchParams({ticket:r.ticket});a.download=id.replace(/\.sqlite3$/,'')+'.cvbackup';document.body.append(a);a.click();a.remove();
    $('recovery-status').textContent=translate('Šifrirana kopija pripremljena je za preuzimanje.');
});

let integrityTimer;
async function refreshIntegrity(){
    clearTimeout(integrityTimer);
    const r=await api('/api/recovery/integrity');
    const target=$('integrity-results');target.replaceChildren();
    const label=status=>translate(({ok:'Provjereno',rebuilt:'Obnovljeno',failed:'Neispravno',unavailable:'Nedostupno'})[status]||'Nedostupno');
    target.append(make('p',translate('Indeks pretraživanja')+': '+label(r.search)));
    if(r.running){target.append(make('p',translate('Provjera u tijeku')));integrityTimer=setTimeout(()=>{if(current==='settings')refreshIntegrity().catch(fail)},1500);}
    for(const item of r.workspaces)target.append(make('p',(item.id==='primary'?translate('Originalna baza'):item.id)+': '+label(item.status)));
}
$('integrity-check').onclick=()=>recoveryAction(async()=>{await post('/api/recovery/integrity',{});await refreshIntegrity()});
$('encrypted-restore').onclick=()=>recoveryAction(async()=>{
    const file=$('encrypted-file').files?.[0],password=$('encrypted-password').value;
    if(!file||password.length<16)throw Error(translate('Odaberite šifriranu kopiju i unesite lozinku.'));
    if(!confirm(translate('Vratiti kopiju u zaseban radni prostor? Aktivna baza neće se mijenjati.')))return;
    $('encrypted-password').value='';
    const r=await api('/api/recovery/encrypted-restore',{method:'POST',headers:{'X-Local-Token':token,'X-Backup-Passphrase':encodeURIComponent(password),'Content-Type':'application/octet-stream'},body:file});
    $('encrypted-file').value='';await refreshRecovery();$('recovery-space').value=r.id;
    $('recovery-status').textContent=translate('Oporavljeni prostor je izrađen.');
});

let protectedState={configured:false,unlocked:false,status:'locked',archives:[],orphans:[]};
function syncProtected(){
    const unlocked=protectedState.unlocked;
    const selected=protectedState.archives.find(x=>x.archive===$('protected-archive').value);
    $('protected-confirm-label').hidden=protectedState.configured;
    $('protected-unlock').disabled=recoveryBusy||unlocked;
    $('protected-lock').disabled=recoveryBusy||!unlocked;
    $('protected-create').disabled=recoveryBusy||!unlocked;
    $('protected-verify').disabled=recoveryBusy||!unlocked;
    $('protected-download').disabled=recoveryBusy||!unlocked||selected?.status!=='ok';
    $('protected-restore').disabled=$('protected-download').disabled;
    $('protected-manifest').disabled=$('protected-download').disabled;
    $('protected-restore-test').disabled=$('protected-download').disabled;
    $('vault-enroll').disabled=recoveryBusy||!unlocked||protectedState.vault==='enabled';
    $('replica-configure').disabled=recoveryBusy||!unlocked||protectedState.vault!=='enabled';
    $('replica-copy').disabled=$('replica-configure').disabled||!protectedState.replica_directory;
}
async function refreshProtected(){
    protectedState=await api('/api/recovery/protected');
    const currentId=$('protected-archive').value;
    $('protected-archive').replaceChildren(new Option(translate('Odaberi kopiju'),''));
    for(const item of protectedState.archives){
        const status=translate(item.status==='ok'?'Provjereno':item.status==='failed'?'Neispravno':'Nedostupno');
        $('protected-archive').add(new Option(new Date(item.created*1000).toLocaleString()+' · '+n(item.bytes)+' B · '+status,item.archive));
    }
    if(protectedState.archives.some(x=>x.archive===currentId))$('protected-archive').value=currentId;
    $('protected-status').textContent=translate(!protectedState.configured?'Katalog nije postavljen.':!protectedState.unlocked?'Katalog je zaključan.':protectedState.status==='verified'?'Katalog je provjeren.':'Katalog zahtijeva provjeru.');
    $('protected-orphans').textContent=protectedState.orphans.length?translate('Nepotvrđeni arhivi (sačuvani)')+': '+protectedState.orphans.join(', '):'';
    $('vault-status').textContent=translate('Sigurna pohrana ključa')+': '+translate(protectedState.vault==='enabled'?'Omogućeno':protectedState.vault==='attention'?'Zahtijeva provjeru':'Nije postavljeno')+' · '+(protectedState.vault_backend||'—');
    $('replica-directory').value=protectedState.replica_directory||'';
    $('replica-status').textContent=translate('Neovisna kopija')+': '+translate(protectedState.replica==='verified'?'Provjereno':protectedState.replica==='attention'?'Zahtijeva provjeru':protectedState.replica==='pending'?'Čeka kopiranje':'Nije postavljeno');
    syncProtected();
}
$('protected-archive').onchange=syncProtected;
$('protected-unlock').onclick=()=>recoveryAction(async()=>{
    const password=$('protected-password').value,initialize=!protectedState.configured;
    if(password.length<16||(initialize&&password!==$('protected-confirm').value))throw Error(translate('Lozinke se moraju podudarati i imati najmanje 16 znakova.'));
    if(initialize&&!confirm(translate('Izraditi novi zaštićeni katalog?')))return;
    $('protected-password').value='';$('protected-confirm').value='';
    await post('/api/recovery/protected-unlock',{password,initialize});
    await refreshProtected();
});
$('protected-lock').onclick=()=>recoveryAction(async()=>{await post('/api/recovery/protected-lock',{});await refreshProtected()});
$('protected-create').onclick=()=>recoveryAction(async()=>{
    const r=await post('/api/recovery/protected-create',{});
    await refreshProtected();$('protected-archive').value=r.id;
    $('recovery-status').textContent=translate('Šifrirana kopija je izrađena.');
});
$('protected-verify').onclick=()=>recoveryAction(async()=>{await post('/api/recovery/protected-verify',{});await refreshProtected()});
$('protected-download').onclick=()=>{const a=document.createElement('a');a.href='/api/recovery/protected-download?'+new URLSearchParams({id:$('protected-archive').value});a.download=$('protected-archive').value;document.body.append(a);a.click();a.remove()};
$('protected-restore').onclick=()=>recoveryAction(async()=>{
    if(!confirm(translate('Vratiti kopiju u zaseban radni prostor? Aktivna baza neće se mijenjati.')))return;
    const r=await post('/api/recovery/protected-restore',{id:$('protected-archive').value,confirmed:true});
    await refreshRecovery();$('recovery-space').value=r.id;
    $('recovery-status').textContent=translate('Oporavljeni prostor je izrađen.');
});

$('vault-enroll').onclick=()=>recoveryAction(async()=>{
    if(!confirm(translate('Pohraniti pristupnu frazu u sigurnu pohranu operacijskog sustava?')))return;
    await post('/api/recovery/protected-enroll',{confirmed:true});await refreshProtected();
});
$('replica-configure').onclick=()=>recoveryAction(async()=>{
    const directory=$('replica-directory').value.trim();
    if(!directory||!confirm(translate('Spremiti ovo odredište za automatsku replikaciju?')))return;
    await post('/api/recovery/protected-replica',{directory,confirmed:true});await refreshProtected();
});
$('replica-copy').onclick=()=>recoveryAction(async()=>{await post('/api/recovery/protected-replicate',{});await refreshProtected()});
$('protected-restore-test').onclick=()=>recoveryAction(async()=>{
    const r=await post('/api/recovery/protected-restore-test',{id:$('protected-archive').value});
    $('recovery-status').textContent=translate('Test oporavka uspješan')+' · '+translate('Zapisa')+': '+n(r.records);
});

$('protected-manifest').onclick=()=>{const a=document.createElement('a'),id=$('protected-archive').value;a.href='/api/recovery/protected-manifest?'+new URLSearchParams({id});a.download=id+'.manifest.json';document.body.append(a);a.click();a.remove()};

let nationalPage=1,nationalSequence=0;
async function nationalSearch(nextPage){
    const seq=++nationalSequence, country=$('national-country').value;
    $('national-status').textContent=translate('Učitavanje…');
    $('national-rows').replaceChildren();$('national-prev').disabled=true;$('national-next').disabled=true;
    $('national-search').disabled=true;
    try{
        const status=await api('/api/national/status');
        if(seq!==nationalSequence)return;
        if(!status[country]?.available){$('national-status').textContent=translate('Nacionalna baza nije ugrađena u ovo izdanje.');$('national-page').textContent='';return;}
        const result=await api('/api/national/gb/search?'+new URLSearchParams({q:$('national-query').value,page:String(nextPage)}));
        if(seq!==nationalSequence)return;
        nationalPage=result.page;
        $('national-status').textContent=n(result.total_snapshot)+' · '+result.snapshot;
        $('national-page').textContent=translate('Stranica ')+nationalPage;
        for(const record of result.rows){
            const row=make('tr');for(const value of [record.name,record.registration_number,record.city,record.status])row.append(make('td',value||'—'));
            const action=make('td'),button=make('button',translate('Detalji →'),'textbtn');
            button.onclick=()=>nationalDetail(record.registration_number).catch(fail);action.append(button);row.append(action);$('national-rows').append(row);
        }
        if(!result.rows.length){const row=make('tr'),td=make('td',translate('Nema rezultata za odabrane kriterije.'));td.colSpan=5;row.append(td);$('national-rows').append(row);}
        $('national-prev').disabled=nationalPage<=1;$('national-next').disabled=!result.next;
    }finally{if(seq===nationalSequence)$('national-search').disabled=false;}
}
async function nationalDetail(number){
    const data=await api('/api/national/gb/detail?'+new URLSearchParams({number}));
    $('national-title').textContent=data.CompanyName;
    const body=$('national-detail-body');body.replaceChildren();
    for(const [key,value] of Object.entries(data)){if(!value)continue;const line=make('div',undefined,'detail-field');line.append(make('small',key),make('p',value));body.append(line);}
    $('national-detail').showModal();
}
$('national-country').onchange=()=>nationalSearch(1).catch(fail);
$('national-search').onclick=()=>nationalSearch(1).catch(fail);
$('national-query').onkeydown=event=>{if(event.key==='Enter')nationalSearch(1).catch(fail);};
$('national-prev').onclick=()=>nationalSearch(nationalPage-1).catch(fail);
$('national-next').onclick=()=>nationalSearch(nationalPage+1).catch(fail);
$('national-close').onclick=()=>$('national-detail').close();


function addRegistryProfile(id,body){
    const panel=make('div',undefined,'detail-field profile-registry');
    panel.append(make('h3',translate('Dodatni poslovni podaci')));
    const status=make('p',translate('Učitavanje…'),'muted'),select=make('select'),records=make('div'),next=make('button',translate('Sljedeća →'),'btn secondary'),prev=make('button',translate('← Prethodna'),'btn secondary');
    select.setAttribute('aria-label',translate('Snimka')); next.disabled=true;prev.disabled=true;
    panel.append(status,select,records,prev,next);body.append(panel);
    let offset=0,seq=0;
    async function load(){
        const request=++seq;next.disabled=true;prev.disabled=true;status.textContent=translate('Učitavanje…');
        try{
            const data=await api('/api/company-registry/'+id+'?'+new URLSearchParams({snapshot:select.value,offset:String(offset)}));
            if(request!==seq)return;
            if(!select.options.length){for(const s of data.snapshots)select.add(new Option(s.snapshot+(s.complete?'':' · '+translate('Nepotpuna snimka')),s.snapshot));select.value=data.snapshot;}
            records.replaceChildren();
            for(const row of data.rows){const section=make('details');section.append(make('summary',row.category+' · '+row.ordinal));for(const [k,v] of Object.entries(row.data)){const field=make('div',undefined,'detail-field');field.append(make('small',k),make('p',typeof v==='object'?JSON.stringify(v):String(v??'—')));section.append(field)}records.append(section)}
            status.textContent=data.rows.length?data.snapshot+' · '+(offset+1)+'–'+(offset+data.rows.length):translate('Nema povezanih registarskih zapisa.');
            prev.disabled=offset===0;next.disabled=!data.next;
        }catch(e){if(request===seq)status.textContent=translate('Registarski podaci nisu dostupni.');}
    }
    select.onchange=()=>{offset=0;void load()};next.onclick=()=>{offset+=25;void load()};prev.onclick=()=>{offset=Math.max(0,offset-25);void load()};void load();
}
