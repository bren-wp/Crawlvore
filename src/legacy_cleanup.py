"""Offline, verified removal of the original legacy CSV import, not user imports."""
import argparse
import csv
import hashlib
import io
import json
import sqlite3
from collections import defaultdict
from contextlib import closing
from pathlib import Path
from company_fields import COLS,FIELDS,norm
from data_safety import verified_backup,workspace_lock
from company_store import Store

LEGACY_SHA256="ea2a7bcd8df071b7f6525442866680dc2efe0eb25457bc6796d6a6f97cff6891"

def seed_rows(raw, expected=LEGACY_SHA256):
    if hashlib.sha256(raw).hexdigest()!=expected:
        raise ValueError("Datoteka nije potvrđeni početni uvoz.")
    result=defaultdict(list)
    reader=csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    if reader.fieldnames!=FIELDS:raise ValueError("Neočekivana struktura uvoza.")
    for row in reader:
        vals={k:str(row[f] or "").strip() for k,f in zip(COLS,FIELDS)}
        if vals["mbs"].isascii() and vals["mbs"].isdigit() and len(vals["mbs"])<=9:vals["mbs"]=vals["mbs"].zfill(9)
        result[norm(vals["title"])+"\x1f"+norm(vals["city"])].append(vals)
    return result

def review(db,seeds):
    db.row_factory=sqlite3.Row
    refs={r[0] for r in db.execute("SELECT m.name FROM sqlite_master m, pragma_table_info(m.name) p WHERE m.type='table' AND p.name='company_id'")}
    if refs-{"origins","alternate_values","company_history","mail_log"}:
        raise ValueError("Nepoznata povezana tablica.")
    result={"remove":[],"linked":0,"preserved":0}
    for r in db.execute("SELECT c.* FROM companies c WHERE EXISTS (SELECT 1 FROM origins o WHERE o.company_id=c.id AND o.provider='csv')"):
        ident=r["identity"]
        if ident not in seeds:continue
        providers={x[0] for x in db.execute("SELECT provider FROM origins WHERE company_id=?",(r["id"],))}
        if "registry" in providers:
            result["linked"]+=1
            continue
        if providers!={"csv"} or r["source"] is not None or any(r[k] for k in ("oib","email","industry")) or r["entity_kind"] not in ("","unknown"):
            result["preserved"]+=1;continue
        if not any(all(r[k]==v for k,v in vals.items()) for vals in seeds[ident]):
            result["preserved"]+=1;continue
        if any(db.execute("SELECT 1 FROM "+table+" WHERE company_id=?",(r["id"],)).fetchone() for table in sorted(refs-{"origins"})):  # nosec B608 -- refs checked against fixed allowlist above.
            result["preserved"]+=1;continue
        result["remove"].append(r["id"])
    return result

def counts(result):
    return {"remove":len(result["remove"]),"linked":result["linked"],"preserved":result["preserved"]}

def clean(database,seeds,apply=False):
    database=Path(database).resolve(strict=True)
    with closing(sqlite3.connect(database.as_uri()+"?mode=ro",uri=True)) as db:
        db.execute("BEGIN")
        before=review(db,seeds)
    if not apply or not before["remove"]:return counts(before)
    with workspace_lock(database.parent):
        # Recheck under exclusive application lock before creating recovery copy.
        backup=verified_backup(database)
        if backup is None:raise ValueError("Nedostaje sigurnosna kopija.")
        store=Store(database)
        with store.db() as db:
            db.execute("BEGIN IMMEDIATE")
            current=review(db,seeds)
            if current!=before:raise ValueError("Baza se promijenila. Ponovite pregled.")
            official_before=db.execute("SELECT count(*) FROM registry_rows").fetchone()[0]
            for identifier in current["remove"]:
                db.execute("DELETE FROM origins WHERE company_id=?",(identifier,))
                db.execute("DELETE FROM companies WHERE id=?",(identifier,))
            if db.execute("PRAGMA foreign_key_check").fetchone() or db.execute("SELECT count(*) FROM registry_rows").fetchone()[0]!=official_before:
                raise ValueError("Provjera integriteta nije uspjela.")
            if store.fts_available:
                db.execute("INSERT INTO company_fts(company_fts,rank) VALUES('integrity-check',1)")
        return dict(counts(current),deleted=len(current["remove"]),backup=backup.name)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("database",type=Path)
    p.add_argument("original_csv",type=Path)
    p.add_argument("--apply",action="store_true")
    args=p.parse_args()
    if args.original_csv.stat().st_size>16*1024**2:raise ValueError("Neočekivana veličina uvoza.")
    print(json.dumps(clean(args.database,seed_rows(args.original_csv.read_bytes()),args.apply),ensure_ascii=False))

if __name__=="__main__":main()
