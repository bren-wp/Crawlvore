let recoveryList:{id:string;bytes:number}[]=[];
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
    const r=await api<{backups:{id:string;bytes:number}[];recovered:{id:string}[];active:string;selected:string}>('/api/recovery');
    recoveryList=r.backups||[];
    const label=(id:string)=>id==='primary'?translate('Originalna baza'):id;
    $('workspace-active').textContent=translate('Aktivni radni prostor')+': '+label(r.active||'primary');
    $('workspace-selected').textContent=translate('Odabir za sljedeće pokretanje')+': '+label(r.selected||'primary');
    for(const [id,items,caption] of ([['recovery-backup',recoveryList,'Odaberi kopiju'],['recovery-space',r.recovered||[],'Odaberi prostor']] as const)){
        const select=$(id),prev=select.value;
        select.replaceChildren(new Option(translate(caption),''));
        for(const item of items)select.add(new Option(item.id,item.id));
        if(items.some(x=>x.id===prev))select.value=prev;
    }
    syncRecovery();
    await refreshIntegrity();
    await refreshProtected();
}
async function recoveryAction(action:()=>Promise<void>){
    if(recoveryBusy)return;
    recoveryBusy=true;syncRecovery();
    try{await action()}catch(e){fail(e)}finally{recoveryBusy=false;syncRecovery()}
}
$('recovery-backup').onchange=syncRecovery;
$('recovery-space').onchange=()=>{$('recovery-preview').replaceChildren();syncRecovery()};
$('recovery-refresh').onclick=()=>recoveryAction(refreshRecovery);
$('recovery-create').onclick=()=>recoveryAction(async()=>{
    const r=await post<{id:string}>('/api/recovery/create',{});
    await refreshRecovery();$('recovery-backup').value=r.id;
    $('recovery-status').textContent=translate('Kopija je izrađena.');
});
$('recovery-download').onclick=()=>{location.href='/api/recovery/download?'+new URLSearchParams({id:$('recovery-backup').value})};
$('recovery-restore').onclick=()=>{
    const id=$('recovery-backup').value;
    if(!id||!confirm(translate('Vratiti kopiju u zaseban radni prostor? Aktivna baza neće se mijenjati.')))return;
    void recoveryAction(async()=>{
        const r=await post<{id:string}>('/api/recovery/restore',{id,confirmed:true});
        await refreshRecovery();$('recovery-space').value=r.id;
        $('recovery-status').textContent=translate('Oporavljeni prostor je izrađen.');
        $('recovery-preview').replaceChildren();
    });
};
$('recovery-inspect').onclick=()=>recoveryAction(async()=>{
    const id=$('recovery-space').value;
    const r=await api<{id:string;total:number;rows:{title:string;city:string}[]}>('/api/recovery/inspect?'+new URLSearchParams({id}));
    if($('recovery-space').value!==id)return;
    const preview=$('recovery-preview');preview.replaceChildren(make('strong',translate('Pregled samo za čitanje')+' · '+n(r.total)));
    for(const row of r.rows)preview.append(make('p',row.title+' · '+row.city,'muted'));
});

function selectWorkspace(id:string){
    if(!id||!confirm(translate('Promijeniti radni prostor pri sljedećem pokretanju? Sve baze ostaju sačuvane.')))return;
    void recoveryAction(async()=>{await post('/api/recovery/select',{id,confirmed:true});await refreshRecovery();$('recovery-status').textContent=translate('Odabir je spremljen. Zatvorite i ponovno pokrenite aplikaciju.');});
}
$('workspace-activate').onclick=()=>selectWorkspace($('recovery-space').value);
$('workspace-primary').onclick=()=>selectWorkspace('primary');

$('backup-encrypt').onclick=()=>recoveryAction(async()=>{
    const password=$('backup-password').value, id=$('recovery-backup').value;
    if(password.length<16||password!==$('backup-confirm').value)throw Error(translate('Lozinke se moraju podudarati i imati najmanje 16 znakova.'));
    $('backup-password').value='';$('backup-confirm').value='';
    const r=await post<{ticket:string}>('/api/recovery/encrypt',{id,password});
    const a=document.createElement('a');a.href='/api/recovery/encrypted-download?'+new URLSearchParams({ticket:r.ticket});a.download=id.replace(/\.sqlite3$/,'')+'.cvbackup';document.body.append(a);a.click();a.remove();
    $('recovery-status').textContent=translate('Šifrirana kopija pripremljena je za preuzimanje.');
});

let integrityTimer:ReturnType<typeof setTimeout>;
async function refreshIntegrity(){
    clearTimeout(integrityTimer);
    const r=await api<{running:boolean;search:string;workspaces:{id:string;status:string}[]}>('/api/recovery/integrity');
    const target=$('integrity-results');target.replaceChildren();
    const label=(status:string)=>translate(({ok:'Provjereno',rebuilt:'Obnovljeno',failed:'Neispravno',unavailable:'Nedostupno'} as Record<string,string>)[status]||'Nedostupno');
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
    const r=await api<{id:string}>('/api/recovery/encrypted-restore',{method:'POST',headers:{'X-Local-Token':token,'X-Backup-Passphrase':encodeURIComponent(password),'Content-Type':'application/octet-stream'},body:file});
    $('encrypted-file').value='';await refreshRecovery();$('recovery-space').value=r.id;
    $('recovery-status').textContent=translate('Oporavljeni prostor je izrađen.');
});

