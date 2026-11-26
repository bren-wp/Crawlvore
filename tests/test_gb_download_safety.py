import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from gb_download import GBDownload, DownloadCancelled

class DownloadSafetyTests(unittest.TestCase):
    def test_failure_preserves_existing_workspace_and_allows_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); original=root/'companies.sqlite3';original.write_bytes(b'unchanged')
            job=GBDownload(root/'GB'/'installed')
            with patch('gb_download.fetch_snapshot',side_effect=OSError('disk full')):
                job.start();job.thread.join(5)
            self.assertEqual(job.status()['status'],'failed')
            self.assertEqual(original.read_bytes(),b'unchanged')
            self.assertFalse(job.destination.exists())
            with patch('gb_download.fetch_snapshot',return_value={'rows':1,'snapshot':'2026-11-01'}):
                job.start();job.thread.join(5)
            self.assertEqual(job.status()['status'],'complete')

    def test_cancel_and_no_duplicate_job(self):
        with tempfile.TemporaryDirectory() as tmp:
            import threading
            entered=threading.Event();release=threading.Event()
            def work(destination,check,progress):
                entered.set();release.wait(5);check()
            job=GBDownload(Path(tmp)/'installed')
            with patch('gb_download.fetch_snapshot',side_effect=work) as fetch:
                job.start();self.assertTrue(entered.wait(5));job.start()
                self.assertEqual(fetch.call_count,1)
                job.cancel.set();release.set();job.thread.join(5)
            self.assertEqual(job.status()['status'],'cancelled')
            self.assertFalse(job.destination.exists())
