"""Canonical directory field contracts and normalization."""
import unicodedata

FIELDS = ['Title','Logo URL','Website URL','Social URL','Street Address','Postal Code','City','Country','Phone Number','Phone/Fax','Responsible Person','Year of Establishment','Number of Employees','Account Number','Mbs Number','Rating Value','Description','Product/Company Description']
COLS = ['title','logo','website','social','address','postal','city','country','phone','fax','person','year','employees','account','mbs','rating','description','products']
ENTITY_KINDS = ('company','entrepreneur','institution','nonprofit','unknown')

def norm(s):
    return ' '.join(unicodedata.normalize('NFC', str(s or '')).casefold().split())

def formula_safe(v):
    return "'"+v if v.lstrip().startswith(('=','+','-','@','\t','\r','\n')) or v.startswith(('\t','\r','\n')) else v

