import tempfile,unittest,hashlib,csv,io
from pathlib import Path
from company_store import Store
from company_fields import FIELDS
from registry import Registry
from legacy_cleanup import seed_rows,clean

class LegacyCleanupTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        self.db=self.root/"companies.sqlite3"
        self.store=Store(self.db);Registry(self.store)
        buffer=io.StringIO()
        writer=csv.DictWriter(buffer,fieldnames=FIELDS);writer.writeheader()
        writer.writerow({"Title":"Stari primjer","City":"Rijeka","Phone Number":"051123456"})
        writer.writerow({"Title":"Povezani primjer","City":"Rijeka","Phone Number":"051123456"})
        writer.writerow({"Title":"Izmijenjeni primjer","City":"Rijeka","Phone Number":"051123456"})
        raw=buffer.getvalue().encode()
        self.seeds=seed_rows(raw,hashlib.sha256(raw).hexdigest())
        self.store.import_csv(io.StringIO(buffer.getvalue()))
        with self.store.db() as db:
            db.execute("UPDATE companies SET phone='999' WHERE title='Izmijenjeni primjer'")
            self.store.upsert(db,{"title":"Neovisni korisnički unos","city":"Rijeka"},provider="csv")
            self.store.upsert(db,{"title":"Povezani primjer","city":"Rijeka","mbs":"000000001"},provider="registry")
            # Explicitly link the legacy row to the authoritative provider as in the actual migrated database.
            old=db.execute("SELECT id FROM companies WHERE title='Povezani primjer' AND mbs=''").fetchone()
            if old:
                new=db.execute("SELECT id FROM companies WHERE mbs='000000001'").fetchone()[0]
                db.execute("DELETE FROM origins WHERE company_id=?",(new,))
                db.execute("DELETE FROM companies WHERE id=?",(new,))
                db.execute("UPDATE companies SET mbs='000000001' WHERE id=?",(old[0],))
                db.execute("INSERT INTO origins(company_id,provider,url) VALUES (?,'registry','')",(old[0],))
    def test_exact_legacy_only_and_backup(self):
        self.assertEqual(clean(self.db,self.seeds),{"remove":1,"linked":1,"preserved":1})
        result=clean(self.db,self.seeds,True)
        self.assertEqual(result["deleted"],1)
        self.assertTrue((self.root/"backups"/result["backup"]).is_file())
        self.assertEqual(self.store.stats()["total"],3)
        self.assertEqual(self.store.query(q="Povezani primjer")["total"],1)
        self.assertEqual(clean(self.db,self.seeds)["remove"],0)
    def test_untrusted_csv_rejected(self):
        with self.assertRaises(ValueError):seed_rows(b"bad")
