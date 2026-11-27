let nationalPage=1,nationalSequence=0;
type NationalDownloadState={status:string;phase?:string;bytes?:number;saved_bytes?:number;total?:number};
function showNationalDownload(state:NationalDownloadState){
    const paused=['paused','cancelled','failed'].includes(state.status),running=state.status==='running';
    $('national-download').disabled=running;
    $('national-download').textContent=translate(paused&&state.saved_bytes?'Nastavi preuzimanje':'Preuzmi britansku bazu');
    const message=running?translate('Preuzimanje i priprema baze…'):paused?(state.saved_bytes?translate('Prethodno preuzeti podaci su sačuvani.'):translate('Preuzimanje nije uspjelo. Pokušajte ponovno.')):translate('Nacionalna baza nije ugrađena u ovo izdanje.');
    const saved=state.saved_bytes||0,total=state.total||0;
    $('national-status').textContent=message+(saved&&total?' · '+translate('Spremljeno na disk')+': '+n(Math.floor(saved/1048576))+' / '+n(Math.ceil(total/1048576))+' MiB':'');
}
async function nationalSearch(nextPage:number){
    const seq=++nationalSequence, country=$('national-country').value;
    $('national-status').textContent=translate('Učitavanje…');
    $('national-rows').replaceChildren();$('national-prev').disabled=true;$('national-next').disabled=true;
    $('national-search').disabled=true;
    try{
        const status=await api<Record<string,{available:boolean}>>('/api/national/status');
        if(seq!==nationalSequence)return;
        $('national-download').hidden=Boolean(status[country]?.available);
        if(!status[country]?.available){
            const state=await api<NationalDownloadState>('/api/national/gb/download');
            if(seq!==nationalSequence)return;
            showNationalDownload(state);
            $('national-page').textContent='';return;
        }
        const result=await api<{page:number;total_snapshot:number;snapshot:string;rows:{name:string;registration_number:string;city:string;status:string}[];next:boolean}>('/api/national/gb/search?'+new URLSearchParams({q:$('national-query').value,page:String(nextPage)}));
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
async function nationalDetail(number:string){
    const data=await api<Record<string,string>>('/api/national/gb/detail?'+new URLSearchParams({number}));
    $('national-title').textContent=data.CompanyName;
    const body=$('national-detail-body');body.replaceChildren();
    for(const [key,value] of Object.entries(data)){if(!value)continue;const line=make('div',undefined,'detail-field');line.append(make('small',key),make('p',value));body.append(line);}
    $('national-detail').showModal();
}
$('national-country').onchange=()=>nationalSearch(1).catch(fail);
$('national-search').onclick=()=>nationalSearch(1).catch(fail);
$('national-download').onclick=async()=>{
    if(!confirm(translate('Preuzeti britansku bazu? Potrebna je internetska veza i najmanje 20 GiB slobodnog prostora.')))return;
    $('national-download').disabled=true;
    try{
        await post('/api/national/gb/download',{confirmed:true});
        $('national-status').textContent=translate('Preuzimanje i priprema baze…');
        const timer=setInterval(async()=>{
            try{
                const state=await api<NationalDownloadState>('/api/national/gb/download');
                if(state.status==='running'){showNationalDownload(state);return;}
                clearInterval(timer);$('national-download').disabled=false;
                if(state.status==='complete')await nationalSearch(1);
                else showNationalDownload(state);
            }catch(e){clearInterval(timer);$('national-download').disabled=false;fail(e)}
        },2000);
    }catch(e){$('national-download').disabled=false;fail(e)}
};
$('national-query').onkeydown=event=>{if(event.key==='Enter')nationalSearch(1).catch(fail);};
$('national-prev').onclick=()=>nationalSearch(nationalPage-1).catch(fail);
$('national-next').onclick=()=>nationalSearch(nationalPage+1).catch(fail);
$('national-close').onclick=()=>$('national-detail').close();


