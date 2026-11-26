import tempfile
import unittest
from pathlib import Path

from core import Store
from registry import Registry


class RegistryQueryPlanTests(unittest.TestCase):
    def test_related_lookup_uses_mbs_index(self):
        with tempfile.TemporaryDirectory() as temporary:
            store=Store(Path(temporary)/'db.sqlite3')
            Registry(store)
            with store.db() as db:
                plan=db.execute("EXPLAIN QUERY PLAN SELECT payload FROM registry_rows INDEXED BY registry_mbs WHERE snapshot=? AND mbs=? AND category=? ORDER BY ordinal",('1','000000001','email_adrese')).fetchall()
                self.assertTrue(any('registry_mbs' in row[3] and 'mbs=?' in row[3] for row in plan))
