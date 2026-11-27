let protectedState:{configured:boolean;unlocked:boolean;status:string;archives:{archive:string;bytes:number;created:number;status:string}[];orphans:string[];vault?:string;vault_backend?:string;replica?:string;replica_directory?:string}={configured:false,unlocked:false,status:'locked',archives:[],orphans:[]};
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
    protectedState=await api<typeof protectedState>('/api/recovery/protected');
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
    const r=await post<{id:string}>('/api/recovery/protected-create',{});
    await refreshProtected();$('protected-archive').value=r.id;
    $('recovery-status').textContent=translate('Šifrirana kopija je izrađena.');
});
$('protected-verify').onclick=()=>recoveryAction(async()=>{await post('/api/recovery/protected-verify',{});await refreshProtected()});
$('protected-download').onclick=()=>{const a=document.createElement('a');a.href='/api/recovery/protected-download?'+new URLSearchParams({id:$('protected-archive').value});a.download=$('protected-archive').value;document.body.append(a);a.click();a.remove()};
$('protected-restore').onclick=()=>recoveryAction(async()=>{
    if(!confirm(translate('Vratiti kopiju u zaseban radni prostor? Aktivna baza neće se mijenjati.')))return;
    const r=await post<{id:string}>('/api/recovery/protected-restore',{id:$('protected-archive').value,confirmed:true});
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
    const r=await post<{verified:boolean;records:number}>('/api/recovery/protected-restore-test',{id:$('protected-archive').value});
    $('recovery-status').textContent=translate('Test oporavka uspješan')+' · '+translate('Zapisa')+': '+n(r.records);
});

$('protected-manifest').onclick=()=>{const a=document.createElement('a'),id=$('protected-archive').value;a.href='/api/recovery/protected-manifest?'+new URLSearchParams({id});a.download=id+'.manifest.json';document.body.append(a);a.click();a.remove()};

