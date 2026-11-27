"""Presentation of registry progress; never report completion before commit."""
def sync_progress(status, categories):
    state=status.get("status")
    phase=status.get("phase")
    if state=="completed" and status.get("update_available") and phase!="complete":
        return 0,"Dostupna je nova snimka. Potvrdite preuzimanje."
    if state=="completed" and phase=="complete":
        return 100,"Sinkronizacija je završena."
    if state=="failed":return 0,"Sinkronizacija nije uspjela. Spremljeni podaci su sačuvani."
    if state=="stopped":return 0,"Sinkronizacija je zaustavljena. Preuzete stranice su sačuvane."
    if state not in ("running","stopping"):return 0,"Nema aktivne sinkronizacije."
    if state=="stopping":return 0,"Zaustavljanje operacije…"
    if phase=="finalizing":return 99,"Završna provjera i spremanje poslovnih podataka…"
    if phase=="projection":
        total=max(1,status.get("projection_total",0))
        count=max(0,min(total,status.get("projected",0)))
        return 85+14*count/total,f"Obrada tvrtki: {count:,} / {total:,}".replace(",",".")
    if phase=="download":
        rows=[r for r in categories if r["snapshot"]==status.get("snapshot_id")]
        total=max(1,status.get("last",0))
        done=min(total,sum(bool(r["done"]) for r in rows))
        return 85*done/total,f"Preuzimanje kategorija: {done} / {total}"
    return 0,"Provjera pristupa i dostupnih podataka…"
