import tempfile
import unittest
from pathlib import Path
from company_store import Store
from duplicate_review import preview, merge
from data_safety import verified_backup
from native_client import WorkerProcess

class DuplicateReviewTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        self.store=Store(self.root/"companies.sqlite3")
        self.legacy={"title":"Test d.o.o.","city":"Rijeka","address":"Ulica 1","phone":"051123456"}
        self.official={"title":"Test D. O. O.","city":"Rijeka","address":"Ulica 1","mbs":"000000001","email":"a@example.invalid"}
        with self.store.db() as c:
            self.store.upsert(c,self.legacy,provider="csv")
            self.store.upsert(c,self.official,provider="registry")
    def selections(self):
        return [{"legacy":p["legacy"]["id"],"canonical":p["canonical"]["id"],"fingerprint":p["fingerprint"]} for p in preview(self.store)["pairs"]]
    def test_merge_preserves_contacts_archive_search_and_reimport(self):
        pairs=self.selections()
        self.assertEqual(len(pairs),1)
        backup=verified_backup(self.store.path)
        self.assertEqual(merge(self.store,pairs,backup.name)["merged"],1)
        self.assertTrue(backup.is_file())
        self.assertEqual(self.store.stats()["total"],1)
        canonical=self.store.detail(pairs[0]["canonical"])
        self.assertEqual(canonical["phone"],self.legacy["phone"])
        self.assertEqual(canonical["mbs"],self.official["mbs"])
        self.assertEqual({r["provider"] for r in canonical["sources"]},{"registry","csv"})
        with self.store.db() as db:
            self.assertEqual(db.execute("SELECT count(*) FROM duplicate_merge_archive").fetchone()[0],1)
            self.assertFalse(db.execute("PRAGMA foreign_key_check").fetchall())
            self.store.upsert(db,self.legacy,provider="csv")
        self.assertEqual(self.store.stats()["total"],1)
        self.assertEqual(self.store.query(contact="phone")["total"],1)
    def test_stale_review_rolls_back(self):
        pairs=self.selections()
        with self.store.db() as db:db.execute("UPDATE companies SET phone='999' WHERE id=?",(pairs[0]["legacy"],))
        with self.assertRaises(ValueError):merge(self.store,pairs,"test-backup")
        self.assertEqual(self.store.stats()["total"],2)
    def test_same_name_different_address_and_conflicting_ids(self):
        with self.store.db() as db:db.execute("UPDATE companies SET address='Ulica 2' WHERE mbs=''")
        self.assertEqual(preview(self.store)["count"],0)
        with self.store.db() as db:db.execute("UPDATE companies SET address='Ulica 1',mbs='000000002' WHERE mbs=''")
        self.assertEqual(preview(self.store)["count"],0)
    def test_multiple_official_matches_not_suggested(self):
        with self.store.db() as db:self.store.upsert(db,dict(self.official,mbs="000000002"),provider="registry")
        self.assertEqual(preview(self.store)["count"],0)
    def test_requires_backup_and_nonempty_approval(self):
        with self.assertRaises(ValueError):merge(self.store,self.selections(),"")
        with self.assertRaises(ValueError):merge(self.store,[],"test")
    def test_authenticated_worker_merge_creates_real_backup(self):
        worker=WorkerProcess(self.root,smoke=True)
        try:
            client=worker.client
            result=client.request("/api/duplicates")
            pairs=[{"legacy":p["legacy"]["id"],"canonical":p["canonical"]["id"],"fingerprint":p["fingerprint"]} for p in result["pairs"]]
            self.assertEqual(len(pairs),1)
            with self.assertRaises(ValueError):client.request("/api/duplicates/merge",data={"pairs":pairs})
            self.assertEqual(client.request("/api/stats")["total"],2)
            result=client.request("/api/duplicates/merge",data={"confirmed":True,"pairs":pairs})
            self.assertEqual(result["merged"],1)
            self.assertTrue((self.root/"backups"/result["backup"]).is_file())
            self.assertEqual(client.request("/api/stats")["total"],1)
        finally:worker.close()
