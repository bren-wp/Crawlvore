"""Workspace-private bookmarks keyed by stable official MBS, not transient SQLite IDs."""
import re

def schema(c):
    c.execute("""CREATE TABLE IF NOT EXISTS saved_companies (
        mbs TEXT PRIMARY KEY, title TEXT NOT NULL, saved_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )""")

def change(store,mbs,selected):
    if not isinstance(mbs,str) or not re.fullmatch(r"[0-9]{9}",mbs) or type(selected) is not bool:
        raise ValueError("Neispravan odabir tvrtke.")
    with store.db() as c:
        schema(c)
        if selected:
            row=c.execute("SELECT title FROM companies WHERE mbs=?",(mbs,)).fetchone()
            if row is None:raise ValueError("Tvrtka nije pronađena.")
            c.execute("INSERT OR IGNORE INTO saved_companies(mbs,title) VALUES (?,?)",(mbs,row["title"]))
        else:c.execute("DELETE FROM saved_companies WHERE mbs=?",(mbs,))
        return {"saved":selected}

def browse(store,after=""):
    if not isinstance(after,str) or (after and not re.fullmatch(r"[0-9]{9}",after)):raise ValueError("Neispravan pokazivač.")
    with store.db() as c:
        schema(c)
        rows=[dict(r) for r in c.execute("""SELECT s.mbs,coalesce(c.title,s.title) title,c.id,c.city,c.email,s.saved_at
              FROM saved_companies s LEFT JOIN companies c ON c.mbs=s.mbs
              WHERE s.mbs>? ORDER BY s.mbs LIMIT 101""",(after,))]
        return {"rows":rows[:100],"next":rows[99]["mbs"] if len(rows)>100 else ""}
