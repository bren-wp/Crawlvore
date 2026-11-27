"""Conservative duplicate review and transactional merge of explicitly approved pairs."""
import hashlib
import json
import re
from collections import defaultdict
from company_fields import COLS, norm

FIELDS=COLS+["oib","email","industry"]
MAX_LEGACY=100000
MAX_PAIRS=100

def key(row):
    # Do not discard legal suffixes or street numbers.
    return tuple(" ".join(re.findall(r"\w+",norm(row[field]))) for field in ("title","city","address"))

def compatible(a,b):
    if any(a[f] and b[f] and a[f]!=b[f] for f in ("oib","mbs")):
        return False
    return (a["entity_kind"] in ("","unknown") or b["entity_kind"] in ("","unknown") or a["entity_kind"]==b["entity_kind"])

def fingerprint(legacy,official):
    return hashlib.sha256(json.dumps([dict(legacy),dict(official)],sort_keys=True,ensure_ascii=False).encode()).hexdigest()

def candidates(db):
    legacy=defaultdict(list)
    count=0
    for row in db.execute("""SELECT c.id,c.title,c.city,c.address,c.oib,c.mbs,c.entity_kind FROM companies c WHERE EXISTS
         (SELECT 1 FROM origins o WHERE o.company_id=c.id AND o.provider IN ('csv','tvrtke'))
         AND NOT EXISTS (SELECT 1 FROM origins o WHERE o.company_id=c.id AND o.provider='registry')"""):
        count+=1
        if count>MAX_LEGACY:raise ValueError("Prevelik broj starih zapisa za sigurni pregled.")
        identity=key(row)
        if all(identity):legacy[identity].append(row)
    official=defaultdict(list)
    for row in db.execute("""SELECT c.id,c.title,c.city,c.address,c.oib,c.mbs,c.entity_kind FROM companies c WHERE EXISTS
        (SELECT 1 FROM origins o WHERE o.company_id=c.id AND o.provider='registry')"""):
        identity=key(row)
        if identity in legacy and len(official[identity])<2:
            official[identity].append(row)
    for identity,rows in official.items():
        if len(legacy[identity])!=1 or len(rows)!=1:continue
        old,new=legacy[identity][0],rows[0]
        if compatible(old,new):
            yield tuple(db.execute("SELECT * FROM companies WHERE id=?",(r["id"],)).fetchone() for r in (old,new))

def archived_target(db, identity, source, values, entity_kind):
    if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='duplicate_merge_archive'").fetchone():return None
    archived=db.execute("SELECT canonical_id,payload FROM duplicate_merge_archive WHERE legacy_identity=?",(identity,)).fetchone()
    if archived is None and source:
        archived=db.execute("SELECT canonical_id,payload FROM duplicate_merge_archive WHERE legacy_source=?",(source,)).fetchone()
    if archived is None:return None
    previous=json.loads(archived["payload"])["legacy"]
    target=db.execute("SELECT * FROM companies WHERE id=?",(archived["canonical_id"],)).fetchone()
    incoming=dict(values,entity_kind=entity_kind)
    if target is None or key(previous)!=key(incoming) or not compatible(incoming,target):
        raise ValueError("Ranije spojeni zapis ima promijenjene podatke; potreban je pregled.")
    # Keep official ID and official title even when an old CSV is reimported.
    return target

def preview(store):
    with store.db() as db:
        db.execute("BEGIN")
        result=[]
        for old,new in candidates(db):
            def view(r):
                return {k:r[k] for k in ("id","title","city","address","oib","mbs","email","phone","website")}
            result.append({"legacy":view(old),"canonical":view(new),"fingerprint":fingerprint(old,new)})
            if len(result)>1000:raise ValueError("Previše kandidata; potreban je pojedinačni stručni pregled.")
        return {"pairs":result,"count":len(result)}

