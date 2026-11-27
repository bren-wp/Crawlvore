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
    $('settings-api').textContent=translate(r.configured?'Pristup omogućen':'Pristup nije omogućen');
    await refreshRecovery();
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

$('registry-credentials-apply').onclick=async()=>{const secret=$('registry-client-secret'),persist=$('registry-credentials-persist').checked;try{await post('/api/registry/credentials',{client_id:$('registry-client-id').value,client_secret:secret.value,persist,permission:persist});$('registry-client-id').value='';$('registry-credentials-persist').checked=true;await refreshSettings();toast(translate(persist?'Pristupni podaci sigurno su spremljeni.':'Pristupni podaci vrijede samo za ovu sesiju.'));}catch(e){fail(e)}finally{secret.value=''}};
$('registry-credentials-forget').onclick=async()=>{try{const result=await post<{revocation_verified:boolean}>('/api/registry/forget',{});$('registry-credentials-persist').checked=true;$('reg-permission').checked=false;previousRegistryAuthorization=false;await refreshSettings();toast(translate(result.revocation_verified?'Spremljeni pristup je uklonjen.':'Pristup je isključen za ovu sesiju. Trajno uklanjanje nije potvrđeno.'));}catch(e){fail(e)}};

$('file').onchange=()=>{const f=$('file').files?.[0];$('file-name').textContent=f?f.name:translate('Nije odabrana datoteka.');$('import-btn').disabled=!f||f.size>2*1024**3;if(f&&f.size>2*1024**3)toast(translate('Datoteka je prevelika (2 GiB).'));};$('import-btn').onclick=async()=>{const f=$('file').files?.[0];if(!f||f.size>2*1024**3)return;$('import-btn').disabled=true;$('file').disabled=true;try{const r=await api<{read:number;added:number}>(f.name.toLowerCase().endsWith('.json')?'/api/import-json':'/api/import',{method:'POST',headers:{'X-Local-Token':token},body:f});toast(translate('Učitano ')+n(r.read)+translate(' · novih ')+n(r.added));await cities();await providers();$('file').value='';$('file-name').textContent=translate('Nije odabrana datoteka.');}catch(e){fail(e);$('import-btn').disabled=false}finally{$('file').disabled=false}};

