import json
import pathlib
import tempfile
import unittest
import zipfile

from tools.package_web import approved, build, REQUIRED


class WebPackageTests(unittest.TestCase):
    def test_private_payloads_rejected(self):
        for name in ("storage/data/HR/companies.sqlite3", "storage/data/GB/GB-company-000001.json",
                     "credentials.json", "assets/private.zip", "../index.php"):
            with self.subTest(name=name):
                self.assertFalse(approved(name, b"private"))
        self.assertFalse(approved("storage/data/HR/manifest.json", json.dumps({
            "version": 1, "country": "HR", "count": 1,
            "published_at": "2026-01-01", "shards": ["private.json"]}).encode()))

    def test_exact_commit_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = build(pathlib.Path(tmp) / "Crawlvora-Web.zip")
            with zipfile.ZipFile(out) as archive:
                self.assertTrue(REQUIRED <= set(archive.namelist()))
                self.assertIsNone(archive.testzip())
                self.assertEqual(archive.read("storage/.htaccess").strip(), b"Require all denied")
                self.assertTrue(all(not name.startswith("webstranica/") for name in archive.namelist()))
            with self.assertRaises(FileExistsError):
                build(out)
