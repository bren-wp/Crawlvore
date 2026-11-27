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

    def test_upgrade_does_not_replace_catalogs_and_is_reproducible(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            first = build(root / "upgrade-a.zip", upgrade=True)
            second = build(root / "upgrade-b.zip", upgrade=True)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            with zipfile.ZipFile(first) as archive:
                self.assertIn("storage/.htaccess", archive.namelist())
                self.assertFalse(any(name.startswith("storage/data/") for name in archive.namelist()))
                self.assertIn("index.php", archive.namelist())
                self.assertNotIn("robots.txt", archive.namelist())
                self.assertNotIn("site-config.json", archive.namelist())
                self.assertNotIn("sitemap.xml", archive.namelist())
            fresh = build(root / "fresh.zip")
            with zipfile.ZipFile(fresh) as archive:
                self.assertIn("storage/data/HR/manifest.json", archive.namelist())

    def test_configured_seo_uses_only_explicit_deployment_url(self):
        from xml.etree import ElementTree as ET
        with tempfile.TemporaryDirectory() as tmp:
            out = build(pathlib.Path(tmp) / "seo.zip", base_url="https://example.invalid/catalog/", upgrade=True)
            with zipfile.ZipFile(out) as archive:
                cfg = json.loads(archive.read("site-config.json"))
                self.assertEqual(cfg["base_url"], "https://example.invalid/catalog/")
                root = ET.fromstring(archive.read("sitemap.xml"))
                urls = root.findall("{*}url/{*}loc")
                self.assertEqual(len(urls), 28)
                self.assertTrue(all(u.text.startswith(cfg["base_url"]) for u in urls))
                self.assertIn(b"Disallow: /catalog/storage/", archive.read("robots.txt"))
            for base in ("http://example.invalid/", "https://user@example.invalid/", "https://example.invalid/../x", "https://example.invalid/?x=1"):
                with self.assertRaises(ValueError):
                    build(pathlib.Path(tmp) / "invalid.zip", base_url=base)

    def test_extracting_upgrade_preserves_published_catalog_and_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            site = root / "site"
            catalog = site / "storage/data/HR"
            catalog.mkdir(parents=True)
            existing = {
                catalog / "manifest.json": b'{"published":true}',
                catalog / "HR-company-000001.json": b'[{"name":"Synthetic"}]',
                site / "site-config.json": b'{"base_url":"https://example.invalid/"}',
                site / "sitemap.xml": b'old sitemap',
                site / "robots.txt": b'old robots',
            }
            for path, content in existing.items():
                path.write_bytes(content)
            archive = build(root / "upgrade.zip", upgrade=True)
            with zipfile.ZipFile(archive) as package:
                package.extractall(site)
            for path, content in existing.items():
                self.assertEqual(path.read_bytes(), content)
            self.assertTrue((site / "index.php").is_file())
            self.assertEqual((site / "storage/.htaccess").read_bytes().strip(), b"Require all denied")
