"""Order-independent comparison of complete public snapshots, preserving duplicate counts."""
import json
import hashlib


def compare(registry, before, after):
    if not before.isdigit() or not after.isdigit() or before == after:
        raise ValueError('Odaberite dvije različite snimke.')
    with registry.store.db() as c:
        c.execute('BEGIN')
        runs={r['snapshot']:json.loads(r['manifest']) for r in c.execute('SELECT * FROM registry_runs WHERE complete=1 AND snapshot IN (?,?)',(before,after))}
        if set(runs)!={before,after}: raise ValueError('Usporedba zahtijeva dvije dovršene snimke.')
        def digest(payload):
            return hashlib.sha256(json.dumps(json.loads(payload),sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
        c.create_function('canonical_digest',1,digest,deterministic=True)
        # Temporary tables keep large comparisons out of Python memory.
        c.execute('CREATE TEMP TABLE diff_counts(category TEXT,mbs TEXT,digest TEXT,old_n INTEGER,new_n INTEGER,PRIMARY KEY(category,mbs,digest)) WITHOUT ROWID')
        c.execute('''INSERT INTO diff_counts SELECT category,mbs,canonical_digest(payload),count(*),0
            FROM registry_rows WHERE snapshot=? GROUP BY category,mbs,canonical_digest(payload)''',(before,))
        c.execute('''INSERT INTO diff_counts SELECT category,mbs,canonical_digest(payload),0,count(*)
            FROM registry_rows WHERE snapshot=? GROUP BY category,mbs,canonical_digest(payload)
            ON CONFLICT(category,mbs,digest) DO UPDATE SET new_n=excluded.new_n''',(after,))
        counts={r['category']:dict(r) for r in c.execute('''SELECT category,
          sum(max(new_n-old_n,0)) AS added, sum(max(old_n-new_n,0)) AS removed,
          count(DISTINCT CASE WHEN old_n<>new_n AND mbs<>'' THEN mbs END) AS affected_subjects
          FROM diff_counts GROUP BY category''')}
        result=[]
        for cat in sorted(set(runs[before])|set(runs[after])):
            comparable=cat in runs[before] and cat in runs[after] and runs[before][cat]==runs[after][cat]
            item={'category':cat,'comparable':comparable}
            if comparable: item.update(counts.get(cat,{'added':0,'removed':0,'affected_subjects':0}))
            result.append(item)
        return {'before':before,'after':after,'categories':result}
