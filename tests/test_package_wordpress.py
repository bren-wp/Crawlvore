import pathlib
import tempfile
import unittest
import zipfile
from tools.package_wordpress import build, REQUIRED


class WordpressPackageTests(unittest.TestCase):
    def test_exact_plugin_files_reproducible_and_exclusive(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            first = build(root / "Crawlvora-WordPress.zip")
            second = build(root / "repeat.zip")
            self.assertEqual(first.read_bytes(), second.read_bytes())
            with zipfile.ZipFile(first) as archive:
                self.assertEqual(set(archive.namelist()), REQUIRED)
                self.assertIsNone(archive.testzip())
            with self.assertRaises(FileExistsError):
                build(first)
            self.assertEqual(first.read_bytes(), second.read_bytes())
