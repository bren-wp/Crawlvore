function addRegistryProfile(id: number|string,body:HTMLElement){
    const panel=make('div',undefined,'detail-field profile-registry');
    panel.append(make('h3',translate('Dodatni poslovni podaci')));
    const status=make('p',translate('Učitavanje…'),'muted'),select=make('select'),records=make('div'),next=make('button',translate('Sljedeća →'),'btn secondary'),prev=make('button',translate('← Prethodna'),'btn secondary');
    select.setAttribute('aria-label',translate('Snimka')); next.disabled=true;prev.disabled=true;
    panel.append(status,select,records,prev,next);body.append(panel);
    let offset=0,seq=0;
    async function load(){
        const request=++seq;next.disabled=true;prev.disabled=true;status.textContent=translate('Učitavanje…');
        try{
            const data=await api<{snapshot:string;snapshots:{snapshot:string;complete:number}[];rows:{category:string;ordinal:number;data:Record<string,unknown>}[];next:boolean}>('/api/company-registry/'+id+'?'+new URLSearchParams({snapshot:select.value,offset:String(offset)}));
            if(request!==seq)return;
            if(!select.options.length){for(const s of data.snapshots)select.add(new Option(s.snapshot+(s.complete?'':' · '+translate('Nepotpuna snimka')),s.snapshot));select.value=data.snapshot;}
            records.replaceChildren();
            for(const row of data.rows){const section=make('details');section.append(make('summary',row.category+' · '+row.ordinal));for(const [k,v] of Object.entries(row.data)){const field=make('div',undefined,'detail-field');field.append(make('small',k),make('p',typeof v==='object'?JSON.stringify(v):String(v??'—')));section.append(field)}records.append(section)}
            status.textContent=data.rows.length?data.snapshot+' · '+(offset+1)+'–'+(offset+data.rows.length):translate('Nema dodatnih poslovnih zapisa.');
            prev.disabled=offset===0;next.disabled=!data.next;
        }catch(e){if(request===seq)status.textContent=translate('Dodatni poslovni podaci nisu dostupni.');}
    }
    select.onchange=()=>{offset=0;void load()};next.onclick=()=>{offset+=25;void load()};prev.onclick=()=>{offset=Math.max(0,offset-25);void load()};void load();
}
