import http.client
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from core import Store
from native_client import NativeClient, WorkerProcess

class NativeClientTests(unittest.TestCase):
    def test_ready_line_is_strict(self):
        token="a"*64
        self.assertEqual(NativeClient.from_ready("CRAWLVORA_READY http://127.0.0.1:12345/session/"+token).port,12345)
        for url in ("http://localhost:12345","http://127.0.0.1:0","http://127.0.0.1:99999","https://127.0.0.1:12345","http://example.invalid:12345"):
            with self.assertRaises(ValueError):
                NativeClient.from_ready("CRAWLVORA_READY "+url+"/session/"+token)
        with self.assertRaises(ValueError):NativeClient.from_ready("CRAWLVORA_READY http://127.0.0.1:12345/session/"+token+"/extra")
    def test_worker_api_without_html_or_browser(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace=Path(tmp)
            store=Store(workspace/"companies.sqlite3")
            with store.db() as db:
                store.upsert(db,{"title":"Sintetička tvrtka","mbs":"000000001","email":"kontakt@example.invalid"},provider="registry")
            worker=WorkerProcess(workspace,smoke=True)
            try:
                client=worker.client
                found=client.request("/api/companies",{"q":"000000001"})
                self.assertEqual(found["total"],1)
                detail=client.request("/api/company/"+str(found["rows"][0]["id"]))
                self.assertEqual(detail["email"],"kontakt@example.invalid")
                self.assertEqual(client.request("/api/stats")["total"],1)
                with self.assertRaises(ValueError):client.request("/")
                for route,status in (("/",404),("/app.js",404),("/api/stats",403)):
                    conn=http.client.HTTPConnection("127.0.0.1",client.port,timeout=5)
                    try:
                        conn.request("GET",route)
                        with conn.getresponse() as response:
                            self.assertEqual(response.status,status)
                            self.assertIn("application/json",response.getheader("Content-Type",""))
                            json.loads(response.read())
                    finally:conn.close()
                self.assertTrue(client.request("/api/stop",data={})["ok"])
                with patch("native_client.http.client.HTTPConnection") as connector:
                    with self.assertRaises(ValueError):client.request("https://example.invalid/api/stats")
                    connector.assert_not_called()
            finally:worker.close()
            self.assertEqual(worker.process.returncode,0)
