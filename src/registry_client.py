"""Bounded HTTP transport and OAuth2 for the official Croatian registry."""
import json
import time
from urllib.parse import urlsplit
import requests
from network import public_session
from core import UA

BASE='https://sudreg-data.gov.hr/api/javni'
TOKEN_URL='https://sudreg-data.gov.hr/api/oauth/token'
SPEC_URL=BASE+'/dokumentacija/open_api'

class TransientRegistryError(ValueError):
    """Retryable network or server failure; never used for access denials."""

class Client:
    def __init__(self,bot,creds,delay=3):
        self.bot=bot; self.creds=creds; self.delay=delay; self.session=public_session(); self.session.trust_env=False; self.token=''; self.expiry=0
        self.session.headers.update({'User-Agent':UA,'Accept':'application/json','Content-Type':'application/json'})
    def close(self): self.session.close()
    def request(self,method,url,**kw):
        if urlsplit(url).netloc!='sudreg-data.gov.hr' or not url.startswith('https://'): raise ValueError('Nedopušten API host.')
        for attempt in range(3):
            self.bot.wait(self.delay-(time.monotonic()-self.bot.last_request)); self.bot.last_request=time.monotonic()
            try:
                with self.session.request(method,url,timeout=(10,60),allow_redirects=False,stream=True,**kw) as r:
                    if r.status_code in (429,403): raise PermissionError(f'Crawlvora: HTTP {r.status_code}. Prikupljanje zaustavljeno.')
                    if r.status_code>=500:
                        if attempt<2: self.bot.wait(2**(attempt+1)); continue
                        raise TransientRegistryError('Privremena pogreška poslužitelja.')
                    chunks=[]; size=0
                    for chunk in r.iter_content(65536):
                        self.bot.wait(0); size+=len(chunk)
                        if size>10*1024*1024: raise ValueError('Odgovor veći od 10 MB; smanjite veličinu stranice.')
                        chunks.append(chunk)
                    try: body=json.loads(b''.join(chunks))
                    except (ValueError,UnicodeError): raise ValueError(f'Crawlvora: neispravan JSON (HTTP {r.status_code}).') from None
                    return r.status_code, r.headers, body
            except requests.RequestException:
                if attempt==2: raise TransientRegistryError('Mrežna pogreška poslovnih podataka.') from None
                self.bot.wait(2**(attempt+1))
    def auth(self):
        code,_,body=self.request('POST',TOKEN_URL,auth=self.creds,data={'grant_type':'client_credentials'},headers={'Content-Type':'application/x-www-form-urlencoded'})
        if code!=200 or not isinstance(body,dict) or not isinstance(body.get('access_token'),str) or not body['access_token']: raise ValueError(f'OAuth2 autentikacija nije uspjela (HTTP {code}). Provjerite pristupne podatke.')
        self.token=body['access_token']; self.expiry=time.monotonic()+max(1,int(body.get('expires_in',300))-30)
    def get(self,name,params=None):
        for attempt in range(2):
            if time.monotonic()>=self.expiry: self.auth()
            code,h,b=self.request('GET',BASE+'/'+name,params=params or {},headers={'Authorization':'Bearer '+self.token})
            if code==401 and attempt==0: self.expiry=0; continue
            if code==200: return h,b
            if code==400 and isinstance(b,dict) and str(b.get('error_code'))=='505': return h,[]
            raise ValueError(f'Crawlvora: {name} · HTTP {code}.')
        raise ValueError('Autentikacija nije uspjela.')
    def spec(self):
        code,_,body=self.request('GET',SPEC_URL,headers={'Accept':'application/openapi+json, application/json'})
        if code!=200 or not isinstance(body,dict) or 'paths' not in body: raise ValueError('OpenAPI specifikacija nije dostupna.')
        return body
