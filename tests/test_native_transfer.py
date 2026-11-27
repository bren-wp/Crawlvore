import json
import tempfile
import unittest
from pathlib import Path
from native_client import WorkerProcess
from native_transfer import upload,download

class NativeTransferTests(unittest.TestCase):
    def test_real_authenticated_import_export_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);workspace=root/"workspace"
            worker=WorkerProcess(workspace,smoke=True)
            try:
                source=root/"input.json"
                source.write_text(json.dumps([{"title":"Testna tvrtka","email":"test@example.invalid"}]),encoding="utf-8")
                result=upload(worker.client,"/api/import-json",source)
                self.assertEqual(result["added"],1)
                self.assertEqual(worker.client.request("/api/stats")["total"],1)
                target=root/"output.json"
                result=download(worker.client,"/api/export-fields",{"fields":"title,email","format":"json"},target)
                self.assertEqual(result["bytes"],target.stat().st_size)
                self.assertEqual(json.loads(target.read_text(encoding="utf-8")),[{"title":"Testna tvrtka","email":"test@example.invalid"}])
                with self.assertRaises(ValueError):download(worker.client,"/api/export-json",{},target)
                with self.assertRaises(ValueError):download(worker.client,"/api/stats",{},root/"bad.json")
                with self.assertRaises(ValueError):upload(worker.client,"/api/mail/send",source)
            finally:worker.close()
