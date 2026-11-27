import tempfile
import unittest
from pathlib import Path
from native_client import WorkerProcess

class SavedCompaniesTests(unittest.TestCase):
    def test_authenticated_saved_selection_survives_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            worker=WorkerProcess(root,smoke=True)
            try:
                from native_transfer import upload
                p=root/"fixture.json"
                p.write_text('[{"title":"Testna tvrtka","mbs":"000000001"}]',encoding="utf-8")
                upload(worker.client,"/api/import-json",p)
                client=worker.client
                self.assertEqual(client.request("/api/saved-companies")["rows"],[])
                client.request("/api/saved-companies",data={"mbs":"000000001","saved":True})
                client.request("/api/saved-companies",data={"mbs":"000000001","saved":True})
                self.assertEqual(len(client.request("/api/saved-companies")["rows"]),1)
                with self.assertRaises(ValueError):client.request("/api/saved-companies",data={"mbs":"000000002","saved":True})
            finally:worker.close()
            worker=WorkerProcess(root,smoke=True)
            try:
                client=worker.client
                self.assertEqual(client.request("/api/saved-companies")["rows"][0]["mbs"],"000000001")
                client.request("/api/saved-companies",data={"mbs":"000000001","saved":False})
                self.assertFalse(client.request("/api/saved-companies")["rows"])
                self.assertEqual(client.request("/api/stats")["total"],1)
            finally:worker.close()