def merge(store, approved, backup):
    """Call only after a verified backup and explicit user approval."""
    if not isinstance(approved,list) or not 1<=len(approved)<=MAX_PAIRS or not backup:
        raise ValueError("Potrebna je potvrda odabranih parova i sigurnosna kopija.")
    requests={}
    for pair in approved:
        if not isinstance(pair,dict) or set(pair)!={"legacy","canonical","fingerprint"}:
            raise ValueError("Neispravan par.")
        old,new=pair["legacy"],pair["canonical"]
        if type(old) is not int or type(new) is not int or old==new or old in requests or not isinstance(pair["fingerprint"],str):
            raise ValueError("Neispravan identitet para.")
        requests[old]=(new,pair["fingerprint"])
    with store.db() as db:
        db.execute("BEGIN IMMEDIATE")
        matches={old["id"]:(old,new) for old,new in candidates(db) if old["id"] in requests}
        if set(matches)!=set(requests):raise ValueError("Kandidati su promijenjeni. Osvježite pregled.")
        for old_id,(old,new) in matches.items():
            if requests[old_id]!=(new["id"],fingerprint(old,new)):
                raise ValueError("Zapis je promijenjen. Osvježite pregled.")
        db.execute("""CREATE TABLE IF NOT EXISTS duplicate_merge_archive (
             legacy_id INTEGER NOT NULL, canonical_id INTEGER NOT NULL,
             legacy_identity TEXT NOT NULL PRIMARY KEY, legacy_source TEXT, payload TEXT NOT NULL,
             backup TEXT NOT NULL, merged_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
        db.execute("CREATE UNIQUE INDEX IF NOT EXISTS duplicate_source ON duplicate_merge_archive(legacy_source) WHERE legacy_source IS NOT NULL")
        refs={r[0] for r in db.execute("SELECT m.name FROM sqlite_master m, pragma_table_info(m.name) p WHERE m.type='table' AND p.name='company_id'")}
        if refs-{"origins","alternate_values","company_history","mail_log"}:
            raise ValueError("Nepoznata povezana tablica; spajanje je zaustavljeno.")
        mail=bool(db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='mail_log'").fetchone())
        for old_id,(old,new) in matches.items():
            target=new["id"]
            if mail and db.execute("SELECT 1 FROM mail_log WHERE company_id=? AND state='pending'",(old_id,)).fetchone():
                raise ValueError("Slanje poruke još nije završeno.")
            origins=[dict(r) for r in db.execute("SELECT * FROM origins WHERE company_id=?",(old_id,))]
            alternatives=[dict(r) for r in db.execute("SELECT * FROM alternate_values WHERE company_id=?",(old_id,))]
            history=[dict(r) for r in db.execute("SELECT * FROM company_history WHERE company_id=?",(old_id,))]
            mail_ids=[r[0] for r in db.execute("SELECT id FROM mail_log WHERE company_id=?",(old_id,))] if mail else []
            archive={"legacy":dict(old),"canonical_before":dict(new),"origins":origins,"alternatives":alternatives,"history":history,"mail_ids":mail_ids}
            db.execute("INSERT INTO duplicate_merge_archive(legacy_id,canonical_id,legacy_identity,legacy_source,payload,backup) VALUES (?,?,?,?,?,?)",
                       (old_id,target,old["identity"],old["source"],json.dumps(archive,ensure_ascii=False),backup))
            for r in origins:
                db.execute("INSERT OR IGNORE INTO origins(company_id,provider,url,updated) VALUES (?,?,?,?)",(target,r["provider"],r["url"],r["updated"]))
            for r in alternatives:
                db.execute("INSERT OR IGNORE INTO alternate_values(company_id,field,value,provider,observed_at) VALUES (?,?,?,?,?)",
                           (target,r["field"],r["value"],r["provider"],r["observed_at"]))
            provider=origins[0]["provider"] if origins else "csv"
            for field in FIELDS:
                if old[field] and new[field] and old[field]!=new[field]:
                    db.execute("INSERT OR IGNORE INTO alternate_values(company_id,field,value,provider) VALUES (?,?,?,?)",
                               (target,field,old[field],provider))
            # Official identity and existing values win. Only fill missing non-identity fields.
            values={field:new[field] or (old[field] if field not in ("title","oib","mbs","city","address","country") else "") for field in FIELDS}
            changes={field:{"before":new[field],"after":value} for field,value in values.items() if new[field]!=value}
            db.execute("UPDATE company_history SET company_id=? WHERE company_id=?",(target,old_id))
            if mail:db.execute("UPDATE mail_log SET company_id=? WHERE company_id=?",(target,old_id))
            db.execute("DELETE FROM origins WHERE company_id=?",(old_id,))
            db.execute("DELETE FROM alternate_values WHERE company_id=?",(old_id,))
            db.execute("DELETE FROM companies WHERE id=?",(old_id,))
            db.execute("UPDATE companies SET title=?,logo=?,website=?,social=?,address=?,postal=?,city=?,country=?,phone=?,fax=?,person=?,year=?,employees=?,account=?,mbs=?,rating=?,description=?,products=?,oib=?,email=?,industry=?,search_text=? WHERE id=?",
                       (*values.values(),norm(" ".join(values.values())),target))
            db.execute("INSERT INTO company_history(company_id,provider,changes) VALUES (?,?,?)",(target,"csv",json.dumps(changes,ensure_ascii=False)))
        if db.execute("PRAGMA foreign_key_check").fetchone():raise ValueError("Neispravne veze nakon spajanja.")
        return {"merged":len(matches),"backup":backup}
