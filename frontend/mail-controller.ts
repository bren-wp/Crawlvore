'use strict';
interface MailSettings {configured:boolean;vault_available:boolean;host?:string;port?:number;username?:string;sender?:string}
interface MailEntry {subject:string;recipient:string;created:number;state:string}
let mailCompany=0,mailBusy=false,mailConfigured=false;
const mailStates:Record<string,string>={pending:'Ishod još nije potvrđen',accepted:'SMTP je prihvatio poruku',unknown:'Ishod nepoznat — provjerite prije ponovnog slanja',rejected:'Odbijeno'};
function mailControls(){ $('mail-send').disabled=mailBusy||!mailConfigured||!$('mail-confirm').checked||!$('mail-basis').value||!$('mail-subject').value.trim()||!$('mail-body').value.trim(); }
async function mailSettings(){
 const s=await api<MailSettings>('/api/mail/settings');
 mailConfigured=s.configured;
 $('mail-config-status').textContent=s.configured?'SMTP pristup spremljen.':s.vault_available?'SMTP nije konfiguriran.':'Sigurna pohrana nije dostupna.';
 $('mail-host').value=s.host||'';$('mail-port').value=String(s.port||587);$('mail-user').value=s.username||'';$('mail-sender').value=s.sender||'';mailControls();
}
async function mailHistory(){
 const company=mailCompany, entries=await api<MailEntry[]>('/api/mail/history?company_id='+company);
 if(company!==mailCompany)return;
 const target=$('mail-history');target.replaceChildren();
 if(!entries.length)target.append(make('p','Nema evidentiranih poruka.','muted'));
 for(const entry of entries){const item=make('div',undefined,'history-event');item.append(make('strong',entry.subject),make('p',entry.recipient),make('small',new Date(entry.created*1000).toLocaleString('hr-HR')+' · '+(mailStates[entry.state]||entry.state)));target.append(item);}
}
async function openMail(company:CompanyDetails){
 if(mailBusy)return;
 if(typeof company.email!=='string'||!company.email.trim())throw Error('Subjekt nema adresu e-pošte.');
 mailCompany=company.id;$('mail-company').textContent=company.title;$('mail-recipient').value=company.email.trim();
 $('mail-template').value='custom';$('mail-subject').value='';$('mail-body').value='';$('mail-basis').value='';$('mail-confirm').checked=false;$('mail-password').value='';$('mail-result').textContent='';mailConfigured=false;mailControls();
 $('mail-dialog').showModal();await Promise.all([mailSettings(),mailHistory()]);
}
$('mail-close').onclick=()=>{if(!mailBusy)$('mail-dialog').close();};
$('mail-dialog').addEventListener('cancel',e=>{if(mailBusy)e.preventDefault();});
$('mail-dialog').addEventListener('close',()=>{$('mail-password').value='';$('mail-subject').value='';$('mail-body').value='';$('mail-confirm').checked=false;});
$('mail-save').onclick=async()=>{if(mailBusy)return;try{
 if(!confirm('Spremiti pristupne podatke u sigurnu pohranu operacijskog sustava?'))return;
 mailBusy=true;mailControls();await post('/api/mail/configure',{host:$('mail-host').value.trim(),port:Number($('mail-port').value),username:$('mail-user').value,password:$('mail-password').value,sender:$('mail-sender').value.trim(),confirmed:true});await mailSettings();
 }catch(e){$('mail-result').textContent=e instanceof Error?e.message:'Postavke nisu spremljene.';}finally{$('mail-password').value='';mailBusy=false;mailControls();}};
$('mail-forget').onclick=async()=>{if(mailBusy||!confirm('Ukloniti SMTP pristup iz sigurne pohrane?'))return;try{mailBusy=true;mailControls();await post('/api/mail/forget',{});await mailSettings();}catch(e){$('mail-result').textContent=e instanceof Error?e.message:'Pristup nije uklonjen.';}finally{mailBusy=false;mailControls();}};
$('mail-template').onchange=async()=>{if(mailBusy)return;try{const key=$('mail-template').value;const templates=await api<Record<string,{subject:string;body:string}>>('/api/mail/templates');if($('mail-template').value===key){$('mail-subject').value=templates[key].subject;$('mail-body').value=templates[key].body;mailControls();}}catch(e){fail(e);}};
for(const id of ['mail-subject','mail-body','mail-basis','mail-confirm'])$(id).addEventListener('input',mailControls);
$('mail-block').onclick=async()=>{if(mailBusy||!confirm('Zabraniti buduće slanje na ovu adresu?'))return;try{mailBusy=true;mailControls();await post('/api/mail/block',{recipient:$('mail-recipient').value,confirmed:true});$('mail-result').textContent='Adresa je dodana na popis zabrane slanja.';$('mail-confirm').checked=false;}catch(e){fail(e);}finally{mailBusy=false;mailControls();}};
$('mail-send').onclick=async()=>{if(mailBusy||$('mail-send').disabled)return;
 const recipient=$('mail-recipient').value,subject=$('mail-subject').value,body=$('mail-body').value,basis=$('mail-basis').value;
 if(!confirm('Poslati jednu poruku na '+recipient+'?\n\nPredmet: '+subject))return;
 mailBusy=true;mailControls();$('mail-result').textContent='Slanje je u tijeku…';
 try{const r=await post<{state:string}>('/api/mail/send',{company_id:mailCompany,recipient,subject,body,basis,confirmed:true,request_id:crypto.randomUUID()});$('mail-result').textContent=mailStates[r.state]||'Ishod nije potvrđen.';await mailHistory();}
 catch(e){$('mail-result').textContent=(e instanceof Error?e.message:'Ishod nije potvrđen.')+' Provjerite evidenciju prije ponavljanja.';}
 finally{$('mail-confirm').checked=false;mailBusy=false;mailControls();}
};
