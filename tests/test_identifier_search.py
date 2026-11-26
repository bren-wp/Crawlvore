import tempfile
import unittest
from pathlib import Path

from core import Store


class IdentifierSearchTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.store=Store(Path(self.temporary.name)/'directory.sqlite3')
        with self.store.db() as db:
            self.store.upsert(db,{'title':'Čelik primjer','oib':'12345678903','mbs':'12345','city':'Rijeka'})
            self.store.upsert(db,{'title':'Other company','phone':'12345678903','description':'000012345','city':'Zagreb'})

    def titles(self,query,**filters):
        return [row['title'] for row in self.store.query(q=query,**filters)['rows']]

    def test_name_search(self):
        self.assertEqual(self.titles('ČELIK'),['Čelik primjer'])
        self.assertEqual(self.titles('primjer'),['Čelik primjer'])

    def test_oib_search_without_prefix(self):
        for query in ('12345678903',' 123 456 789 03 ','oib:12345678903'):
            with self.subTest(query=query):
                self.assertEqual(self.titles(query),['Čelik primjer'])

    def test_mbs_search_without_prefix(self):
        for query in ('000012345','12345','mbs:12345','000-012-345'):
            with self.subTest(query=query):
                self.assertEqual(self.titles(query),['Čelik primjer'])

    def test_combined_filters_and_legacy_mbs(self):
        self.assertEqual(self.titles('12345678903',city='Zagreb'),[])
        self.assertEqual(self.titles('12345',city='Rijeka'),['Čelik primjer'])
        with self.store.db() as db:
            db.execute("UPDATE companies SET mbs='12345' WHERE title=?",('Čelik primjer',))
        self.assertEqual(self.titles('000012345'),['Čelik primjer'])
