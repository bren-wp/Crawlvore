"""Provider-specific count preserves origin deduplication and filter semantics."""
import tempfile
import unittest
from pathlib import Path
from core import Store


class ProviderCountTests(unittest.TestCase):
    def test_provider_count_matches_existing_correlated_query(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=Store(Path(tmp)/'synthetic.sqlite3')
            with store.db() as db:
                for i in range(60):
                    store.upsert(db,{'title':f'Synthetic {i:03}','city':f'City {i%3}'},provider='csv')
                for i in (1,2,5,20,45):
                    for suffix in ('a','b'):
                        db.execute('INSERT INTO origins(company_id,provider,url) VALUES(?,?,?)',
                                   (i,'registry','https://example.invalid/'+suffix))
            for provider in ('registry','csv','missing'):
                for filters in ({},{'city':'City 1'},{'q':'Synthetic 00'},{'contact':'missing'}):
                    where,args=store.where(provider=provider,**filters)
                    with store.db() as db:
                        expected=db.execute('SELECT count(*) FROM companies'+where,args).fetchone()[0]
                    with self.subTest(provider=provider,filters=filters):
                        result=store.query(provider=provider,limit=2,page=2,**filters)
                        self.assertEqual(result['total'],expected)
                        self.assertEqual(len(result['rows']),min(2,max(0,expected-2)))
