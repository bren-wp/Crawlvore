"""Bounded HTTP transport and OAuth2 for the official Croatian registry."""
import json
import time
import re
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone
import requests
from network import public_session
from core import UA

BASE='https://sudreg-data.gov.hr/api/javni'
TOKEN_URL='https://sudreg-data.gov.hr/api/oauth/token'
SPEC_URL=BASE+'/dokumentacija/open_api'

class TransientRegistryError(ValueError):
    """Retryable network or server failure; never used for access denials."""

def retry_after(value, fallback):
    try:
        if value is None:return fallback
        if re.fullmatch(r"[0-9]{1,9}",value):return max(fallback,int(value))
        moment=parsedate_to_datetime(value)
        if moment.tzinfo is None:return fallback
        return max(fallback,(moment-datetime.now(timezone.utc)).total_seconds())
    except (ValueError,TypeError,OverflowError):
        return fallback

def safe_log_id(headers):
    value=headers.get("X-Log-Id","")
    return " (ID odgovora: "+value+")" if re.fullmatch(r"[A-Za-z0-9_.-]{1,80}",value) else ""

class Client:
    def __init__(self,bot,creds,delay=3):
        self.bot=bot; self.creds=creds; self.delay=delay; self.session=public_session(); self.session.trust_env=False; self.token=''; self.expiry=0
        self.session.headers.update({'User-Agent':UA,'Accept':'application/json','Content-Type':'application/json'})
    def close(self): self.session.close()
    def request(self,method,url,**kw):
        if url not in (TOKEN_URL,SPEC_URL) and not re.fullmatch(re.escape(BASE)+r'/[a-z][a-z0-9_]{0,80}',url): raise ValueError('Nedopušten API host.')
        for attempt in range(3):
            self.bot.wait(self.delay-(time.monotonic()-self.bot.last_request)); self.bot.last_request=time.monotonic()
            try:
                with self.session.request(method,url,timeout=(10,60),allow_redirects=False,stream=True,**kw) as r:
                    diagnostic=safe_log_id(r.headers)
                    if 300<=r.status_code<400:
                        raise PermissionError("Preusmjeravanje API zahtjeva nije dopušteno."+diagnostic)
                    if r.status_code==403:
                        raise PermissionError("Pristup poslovnim podacima nije dopušten (HTTP 403)."+diagnostic)
                    if r.status_code==429 or r.status_code in (502,503,504,500):
                        wait=retry_after(r.headers.get("Retry-After"),2**(attempt+1))
                        if attempt<2 and wait<=120:
                            self.bot.wait(wait);continue
                        if r.status_code==429:
                            # Never retry sooner than the provider requests, including scheduler retries.
                            raise PermissionError("Ograničenje broja zahtjeva (HTTP 429); nastavite poslije vremena koje je odredio pružatelj."+diagnostic)
                        if wait>120:
                            raise PermissionError("Poslužitelj traži dulju pauzu; nastavite kasnije."+diagnostic)
                        raise TransientRegistryError("Privremena pogreška poslužitelja."+diagnostic)
                    if r.status_code>=500:
                        raise ValueError(f"API pogreška (HTTP {r.status_code})."+diagnostic)
                    chunks=[]; size=0
                    for chunk in r.iter_content(65536):
                        self.bot.wait(0); size+=len(chunk)
                        if size>10*1024*1024: raise ValueError('Odgovor veći od 10 MB; smanjite veličinu stranice.')
                        chunks.append(chunk)
                    if r.status_code==401:return r.status_code,r.headers,{}
                    try: body=json.loads(b''.join(chunks))
                    except (ValueError,UnicodeError): raise ValueError(f'Tvrtke: neispravan JSON (HTTP {r.status_code}).') from None
                    return r.status_code, r.headers, body
            except requests.exceptions.SSLError:
                raise PermissionError('TLS provjera API poslužitelja nije uspjela.') from None
            except requests.RequestException:
                if attempt==2: raise TransientRegistryError('Mrežna pogreška poslovnih podataka.') from None
                self.bot.wait(2**(attempt+1))
    def auth(self):
        code,_,body=self.request('POST',TOKEN_URL,auth=self.creds,data={'grant_type':'client_credentials'},headers={'Content-Type':'application/x-www-form-urlencoded'})
        if code!=200 or not isinstance(body,dict) or not isinstance(body.get('access_token'),str) or not body['access_token']: raise ValueError(f'OAuth2 autentikacija nije uspjela (HTTP {code}). Provjerite pristupne podatke.')
        token=body['access_token']
        if len(token)>16384 or any(ord(ch)<33 or ord(ch)>126 for ch in token):
            raise ValueError("Neispravan OAuth2 token.")
        expires=body.get('expires_in',300)
        if type(expires) not in (str,int) or not re.fullmatch(r"[0-9]{1,9}",str(expires)) or int(expires)<=0:
            raise ValueError("Neispravno trajanje OAuth2 tokena.")
        self.token=token; self.expiry=time.monotonic()+max(1,min(3600,int(expires))-30)
    def get(self,name,params=None):
        if not re.fullmatch(r'[a-z][a-z0-9_]{0,80}',name):raise ValueError('Nedopuštena API metoda.')
        for attempt in range(2):
            if time.monotonic()>=self.expiry: self.auth()
            code,h,b=self.request('GET',BASE+'/'+name,params=params or {},headers={'Authorization':'Bearer '+self.token})
            if code==401 and attempt==0: self.expiry=0; continue
            if code==200: return h,b
            if code==400 and isinstance(b,dict) and str(b.get('error_code'))=='505': return h,[]
            raise ValueError(f'Tvrtke: {name} · HTTP {code}.')
        raise ValueError('Autentikacija nije uspjela.')
    def spec(self):
        code,_,body=self.request('GET',SPEC_URL,headers={'Accept':'application/openapi+json, application/json'})
        if code!=200 or not isinstance(body,dict) or 'paths' not in body: raise ValueError('OpenAPI specifikacija nije dostupna.')
        return body
